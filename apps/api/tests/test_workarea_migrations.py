"""Integrationstests fuer die WorkArea-/KB-Migrations (0073-0077, ADR-0047).

Belegt:

- Alle zehn neuen Tabellen existieren nach dem Migrations-Lauf.
- "Genau eine private Area je (Workspace, Agent)" (partial unique Index).
- Scope-Owner-Kopplung: 'shared' MIT Owner bzw. 'private' OHNE Owner scheitert
  am Zeilen-CHECK.
- co_occurs_with-Backstop: Kante ohne co_-Felder scheitert, `co_n = 19`
  scheitert, `co_n = 20` mit vollstaendigen co_-Feldern passiert.
- RLS: die `tenant_isolation`-Policy liegt auf allen zehn neuen Tabellen
  (pg_policies-Introspektion, Muster test_rls_isolation.py).

Idempotenz der gesamten Migrations-Kette (Runner 2x = No-op) ist durch die
bestehenden Migrations-Tests abgedeckt und wird hier bewusst NICHT dupliziert.
Laeuft gegen die zentral migrierte Test-DB (conftest: ``migrated_db`` +
zentraler Integration-Skip ohne DB); Seeds ueber
``who2be_api.testing.workspace_setup``.
"""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import TypeVar
from uuid import UUID, uuid4

import asyncpg
import pytest

from who2be_api.core.config import get_settings
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace

_T = TypeVar("_T")

_NEW_TABLES = (
    "work_area",
    "work_area_grant",
    "wa_artifact",
    "wa_blob",
    "wa_chunk",
    "kb_node",
    "kb_edge",
    "kb_edge_evidence",
    "kb_node_source_area",
    "kb_conflict",
)

_OCCURRED_AT = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)


def _with_seed(body: Callable[[asyncpg.Connection, UUID, UUID], Awaitable[_T]]) -> _T:
    """Fuehrt ``body(conn, workspace_id, agent_id)`` gegen die migrierte DB aus.

    ``setup_workspace``/``cleanup_workspaces`` rufen intern selbst
    ``asyncio.run`` auf und muessen deshalb AUSSERHALB der Coroutine laufen
    (Muster test_memory_retrieval_baseline.py). Die KB-Tabellen haengen nicht
    am Workspace-CASCADE (kein FK auf workspace, s. 0077) — das Cleanup
    loescht sie daher explizit, bevor die Org faellt.
    """
    owner = fresh_user_id()
    workspace_id = setup_workspace(owner)

    async def _run() -> _T:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            agent_id: UUID = await conn.fetchval(
                "INSERT INTO agent (workspace_id, owner_id, name) "
                "VALUES ($1, $2, 'wa-mig-agent') RETURNING id",
                workspace_id,
                owner,
            )
            try:
                return await body(conn, workspace_id, agent_id)
            finally:
                await conn.execute("DELETE FROM kb_edge WHERE workspace_id = $1", workspace_id)
                await conn.execute("DELETE FROM kb_node WHERE workspace_id = $1", workspace_id)
        finally:
            await conn.close()

    try:
        return asyncio.run(_run())
    finally:
        cleanup_workspaces([owner])


async def _insert_area(
    conn: asyncpg.Connection,
    workspace_id: UUID,
    *,
    scope: str,
    owner_agent_id: UUID | None,
    name: str,
) -> UUID:
    area_id: UUID = await conn.fetchval(
        "INSERT INTO work_area (workspace_id, scope, owner_agent_id, name) "
        "VALUES ($1, $2, $3, $4) RETURNING id",
        workspace_id,
        scope,
        owner_agent_id,
        name,
    )
    return area_id


async def _insert_node(conn: asyncpg.Connection, workspace_id: UUID, content: str) -> UUID:
    node_id: UUID = await conn.fetchval(
        "INSERT INTO kb_node "
        "(workspace_id, tier, content, source_ref, source_ref_kind, "
        " occurred_at, occurred_precision, created_by) "
        "VALUES ($1, 'hypothesis', $2, 'url:https://example.com', 'url', $3, 'day', $4) "
        "RETURNING id",
        workspace_id,
        content,
        _OCCURRED_AT,
        uuid4(),
    )
    return node_id


@pytest.mark.integration
@pytest.mark.usefixtures("migrated_db")
def test_workarea_kb_tables_exist() -> None:
    """0073-0077 legen alle zehn WorkArea-/KB-Tabellen an."""

    async def _run(conn: asyncpg.Connection, workspace_id: UUID, agent_id: UUID) -> None:
        for table in _NEW_TABLES:
            regclass = await conn.fetchval("SELECT to_regclass($1)", table)
            assert regclass is not None, f"Tabelle {table} fehlt nach dem Migrations-Lauf."

    _with_seed(_run)


@pytest.mark.integration
@pytest.mark.usefixtures("migrated_db")
def test_private_area_unique_per_agent() -> None:
    """Genau EINE private Area je (Workspace, Agent) — die zweite scheitert."""

    async def _run(conn: asyncpg.Connection, workspace_id: UUID, agent_id: UUID) -> None:
        await _insert_area(
            conn, workspace_id, scope="private", owner_agent_id=agent_id, name="privat-1"
        )
        with pytest.raises(asyncpg.UniqueViolationError):
            await _insert_area(
                conn, workspace_id, scope="private", owner_agent_id=agent_id, name="privat-2"
            )

    _with_seed(_run)


@pytest.mark.integration
@pytest.mark.usefixtures("migrated_db")
def test_work_area_scope_owner_check() -> None:
    """Scope-Owner-Kopplung: 'shared' MIT Owner und 'private' OHNE Owner
    werden vom Zeilen-CHECK abgewiesen; die jeweils korrekten Kombinationen
    passieren."""

    async def _run(conn: asyncpg.Connection, workspace_id: UUID, agent_id: UUID) -> None:
        with pytest.raises(asyncpg.CheckViolationError):
            await _insert_area(
                conn, workspace_id, scope="shared", owner_agent_id=agent_id, name="falsch-1"
            )
        with pytest.raises(asyncpg.CheckViolationError):
            await _insert_area(
                conn, workspace_id, scope="private", owner_agent_id=None, name="falsch-2"
            )
        await _insert_area(
            conn, workspace_id, scope="private", owner_agent_id=agent_id, name="ok-privat"
        )
        await _insert_area(
            conn, workspace_id, scope="shared", owner_agent_id=None, name="ok-shared"
        )

    _with_seed(_run)


@pytest.mark.integration
@pytest.mark.usefixtures("migrated_db")
def test_kb_edge_co_occurs_check() -> None:
    """co_occurs_with-Backstop (Anforderung O): ohne co_-Felder scheitert die
    Kante, `co_n = 19` ist unterpowert, `co_n = 20` mit vollem co_-Satz
    passiert; andere Kantentypen brauchen keine co_-Felder."""

    async def _run(conn: asyncpg.Connection, workspace_id: UUID, agent_id: UUID) -> None:
        node_a = await _insert_node(conn, workspace_id, "Aussage A")
        node_b = await _insert_node(conn, workspace_id, "Aussage B")

        async def _insert_edge(edge_type: str, co_n: int | None, *, with_co: bool) -> None:
            await conn.execute(
                "INSERT INTO kb_edge "
                "(workspace_id, type, from_anchor, to_anchor, from_node_id, to_node_id, "
                " co_query, co_n, co_from, co_to, created_by) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)",
                workspace_id,
                edge_type,
                str(node_a),
                str(node_b),
                node_a,
                node_b,
                "SELECT 1" if with_co else None,
                co_n,
                _OCCURRED_AT if with_co else None,
                _OCCURRED_AT if with_co else None,
                uuid4(),
            )

        # Kante ohne co_-Felder: der co_occurs-CHECK weist sie ab.
        with pytest.raises(asyncpg.CheckViolationError):
            await _insert_edge("co_occurs_with", None, with_co=False)
        # Unterpowerte Korrelation: n = 19 < 20 scheitert am n-CHECK.
        with pytest.raises(asyncpg.CheckViolationError):
            await _insert_edge("co_occurs_with", 19, with_co=True)
        # Vollstaendiger co_-Satz mit n = 20 passiert.
        await _insert_edge("co_occurs_with", 20, with_co=True)
        # Andere Kantentypen brauchen keine co_-Felder.
        await _insert_edge("supports", None, with_co=False)

    _with_seed(_run)


@pytest.mark.integration
@pytest.mark.usefixtures("migrated_db")
def test_rls_policy_on_all_new_tables() -> None:
    """RLS ist auf allen zehn neuen Tabellen aktiv und traegt die
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
