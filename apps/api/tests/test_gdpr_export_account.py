"""Unit-Tests fuer den account/identity-Block im GDPR-Export (WP-E).

Ohne DB: ein Fake-Pool gibt definierte Antworten. Belegt, dass der Block
sauber zu `null` degradiert, wenn `w2b_self_account()` nicht aufrufbar ist
(PostgresError, z. B. Test-DB ohne GoTrue) — analog
`me_repository._lookup_profile` — und dass der Lookup an den Aufrufer selbst
gebunden ist (`app.current_user_id` transaktionslokal, Migration 0091).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import asyncpg

from who2be_api.core.tenancy import USER_SETTING
from who2be_api.services.gdpr_export_service import GdprExportService


class _FakeRow(dict):  # type: ignore[type-arg]
    """asyncpg.Record-aehnliche Mapping-Schnittstelle (dict-Conversion reicht)."""


class _FakeConn:
    """Connection-Fake: protokolliert GUC-Setzungen und beantwortet den
    Konto-Lookup mit `row` bzw. einer PostgresError."""

    def __init__(self, row: _FakeRow | None, error: bool) -> None:
        self._row = row
        self._error = error
        self.settings: list[tuple[Any, ...]] = []
        self.in_transaction = False

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        self.in_transaction = True
        try:
            yield
        finally:
            self.in_transaction = False

    async def execute(self, query: str, *args: Any) -> str:
        assert self.in_transaction, "GUC nur transaktionslokal setzen"
        self.settings.append(args)
        return "SELECT 1"

    async def fetchrow(self, query: str, *args: Any) -> _FakeRow | None:
        assert "w2b_self_account()" in query
        assert "auth.users" not in query
        if self._error:
            raise asyncpg.PostgresError("function w2b_self_account() does not exist")
        return self._row


class _FakePool:
    def __init__(self, row: _FakeRow | None = None, error: bool = False) -> None:
        self.conn = _FakeConn(row, error)

    async def fetch(self, query: str, *args: Any) -> list[Any]:
        return []

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[_FakeConn]:
        yield self.conn


_EMPTY = {"email": None, "created_at": None, "last_sign_in_at": None}


def test_account_block_degrades_when_self_account_missing() -> None:
    pool = _FakePool(error=True)
    user_id = uuid4()

    bundle = asyncio.run(GdprExportService(pool).export(user_id))

    assert bundle["user_id"] == str(user_id)
    assert bundle["organizations"] == []
    assert bundle["account"] == {"id": str(user_id), **_EMPTY}


def test_account_block_when_user_not_found() -> None:
    pool = _FakePool(row=None)
    user_id = uuid4()

    bundle = asyncio.run(GdprExportService(pool).export(user_id))

    assert bundle["account"] == {"id": str(user_id), **_EMPTY}


def test_account_block_populated_and_scoped_to_self() -> None:
    created = datetime.now(UTC)
    pool = _FakePool(
        row=_FakeRow(email="hello@example.com", created_at=created, last_sign_in_at=None)
    )
    user_id = uuid4()

    bundle = asyncio.run(GdprExportService(pool).export(user_id))

    assert bundle["account"]["email"] == "hello@example.com"
    assert bundle["account"]["created_at"] == created
    assert bundle["account"]["last_sign_in_at"] is None
    # Der Lookup ist an genau diesen User gebunden.
    assert pool.conn.settings == [(USER_SETTING, str(user_id))]
