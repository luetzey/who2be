"""Knowledge Base und Passagen fallen mit dem Workspace (Migration 0105).

Befund aus #888 (Katalog-Scan bis 0104): `kb_node`, `kb_edge`,
`kb_edge_evidence`, `kb_conflict` (0077) und `content_chunk` (0070) tragen
`workspace_id` ohne Fremdschluessel. Weder `WorkspaceRepository.delete` noch
die Organization-CASCADE in `purge_organization` erreichten sie: nach einer
Loeschung blieben Aussagen (`kb_node.content`), Widerspruchs-Begruendungen
(`kb_conflict.reason`) und Inhaltspassagen (`content_chunk.text`) samt
`created_by` verwaist zurueck. Die Kanten hingen nur ueber die NULLABLE
`from_node_id`/`to_node_id` an `kb_node` — eine unaufgeloeste Kante fiel nicht
einmal mit ihren Nodes. 0105 bereinigt die Waisen und haengt alle fuenf
Tabellen per `ON DELETE CASCADE` an `workspace`.

`audit_log` wird hier nur **belegt**, nicht geaendert: die Zeilen ueberleben
Workspace-Loeschung und Org-Purge (append-only, ADR-0031). Wie damit zu
verfahren ist, ist eine Owner-Weiche (Karte t_a0ce24ba); faellt sie, kippt der
Ist-Test bewusst und wird mit der Umsetzung umgeschrieben.

Belegt gegen die echte DB, in einem frisch migrierten Wegwerf-Schema. Ohne DB
greift der zentrale Skip; mit `WHO2BE_REQUIRE_DB=1` schlaegt er hart fehl.
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

_MIGRATION = "0105_kb_chunk_workspace_fk.sql"

_TABLES = ("kb_node", "kb_edge", "kb_edge_evidence", "kb_conflict", "content_chunk")
_NONE = dict.fromkeys(_TABLES, 0)
# Je Workspace: zwei Nodes, eine aufgeloeste und eine unaufgeloeste Kante
# (Anker ohne Node-ID), je eine Evidence, ein Konflikt, eine Passage.
_SEEDED = {
    "kb_node": 2,
    "kb_edge": 2,
    "kb_edge_evidence": 2,
    "kb_conflict": 1,
    "content_chunk": 1,
}

Body = Callable[[asyncpg.Connection, asyncpg.Pool], Awaitable[None]]


def _in_isolated_schema(body: Body, *, stop_before: str | None = None) -> None:
    """Owner-Verbindung + Pool auf einem frisch migrierten Wegwerf-Schema.

    `stop_before` migriert nur bis VOR die genannte Datei (Bestandsfall).
    """
    schema = f"kb_erasure_{secrets.token_hex(6)}"
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
    """Alle Migrationen alphabetisch vor `stop_before`, mit Runner-Eintrag."""
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


async def _node(owner: asyncpg.Connection, ws: UUID, author: UUID) -> UUID:
    node_id: UUID = await owner.fetchval(
        "INSERT INTO kb_node (workspace_id, tier, content, source_ref, source_ref_kind,"
        " occurred_at, occurred_precision, created_by)"
        " VALUES ($1, 'hypothesis', 'Aussage mit Personenbezug', 'url:https://x.test',"
        " 'url', now(), 'day', $2) RETURNING id",
        ws,
        author,
    )
    return node_id


async def _edge(
    owner: asyncpg.Connection, ws: UUID, author: UUID, a: UUID | None, b: UUID | None
) -> None:
    edge_id: UUID = await owner.fetchval(
        "INSERT INTO kb_edge (workspace_id, type, from_anchor, to_anchor,"
        " from_node_id, to_node_id, created_by)"
        " VALUES ($1, 'supports', 'node:a', 'node:b', $2, $3, $4) RETURNING id",
        ws,
        a,
        b,
        author,
    )
    await owner.execute(
        "INSERT INTO kb_edge_evidence (workspace_id, edge_id, side, anchor)"
        " VALUES ($1, $2, 'from', 'artifact:x#b1')",
        ws,
        edge_id,
    )


async def _seed(owner: asyncpg.Connection, ws: UUID) -> None:
    """KB-Aussagen samt Kanten/Evidence/Konflikt und eine Inhaltspassage."""
    author = uuid4()
    a, b = await _node(owner, ws, author), await _node(owner, ws, author)
    await _edge(owner, ws, author, a, b)
    # Unaufgeloeste Kante: haengt an keinem Node, faellt ohne workspace-FK nie.
    await _edge(owner, ws, author, None, None)
    await owner.execute(
        "INSERT INTO kb_conflict (workspace_id, kind, a_id, b_id, reason)"
        " VALUES ($1, 'node', $2, $3, 'Begruendung im Freitext')",
        ws,
        a,
        b,
    )
    await owner.execute(
        "INSERT INTO content_chunk (workspace_id, entity_type, entity_id, version,"
        " locale, ord, text) VALUES ($1, 'playbook', $2, 1, 'de', 0, 'Inhaltstext')",
        ws,
        uuid4(),
    )


async def _counts(owner: asyncpg.Connection, ws: UUID) -> dict[str, int]:
    return {
        table: await owner.fetchval(
            f"SELECT count(*) FROM {table} WHERE workspace_id = $1",  # noqa: S608 — feste Namen
            ws,
        )
        for table in _TABLES
    }


async def _audit(owner: asyncpg.Connection, org_id: UUID, ws: UUID) -> None:
    await owner.execute(
        "INSERT INTO audit_log (org_id, workspace_id, actor_id, action, target, detail)"
        " VALUES ($1, $2, $3, 'member.removed', 'user:x', '{\"note\": \"frei\"}')",
        org_id,
        ws,
        uuid4(),
    )


async def _audit_count(owner: asyncpg.Connection, ws: UUID) -> int:
    count: int = await owner.fetchval("SELECT count(*) FROM audit_log WHERE workspace_id = $1", ws)
    return count


def test_workspace_delete_removes_its_kb_and_chunks() -> None:
    async def body(owner: asyncpg.Connection, pool: asyncpg.Pool) -> None:
        org_id = await _org(owner)
        # Zwei Workspaces: der letzte einer Org ist geschuetzt.
        doomed, sibling = await _workspace(owner, org_id), await _workspace(owner, org_id)
        await _seed(owner, doomed)
        await _seed(owner, sibling)
        assert await _counts(owner, doomed) == _SEEDED

        assert await PgWorkspaceRepository(pool).delete(doomed) is True

        assert await _counts(owner, doomed) == _NONE, "Workspace-Loeschung liess KB/Passagen stehen"
        assert await _counts(owner, sibling) == _SEEDED

    _in_isolated_schema(body)


def test_org_purge_removes_kb_and_chunks_of_all_its_workspaces() -> None:
    async def body(owner: asyncpg.Connection, _pool: asyncpg.Pool) -> None:
        org_id, other_org = await _org(owner), await _org(owner)
        ws_a, ws_b = await _workspace(owner, org_id), await _workspace(owner, org_id)
        ws_other = await _workspace(owner, other_org)
        for ws in (ws_a, ws_b, ws_other):
            await _seed(owner, ws)

        await PgAccountPurgeRepository(owner).purge_organization(org_id)

        assert await _counts(owner, ws_a) == _NONE, "Org-Purge liess KB/Passagen stehen"
        assert await _counts(owner, ws_b) == _NONE, "Org-Purge liess KB/Passagen stehen"
        assert await _counts(owner, ws_other) == _SEEDED

    _in_isolated_schema(body)


def test_migration_removes_existing_orphans_and_keeps_live_rows() -> None:
    async def body(owner: asyncpg.Connection, _pool: asyncpg.Pool) -> None:
        org_id = await _org(owner)
        live = await _workspace(owner, org_id)
        gone = uuid4()  # Workspace, der vor 0105 geloescht wurde
        await _seed(owner, live)
        await _seed(owner, gone)
        assert await _counts(owner, gone) == _SEEDED

        await apply_migrations(owner, MIGRATIONS_DIR)

        assert await _counts(owner, gone) == _NONE, "0105 hat Bestands-Waisen uebrig gelassen"
        assert await _counts(owner, live) == _SEEDED

    _in_isolated_schema(body, stop_before=_MIGRATION)


def test_audit_log_survives_workspace_delete_and_org_purge_as_is() -> None:
    """Ist-Verhalten, bewusst unveraendert (Owner-Weiche t_a0ce24ba).

    `audit_log` hat keinen FK auf `workspace`/`organization` und ist fuer die
    Laufzeitrolle append-only (0044). Nach Workspace-Loeschung und Org-Purge
    bleiben die Zeilen samt `actor_id`, `target` und `detail` stehen. Kippt
    dieser Test, wurde die Weiche umgesetzt — dann mit ihr umschreiben.
    """

    async def body(owner: asyncpg.Connection, pool: asyncpg.Pool) -> None:
        org_id = await _org(owner)
        doomed, sibling = await _workspace(owner, org_id), await _workspace(owner, org_id)
        await _audit(owner, org_id, doomed)
        await _audit(owner, org_id, sibling)

        assert await PgWorkspaceRepository(pool).delete(doomed) is True
        assert await _audit_count(owner, doomed) == 1

        await PgAccountPurgeRepository(owner).purge_organization(org_id)
        assert await _audit_count(owner, sibling) == 1
        assert await _audit_count(owner, doomed) == 1

    _in_isolated_schema(body)
