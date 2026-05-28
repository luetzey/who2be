"""Integrationstest fuer Personae unter `/v1/workspaces/{ws_id}/personas`.

Belegt die Versions-Erzeugung bei `PUT` und die Workspace-Isolation. Laeuft
nur mit erreichbarer Datenbank; ohne DB wird der Test uebersprungen.
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


def _persona_body(description: str) -> dict[str, object]:
    return {
        "name": "QA-Bot",
        "content": {
            "description": description,
            "system_prompt": "Be precise.",
            "traits": ["thorough"],
        },
    }


@pytest.mark.integration
def test_persona_crud_versioning_and_isolation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    other = fresh_user_id()
    ws = setup_workspace(owner)
    other_ws = setup_workspace(other)
    auth = _auth(owner)
    base = f"/v1/workspaces/{ws}/personas"

    try:
        with TestClient(app) as client:
            assert client.get(base).status_code == 401

            created = client.post(base, json=_persona_body("v1"), headers=auth)
            assert created.status_code == 201
            persona = created.json()
            persona_id = persona["id"]
            assert persona["current_version"] == 1
            assert persona["workspace_id"] == str(ws)

            fetched = client.get(f"{base}/{persona_id}", headers=auth).json()
            assert fetched["content"]["description"] == "v1"

            listed = client.get(base, headers=auth).json()
            assert [p["id"] for p in listed] == [persona_id]

            updated = client.put(
                f"{base}/{persona_id}",
                json=_persona_body("v2"),
                headers=auth,
            )
            assert updated.status_code == 200
            assert updated.json()["current_version"] == 2

            current = client.get(f"{base}/{persona_id}", headers=auth).json()
            assert current["content"]["description"] == "v2"

            versions = client.get(f"{base}/{persona_id}/versions", headers=auth).json()
            assert [v["version"] for v in versions] == [2, 1]

            v1 = client.get(f"{base}/{persona_id}/versions/1", headers=auth).json()
            assert v1["content"]["description"] == "v1"

            # Cross-Workspace: fremder User mit eigenem Workspace sieht 403,
            # weil er keine Membership im Owner-Workspace hat.
            assert client.get(base, headers=_auth(other)).status_code == 403
            # Im eigenen Workspace ist die Persona nicht sichtbar.
            other_base = f"/v1/workspaces/{other_ws}/personas"
            assert client.get(other_base, headers=_auth(other)).json() == []
    finally:
        cleanup_workspaces([owner, other])


@pytest.mark.integration
def test_persona_pagination_via_cursor_and_limit_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    other = fresh_user_id()
    ws = setup_workspace(owner)
    setup_workspace(other)
    auth = _auth(owner)
    base = f"/v1/workspaces/{ws}/personas"

    try:
        with TestClient(app) as client:
            created_ids: list[str] = []
            for i in range(3):
                resp = client.post(base, json=_persona_body(f"v{i}"), headers=auth)
                assert resp.status_code == 201
                created_ids.append(resp.json()["id"])

            page1 = client.get(f"{base}?limit=2", headers=auth)
            assert page1.status_code == 200
            assert len(page1.json()) == 2
            cursor = page1.headers.get("X-Next-Cursor")
            assert cursor is not None

            page2 = client.get(f"{base}?limit=2&cursor={cursor}", headers=auth)
            assert page2.status_code == 200
            assert len(page2.json()) == 1
            assert "X-Next-Cursor" not in page2.headers

            seen = {p["id"] for p in page1.json()} | {p["id"] for p in page2.json()}
            assert seen == set(created_ids)

            # Cross-Workspace: fremder Aufruf 403 (kein Membership).
            assert client.get(base, headers=_auth(other)).status_code == 403

            # Validation: Limit-Bereich und Cursor-Form.
            assert client.get(f"{base}?limit=0", headers=auth).status_code == 422
            assert client.get(f"{base}?limit=201", headers=auth).status_code == 422
            assert client.get(f"{base}?cursor=!!!", headers=auth).status_code == 422
    finally:
        cleanup_workspaces([owner, other])
