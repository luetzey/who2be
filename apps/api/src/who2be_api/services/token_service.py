"""Geschaeftslogik fuer das API-Token-Aggregat."""

from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status

from who2be_api.core.security import hash_token, new_token
from who2be_api.repositories.token_repository import TokenRepository
from who2be_models import TokenCreate, TokenCreated, TokenRead, encode_cursor


class TokenService:
    """Erzeugt, listet und widerruft API-Token eines Owners."""

    def __init__(self, token_repo: TokenRepository) -> None:
        self._repo = token_repo

    async def create(self, owner_id: UUID, data: TokenCreate) -> TokenCreated:
        """Legt einen Token an; der Klartext wird genau einmal zurueckgegeben."""
        plaintext = new_token()
        stored = await self._repo.insert(owner_id, data.name, hash_token(plaintext))
        return TokenCreated(**stored.model_dump(), token=plaintext)

    async def list_all(
        self,
        owner_id: UUID,
        limit: int,
        cursor: tuple[datetime, UUID] | None,
    ) -> tuple[list[TokenRead], str | None]:
        rows = await self._repo.list_by_owner(owner_id, limit + 1, cursor)
        if len(rows) > limit:
            items = rows[:limit]
            tail = items[-1]
            return items, encode_cursor(tail.created_at, tail.id)
        return rows, None

    async def revoke(self, owner_id: UUID, token_id: UUID) -> None:
        """Widerruft einen eigenen Token; 404, wenn er nicht (mehr) existiert."""
        revoked = await self._repo.revoke(owner_id, token_id)
        if not revoked:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Token nicht gefunden.",
            )
