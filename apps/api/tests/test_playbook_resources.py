"""Integrationstest fuer Playbook->Resource-Block-Refs (Phase 2.2).

Pfad `/v1/workspaces/{ws}/playbooks/{id}/resource_links`. Deckt ab:
Set-Replace-Semantik, `available`/`preview`-Aufloesung gegen die aktive
Resource-Version, das "Block geloescht"-Verhalten nach einer neuen Version
ohne den Block, und Cross-Workspace-Isolation. Skippt ohne erreichbare DB.
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


def _block(block_id: str, text: str) -> dict[str, object]:
    return {
        "id": block_id,
        "type": "paragraph",
        "props": {},
        "content": [{"type": "text", "text": text, "styles": {}}],
        "children": [],
    }


def _resource_body(name: str, blocks: list[dict[str, object]]) -> dict[str, object]:
    return {"name": name, "content": {"description": "", "blocks": blocks}}


def _playbook_body(name: str) -> dict[str, object]:
    return {
        "name": name,
        "content": {
            "description": "d",
            "body": "1. Step.",
            "type": "workflow",
            "tags": [],
            "triggers": None,
        },
    }


def _activate(
    client: TestClient, base: str, entity_id: str, version: int, auth: dict[str, str]
) -> None:
    for to in ("draft", "review", "active"):
        resp = client.post(
            f"{base}/{entity_id}/versions/{version}/transition", json={"to": to}, headers=auth
        )
        assert resp.status_code == 200, resp.text


@pytest.mark.integration
def test_resource_links_set_replace_and_availability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    rbase = f"/v1/workspaces/{ws}/resources"
    pbase = f"/v1/workspaces/{ws}/playbooks"

    try:
        with TestClient(app) as client:
            rid = client.post(
                rbase,
                json=_resource_body(
                    "Doc", [_block("b1", "Erster Block"), _block("b2", "Zweiter")]
                ),
                headers=auth,
            ).json()["id"]
            _activate(client, rbase, rid, 1, auth)

            pid = client.post(pbase, json=_playbook_body("PB"), headers=auth).json()["id"]
            links_url = f"{pbase}/{pid}/resource_links"

            # Leerer Stand.
            assert client.get(links_url, headers=auth).json() == []

            # Set: zwei Bloecke verlinken.
            resp = client.put(
                links_url,
                json={
                    "links": [
                        {"resource_id": rid, "block_id": "b1", "position": 0},
                        {"resource_id": rid, "block_id": "b2", "position": 1},
                    ]
                },
                headers=auth,
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert [link["block_id"] for link in body] == ["b1", "b2"]
            assert all(link["available"] for link in body)
            assert body[0]["preview"] == "Erster Block"
            assert body[0]["resource_name"] == "Doc"

            # Set-Replace: nur noch b1.
            replaced = client.put(
                links_url,
                json={"links": [{"resource_id": rid, "block_id": "b1", "position": 0}]},
                headers=auth,
            ).json()
            assert [link["block_id"] for link in replaced] == ["b1"]

            # Neue aktive Version OHNE b1 -> Link wird unavailable ("Block geloescht").
            client.put(
                rbase + f"/{rid}",
                json=_resource_body("Doc", [_block("b2", "Nur b2")]),
                headers=auth,
            )
            _activate(client, rbase, rid, 2, auth)
            after = client.get(links_url, headers=auth).json()
            assert after[0]["block_id"] == "b1"
            assert after[0]["available"] is False
            assert after[0]["preview"] is None

            # Leere Liste loest alle Links.
            assert client.put(links_url, json={"links": []}, headers=auth).json() == []
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_resource_links_reject_cross_workspace(monkeypatch: pytest.MonkeyPatch) -> None:
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
            # Resource im fremden Workspace.
            foreign_rid = client.post(
                f"/v1/workspaces/{other_ws}/resources",
                json=_resource_body("Foreign", [_block("b1", "x")]),
                headers=_auth(other),
            ).json()["id"]
            pid = client.post(
                f"/v1/workspaces/{ws}/playbooks", json=_playbook_body("PB"), headers=auth
            ).json()["id"]

            # Fremde Resource im eigenen Playbook verlinken -> 404.
            resp = client.put(
                f"/v1/workspaces/{ws}/playbooks/{pid}/resource_links",
                json={"links": [{"resource_id": foreign_rid, "block_id": "b1", "position": 0}]},
                headers=auth,
            )
            assert resp.status_code == 404
    finally:
        cleanup_workspaces([owner, other])
