"""Integrationstest fuer Rate-Limiting (MS-3 H1, slowapi).

Belegt drei Eigenschaften:
1. POST `/v1/personas` antwortet nach dem Limit mit 429.
2. GET-Endpoints sind nicht limitiert.
3. Zwei verschiedene Tokens haben unabhaengige Buckets.

Setup analog `test_personas.py`: nur mit erreichbarer DB; ohne DB Skip.
"""

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import asyncpg
import jwt
import pytest
from fastapi.testclient import TestClient

from who2be_api.core import rate_limit, security
from who2be_api.core.config import Settings, get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.main import app

_TEST_SECRET = "integration-test-jwt-secret-padding-0123456789"
_TEST_LIMIT = "2/minute"


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


def _cleanup(owner_ids: list[UUID]) -> None:
    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await conn.execute("DELETE FROM persona WHERE owner_id = ANY($1::uuid[])", owner_ids)
        finally:
            await conn.close()

    asyncio.run(_run())


def _auth(owner_id: UUID) -> dict[str, str]:
    token = jwt.encode(
        {"sub": str(owner_id), "exp": datetime.now(UTC) + timedelta(hours=1)},
        _TEST_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def _persona_body(name: str) -> dict[str, object]:
    return {
        "name": name,
        "content": {
            "description": "rate-limit-fixture",
            "system_prompt": "Be precise.",
            "traits": ["thorough"],
        },
    }


@pytest.fixture(autouse=True)
def _reset_limiter() -> Iterator[None]:
    """Limiter ist Modul-Singleton; State muss zwischen Tests weg."""
    rate_limit.limiter.reset()
    yield
    rate_limit.limiter.reset()


def _override_settings(monkeypatch: pytest.MonkeyPatch, limit: str) -> None:
    settings = Settings(jwt_secret=_TEST_SECRET, rate_limit_write=limit)
    monkeypatch.setattr(security, "get_settings", lambda: settings)
    monkeypatch.setattr(rate_limit, "get_settings", lambda: settings)


@pytest.mark.integration
def test_post_personas_returns_429_after_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    _override_settings(monkeypatch, _TEST_LIMIT)

    owner = uuid4()
    auth = _auth(owner)

    try:
        with TestClient(app) as client:
            r1 = client.post("/v1/personas", json=_persona_body("p1"), headers=auth)
            r2 = client.post("/v1/personas", json=_persona_body("p2"), headers=auth)
            r3 = client.post("/v1/personas", json=_persona_body("p3"), headers=auth)
            assert r1.status_code == 201
            assert r2.status_code == 201
            assert r3.status_code == 429
    finally:
        _cleanup([owner])


@pytest.mark.integration
def test_get_personas_not_rate_limited(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    _override_settings(monkeypatch, _TEST_LIMIT)

    owner = uuid4()
    auth = _auth(owner)

    try:
        with TestClient(app) as client:
            for _ in range(5):
                response = client.get("/v1/personas", headers=auth)
                assert response.status_code == 200
                assert response.status_code != 429
    finally:
        _cleanup([owner])


@pytest.mark.integration
def test_rate_limit_keyed_per_token(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    _override_settings(monkeypatch, _TEST_LIMIT)

    owner_a = uuid4()
    owner_b = uuid4()
    auth_a = _auth(owner_a)
    auth_b = _auth(owner_b)

    try:
        with TestClient(app) as client:
            assert (
                client.post("/v1/personas", json=_persona_body("a1"), headers=auth_a)
            ).status_code == 201
            assert (
                client.post("/v1/personas", json=_persona_body("a2"), headers=auth_a)
            ).status_code == 201
            # Owner B steckt nicht im Bucket von A — darf weiter schreiben.
            assert (
                client.post("/v1/personas", json=_persona_body("b1"), headers=auth_b)
            ).status_code == 201
            assert (
                client.post("/v1/personas", json=_persona_body("b2"), headers=auth_b)
            ).status_code == 201
            # Owner A ist im Limit, Owner B noch nicht.
            assert (
                client.post("/v1/personas", json=_persona_body("a3"), headers=auth_a)
            ).status_code == 429
            assert (
                client.post("/v1/personas", json=_persona_body("b3"), headers=auth_b)
            ).status_code == 429
    finally:
        _cleanup([owner_a, owner_b])
