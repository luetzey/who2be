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
from who2be_api.core.db import init_connection
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.core.tenancy import TENANT_SETTING
from who2be_api.repositories.workspace_repository import (
    PgWorkspaceRepository,
    ensure_personal_workspace,
)
from who2be_models import DEFAULT_LOCALE

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


@pytest.mark.integration
def test_ensure_personal_workspace_seeds_under_enforced_rls() -> None:
    """Regressionstest Issue #479: der Lazy-Seed eines frischen Nutzers
    (`ensure_personal_workspace`, aufgerufen von `GET /v1/me`) muss auch unter
    erzwungener RLS durchlaufen — d. h. auf der nicht-privilegierten Cloud-Rolle
    `who2be_app` (NOBYPASSRLS), nicht nur auf der Owner-Verbindung, die lokale
    Tests sonst nutzen (dort greift RLS gar nicht, ein Test dagegen waere gruen,
    ohne etwas zu beweisen).

    Alle drei Seed-Schritte (`_seed_default_templates`, `_seed_default_agents`,
    `_publish_seeded_chunks`) schreiben in tenant_isolation-Tabellen (Migration
    0037/0070); deren `WITH CHECK` verlangt `app.current_tenant`. Vor dem Fix
    bricht bereits der erste Insert (`system_prompt_template`) mit
    `InsufficientPrivilegeError` ab — exakt der Traceback aus #479.

    Beweist zugleich Akzeptanzkriterium 2: nach der Transaktion traegt die
    Connection keinen Mandanten mehr (die Setzung in `ensure_personal_workspace`
    ist `is_local` — kein Leak in die naechste Checkout-Phase).
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")

    settings = get_settings()
    schema = f"rlsseed_{secrets.token_hex(6)}"

    async def _run() -> None:
        owner = await asyncpg.connect(settings.database_url)
        app: asyncpg.Connection | None = None
        try:
            await owner.execute(f'CREATE SCHEMA "{schema}"')
            await owner.execute(f'SET search_path TO "{schema}"')
            # Migrationen legen Tabellen + Rolle who2be_app + Grants + Policies
            # im isolierten Schema an (wie oben).
            await apply_migrations(owner, MIGRATIONS_DIR)
            await owner.execute(f"ALTER ROLE who2be_app WITH PASSWORD '{_APP_PASSWORD}'")

            app = await asyncpg.connect(
                settings.database_url, user="who2be_app", password=_APP_PASSWORD
            )
            await app.execute(f'SET search_path TO "{schema}"')
            # Gleicher jsonb-Codec wie der Prod-Pool (core/db.py) — die
            # Seed-Funktionen binden dict-Werte fuer jsonb-Spalten.
            await init_connection(app)

            user_id = uuid4()
            # `ensure_personal_workspace` braucht eine umgebende Transaktion,
            # damit die `is_local`-Setzung darin wirkt (Vorgabe des Fixes) —
            # exakt der Rahmen, in dem der echte Aufrufer (me_repository.fetch)
            # sie aufruft.
            async with app.transaction():
                workspace_id = await ensure_personal_workspace(
                    app,
                    user_id,
                    user_email="seed-rls-479@example.com",
                    content_locale=DEFAULT_LOCALE,
                )

            # --- Kein Leak: nach COMMIT traegt die (weiterhin offene) Connection
            #     keinen Mandanten mehr — auch ohne den Pool-Reset (`RESET ALL`
            #     bei Release), der das in Prod zusaetzlich absichert.
            leaked_tenant = await app.fetchval(f"SELECT current_setting('{TENANT_SETTING}', true)")
            assert leaked_tenant in (None, ""), (
                "app.current_tenant blieb nach der Transaktion gesetzt — Leak-Risiko "
                "fuer die naechste Checkout-Phase dieser gepoolten Connection."
            )

            # --- Alle drei Seed-Schritte sind unter der nicht-privilegierten
            #     Rolle wirklich durchgelaufen. Owner-Connection liest ohne
            #     Tenant-Scope (RLS-Bypass) — reine Existenzpruefung.
            template_count = await owner.fetchval(
                "SELECT count(*) FROM system_prompt_template WHERE workspace_id = $1",
                workspace_id,
            )
            assert template_count > 0, "Seed-Schritt 1 (Default-Templates) lief nicht durch."

            agent_count = await owner.fetchval(
                "SELECT count(*) FROM agent WHERE workspace_id = $1", workspace_id
            )
            assert agent_count > 0, "Seed-Schritt 2 (Default-Agent Builder) lief nicht durch."

            chunk_count = await owner.fetchval(
                "SELECT count(*) FROM content_chunk WHERE workspace_id = $1", workspace_id
            )
            assert chunk_count > 0, "Seed-Schritt 3 (Passagen) lief nicht durch."
        finally:
            if app is not None:
                await app.close()
            await owner.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            await owner.close()

    asyncio.run(_run())


def test_workspace_create_seeds_under_enforced_rls() -> None:
    """Regressionstest Issue #479, zweiter Aufrufer: `PgWorkspaceRepository.create`.

    `ensure_personal_workspace` ist nicht der einzige Pfad, der in einen
    frisch angelegten Workspace seedet — `create` (explizites Anlegen eines
    weiteren Workspace) ruft dieselben drei Seed-Funktionen in derselben
    Transaktionsform auf. Der Traceback aus #479 nennt nur den ersten, weil
    der Lazy-Seed beim ersten `/v1/me` frueher zuschlaegt; der Fehler ist
    derselbe. Ohne `_scope_to_new_workspace` bricht auch dieser Pfad unter
    erzwungener RLS ab — dieser Test haelt das fest, damit ein halber Fix
    nicht als ganzer durchgeht.

    Faehrt bewusst ueber einen echten Pool als `who2be_app`, nicht ueber eine
    Einzel-Connection: `create` zieht sich seine Connection selbst
    (`self._pool.acquire()`), und genau diese Pool-Semantik samt Release ist
    Teil dessen, was hier gelten muss.
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")

    settings = get_settings()
    schema = f"rlscreate_{secrets.token_hex(6)}"

    async def _run() -> None:
        owner = await asyncpg.connect(settings.database_url)
        pool: asyncpg.Pool | None = None
        try:
            await owner.execute(f'CREATE SCHEMA "{schema}"')
            await owner.execute(f'SET search_path TO "{schema}"')
            await apply_migrations(owner, MIGRATIONS_DIR)
            await owner.execute(f"ALTER ROLE who2be_app WITH PASSWORD '{_APP_PASSWORD}'")

            # Org als Owner anlegen: `organization` traegt keine
            # tenant_isolation-Policy (control-plane), der Seed-Pfad beginnt
            # erst beim Workspace.
            org_id = await owner.fetchval(
                "INSERT INTO organization (name, slug, kind) "
                "VALUES ('RLS Create', $1, 'personal') RETURNING id",
                f"rls-create-{secrets.token_hex(4)}",
            )
            user_id = uuid4()

            pool = await asyncpg.create_pool(
                settings.database_url,
                user="who2be_app",
                password=_APP_PASSWORD,
                min_size=1,
                max_size=1,
                init=init_connection,
                server_settings={"search_path": schema},
            )
            assert pool is not None
            created = await PgWorkspaceRepository(pool).create(
                org_id, user_id, "Zweiter", "zweiter", DEFAULT_LOCALE
            )
            assert created is not None

            # Der Seed hat tatsaechlich geschrieben — sonst waere der Test
            # gruen, ohne etwas zu beweisen.
            async with pool.acquire() as check:
                await check.execute(
                    f"SELECT set_config('{TENANT_SETTING}', $1, false)", str(created.id)
                )
                seeded = await check.fetchval(
                    "SELECT count(*) FROM system_prompt_template WHERE workspace_id = $1",
                    created.id,
                )
            assert seeded > 0, "Seed hat keine Templates angelegt"

            # Kein Leak: eine frisch gezogene Connection traegt keinen Mandanten
            # aus dem Seed (die Setzung war `is_local`).
            async with pool.acquire() as fresh:
                leaked = await fresh.fetchval(f"SELECT current_setting('{TENANT_SETTING}', true)")
            assert leaked in (None, ""), f"Mandant aus dem Seed geleakt: {leaked!r}"
        finally:
            if pool is not None:
                await pool.close()
            await owner.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            await owner.close()

    asyncio.run(_run())
