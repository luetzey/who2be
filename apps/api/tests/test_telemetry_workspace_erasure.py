"""Telemetrie faellt mit dem Workspace (Migration 0104, Datenschutz-Befund).

`usage_event` und `agent_feedback` (0053) trugen `workspace_id` ohne
Fremdschluessel. Weder `WorkspaceRepository.delete` noch die
Organization-CASCADE in `purge_organization` erreichten sie: nach einer
Loeschung blieben Zeilen samt `actor_id` (Person) und Feedback-Freitext
`note` verwaist zurueck. 0104 bereinigt die Waisen und haengt beide Tabellen
per `ON DELETE CASCADE` an `workspace`; `feedback_resolution` faellt ueber
seinen FK auf `agent_feedback` mit.

Belegt gegen die echte DB, in einem frisch migrierten Wegwerf-Schema:

- **Workspace-Loeschung** (`PgWorkspaceRepository.delete`, API-Pfad) raeumt
  die Telemetrie dieses Workspace, die eines Geschwister-Workspace bleibt.
- **Org-Purge** (`purge_organization`, Owner-Verbindung wie der Purge-Job)
  raeumt die Telemetrie aller Workspaces der Org, die einer fremden Org bleibt.
- **Bestand:** Waisen aus der Zeit vor 0104 entfernt die Migration selbst,
  sonst liesse sich der Fremdschluessel gar nicht anlegen.

Ohne DB greift der zentrale Skip; mit `WHO2BE_REQUIRE_DB=1` schlaegt er hart fehl.
"""

from __future__ import annotations

import asyncio
import secrets
from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

import asyncpg
import pytest

from who2be_api.core.config import get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.repositories.account_repository import PgAccountPurgeRepository
from who2be_api.repositories.workspace_repository import PgWorkspaceRepository

pytestmark = pytest.mark.integration

_MIGRATION = "0104_telemetry_workspace_fk.sql"

Body = Callable[[asyncpg.Connection, asyncpg.Pool], Awaitable[None]]


def _in_isolated_schema(body: Body, *, stop_before: str | None = None) -> None:
    """Owner-Verbindung + Pool auf einem frisch migrierten Wegwerf-Schema.

    `stop_before` migriert nur bis VOR die genannte Datei (Bestandsfall).
    """
    schema = f"telemetry_erasure_{secrets.token_hex(6)}"
    url = get_settings().database_url

    async def _run() -> None:
        owner = await asyncpg.connect(url)
        pool: asyncpg.Pool | None = None
        try:
            await owner.execute(f'CREATE SCHEMA "{schema}"')
            await owner.execute(f'SET search_path TO "{schema}", public')
            if stop_before is None:
                await apply_migrations(owner, MIGRATIONS_DIR)
            else:
                await _apply_until(owner, stop_before)
            pool = await asyncpg.create_pool(
                url,
                min_size=1,
                max_size=2,
                server_settings={"search_path": f'"{schema}", public'},
            )
            await body(owner, pool)
        finally:
            if pool is not None:
                await pool.close()
            await owner.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            await owner.close()

    asyncio.run(_run())


async def _apply_until(conn: asyncpg.Connection, stop_before: str) -> None:
    """Wendet alle Migrationen an, die alphabetisch vor `stop_before` liegen —
    mit Eintrag in `schema_migrations` wie der Runner, damit ein spaeteres
    `apply_migrations` nur noch den Rest nachzieht."""
    await conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        " version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
    )
    for path in sorted(MIGRATIONS_DIR.glob("*.sql"), key=lambda p: p.name):
        if path.name >= stop_before:
            break
        async with conn.transaction():
            await conn.execute(path.read_text(encoding="utf-8"))
            await conn.execute("INSERT INTO schema_migrations (version) VALUES ($1)", path.name)


async def _org(owner: asyncpg.Connection) -> UUID:
    org_id: UUID = await owner.fetchval(
        "INSERT INTO organization (name, slug, kind) VALUES ('o', $1, 'company') RETURNING id",
        f"o-{secrets.token_hex(4)}",
    )
    return org_id


async def _workspace(owner: asyncpg.Connection, org_id: UUID) -> UUID:
    ws_id: UUID = await owner.fetchval(
        "INSERT INTO workspace (org_id, name, slug) VALUES ($1, 'w', $2) RETURNING id",
        org_id,
        f"w-{secrets.token_hex(4)}",
    )
    return ws_id


async def _telemetry(owner: asyncpg.Connection, workspace_id: UUID) -> None:
    """Je eine Nutzungs- und Feedback-Zeile mit Person und Freitext, dazu eine
    Triage-Zeile am Feedback."""
    actor = uuid4()
    await owner.execute(
        "INSERT INTO usage_event (workspace_id, actor_id, entity_type, entity_id, outcome) "
        "VALUES ($1, $2, 'playbook', $3, 'applied')",
        workspace_id,
        actor,
        uuid4(),
    )
    feedback_id: UUID = await owner.fetchval(
        "INSERT INTO agent_feedback (workspace_id, actor_id, entity_type, entity_id, signal, note) "
        "VALUES ($1, $2, 'playbook', $3, 'unclear', 'Freitext mit Personenbezug') "
        "RETURNING id",
        workspace_id,
        actor,
        uuid4(),
    )
    await owner.execute(
        "INSERT INTO feedback_resolution (workspace_id, feedback_id, resolution, actor_id) "
        "VALUES ($1, $2, 'addressed', $3)",
        workspace_id,
        feedback_id,
        actor,
    )


async def _counts(owner: asyncpg.Connection, workspace_id: UUID) -> dict[str, int]:
    return {
        table: await owner.fetchval(
            f"SELECT count(*) FROM {table} WHERE workspace_id = $1",  # noqa: S608 — feste Namen
            workspace_id,
        )
        for table in ("usage_event", "agent_feedback", "feedback_resolution")
    }


_NONE = {"usage_event": 0, "agent_feedback": 0, "feedback_resolution": 0}
_ONE = {"usage_event": 1, "agent_feedback": 1, "feedback_resolution": 1}


def test_workspace_delete_removes_its_telemetry() -> None:
    async def body(owner: asyncpg.Connection, pool: asyncpg.Pool) -> None:
        org_id = await _org(owner)
        # Zwei Workspaces: der letzte einer Org ist geschuetzt.
        doomed, sibling = await _workspace(owner, org_id), await _workspace(owner, org_id)
        await _telemetry(owner, doomed)
        await _telemetry(owner, sibling)
        assert await _counts(owner, doomed) == _ONE

        assert await PgWorkspaceRepository(pool).delete(doomed) is True

        assert await _counts(owner, doomed) == _NONE, "Workspace-Loeschung liess Telemetrie stehen"
        assert await _counts(owner, sibling) == _ONE

    _in_isolated_schema(body)


def test_org_purge_removes_telemetry_of_all_its_workspaces() -> None:
    async def body(owner: asyncpg.Connection, _pool: asyncpg.Pool) -> None:
        org_id, other_org = await _org(owner), await _org(owner)
        ws_a, ws_b = await _workspace(owner, org_id), await _workspace(owner, org_id)
        ws_other = await _workspace(owner, other_org)
        for ws in (ws_a, ws_b, ws_other):
            await _telemetry(owner, ws)

        await PgAccountPurgeRepository(owner).purge_organization(org_id)

        assert await _counts(owner, ws_a) == _NONE, "Org-Purge liess Telemetrie stehen"
        assert await _counts(owner, ws_b) == _NONE, "Org-Purge liess Telemetrie stehen"
        assert await _counts(owner, ws_other) == _ONE

    _in_isolated_schema(body)


def test_migration_removes_existing_orphans_and_keeps_live_rows() -> None:
    async def body(owner: asyncpg.Connection, _pool: asyncpg.Pool) -> None:
        org_id = await _org(owner)
        live = await _workspace(owner, org_id)
        gone = uuid4()  # Workspace, der vor 0104 geloescht wurde
        await _telemetry(owner, live)
        await _telemetry(owner, gone)
        assert await _counts(owner, gone) == _ONE

        await apply_migrations(owner, MIGRATIONS_DIR)

        assert await _counts(owner, gone) == _NONE, "0104 hat Bestands-Waisen uebrig gelassen"
        assert await _counts(owner, live) == _ONE

    _in_isolated_schema(body, stop_before=_MIGRATION)
