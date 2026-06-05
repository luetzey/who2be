"""Unit-Tests fuer den account/identity-Block im GDPR-Export (WP-E).

Ohne DB: ein Fake-Pool gibt definierte Antworten. Belegt, dass der Block
sauber zu `null` degradiert, wenn `auth.users` fehlt (PostgresError) — analog
`me_repository._lookup_email`.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import asyncpg

from who2be_api.services.gdpr_export_service import GdprExportService


class _MissingAuthPool:
    """Fake-Pool: jede Query schlaegt mit einer PostgresError fehl —
    simuliert eine Test-DB ohne `auth.users`-Schema."""

    async def fetch(self, query: str, *args: Any) -> list[Any]:
        return []

    async def fetchrow(self, query: str, *args: Any) -> None:
        raise asyncpg.PostgresError("relation auth.users does not exist")

    async def acquire(self) -> Any:  # pragma: no cover — nicht genutzt im Pfad
        raise NotImplementedError


def test_account_block_degrades_when_auth_users_missing() -> None:
    service = GdprExportService(_MissingAuthPool())
    user_id = uuid4()

    bundle = asyncio.run(service.export(user_id))

    assert bundle["user_id"] == str(user_id)
    assert bundle["organizations"] == []
    assert bundle["account"] == {
        "id": str(user_id),
        "email": None,
        "created_at": None,
        "last_sign_in_at": None,
    }


class _NotFoundAuthPool:
    """Fake-Pool: `auth.users` existiert, der User aber nicht."""

    async def fetch(self, query: str, *args: Any) -> list[Any]:
        return []

    async def fetchrow(self, query: str, *args: Any) -> None:
        return None

    async def acquire(self) -> Any:  # pragma: no cover
        raise NotImplementedError


def test_account_block_when_user_not_in_auth_users() -> None:
    service = GdprExportService(_NotFoundAuthPool())
    user_id = uuid4()

    bundle = asyncio.run(service.export(user_id))

    assert bundle["account"] == {
        "id": str(user_id),
        "email": None,
        "created_at": None,
        "last_sign_in_at": None,
    }


class _FakeRow(dict):  # type: ignore[type-arg]
    """asyncpg.Record-aehnliche Mapping-Schnittstelle (dict-Conversion reicht)."""


class _PresentAuthPool:
    """Fake-Pool: `auth.users` liefert eine Zeile mit Email + Timestamps."""

    def __init__(self, email: str, created_at: datetime) -> None:
        self._email = email
        self._created_at = created_at

    async def fetch(self, query: str, *args: Any) -> list[Any]:
        return []

    async def fetchrow(self, query: str, *args: Any) -> _FakeRow:
        return _FakeRow(
            email=self._email,
            created_at=self._created_at,
            last_sign_in_at=None,
        )

    async def acquire(self) -> Any:  # pragma: no cover
        raise NotImplementedError


def test_account_block_populated_from_auth_users() -> None:
    created = datetime.now(UTC)
    pool = _PresentAuthPool("hello@example.com", created)
    service = GdprExportService(pool)
    user_id = uuid4()

    bundle = asyncio.run(service.export(user_id))

    assert bundle["account"]["email"] == "hello@example.com"
    assert bundle["account"]["created_at"] == created
    assert bundle["account"]["last_sign_in_at"] is None
