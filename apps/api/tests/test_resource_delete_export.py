"""Integrationstests: Hard-Delete + Einzel-Export einer Resource (ADR-0032).

Deckt ab:
- DELETE: 204 + danach 404; 404 unbekannt; 403 Viewer; 409 bei eingehender
  Referenz (Playbook-Block-Ref ODER Eltern-Composite) mit Verwendern im Body;
  keine Waisen-Versionen/Links.
- EXPORT: JSON-Struktur; Markdown (text/markdown + Attachment); 404 unbekannt;
  Viewer darf exportieren.

Laeuft nur mit erreichbarer Datenbank; ohne DB wird der Test uebersprungen.
"""

from __future__ import annotations

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
from who2be_api.testing.workspace_setup import (
    cleanup_workspaces,
    fresh_user_id,
    setup_workspace,
)
from who2be_models import WorkspaceRole

_TEST_SECRET = "integration-test-jwt-secret-padding-0123456789"
_UNKNOWN = "00000000-0000-0000-0000-000000000000"


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


def _auth(user_id: UUID) -> dict[str, str]:
    token = jwt.encode(
        {
            "sub": str(user_id),
            "aud": "authenticated",
            "role": "authenticated",
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        _TEST_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def _add_member(workspace_id: UUID, user_id: UUID, role: WorkspaceRole) -> None:
    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await conn.execute(
                "INSERT INTO workspace_member (workspace_id, user_id, role) "
                "VALUES ($1, $2, $3) "
                "ON CONFLICT (workspace_id, user_id) DO UPDATE SET role = excluded.role",
                workspace_id,
                user_id,
                role.value,
            )
        finally:
            await conn.close()

    asyncio.run(_run())


def _count_versions(resource_id: str) -> int:
    async def _run() -> int:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            value: int = await conn.fetchval(
                "SELECT count(*) FROM resource_version WHERE resource_id = $1",
                UUID(resource_id),
            )
            return value
        finally:
            await conn.close()

    return asyncio.run(_run())


def _heading(block_id: str, text: str) -> dict[str, object]:
    return {
        "id": block_id,
        "type": "heading",
        "props": {"level": 1},
        "content": [{"type": "text", "text": text, "styles": {}}],
        "children": [],
    }


def _resource_body(
    name: str = "Doc", blocks: list[dict[str, object]] | None = None
) -> dict[str, object]:
    return {
        "name": name,
        "content": {
            "description": "",
            "blocks": blocks if blocks is not None else [_heading("h1", "Inhalt X")],
            "tags": ["docs"],
        },
    }


def _playbook_body(name: str = "PB") -> dict[str, object]:
    return {
        "name": name,
        "content": {
            "description": "d",
            "body": "Body.",
            "type": "workflow",
            "tags": [],
            "triggers": None,
        },
    }


@pytest.mark.integration
def test_resource_delete_happy_and_orphans(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    base = f"/v1/workspaces/{ws}/resources"
    try:
        with TestClient(app) as client:
            rid = client.post(base, json=_resource_body(), headers=auth).json()["id"]
            assert _count_versions(rid) == 1

            deleted = client.delete(f"{base}/{rid}", headers=auth)
            assert deleted.status_code == 204, deleted.text
            assert client.get(f"{base}/{rid}", headers=auth).status_code == 404
            assert _count_versions(rid) == 0

            assert client.delete(f"{base}/{_UNKNOWN}", headers=auth).status_code == 404
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_resource_delete_viewer_forbidden(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    viewer = fresh_user_id()
    ws = setup_workspace(owner)
    _add_member(ws, viewer, WorkspaceRole.viewer)
    base = f"/v1/workspaces/{ws}/resources"
    try:
        with TestClient(app) as client:
            rid = client.post(base, json=_resource_body(), headers=_auth(owner)).json()["id"]
            assert client.delete(f"{base}/{rid}", headers=_auth(viewer)).status_code == 403
            assert client.get(f"{base}/{rid}", headers=_auth(owner)).status_code == 200
    finally:
        cleanup_workspaces([owner, viewer])


@pytest.mark.integration
def test_resource_delete_blocked_by_playbook(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    resources = f"/v1/workspaces/{ws}/resources"
    playbooks = f"/v1/workspaces/{ws}/playbooks"
    try:
        with TestClient(app) as client:
            rid = client.post(resources, json=_resource_body(), headers=auth).json()["id"]
            pid = client.post(playbooks, json=_playbook_body("Beta"), headers=auth).json()["id"]
            link = client.put(
                f"{playbooks}/{pid}/resource_links",
                json={"links": [{"resource_id": rid, "block_id": "h1", "position": 0}]},
                headers=auth,
            )
            assert link.status_code == 200, link.text

            blocked = client.delete(f"{resources}/{rid}", headers=auth)
            assert blocked.status_code == 409, blocked.text
            detail = blocked.json()["detail"]
            assert detail["blocked_by"]["playbooks"][0]["playbook_name"] == "Beta"
            assert client.get(f"{resources}/{rid}", headers=auth).status_code == 200
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_resource_delete_blocked_by_composite(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    base = f"/v1/workspaces/{ws}/resources"
    try:
        with TestClient(app) as client:
            child = client.post(base, json=_resource_body("Child"), headers=auth).json()["id"]
            parent = client.post(base, json=_resource_body("Parent"), headers=auth).json()["id"]
            composed = client.put(
                f"{base}/{parent}/sub_resources",
                json={"links": [{"child_id": child, "position": 0, "link_scope": "resource"}]},
                headers=auth,
            )
            assert composed.status_code == 200, composed.text

            blocked = client.delete(f"{base}/{child}", headers=auth)
            assert blocked.status_code == 409, blocked.text
            detail = blocked.json()["detail"]
            assert [c["name"] for c in detail["blocked_by"]["composites"]] == ["Parent"]
            assert client.get(f"{base}/{child}", headers=auth).status_code == 200
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_resource_export_json_and_markdown(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    viewer = fresh_user_id()
    ws = setup_workspace(owner)
    _add_member(ws, viewer, WorkspaceRole.viewer)
    base = f"/v1/workspaces/{ws}/resources"
    try:
        with TestClient(app) as client:
            rid = client.post(base, json=_resource_body(), headers=_auth(owner)).json()["id"]

            res = client.get(f"{base}/{rid}/export", headers=_auth(owner))
            assert res.status_code == 200, res.text
            assert f"who2be-resource-{rid}.json" in res.headers["content-disposition"]
            body = res.json()
            assert body["entity"] == "resource"
            assert body["resource"]["id"] == rid
            assert "workspace_id" not in body["resource"]
            assert len(body["resource"]["versions"]) == 1

            md = client.get(f"{base}/{rid}/export?format=markdown", headers=_auth(owner))
            assert md.status_code == 200, md.text
            assert md.headers["content-type"].startswith("text/markdown")
            assert f"who2be-resource-{rid}.md" in md.headers["content-disposition"]
            assert "Inhalt X" in md.text

            assert client.get(f"{base}/{rid}/export", headers=_auth(viewer)).status_code == 200
            assert client.get(f"{base}/{_UNKNOWN}/export", headers=_auth(owner)).status_code == 404
    finally:
        cleanup_workspaces([owner, viewer])
