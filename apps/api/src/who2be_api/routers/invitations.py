"""REST-Endpunkte fuer Workspace-Invitations.

Zwei Router:
- `router` (Workspace-scoped, admin-only): erstellen/listen/widerrufen.
  Der 201-Response traegt den Klartext-Token genau einmal — der Caller
  verschickt den Mail-Link (best-effort) bzw. teilt ihn manuell.
- `accept_router` (top-level, **anonym authentifiziert**): ein anderer User
  akzeptiert die Einladung per Klartext-Token aus der Mail und wird Mitglied.
  Single-use; akzeptiert/widerrufen/abgelaufen → 410 Gone.
"""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel

from who2be_api.core.db import get_pool
from who2be_api.core.rate_limit import limiter, write_limit
from who2be_api.core.security import (
    WorkspaceContext,
    get_current_user,
    get_current_workspace,
    require_role,
)
from who2be_api.repositories.invitation_repository import PgInvitationRepository
from who2be_api.services.invitation_service import InvitationService
from who2be_models import InvitationCreate, InvitationCreated, InvitationRead, WorkspaceRole

router = APIRouter(prefix="/invitations", tags=["invitations"])
accept_router = APIRouter(prefix="/v1/invitations", tags=["invitations"])


def get_invitation_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> InvitationService:
    return InvitationService(PgInvitationRepository(pool))


Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]
UserId = Annotated[UUID, Depends(get_current_user)]
Service = Annotated[InvitationService, Depends(get_invitation_service)]


class InvitationAcceptResult(BaseModel):
    """Antwort auf einen erfolgreichen Accept — der beigetretene Workspace."""

    workspace_id: UUID


@router.post("", status_code=status.HTTP_201_CREATED)
@limiter.limit(write_limit)
async def create_invitation(
    request: Request, data: InvitationCreate, ctx: Ctx, service: Service
) -> InvitationCreated:
    require_role(ctx, WorkspaceRole.admin)
    return await service.create(ctx, data)


@router.get("")
async def list_invitations(ctx: Ctx, service: Service) -> list[InvitationRead]:
    require_role(ctx, WorkspaceRole.admin)
    return await service.list_pending(ctx)


@router.delete("/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_invitation(invitation_id: UUID, ctx: Ctx, service: Service) -> None:
    require_role(ctx, WorkspaceRole.admin)
    await service.revoke(ctx, invitation_id)


@accept_router.post("/{token}/accept")
@limiter.limit(write_limit)
async def accept_invitation(
    request: Request, token: str, user_id: UserId, service: Service
) -> InvitationAcceptResult:
    workspace_id = await service.accept(token, user_id)
    return InvitationAcceptResult(workspace_id=workspace_id)
