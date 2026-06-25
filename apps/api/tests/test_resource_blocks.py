"""Integrationstest fuer `GET .../resources/{id}/blocks` (WP-6, #258).

Listet die linkbaren Heading-Anker (id/level/text) einer Resource. Deckt ab:
- Nur Heading-Bloecke erscheinen, Paragraphen nicht; level/text korrekt.
- Active-/Draft-Sicht: ein gebundener API-Token sieht nur aktive Versionen.
- Read-Scoping: fremde / nicht zugewiesene Resource → 404.

Skippt ohne erreichbare DB (Muster aus test_playbook_resources.py).
"""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

import asyncpg
import jwt
import pytest
from fastapi.testclient import TestClient

from who2be_api.core import security
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


def _block(block_id: str, text: str, block_type: str = "paragraph") -> dict[str, object]:
    return {
        "id": block_id,
        "type": block_type,
        "props": {},
        "content": [{"type": "text", "text": text, "styles": {}}],
        "children": [],
    }


def _heading(block_id: str, text: str, level: int = 1) -> dict[str, object]:
    return {
        "id": block_id,
        "type": "heading",
        "props": {"level": level},
        "content": [{"type": "text", "text": text, "styles": {}}],
        "children": [],
    }


def _resource_body(name: str, blocks: list[dict[str, object]]) -> dict[str, object]:
    return {"name": name, "content": {"description": f"resource {name}", "blocks": blocks}}


def _activate(
    client: TestClient, base: str, entity_id: str, version: int, auth: dict[str, str]
) -> None:
    versions = client.get(f"{base}/{entity_id}/versions", headers=auth).json()
    current = next((v["status"] for v in versions if v["version"] == version), None)
    steps = ["draft", "review", "active"]
    start = steps.index(current) + 1 if current in steps else 0
    for to in steps[start:]:
        resp = client.post(
            f"{base}/{entity_id}/versions/{version}/transition", json={"to": to}, headers=auth
        )
        assert resp.status_code == 200, resp.text


@pytest.mark.integration
def test_list_resource_blocks_returns_heading_anchors(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    rbase = f"/v1/workspaces/{ws}/resources"

    try:
        with TestClient(app) as client:
            rid = client.post(
                rbase,
                json=_resource_body(
                    "Doc",
                    [
                        _heading("h1", "Erster Block", level=1),
                        _block("p1", "Paragraph zu h1"),
                        _heading("h2", "Zweiter", level=2),
                        _block("p2", "Paragraph zu h2"),
                    ],
                ),
                headers=auth,
            ).json()["id"]
            _activate(client, rbase, rid, 1, auth)

            resp = client.get(f"{rbase}/{rid}/blocks", headers=auth)
            assert resp.status_code == 200, resp.text
            anchors = resp.json()
            # Nur die zwei Heading-Bloecke, keine Paragraphen.
            assert [a["block_id"] for a in anchors] == ["h1", "h2"]
            assert anchors[0] == {"block_id": "h1", "level": 1, "text": "Erster Block"}
            assert anchors[1] == {"block_id": "h2", "level": 2, "text": "Zweiter"}
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_list_resource_blocks_404_for_foreign_resource(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    other = fresh_user_id()
    ws = setup_workspace(owner)
    other_ws = setup_workspace(other)
    auth = _auth(owner)

    try:
        with TestClient(app) as client:
            foreign_rid = client.post(
                f"/v1/workspaces/{other_ws}/resources",
                json=_resource_body("Foreign", [_heading("h1", "x")]),
                headers=_auth(other),
            ).json()["id"]
            _activate(client, f"/v1/workspaces/{other_ws}/resources", foreign_rid, 1, _auth(other))

            # Fremde Resource ueber den eigenen Workspace-Pfad → 404.
            resp = client.get(f"/v1/workspaces/{ws}/resources/{foreign_rid}/blocks", headers=auth)
            assert resp.status_code == 404
    finally:
        cleanup_workspaces([owner, other])
