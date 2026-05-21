"""Persistenz fuer das API-Token-Aggregat (`api_token`).

Verantwortung: SQL + Row↔Model-Mapping, keine Geschaeftsregeln. SQL-Werte
ausschliesslich ueber asyncpg-Parameter-Binding (§6).
"""

from typing import Protocol
from uuid import UUID

import asyncpg

from who2be_models import TokenRead


class TokenRepository(Protocol):
    """Service-seitige Abstraktion fuer den Token-Zugriff."""

    async def insert(self, owner_id: UUID, name: str, token_hash: str) -> TokenRead: ...

    async def list_by_owner(self, owner_id: UUID) -> list[TokenRead]: ...

    async def fetch_owner_by_hash(self, token_hash: str) -> UUID | None: ...

    async def revoke(self, owner_id: UUID, token_id: UUID) -> bool: ...

    async def touch_last_used(self, token_hash: str) -> None: ...


class PgTokenRepository:
    """asyncpg-Implementierung von `TokenRepository`."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def insert(self, owner_id: UUID, name: str, token_hash: str) -> TokenRead:
        row = await self._pool.fetchrow(
            "INSERT INTO api_token (owner_id, name, token_hash) "
            "VALUES ($1, $2, $3) "
            "RETURNING id, name, created_at, last_used_at, revoked_at",
            owner_id,
            name,
            token_hash,
        )
        return TokenRead.model_validate(dict(row))

    async def list_by_owner(self, owner_id: UUID) -> list[TokenRead]:
        rows = await self._pool.fetch(
            "SELECT id, name, created_at, last_used_at, revoked_at "
            "FROM api_token WHERE owner_id = $1 ORDER BY created_at DESC",
            owner_id,
        )
        return [TokenRead.model_validate(dict(row)) for row in rows]

    async def fetch_owner_by_hash(self, token_hash: str) -> UUID | None:
        row = await self._pool.fetchrow(
            "SELECT owner_id FROM api_token "
            "WHERE token_hash = $1 AND revoked_at IS NULL",
            token_hash,
        )
        owner_id: UUID | None = row["owner_id"] if row is not None else None
        return owner_id

    async def revoke(self, owner_id: UUID, token_id: UUID) -> bool:
        result = await self._pool.execute(
            "UPDATE api_token SET revoked_at = now() "
            "WHERE id = $1 AND owner_id = $2 AND revoked_at IS NULL",
            token_id,
            owner_id,
        )
        return bool(result == "UPDATE 1")

    async def touch_last_used(self, token_hash: str) -> None:
        await self._pool.execute(
            "UPDATE api_token SET last_used_at = now() "
            "WHERE token_hash = $1 AND revoked_at IS NULL",
            token_hash,
        )
