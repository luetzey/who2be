"""Integrationstest fuer `/v1/tokens` und `get_current_user`.

Deckt AC1 (API-Token erstellen/listen/widerrufen) ab und belegt beide
Auth-Wege. Laeuft nur mit erreichbarer Datenbank; ohne DB wird der Test
uebersprungen.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import asyncpg
import jwt
import pytest
from fastapi.testclient import TestClient

from who2be_api.core import security
from who2be_api.core.config import Settings, get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.main import app

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


def _cleanup(owner_id: UUID) -> None:
    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await conn.execute("DELETE FROM api_token WHERE owner_id = $1", owner_id)
        finally:
            await conn.close()

    asyncio.run(_run())


@pytest.mark.integration
def test_token_lifecycle_and_both_auth_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner_id = uuid4()
    jwt_token = jwt.encode(
        {
            "sub": str(owner_id),
            "aud": "authenticated",
            "role": "authenticated",
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        _TEST_SECRET,
        algorithm="HS256",
    )
    jwt_auth = {"Authorization": f"Bearer {jwt_token}"}

    try:
        with TestClient(app) as client:
            assert client.get("/v1/tokens").status_code == 401

            created = client.post("/v1/tokens", json={"name": "agent"}, headers=jwt_auth)
            assert created.status_code == 201
            body = created.json()
            plaintext = body["token"]
            token_id = body["id"]
            assert plaintext.startswith("w2b_")

            listed = client.get("/v1/tokens", headers=jwt_auth).json()
            assert [t["id"] for t in listed] == [token_id]
            assert "token" not in listed[0]
            assert "token_hash" not in listed[0]

            api_auth = {"Authorization": f"Bearer {plaintext}"}
            assert client.get("/v1/tokens", headers=api_auth).status_code == 200

            revoke = client.delete(f"/v1/tokens/{token_id}", headers=jwt_auth)
            assert revoke.status_code == 204

            assert client.get("/v1/tokens", headers=api_auth).status_code == 401
            assert client.delete(f"/v1/tokens/{token_id}", headers=jwt_auth).status_code == 404
    finally:
        _cleanup(owner_id)


@pytest.mark.integration
def test_token_listing_pagination_and_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner_id = uuid4()
    jwt_token = jwt.encode(
        {
            "sub": str(owner_id),
            "aud": "authenticated",
            "role": "authenticated",
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        _TEST_SECRET,
        algorithm="HS256",
    )
    jwt_auth = {"Authorization": f"Bearer {jwt_token}"}

    try:
        with TestClient(app) as client:
            created_ids: list[str] = []
            for i in range(3):
                resp = client.post("/v1/tokens", json={"name": f"t{i}"}, headers=jwt_auth)
                assert resp.status_code == 201
                created_ids.append(resp.json()["id"])

            page1 = client.get("/v1/tokens?limit=2", headers=jwt_auth)
            assert page1.status_code == 200
            assert len(page1.json()) == 2
            cursor = page1.headers.get("X-Next-Cursor")
            assert cursor is not None

            page2 = client.get(f"/v1/tokens?limit=2&cursor={cursor}", headers=jwt_auth)
            assert page2.status_code == 200
            assert len(page2.json()) == 1
            assert "X-Next-Cursor" not in page2.headers

            seen = {t["id"] for t in page1.json()} | {t["id"] for t in page2.json()}
            assert seen == set(created_ids)

            assert client.get("/v1/tokens?limit=0", headers=jwt_auth).status_code == 422
            assert client.get("/v1/tokens?limit=201", headers=jwt_auth).status_code == 422
            assert client.get("/v1/tokens?cursor=!!!", headers=jwt_auth).status_code == 422
    finally:
        _cleanup(owner_id)
