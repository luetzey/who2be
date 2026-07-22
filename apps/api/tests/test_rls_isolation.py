"""Integrationstest fuer die Postgres-RLS-Cloud-Haertung (Track I, Plan §3.1).

Beweist, dass die nicht-privilegierte App-Rolle `who2be_app` (NOBYPASSRLS) mit
gesetztem `app.current_tenant` KEINE fremden Workspace-Zeilen sieht — auch dann
nicht, wenn die App-`WHERE workspace_id`-Filter komplett entfallen (die Queries
hier sind bewusst ohne `WHERE`). Genau das ist die zweite Verteidigungslinie,
die RLS liefert.

Laeuft in einem isolierten Schema (wie test_phase21/23_migrations), damit
`public` und parallele Integration-Tests unangetastet bleiben. Die Rolle
`who2be_app` ist cluster-global; sie wird idempotent von Migration 0036 angelegt
und hier nur mit einem Test-Passwort versehen.
"""

import asyncio
import secrets
from uuid import UUID, uuid4

import asyncpg
import pytest

from who2be_api.core.config import get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations

# Test-only Passwort fuer die App-Rolle. Konstante (kein Injection-Vektor) —
# wird per format() in ALTER ROLE eingesetzt.
_APP_PASSWORD = "rls_test_secret"  # noqa: S105 — Test-Fixture, kein echtes Secret

# Tabellen, die eine workspace_id/org_id-Spalte tragen, aber BEWUSST keine
# tenant_isolation-Policy haben. Nur `workspace`: es traegt `org_id`, ist aber
# die control-plane-Wurzel (Parent des Mandanten, kein Mandant im RLS-Sinn) —
# dokumentiert in 0037 und core/security.py (org-Lookup laeuft vor tenant_scope).
# Jeder weitere Eintrag hier muss eine bewusste, begruendete Ausnahme sein.
_RLS_EXEMPT_SCOPED_TABLES = frozenset({"workspace"})


def _db_reachable() -> bool:
    async def _check() -> bool:
        try:
            conn = await asyncpg.connect(get_settings().database_url)
        except (asyncpg.PostgresError, OSError):
            return False
        await conn.close()
        return True

    return asyncio.run(_check())


async def _seed(conn: asyncpg.Connection) -> dict[str, UUID]:
    """Legt zwei Orgs/Workspaces mit je einer Persona + Version + Entitlement an."""
    owner = uuid4()
    ids: dict[str, UUID] = {}
    for key in ("a", "b"):
        org_id = await conn.fetchval(
            "INSERT INTO organization (name, slug, kind) VALUES ($1, $1, 'company') RETURNING id",
            f"org-{key}-{secrets.token_hex(4)}",
        )
        ws_id = await conn.fetchval(
            "INSERT INTO workspace (org_id, name, slug) VALUES ($1, $2, $2) RETURNING id",
            org_id,
            f"ws-{key}",
        )
        persona_id = await conn.fetchval(
            "INSERT INTO persona (workspace_id, owner_id, name) VALUES ($1, $2, $3) RETURNING id",
            ws_id,
            owner,
            f"persona-{key}",
        )
        await conn.execute(
            "INSERT INTO persona_version "
            "(persona_id, workspace_id, version, content, status, created_by) "
            "VALUES ($1, $2, 1, '{}'::jsonb, 'active', $3)",
            persona_id,
            ws_id,
            owner,
        )
        await conn.execute(
            "INSERT INTO org_entitlement (org_id, status, features) "
            "VALUES ($1, 'active', '[]'::jsonb)",
            org_id,
        )
        await conn.execute(
            "INSERT INTO workspace_invitation "
            "(workspace_id, email, role, token_hash, expires_at, created_by) "
            "VALUES ($1, $2, 'editor', $3, now() + interval '1 day', $4)",
            ws_id,
            f"invitee-{key}@example.com",
            secrets.token_hex(16),
            owner,
        )
        ids[f"org_{key}"] = org_id
        ids[f"ws_{key}"] = ws_id
        ids[f"persona_{key}"] = persona_id
    return ids


@pytest.mark.integration
def test_rls_blocks_cross_workspace_reads_for_app_role() -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")

    settings = get_settings()
    schema = f"rls_{secrets.token_hex(6)}"

    async def _run() -> None:
        owner = await asyncpg.connect(settings.database_url)
        app: asyncpg.Connection | None = None
        try:
            await owner.execute(f'CREATE SCHEMA "{schema}"')
            await owner.execute(f'SET search_path TO "{schema}"')
            # Migrationen legen Tabellen + Rolle who2be_app + Grants + Policies
            # im isolierten Schema an.
            await apply_migrations(owner, MIGRATIONS_DIR)
            ids = await _seed(owner)
            # Test-Passwort fuer die (von 0036 angelegten) Rolle setzen.
            await owner.execute(f"ALTER ROLE who2be_app WITH PASSWORD '{_APP_PASSWORD}'")

            app = await asyncpg.connect(
                settings.database_url, user="who2be_app", password=_APP_PASSWORD
            )
            await app.execute(f'SET search_path TO "{schema}"')

            # --- Workspace A: nur A-Zeilen sichtbar, OHNE WHERE-Filter. ---
            await app.execute(
                "SELECT set_config('app.current_tenant', $1, false)", str(ids["ws_a"])
            )
            persona_ws = await app.fetch("SELECT workspace_id FROM persona")
            assert {row["workspace_id"] for row in persona_ws} == {ids["ws_a"]}, (
                "RLS leakt fremde Persona-Zeilen trotz gesetztem Tenant A"
            )
            version_ws = await app.fetch("SELECT workspace_id FROM persona_version")
            assert {row["workspace_id"] for row in version_ws} == {ids["ws_a"]}

            # --- Workspace B: Sicht wandert mit dem Mandanten. ---
            await app.execute(
                "SELECT set_config('app.current_tenant', $1, false)", str(ids["ws_b"])
            )
            persona_ws_b = await app.fetch("SELECT workspace_id FROM persona")
            assert {row["workspace_id"] for row in persona_ws_b} == {ids["ws_b"]}

            # --- Fremder Mandant: kein Treffer, auch ohne WHERE. ---
            await app.execute("SELECT set_config('app.current_tenant', $1, false)", str(uuid4()))
            stranger = await app.fetch("SELECT workspace_id FROM persona")
            assert stranger == []

            # --- WITH CHECK: Insert in fremden Workspace wird abgewiesen. ---
            await app.execute(
                "SELECT set_config('app.current_tenant', $1, false)", str(ids["ws_a"])
            )
            with pytest.raises(asyncpg.PostgresError):
                await app.execute(
                    "INSERT INTO persona (workspace_id, owner_id, name) "
                    "VALUES ($1, $2, 'cross-tenant')",
                    ids["ws_b"],
                    uuid4(),
                )

            # --- Org-Tabelle: strikt bei gesetztem app.current_org ... ---
            await app.execute("SELECT set_config('app.current_org', $1, false)", str(ids["org_a"]))
            ent = await app.fetch("SELECT org_id FROM org_entitlement")
            assert {row["org_id"] for row in ent} == {ids["org_a"]}

            # --- ... permissiv-bei-unset (Webhook-Schreibpfad ohne Org-Scope). ---
            await app.execute("RESET app.current_org")
            ent_all = await app.fetch("SELECT org_id FROM org_entitlement")
            assert {row["org_id"] for row in ent_all} == {ids["org_a"], ids["org_b"]}

            # --- workspace_invitation (0050): strikt bei gesetztem Tenant ... ---
            await app.execute(
                "SELECT set_config('app.current_tenant', $1, false)", str(ids["ws_a"])
            )
            inv = await app.fetch("SELECT workspace_id FROM workspace_invitation")
            assert {row["workspace_id"] for row in inv} == {ids["ws_a"]}, (
                "RLS leakt fremde Invitation-Zeilen trotz gesetztem Tenant A"
            )
            # --- ... permissiv-bei-unset (token-basierter Accept-Pfad, kein Scope). ---
            await app.execute("RESET app.current_tenant")
            inv_all = await app.fetch("SELECT workspace_id FROM workspace_invitation")
            assert {row["workspace_id"] for row in inv_all} == {ids["ws_a"], ids["ws_b"]}, (
                "Accept-Pfad ohne Tenant-Scope muss die Invitation finden (permissiv-bei-unset)"
            )
        finally:
            if app is not None:
                await app.close()
            await owner.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            await owner.close()

    asyncio.run(_run())


@pytest.mark.integration
def test_every_scoped_table_has_rls_policy() -> None:
    """Generischer Coverage-Guard: JEDE Tabelle mit workspace_id/org_id-Spalte
    (ausser der dokumentierten Ausnahme `workspace`) MUSS RLS aktiviert haben und
    mindestens eine Policy tragen.

    Faengt kuenftige Luecken automatisch, ohne dass eine Tabellenliste manuell
    gepflegt werden muss — genau die Regression, die historisch passierte
    (`workspace_invitation` fehlte in 0037 und musste per 0050 nachgezogen
    werden; die 0068-Steuer-Tabellen ebenso). Neue scoped Tabellen ohne Policy
    lassen diesen Test fehlschlagen, bis entweder eine Policy ergaenzt oder die
    Tabelle bewusst in `_RLS_EXEMPT_SCOPED_TABLES` aufgenommen wird.
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")

    settings = get_settings()
    schema = f"rlscov_{secrets.token_hex(6)}"

    async def _run() -> None:
        owner = await asyncpg.connect(settings.database_url)
        try:
            await owner.execute(f'CREATE SCHEMA "{schema}"')
            await owner.execute(f'SET search_path TO "{schema}"')
            await apply_migrations(owner, MIGRATIONS_DIR)

            rows = await owner.fetch(
                "SELECT DISTINCT table_name FROM information_schema.columns "
                "WHERE table_schema = current_schema() "
                "AND column_name IN ('workspace_id', 'org_id')"
            )
            scoped = {row["table_name"] for row in rows} - _RLS_EXEMPT_SCOPED_TABLES
            assert scoped, "Sanity: es muessen scoped Tabellen gefunden werden."

            missing_rls: list[str] = []
            missing_policy: list[str] = []
            for table in sorted(scoped):
                rls_enabled = await owner.fetchval(
                    "SELECT c.relrowsecurity FROM pg_class c "
                    "JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE n.nspname = current_schema() AND c.relname = $1",
                    table,
                )
                if not rls_enabled:
                    missing_rls.append(table)
                    continue
                policy_count = await owner.fetchval(
                    "SELECT count(*) FROM pg_policies "
                    "WHERE schemaname = current_schema() AND tablename = $1",
                    table,
                )
                if not policy_count:
                    missing_policy.append(table)

            assert not missing_rls, (
                f"Scoped Tabellen OHNE ENABLE ROW LEVEL SECURITY: {missing_rls} — "
                "Policy ergaenzen oder bewusst in _RLS_EXEMPT_SCOPED_TABLES aufnehmen."
            )
            assert not missing_policy, (
                f"Scoped Tabellen mit RLS aber OHNE Policy: {missing_policy} — "
                "tenant_isolation-Policy ergaenzen."
            )
        finally:
            await owner.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            await owner.close()

    asyncio.run(_run())
