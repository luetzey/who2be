"""Integrationstests fuer die Phase-2-Migrations (0078-0079, ADR-0049/0047).

Belegt:

- Die vier neuen Tabellen (`wa_table`, `wa_category_rule`,
  `wa_source_convention`, `agent_access_log`) existieren nach dem
  Migrations-Lauf.
- `UNIQUE (area_id, pattern)` auf `wa_category_rule` greift (Upsert-Vertrag L);
  dasselbe Pattern in einer ANDEREN Area bleibt erlaubt.
- Zugriffslog-Dedupe (User-Entscheidung 6): `ON CONFLICT DO NOTHING` gegen
  `UNIQUE (agent_id, ref_kind, ref_id, operation, access_date)` ist ein No-op;
  eine andere Operation am selben Tag ist eine NEUE Zeile.
- Append-only (Muster 0044): die Laufzeitrolle `who2be_app` darf auf
  `agent_access_log` INSERT/SELECT, aber weder UPDATE noch DELETE —
  Grant-Introspektion im Haupt-Schema plus Laufzeit-Beweis im isolierten
  Schema (Vorlage test_audit_append_only.py).
- `agent.model_provider`/`model_name` existieren (betreiber-gepflegte
  Modell-Config, User-Entscheidung 6).
- RLS: die `tenant_isolation`-Policy liegt auf allen vier neuen Tabellen
  (pg_policies-Introspektion, Muster test_workarea_migrations.py).

Idempotenz der gesamten Migrations-Kette (Runner 2x = No-op) ist durch die
bestehenden Migrations-Tests abgedeckt und wird hier bewusst NICHT dupliziert.
Laeuft gegen die zentral migrierte Test-DB (conftest: ``migrated_db`` +
zentraler Integration-Skip ohne DB); Seeds ueber
``who2be_api.testing.workspace_setup``.
"""

import asyncio
import secrets
from collections.abc import Awaitable, Callable
from datetime import date
from typing import TypeVar
from uuid import UUID, uuid4

import asyncpg
import pytest

from who2be_api.core.config import get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace

_T = TypeVar("_T")

_NEW_TABLES = (
    "wa_table",
    "wa_category_rule",
    "wa_source_convention",
    "agent_access_log",
)

_ACCESS_DATE = date(2026, 8, 14)

# Test-only Passwort fuer die App-Rolle (kein Injection-Vektor; per f-String
# in ALTER ROLE eingesetzt — Muster test_audit_append_only.py).
_APP_PASSWORD = "phase2_test_secret"  # noqa: S105 — Test-Fixture, kein echtes Secret


def _with_seed(body: Callable[[asyncpg.Connection, UUID, UUID], Awaitable[_T]]) -> _T:
    """Fuehrt ``body(conn, workspace_id, agent_id)`` gegen die migrierte DB aus.

    ``setup_workspace``/``cleanup_workspaces`` rufen intern selbst
    ``asyncio.run`` auf und muessen deshalb AUSSERHALB der Coroutine laufen
    (Muster test_workarea_migrations.py). Alle vier neuen Tabellen haengen
    per FK-Kette am Workspace-CASCADE (wa_* ueber `work_area`,
    `agent_access_log` ueber `agent`) — kein explizites Cleanup noetig.
    """
    owner = fresh_user_id()
    workspace_id = setup_workspace(owner)

    async def _run() -> _T:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            agent_id: UUID = await conn.fetchval(
                "INSERT INTO agent (workspace_id, owner_id, name) "
                "VALUES ($1, $2, 'phase2-mig-agent') RETURNING id",
                workspace_id,
                owner,
            )
            return await body(conn, workspace_id, agent_id)
        finally:
            await conn.close()

    try:
        return asyncio.run(_run())
    finally:
        cleanup_workspaces([owner])


async def _insert_shared_area(conn: asyncpg.Connection, workspace_id: UUID, name: str) -> UUID:
    area_id: UUID = await conn.fetchval(
        "INSERT INTO work_area (workspace_id, scope, owner_agent_id, name) "
        "VALUES ($1, 'shared', NULL, $2) RETURNING id",
        workspace_id,
        name,
    )
    return area_id


async def _insert_rule(
    conn: asyncpg.Connection, workspace_id: UUID, area_id: UUID, pattern: str
) -> None:
    await conn.execute(
        "INSERT INTO wa_category_rule (workspace_id, area_id, pattern, category, created_by) "
        "VALUES ($1, $2, $3, 'groceries', 'user:test')",
        workspace_id,
        area_id,
        pattern,
    )


async def _insert_log_entry(
    conn: asyncpg.Connection,
    workspace_id: UUID,
    agent_id: UUID,
    *,
    ref_id: str,
    operation: str,
) -> str:
    """Schreibt einen Log-Eintrag wie der Service: ON CONFLICT DO NOTHING."""
    status: str = await conn.execute(
        "INSERT INTO agent_access_log "
        "(workspace_id, agent_id, ref_kind, ref_id, operation, "
        " sensitivity_at_access, access_date) "
        "VALUES ($1, $2, 'artifact', $3, $4, 'general', $5) "
        "ON CONFLICT DO NOTHING",
        workspace_id,
        agent_id,
        ref_id,
        operation,
        _ACCESS_DATE,
    )
    return status


@pytest.mark.integration
@pytest.mark.usefixtures("migrated_db")
def test_phase2_tables_exist() -> None:
    """0078-0079 legen alle vier Phase-2-Tabellen an."""

    async def _run(conn: asyncpg.Connection, workspace_id: UUID, agent_id: UUID) -> None:
        for table in _NEW_TABLES:
            regclass = await conn.fetchval("SELECT to_regclass($1)", table)
            assert regclass is not None, f"Tabelle {table} fehlt nach dem Migrations-Lauf."

    _with_seed(_run)


@pytest.mark.integration
@pytest.mark.usefixtures("migrated_db")
def test_category_rule_unique_per_area_and_pattern() -> None:
    """`UNIQUE (area_id, pattern)`: dasselbe Pattern scheitert in derselben
    Area, ist in einer anderen Area aber erlaubt (Upsert-Vertrag L)."""

    async def _run(conn: asyncpg.Connection, workspace_id: UUID, agent_id: UUID) -> None:
        area_a = await _insert_shared_area(conn, workspace_id, "regeln-a")
        area_b = await _insert_shared_area(conn, workspace_id, "regeln-b")
        await _insert_rule(conn, workspace_id, area_a, "REWE*")
        with pytest.raises(asyncpg.UniqueViolationError):
            await _insert_rule(conn, workspace_id, area_a, "REWE*")
        # Andere Area, gleiches Pattern: erlaubt (Regeln sind area-lokal).
        await _insert_rule(conn, workspace_id, area_b, "REWE*")

    _with_seed(_run)


@pytest.mark.integration
@pytest.mark.usefixtures("migrated_db")
def test_access_log_dedupe_per_day_and_operation() -> None:
    """Zugriffslog-Dedupe (Entscheidung 6): derselbe Zugriff am selben Tag ist
    per ON CONFLICT DO NOTHING ein No-op; eine andere Operation am selben
    Element+Tag ist eine NEUE Zeile."""

    async def _run(conn: asyncpg.Connection, workspace_id: UUID, agent_id: UUID) -> None:
        ref_id = str(uuid4())
        first = await _insert_log_entry(
            conn, workspace_id, agent_id, ref_id=ref_id, operation="read"
        )
        duplicate = await _insert_log_entry(
            conn, workspace_id, agent_id, ref_id=ref_id, operation="read"
        )
        assert first == "INSERT 0 1"
        assert duplicate == "INSERT 0 0", "Doppelter Tages-Zugriff muss ein No-op sein."
        # operation ist Teil des Dedupe-Schluessels: write ist eine neue Zeile.
        second_op = await _insert_log_entry(
            conn, workspace_id, agent_id, ref_id=ref_id, operation="write"
        )
        assert second_op == "INSERT 0 1"
        count = await conn.fetchval(
            "SELECT count(*) FROM agent_access_log WHERE agent_id = $1 AND ref_id = $2",
            agent_id,
            ref_id,
        )
        assert count == 2

    _with_seed(_run)


@pytest.mark.integration
@pytest.mark.usefixtures("migrated_db")
def test_agent_model_config_columns_exist() -> None:
    """`agent.model_provider`/`model_name` existieren als nullable text
    (betreiber-gepflegte Modell-Config, User-Entscheidung 6)."""

    async def _run(conn: asyncpg.Connection, workspace_id: UUID, agent_id: UUID) -> None:
        rows = await conn.fetch(
            "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = 'agent' "
            "AND column_name IN ('model_provider', 'model_name')",
        )
        columns = {row["column_name"]: row for row in rows}
        assert set(columns) == {"model_provider", "model_name"}
        for row in columns.values():
            assert row["data_type"] == "text"
            assert row["is_nullable"] == "YES"

    _with_seed(_run)


@pytest.mark.integration
@pytest.mark.usefixtures("migrated_db")
def test_rls_policy_on_all_new_tables() -> None:
    """RLS ist auf allen vier neuen Tabellen aktiv und traegt die
    `tenant_isolation`-Policy (pg_policies-Introspektion)."""

    async def _run(conn: asyncpg.Connection, workspace_id: UUID, agent_id: UUID) -> None:
        for table in _NEW_TABLES:
            rls_enabled = await conn.fetchval(
                "SELECT c.relrowsecurity FROM pg_class c "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = current_schema() AND c.relname = $1",
                table,
            )
            assert rls_enabled, f"Tabelle {table} ohne ENABLE ROW LEVEL SECURITY."
            policy_count = await conn.fetchval(
                "SELECT count(*) FROM pg_policies "
                "WHERE schemaname = current_schema() AND tablename = $1 "
                "AND policyname = 'tenant_isolation'",
                table,
            )
            assert policy_count == 1, f"Tabelle {table} ohne tenant_isolation-Policy."

    _with_seed(_run)


@pytest.mark.integration
@pytest.mark.usefixtures("migrated_db")
def test_access_log_grants_are_append_only() -> None:
    """Grant-Introspektion (0044-Muster): `who2be_app` hat auf
    `agent_access_log` SELECT + INSERT, aber weder UPDATE noch DELETE."""

    async def _run(conn: asyncpg.Connection, workspace_id: UUID, agent_id: UUID) -> None:
        role_exists = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'who2be_app')"
        )
        if not role_exists:
            pytest.skip("Rolle who2be_app fehlt lokal — Grant-Introspektion uebersprungen.")
        for privilege, expected in (
            ("SELECT", True),
            ("INSERT", True),
            ("UPDATE", False),
            ("DELETE", False),
        ):
            granted = await conn.fetchval(
                "SELECT has_table_privilege('who2be_app', 'agent_access_log', $1)",
                privilege,
            )
            assert granted is expected, (
                f"agent_access_log: {privilege}-Privileg fuer who2be_app "
                f"erwartet {expected}, ist {granted}."
            )

    _with_seed(_run)


@pytest.mark.integration
def test_access_log_append_only_for_app_role() -> None:
    """Laufzeit-Beweis (Vorlage test_audit_append_only.py): als `who2be_app`
    geht INSERT auf `agent_access_log`, UPDATE/DELETE schlagen mit
    `InsufficientPrivilege` fehl; der Owner behaelt Vollzugriff (Purge)."""

    settings = get_settings()
    schema = f"phase2_{secrets.token_hex(6)}"

    async def _run() -> None:
        owner = await asyncpg.connect(settings.database_url)
        app: asyncpg.Connection | None = None
        try:
            await owner.execute(f'CREATE SCHEMA "{schema}"')
            await owner.execute(f'SET search_path TO "{schema}"')
            await apply_migrations(owner, MIGRATIONS_DIR)

            # Seed als Owner (RLS-Bypass): Org + Workspace + Agent.
            org_id = await owner.fetchval(
                "INSERT INTO organization (name, slug, kind) "
                "VALUES ('o', $1, 'company') RETURNING id",
                f"o-{secrets.token_hex(4)}",
            )
            ws_id = await owner.fetchval(
                "INSERT INTO workspace (org_id, name, slug) VALUES ($1, 'w', 'w') RETURNING id",
                org_id,
            )
            agent_id = await owner.fetchval(
                "INSERT INTO agent (workspace_id, owner_id, name) "
                "VALUES ($1, $2, 'log-agent') RETURNING id",
                ws_id,
                uuid4(),
            )

            # Test-Passwort fuer die App-Rolle.
            await owner.execute(f"ALTER ROLE who2be_app WITH PASSWORD '{_APP_PASSWORD}'")
            app = await asyncpg.connect(
                settings.database_url, user="who2be_app", password=_APP_PASSWORD
            )
            await app.execute(f'SET search_path TO "{schema}"')
            await app.execute("SELECT set_config('app.current_org', $1, false)", str(org_id))
            await app.execute("SELECT set_config('app.current_tenant', $1, false)", str(ws_id))

            # --- Als who2be_app: INSERT erlaubt (Service-Schreibpfad). ---
            log_id = await app.fetchval(
                "INSERT INTO agent_access_log "
                "(workspace_id, agent_id, ref_kind, ref_id, operation, "
                " sensitivity_at_access, access_date) "
                "VALUES ($1, $2, 'node', $3, 'read', 'sensitive', $4) "
                "ON CONFLICT DO NOTHING RETURNING id",
                ws_id,
                agent_id,
                str(uuid4()),
                _ACCESS_DATE,
            )
            assert log_id is not None

            # --- Als who2be_app: UPDATE/DELETE DB-seitig verboten. ---
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await app.execute("UPDATE agent_access_log SET id = id")
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await app.execute("DELETE FROM agent_access_log")

            # --- Als Owner: DELETE weiter erlaubt (Purge/Erasure, 0044). ---
            await owner.execute("DELETE FROM agent_access_log WHERE id = $1", log_id)
        finally:
            if app is not None:
                await app.close()
            await owner.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            await owner.close()

    asyncio.run(_run())
