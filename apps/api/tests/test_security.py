"""Unit-Tests fuer die Auth-Primitiven (`core/security.py`).

Ohne I/O: der Token-Dispatch wird mit einem In-Memory-Fake-Repository
geprueft, JWTs werden mit einem Test-Secret selbst signiert.
"""

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi import HTTPException

from who2be_api.core import security
from who2be_api.core.config import Settings
from who2be_api.core.security import (
    TOKEN_PREFIX,
    get_current_user,
    hash_token,
    new_token,
    resolve_owner,
    verify_supabase_jwt,
)
from who2be_models import TokenRead

_SECRET = "unit-test-jwt-secret-padding-0123456789"


def _encode(claims: dict[str, Any], secret: str = _SECRET) -> str:
    """Signiert ein JWT; ergaenzt ein gueltiges `exp`, falls nicht gesetzt."""
    payload: dict[str, Any] = {
        "exp": datetime.now(UTC) + timedelta(hours=1),
        **claims,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture
def jwt_secret(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_SECRET))
    yield


class FakeTokenRepository:
    """In-Memory-Stub von `TokenRepository` fuer den Dispatch-Test."""

    def __init__(self, owner_by_hash: dict[str, UUID] | None = None) -> None:
        self._owner_by_hash = owner_by_hash or {}
        self.touched: list[str] = []

    async def insert(self, owner_id: UUID, name: str, token_hash: str) -> TokenRead:
        raise NotImplementedError

    async def list_by_owner(self, owner_id: UUID) -> list[TokenRead]:
        raise NotImplementedError

    async def fetch_owner_by_hash(self, token_hash: str) -> UUID | None:
        return self._owner_by_hash.get(token_hash)

    async def revoke(self, owner_id: UUID, token_id: UUID) -> bool:
        raise NotImplementedError

    async def touch_last_used(self, token_hash: str) -> None:
        self.touched.append(token_hash)


def test_hash_token_is_deterministic_and_distinct() -> None:
    assert hash_token("w2b_abc") == hash_token("w2b_abc")
    assert hash_token("w2b_abc") != hash_token("w2b_xyz")


def test_new_token_has_prefix_and_is_unique() -> None:
    first, second = new_token(), new_token()
    assert first.startswith(TOKEN_PREFIX)
    assert first != second


def test_verify_jwt_accepts_valid_token(jwt_secret: None) -> None:
    owner = uuid4()
    assert verify_supabase_jwt(_encode({"sub": str(owner)})) == owner


def test_verify_jwt_rejects_expired_token(jwt_secret: None) -> None:
    token = _encode(
        {"sub": str(uuid4()), "exp": datetime.now(UTC) - timedelta(hours=1)}
    )
    with pytest.raises(HTTPException) as exc:
        verify_supabase_jwt(token)
    assert exc.value.status_code == 401


def test_verify_jwt_rejects_token_without_exp(jwt_secret: None) -> None:
    # Ohne exp wuerde ein JWT sonst unbegrenzt gelten — require=["exp"].
    token = jwt.encode({"sub": str(uuid4())}, _SECRET, algorithm="HS256")
    with pytest.raises(HTTPException):
        verify_supabase_jwt(token)


def test_verify_jwt_rejects_wrong_secret(jwt_secret: None) -> None:
    token = _encode({"sub": str(uuid4())}, "a-different-secret-padding-0123456789")
    with pytest.raises(HTTPException):
        verify_supabase_jwt(token)


def test_verify_jwt_rejects_non_uuid_sub(jwt_secret: None) -> None:
    with pytest.raises(HTTPException):
        verify_supabase_jwt(_encode({"sub": "not-a-uuid"}))


def test_verify_jwt_rejects_missing_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=""))
    token = jwt.encode({"sub": str(uuid4())}, "x" * 32, algorithm="HS256")
    with pytest.raises(HTTPException):
        verify_supabase_jwt(token)


def test_resolve_owner_via_api_token_touches_last_used() -> None:
    plaintext = new_token()
    owner = uuid4()
    repo = FakeTokenRepository({hash_token(plaintext): owner})
    assert asyncio.run(resolve_owner(plaintext, repo)) == owner
    assert repo.touched == [hash_token(plaintext)]


def test_resolve_owner_rejects_unknown_api_token() -> None:
    with pytest.raises(HTTPException) as exc:
        asyncio.run(resolve_owner(new_token(), FakeTokenRepository()))
    assert exc.value.status_code == 401


def test_resolve_owner_via_jwt_leaves_token_table_untouched(jwt_secret: None) -> None:
    owner = uuid4()
    repo = FakeTokenRepository()
    assert asyncio.run(resolve_owner(_encode({"sub": str(owner)}), repo)) == owner
    assert repo.touched == []


def test_get_current_user_rejects_missing_credentials() -> None:
    with pytest.raises(HTTPException) as exc:
        asyncio.run(get_current_user(credentials=None))
    assert exc.value.status_code == 401
