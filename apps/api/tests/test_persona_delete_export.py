"""Integrationstests: Hard-Delete + Einzel-Export einer Persona (ADR-0032).

Deckt ab:
- DELETE: 204 + danach 404; 404 unbekannt; 403 Viewer; 409 bei Agent-Referenz
  (Verwender im Body); keine Waisen-Versionen.
- EXPORT: JSON-Struktur (Versionen, keine internen Spalten, Attachment-Header);
  Markdown (text/markdown + Attachment + gerenderter Inhalt); 404 unbekannt;
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


def _count_versions(persona_id: str) -> int:
    async def _run() -> int:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            value: int = await conn.fetchval(
                "SELECT count(*) FROM persona_version WHERE persona_id = $1",
                UUID(persona_id),
            )
            return value
        finally:
            await conn.close()

    return asyncio.run(_run())


def _persona_body(name: str = "Carla") -> dict[str, object]:
    return {
        "name": name,
        "content": {
            "description": "Coach",
            "system_prompt": "",
            "tags": ["support"],
            "content": {
                "description": "",
                "blocks": [
                    {
                        "id": "block-1",
                        "type": "paragraph",
                        "props": {},
                        "content": [{"type": "text", "text": "Empathisch.", "styles": {}}],
                        "children": [],
                    }
                ],
            },
        },
    }


@pytest.mark.integration
def test_persona_delete_happy_and_orphans(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    base = f"/v1/workspaces/{ws}/personas"
    try:
        with TestClient(app) as client:
            pid = client.post(base, json=_persona_body(), headers=auth).json()["id"]
            assert _count_versions(pid) == 1

            deleted = client.delete(f"{base}/{pid}", headers=auth)
            assert deleted.status_code == 204, deleted.text
            # Danach 404 beim Get + keine Waisen-Versionen (CASCADE).
            assert client.get(f"{base}/{pid}", headers=auth).status_code == 404
            assert _count_versions(pid) == 0

            # Unbekannte ID -> 404.
            assert client.delete(f"{base}/{_UNKNOWN}", headers=auth).status_code == 404
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_persona_delete_viewer_forbidden(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    viewer = fresh_user_id()
    ws = setup_workspace(owner)
    _add_member(ws, viewer, WorkspaceRole.viewer)
    base = f"/v1/workspaces/{ws}/personas"
    try:
        with TestClient(app) as client:
            pid = client.post(base, json=_persona_body(), headers=_auth(owner)).json()["id"]
            assert client.delete(f"{base}/{pid}", headers=_auth(viewer)).status_code == 403
            # Persona lebt weiter.
            assert client.get(f"{base}/{pid}", headers=_auth(owner)).status_code == 200
    finally:
        cleanup_workspaces([owner, viewer])


@pytest.mark.integration
def test_persona_delete_blocked_by_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    personas = f"/v1/workspaces/{ws}/personas"
    agents = f"/v1/workspaces/{ws}/agents"
    try:
        with TestClient(app) as client:
            persona = client.post(personas, json=_persona_body(), headers=auth).json()
            # Agent verweist auf die Persona (disabled reicht — kein active-Gate).
            agent = client.post(
                agents,
                json={"name": "Bot", "persona_id": persona["id"]},
                headers=auth,
            )
            assert agent.status_code == 201, agent.text

            blocked = client.delete(f"{personas}/{persona['id']}", headers=auth)
            assert blocked.status_code == 409, blocked.text
            detail = blocked.json()["detail"]
            assert "agents" in detail["blocked_by"]
            assert detail["blocked_by"]["agents"][0]["agent_id"] == agent.json()["id"]
            assert detail["blocked_by"]["agents"][0]["agent_name"] == "Bot"
            # Persona lebt noch (Delete wurde nicht ausgefuehrt).
            assert client.get(f"{personas}/{persona['id']}", headers=auth).status_code == 200
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_persona_export_json_and_markdown(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    viewer = fresh_user_id()
    ws = setup_workspace(owner)
    _add_member(ws, viewer, WorkspaceRole.viewer)
    base = f"/v1/workspaces/{ws}/personas"
    try:
        with TestClient(app) as client:
            pid = client.post(base, json=_persona_body(), headers=_auth(owner)).json()["id"]

            # JSON (Default).
            res = client.get(f"{base}/{pid}/export", headers=_auth(owner))
            assert res.status_code == 200, res.text
            assert "attachment" in res.headers["content-disposition"]
            assert f"who2be-persona-{pid}.json" in res.headers["content-disposition"]
            body = res.json()
            assert body["entity"] == "persona"
            persona = body["persona"]
            assert persona["id"] == pid
            assert "workspace_id" not in persona
            assert len(persona["versions"]) == 1
            for version in persona["versions"]:
                assert "workspace_id" not in version

            # Markdown.
            md = client.get(f"{base}/{pid}/export?format=markdown", headers=_auth(owner))
            assert md.status_code == 200, md.text
            assert md.headers["content-type"].startswith("text/markdown")
            assert f"who2be-persona-{pid}.md" in md.headers["content-disposition"]
            assert "name:" in md.text
            assert "Empathisch." in md.text

            # Viewer darf exportieren.
            assert client.get(f"{base}/{pid}/export", headers=_auth(viewer)).status_code == 200

            # Unbekannte ID -> 404.
            assert client.get(f"{base}/{_UNKNOWN}/export", headers=_auth(owner)).status_code == 404
    finally:
        cleanup_workspaces([owner, viewer])
