"""Integrationstest des Passage-Backfills (ADR-0046).

Der Backfill schliesst die Luecke, die Migration 0070 offen laesst: Chunks
entstehen im Betrieb nur beim Statuswechsel auf `active`, Bestands-Workspaces
haben ihre Inhalte aber laengst aktiviert. Ohne diesen Lauf findet
`search_content` dort nichts.

Zweiter Zweck: Reparatur. Aendert sich der Chunk-Schnitt, baut derselbe Lauf
alles neu — er muss deshalb idempotent sein.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import jwt
import pytest
from fastapi.testclient import TestClient

from who2be_api.core import security
from who2be_api.core.chunk_backfill import backfill_chunks
from who2be_api.core.config import Settings, get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.main import app
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace

_TEST_SECRET = "integration-test-jwt-secret-padding-0123456789"


def _db_reachable() -> bool:
    async def _check() -> bool:
        try:
            conn = await asyncpg.connect(get_settings().database_url)
        except (asyncpg.PostgresError, OSError):
            return False
        await conn.close()
        return True

    return asyncio.run(_check())


def _prepare_db() -> None:
    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await apply_migrations(conn, MIGRATIONS_DIR)
        finally:
            await conn.close()

    asyncio.run(_run())


def _auth(owner_id: UUID) -> dict[str, str]:
    token = jwt.encode(
        {
            "sub": str(owner_id),
            "aud": "authenticated",
            "role": "authenticated",
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        _TEST_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def _run_backfill() -> tuple[int, int, int]:
    async def _run() -> tuple[int, int, int]:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            return await backfill_chunks(conn)
        finally:
            await conn.close()

    return asyncio.run(_run())


def _sql(query: str, *args: Any) -> Any:
    async def _run() -> Any:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            return await conn.fetchval(query, *args)
        finally:
            await conn.close()

    return asyncio.run(_run())


def _blocks() -> list[dict[str, Any]]:
    return [
        {
            "id": "h1",
            "type": "heading",
            "props": {"level": 1},
            "content": [{"type": "text", "text": "Eskalationsstufen", "styles": {}}],
        },
        {
            "id": "p1",
            "type": "paragraph",
            "content": [
                {"type": "text", "text": "Ab Stufe drei uebernimmt die Leitung.", "styles": {}}
            ],
        },
    ]


@pytest.mark.integration
def test_backfill_materializes_passages_for_existing_active_versions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    prefix = f"/v1/workspaces/{ws}"
    rbase = f"{prefix}/resources"

    try:
        with TestClient(app) as client:
            rid = client.post(
                rbase,
                json={
                    "name": "Bestand",
                    "content": {"description": "Alt", "blocks": _blocks(), "tags": []},
                },
                headers=auth,
            ).json()["id"]
            for to in ("review", "active"):
                client.post(f"{rbase}/{rid}/versions/1/transition", json={"to": to}, headers=auth)

            # Bestands-Zustand simulieren: Passagen wegwerfen, als haette es
            # den Transition-Hook zum Aktivierungszeitpunkt noch nicht gegeben.
            _sql("DELETE FROM content_chunk WHERE entity_id = $1 RETURNING 1", UUID(rid))
            assert (
                client.get(
                    f"{prefix}/search/content", params={"q": "Eskalationsstufen"}, headers=auth
                ).json()
                == []
            )

            entities, chunks, _orphans = _run_backfill()
            assert entities >= 1
            assert chunks >= 1

            found = client.get(
                f"{prefix}/search/content", params={"q": "Eskalationsstufen"}, headers=auth
            ).json()
            assert [h["entity_id"] for h in found] == [rid]
            assert found[0]["block_id"] == "h1"

            # Idempotent: ein zweiter Lauf aendert die Trefferlage nicht und
            # verdoppelt die Passagen nicht.
            before = _sql("SELECT count(*) FROM content_chunk WHERE entity_id = $1", UUID(rid))
            _run_backfill()
            after = _sql("SELECT count(*) FROM content_chunk WHERE entity_id = $1", UUID(rid))
            assert before == after
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_backfill_removes_orphaned_chunks() -> None:
    """Verwaiste Chunks (Entity geloescht) werden weggeraeumt.

    `entity_id` ist polymorph ueber fuenf Tabellen und kann keinen FK tragen —
    die Aufraeumung ist deshalb Aufgabe des Backfills.
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    ghost = uuid4()

    async def _insert() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await conn.execute(
                "INSERT INTO content_chunk "
                "(workspace_id, entity_type, entity_id, version, locale, ord, text) "
                "VALUES ($1, 'resource', $2, 1, 'de', 0, 'verwaiste Passage')",
                uuid4(),
                ghost,
            )
        finally:
            await conn.close()

    asyncio.run(_insert())
    assert _sql("SELECT count(*) FROM content_chunk WHERE entity_id = $1", ghost) == 1

    _entities, _chunks, orphans = _run_backfill()

    assert orphans >= 1
    assert _sql("SELECT count(*) FROM content_chunk WHERE entity_id = $1", ghost) == 0
