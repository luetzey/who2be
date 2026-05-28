"""Geschaeftslogik fuer das API-Token-Aggregat.

Token sind pro Workspace gepinnt (Plan §2.1.D). Listen/Revoke filtern auf
`workspace_id`; bei der Anlage wird der Workspace aus dem `WorkspaceContext`
in den Token-Row geschrieben.
"""

from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status

from who2be_api.core.security import WorkspaceContext, hash_token, new_token
from who2be_api.repositories.token_repository import TokenRepository
from who2be_models import TokenCreate, TokenCreated, TokenRead, encode_cursor


class TokenService:
    """Erzeugt, listet und widerruft API-Token eines Workspaces."""

    def __init__(self, token_repo: TokenRepository) -> None:
        self._repo = token_repo

    async def create(self, ctx: WorkspaceContext, data: TokenCreate) -> TokenCreated:
        """Legt einen Token an; der Klartext wird genau einmal zurueckgegeben."""
        plaintext = new_token()
        stored = await self._repo.insert(
            ctx.workspace_id, ctx.user_id, data.name, hash_token(plaintext)
        )
        return TokenCreated(**stored.model_dump(), token=plaintext)

    async def list_all(
        self,
        ctx: WorkspaceContext,
        limit: int,
        cursor: tuple[datetime, UUID] | None,
    ) -> tuple[list[TokenRead], str | None]:
        rows = await self._repo.list_by_workspace(ctx.workspace_id, limit + 1, cursor)
        if len(rows) > limit:
            items = rows[:limit]
            tail = items[-1]
            return items, encode_cursor(tail.created_at, tail.id)
        return rows, None

    async def revoke(self, ctx: WorkspaceContext, token_id: UUID) -> None:
        """Widerruft einen eigenen Token; 404, wenn er nicht (mehr) existiert."""
        revoked = await self._repo.revoke(ctx.workspace_id, token_id)
        if not revoked:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Token nicht gefunden.",
            )
