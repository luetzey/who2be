"""Geschaeftslogik fuer das API-Token-Aggregat.

Token sind pro Workspace gepinnt (Plan §2.1.D). Listen/Revoke filtern auf
`workspace_id`; bei der Anlage wird der Workspace aus dem `WorkspaceContext`
in den Token-Row geschrieben.
"""

from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status

from who2be_api.core.security import (
    WorkspaceContext,
    hash_token,
    new_token,
    require_role,
    role_satisfies,
)
from who2be_api.repositories.token_repository import TokenRepository
from who2be_models import TokenCreate, TokenCreated, TokenRead, WorkspaceRole, encode_cursor


class TokenService:
    """Erzeugt, listet und widerruft API-Token eines Workspaces."""

    def __init__(self, token_repo: TokenRepository) -> None:
        self._repo = token_repo

    async def create(self, ctx: WorkspaceContext, data: TokenCreate) -> TokenCreated:
        """Legt einen Token an; der Klartext wird genau einmal zurueckgegeben.

        Token-CRUD verlangt mindestens `editor` (ADR-0023). Die Token-Rolle ist
        ein Snapshot: ohne explizite Angabe erbt der Token die aktuelle Rolle
        des Erstellers; eine explizit hoehere Rolle als die des Erstellers ist
        verboten (ein editor kann kein admin-Token erzeugen).
        """
        require_role(ctx, WorkspaceRole.editor)
        role = data.role if data.role is not None else ctx.role
        if not role_satisfies(ctx.role, role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Ein Token darf keine hoehere Rolle als sein Ersteller haben.",
            )
        plaintext = new_token()
        stored = await self._repo.insert(
            ctx.workspace_id, ctx.user_id, data.name, hash_token(plaintext), role
        )
        return TokenCreated(**stored.model_dump(), token=plaintext)

    async def list_all(
        self,
        ctx: WorkspaceContext,
        limit: int,
        cursor: tuple[datetime, UUID] | None,
    ) -> tuple[list[TokenRead], str | None]:
        require_role(ctx, WorkspaceRole.editor)
        rows = await self._repo.list_by_workspace(ctx.workspace_id, limit + 1, cursor)
        if len(rows) > limit:
            items = rows[:limit]
            tail = items[-1]
            return items, encode_cursor(tail.created_at, tail.id)
        return rows, None

    async def revoke(self, ctx: WorkspaceContext, token_id: UUID) -> None:
        """Widerruft einen eigenen Token; 404, wenn er nicht (mehr) existiert."""
        require_role(ctx, WorkspaceRole.editor)
        revoked = await self._repo.revoke(ctx.workspace_id, token_id)
        if not revoked:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Token nicht gefunden.",
            )
