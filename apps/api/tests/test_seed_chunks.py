"""Passagen fuer geseedete und zentral verteilte Builder-Inhalte (ADR-0046).

Chunks entstehen normalerweise beim Statuswechsel auf `active`. Zwei Pfade
laufen daran vorbei und schreiben aktive Versionen direkt: der Workspace-Seed
(`_seed_default_agents`) und der Start-Sync (`sync_managed_builder_content`,
In-place-Replace). Ohne die Anbindung an den Chunk-Lauf haette ein frischer
Workspace NULL Passagen — ausgerechnet im Builder-Bestand, dessen eigene
Konventionen die Passagen-Suche empfehlen.

Dazu die Gegenprobe auf der Content-Ebene: das Retrieval-Wissen muss in beiden
Sprach-Packs stehen, sonst kennt der Builder das Tool nicht, das er benutzen
soll.
"""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

import asyncpg
import jwt
import pytest
from fastapi.testclient import TestClient

from who2be_api.core import security
from who2be_api.core.chunk_backfill import backfill_chunks
from who2be_api.core.config import Settings, get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.main import app
from who2be_api.repositories.builder_content import SUPPORTED_LOCALES, get_content_pack
from who2be_api.repositories.workspace_repository import sync_managed_builder_content
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace

_TEST_SECRET = "integration-test-jwt-secret-padding-0123456789"

# Markiger Text, der im kanonischen Stand garantiert NICHT vorkommt — so ist
# „alter Stand" im Test eindeutig von „kanonischer Stand" unterscheidbar.
_STALE_MARKER = "Kaktusklausel"


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


@pytest.mark.integration
def test_seeded_workspace_has_passages(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ein frischer Workspace ist ab Sekunde eins durchsuchbar.

    Vor der Anbindung lieferte `search_content` in einem neuen Workspace
    ausnahmslos `[]` — der Seed schreibt seine aktiven Versionen per Insert,
    nicht ueber `version_status._transition`.
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)

    async def _types() -> dict[str, int]:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            rows = await conn.fetch(
                "SELECT entity_type, count(*) AS n FROM content_chunk "
                "WHERE workspace_id = $1 GROUP BY entity_type",
                ws,
            )
            return {r["entity_type"]: r["n"] for r in rows}
        finally:
            await conn.close()

    try:
        per_type = asyncio.run(_types())
        # Persona, die sechs Playbooks, die Konventions-Resource und die
        # Templates — alle vier Typen des Seeds tragen Passagen.
        assert set(per_type) == {"persona", "playbook", "resource", "system_prompt_template"}
        assert all(n > 0 for n in per_type.values()), per_type

        with TestClient(app) as client:
            res = client.get(
                f"/v1/workspaces/{ws}/search/content",
                params={"q": "Schnittkanten"},
                headers=_auth(owner),
            )
            assert res.status_code == 200, res.text
            hits = res.json()
            assert hits, "Der neue Retrieval-Abschnitt der Konventionen muss auffindbar sein."
            assert any(h["type"] == "resource" for h in hits), hits
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_content_sync_needs_the_chunk_rebuild() -> None:
    """Der Start-Sync ersetzt Inhalte in-place — Passagen bleiben sonst alt.

    Belegt beide Haelften: nach dem Sync zeigt die Passagen-Ebene noch auf den
    alten Text (deshalb ruft `main.py` den Rebuild auf), und der Rebuild bringt
    sie auf den kanonischen Stand.
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    owner = fresh_user_id()
    ws = setup_workspace(owner)

    stale_blocks = json.dumps(
        [
            {
                "id": "stale-h",
                "type": "heading",
                "props": {"level": 2},
                "content": [{"type": "text", "text": _STALE_MARKER, "styles": {}}],
                "children": [],
            }
        ]
    )

    async def _run() -> dict[str, object]:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            # Alten Stand simulieren: Resource-Inhalt ersetzen + Stempel zurueck,
            # danach die Passagen dieses Workspaces darauf aufbauen.
            await conn.execute(
                "UPDATE resource_version rv "
                "SET content = jsonb_set(rv.content, '{blocks}', $2::jsonb) "
                "FROM resource r WHERE rv.resource_id = r.id AND r.workspace_id = $1 "
                "AND r.name = 'Agent-Bau-Konventionen' AND rv.status = 'active'",
                ws,
                stale_blocks,
            )
            await conn.execute(
                "UPDATE resource SET managed_content_version = 0 "
                "WHERE workspace_id = $1 AND name = 'Agent-Bau-Konventionen'",
                ws,
            )
            await backfill_chunks(conn, ws)
            stale_before = await conn.fetchval(
                "SELECT count(*) FROM content_chunk WHERE workspace_id = $1 AND text LIKE $2",
                ws,
                f"%{_STALE_MARKER}%",
            )

            await sync_managed_builder_content(conn)
            stale_after_sync = await conn.fetchval(
                "SELECT count(*) FROM content_chunk WHERE workspace_id = $1 AND text LIKE $2",
                ws,
                f"%{_STALE_MARKER}%",
            )

            await backfill_chunks(conn)
            stale_after_rebuild = await conn.fetchval(
                "SELECT count(*) FROM content_chunk WHERE workspace_id = $1 AND text LIKE $2",
                ws,
                f"%{_STALE_MARKER}%",
            )
            canonical = await conn.fetchval(
                "SELECT count(*) FROM content_chunk "
                "WHERE workspace_id = $1 AND entity_type = 'resource' "
                "AND text LIKE '%Schnittkanten%'",
                ws,
            )
            return {
                "before": stale_before,
                "after_sync": stale_after_sync,
                "after_rebuild": stale_after_rebuild,
                "canonical": canonical,
            }
        finally:
            await conn.close()

    try:
        res = asyncio.run(_run())
    finally:
        cleanup_workspaces([owner])

    assert res["before"] == 1, res
    # Der Sync allein raeumt die Passagen NICHT auf — genau deshalb gibt es den
    # Rebuild im Startpfad.
    assert res["after_sync"] == 1, res
    assert res["after_rebuild"] == 0, res
    assert res["canonical"] == 1, res


@pytest.mark.parametrize("locale", SUPPORTED_LOCALES)
def test_conventions_carry_the_retrieval_section(locale: str) -> None:
    """Ohne diesen Abschnitt kennt der Builder die Passagen-Suche nicht.

    Das Tool ist im System-Prompt sichtbar (`tools-overview`), aber die
    Autoren-Regeln dazu — Ueberschriften als Schnittkanten, nur aktive
    Versionen sind auffindbar — leben in den Konventionen. Der Test bindet
    beides aneinander, damit ein Sprach-Pack nicht zurueckfaellt.
    """
    pack = get_content_pack(locale)
    blocks = json.loads(pack.resource.load_body(locale))
    ids = {b["id"] for b in blocks}
    assert "res-conv-h-retrieval" in ids
    assert "res-conv-li-memory-semantik" in ids

    body = json.dumps(blocks, ensure_ascii=False)
    assert "search_content" in body
    assert "ADR-0046" in body


@pytest.mark.parametrize("locale", SUPPORTED_LOCALES)
def test_persona_and_playbooks_point_at_search_content(locale: str) -> None:
    """Die Konventionen sind ein lazy-Pointer — der Einstieg muss im Prompt stehen."""
    pack = get_content_pack(locale)
    assert "search_content" in pack.persona.load_content(locale)

    by_key = {p.key: p for p in pack.playbooks}
    for key in ("playbook", "maintenance"):
        assert "search_content" in by_key[key].load_body(locale), key
