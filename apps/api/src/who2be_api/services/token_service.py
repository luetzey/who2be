"""Geschaeftslogik fuer das API-Token-Aggregat.

Token sind pro Workspace gepinnt (Plan §2.1.D). Listen/Revoke filtern auf
`workspace_id`; bei der Anlage wird der Workspace aus dem `WorkspaceContext`
in den Token-Row geschrieben.
"""

from datetime import datetime
from uuid import UUID

import asyncpg
from fastapi import HTTPException, status

from who2be_api.core.security import (
    WorkspaceContext,
    hash_token,
    new_token,
    require_role,
    role_satisfies,
)
from who2be_api.repositories.token_repository import TokenRepository
from who2be_api.services.audit_service import AuditService
from who2be_models import TokenCreate, TokenCreated, TokenRead, WorkspaceRole, encode_cursor


class TokenService:
    """Erzeugt, listet und widerruft API-Token eines Workspaces."""

    def __init__(
        self,
        token_repo: TokenRepository,
        audit_service: AuditService | None = None,
        pool: asyncpg.Pool | None = None,
    ) -> None:
        # `pool` ist der Audit-Executor (best-effort, separater Tx-Pfad — die
        # Token-Mutationen selbst sind einzelne Pool-Statements). `audit_service`
        # ist optional, damit aeltere Tests/Fakes ohne Audit-Wiring weiterlaufen.
        self._repo = token_repo
        self._audit = audit_service
        self._pool = pool

    @staticmethod
    def _deny_agent_bound(ctx: WorkspaceContext) -> None:
        """Agent-gebundene Tokens duerfen keine Tokens verwalten.

        Sonst koennte ein eingeschraenkter Agent einen ungebundenen Token mit
        voller Rolle minten und so seine Pro-Agent-Policy komplett umgehen
        (Privilege-Escalation). Token-Verwaltung bleibt menschlichen Sessions
        und nicht-gebundenen Tokens vorbehalten.
        """
        if ctx.tool_policy is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Agent-gebundene Tokens duerfen keine API-Tokens verwalten.",
            )

    async def _assert_agent_in_workspace(self, workspace_id: UUID, agent_id: UUID) -> None:
        """404, wenn der zu bindende Agent nicht in diesem Workspace existiert."""
        if self._pool is None:
            # Ohne Pool (aeltere Test-Fakes) keine DB-Pruefung moeglich; der FK
            # auf `agent.id` faengt zumindest nicht-existente Agenten beim INSERT.
            return
        exists = await self._pool.fetchval(
            "SELECT 1 FROM agent WHERE id = $1 AND workspace_id = $2",
            agent_id,
            workspace_id,
        )
        if exists is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Der zu bindende Agent existiert nicht in diesem Workspace.",
            )

    async def create(self, ctx: WorkspaceContext, data: TokenCreate) -> TokenCreated:
        """Legt einen Token an; der Klartext wird genau einmal zurueckgegeben.

        Token-CRUD verlangt mindestens `editor` (ADR-0023). Die Token-Rolle ist
        ein Snapshot: ohne explizite Angabe erbt der Token die aktuelle Rolle
        des Erstellers; eine explizit hoehere Rolle als die des Erstellers ist
        verboten (ein editor kann kein admin-Token erzeugen).
        """
        require_role(ctx, WorkspaceRole.editor)
        self._deny_agent_bound(ctx)
        role = data.role if data.role is not None else ctx.role
        if not role_satisfies(ctx.role, role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Ein Token darf keine hoehere Rolle als sein Ersteller haben.",
            )
        # Pflicht-Agent-Bindung: der Agent muss im selben Workspace leben. Der
        # Single-Column-FK auf `agent.id` garantiert nur Existenz, nicht die
        # Workspace-Zugehoerigkeit — die pruefen wir hier vor dem INSERT.
        await self._assert_agent_in_workspace(ctx.workspace_id, data.agent_id)
        plaintext = new_token()
        stored = await self._repo.insert(
            ctx.workspace_id,
            ctx.user_id,
            data.name,
            hash_token(plaintext),
            role,
            agent_id=data.agent_id,
            expires_at=data.expires_at,
        )
        if self._audit is not None and self._pool is not None:
            await self._audit.record(
                self._pool,
                action="token.issued",
                actor_id=ctx.user_id,
                workspace_id=ctx.workspace_id,
                target=stored.id,
                detail={
                    "name": data.name,
                    "role": role.value,
                    "agent_id": str(data.agent_id),
                },
            )
        return TokenCreated(**stored.model_dump(), token=plaintext)

    async def list_all(
        self,
        ctx: WorkspaceContext,
        limit: int,
        cursor: tuple[datetime, UUID] | None,
    ) -> tuple[list[TokenRead], str | None]:
        require_role(ctx, WorkspaceRole.editor)
        self._deny_agent_bound(ctx)
        rows = await self._repo.list_by_workspace(ctx.workspace_id, limit + 1, cursor)
        if len(rows) > limit:
            items = rows[:limit]
            tail = items[-1]
            return items, encode_cursor(tail.created_at, tail.id)
        return rows, None

    async def list_by_agent(
        self,
        ctx: WorkspaceContext,
        agent_id: UUID,
        limit: int,
        cursor: tuple[datetime, UUID] | None,
    ) -> tuple[list[TokenRead], str | None]:
        """Listet die Tokens eines bestimmten Agenten (Agent-Konfig-Sektion)."""
        require_role(ctx, WorkspaceRole.editor)
        self._deny_agent_bound(ctx)
        await self._assert_agent_in_workspace(ctx.workspace_id, agent_id)
        rows = await self._repo.list_by_agent(ctx.workspace_id, agent_id, limit + 1, cursor)
        if len(rows) > limit:
            items = rows[:limit]
            tail = items[-1]
            return items, encode_cursor(tail.created_at, tail.id)
        return rows, None

    async def rename(self, ctx: WorkspaceContext, token_id: UUID, name: str) -> TokenRead:
        """Benennt einen Token um; 404, wenn er nicht (mehr) existiert.

        Nur der Name ist editierbar — Secret/Rolle/Agent-Bindung bleiben (ADR-0023).
        """
        require_role(ctx, WorkspaceRole.editor)
        self._deny_agent_bound(ctx)
        renamed = await self._repo.rename(ctx.workspace_id, token_id, name)
        if renamed is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Token nicht gefunden.",
            )
        if self._audit is not None and self._pool is not None:
            await self._audit.record(
                self._pool,
                action="token.renamed",
                actor_id=ctx.user_id,
                workspace_id=ctx.workspace_id,
                target=token_id,
                detail={"name": name},
            )
        return renamed

    async def rotate(self, ctx: WorkspaceContext, token_id: UUID) -> TokenCreated:
        """Erzeugt ein neues Secret fuer einen bestehenden Token (in-place).

        Das alte Secret wird sofort ungueltig; Name/Rolle/Agent-Bindung bleiben.
        404, wenn der Token nicht existiert oder bereits widerrufen ist. Der neue
        Klartext wird genau einmal zurueckgegeben.
        """
        require_role(ctx, WorkspaceRole.editor)
        self._deny_agent_bound(ctx)
        plaintext = new_token()
        stored = await self._repo.rotate(ctx.workspace_id, token_id, hash_token(plaintext))
        if stored is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Token nicht gefunden.",
            )
        if self._audit is not None and self._pool is not None:
            await self._audit.record(
                self._pool,
                action="token.rotated",
                actor_id=ctx.user_id,
                workspace_id=ctx.workspace_id,
                target=token_id,
            )
        return TokenCreated(**stored.model_dump(), token=plaintext)

    async def revoke(self, ctx: WorkspaceContext, token_id: UUID) -> None:
        """Widerruft einen eigenen Token; 404, wenn er nicht (mehr) existiert."""
        require_role(ctx, WorkspaceRole.editor)
        self._deny_agent_bound(ctx)
        revoked = await self._repo.revoke(ctx.workspace_id, token_id)
        if not revoked:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Token nicht gefunden.",
            )
        if self._audit is not None and self._pool is not None:
            await self._audit.record(
                self._pool,
                action="token.revoked",
                actor_id=ctx.user_id,
                workspace_id=ctx.workspace_id,
                target=token_id,
            )
