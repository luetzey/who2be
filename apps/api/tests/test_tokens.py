"""Integrationstest fuer `/v1/workspaces/{ws_id}/tokens` und `get_current_workspace`.

Deckt AC1 (API-Token erstellen/listen/widerrufen) ab und belegt beide
Auth-Wege (JWT + w2b_-Token). Laeuft nur mit erreichbarer Datenbank; ohne DB
wird der Test uebersprungen.
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


def _jwt(owner_id: UUID) -> str:
    return jwt.encode(
        {
            "sub": str(owner_id),
            "aud": "authenticated",
            "role": "authenticated",
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        _TEST_SECRET,
        algorithm="HS256",
    )


@pytest.mark.integration
def test_token_lifecycle_and_both_auth_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner_id = fresh_user_id()
    ws = setup_workspace(owner_id)
    jwt_auth = {"Authorization": f"Bearer {_jwt(owner_id)}"}
    base = f"/v1/workspaces/{ws}/tokens"

    try:
        with TestClient(app) as client:
            assert client.get(base).status_code == 401

            created = client.post(base, json={"name": "agent"}, headers=jwt_auth)
            assert created.status_code == 201
            body = created.json()
            plaintext = body["token"]
            token_id = body["id"]
            assert plaintext.startswith("w2b_")
            assert body["workspace_id"] == str(ws)

            listed = client.get(base, headers=jwt_auth).json()
            assert [t["id"] for t in listed] == [token_id]
            assert "token" not in listed[0]
            assert "token_hash" not in listed[0]

            api_auth = {"Authorization": f"Bearer {plaintext}"}
            assert client.get(base, headers=api_auth).status_code == 200

            revoke = client.delete(f"{base}/{token_id}", headers=jwt_auth)
            assert revoke.status_code == 204

            assert client.get(base, headers=api_auth).status_code == 401
            assert client.delete(f"{base}/{token_id}", headers=jwt_auth).status_code == 404
    finally:
        cleanup_workspaces([owner_id])


@pytest.mark.integration
def test_api_token_rejected_for_other_workspace(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner_id = fresh_user_id()
    other_id = fresh_user_id()
    ws_a = setup_workspace(owner_id)
    ws_b = setup_workspace(other_id)
    jwt_auth = {"Authorization": f"Bearer {_jwt(owner_id)}"}

    try:
        with TestClient(app) as client:
            created = client.post(
                f"/v1/workspaces/{ws_a}/tokens",
                json={"name": "agent"},
                headers=jwt_auth,
            )
            assert created.status_code == 201
            plaintext = created.json()["token"]
            api_auth = {"Authorization": f"Bearer {plaintext}"}

            # Token gepinnt auf ws_a: Aufruf auf ws_b -> 403 (Snapshot-Mismatch).
            assert (
                client.get(f"/v1/workspaces/{ws_b}/tokens", headers=api_auth).status_code
                == 403
            )
    finally:
        cleanup_workspaces([owner_id, other_id])


@pytest.mark.integration
def test_token_listing_pagination_and_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner_id = fresh_user_id()
    ws = setup_workspace(owner_id)
    jwt_auth = {"Authorization": f"Bearer {_jwt(owner_id)}"}
    base = f"/v1/workspaces/{ws}/tokens"

    try:
        with TestClient(app) as client:
            created_ids: list[str] = []
            for i in range(3):
                resp = client.post(base, json={"name": f"t{i}"}, headers=jwt_auth)
                assert resp.status_code == 201
                created_ids.append(resp.json()["id"])

            page1 = client.get(f"{base}?limit=2", headers=jwt_auth)
            assert page1.status_code == 200
            assert len(page1.json()) == 2
            cursor = page1.headers.get("X-Next-Cursor")
            assert cursor is not None

            page2 = client.get(f"{base}?limit=2&cursor={cursor}", headers=jwt_auth)
            assert page2.status_code == 200
            assert len(page2.json()) == 1
            assert "X-Next-Cursor" not in page2.headers

            seen = {t["id"] for t in page1.json()} | {t["id"] for t in page2.json()}
            assert seen == set(created_ids)

            assert client.get(f"{base}?limit=0", headers=jwt_auth).status_code == 422
            assert client.get(f"{base}?limit=201", headers=jwt_auth).status_code == 422
            assert client.get(f"{base}?cursor=!!!", headers=jwt_auth).status_code == 422
    finally:
        cleanup_workspaces([owner_id])
