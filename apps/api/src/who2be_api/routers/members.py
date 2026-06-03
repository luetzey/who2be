"""REST-Endpunkte fuer Workspace-Mitglieder (`/v1/workspaces/{ws}/members`).

Lesen ist jedem Mitglied erlaubt; Rollen-Aenderung und Entfernen sind
admin-only (`require_role`-Gate, Plan §2.3.B — durch Prompt A zur vollen
Permission-Matrix ausgebaut).
"""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Request, status

from who2be_api.core.db import get_pool
from who2be_api.core.rate_limit import limiter, write_limit
from who2be_api.core.security import WorkspaceContext, get_current_workspace, require_role
from who2be_api.repositories.workspace_member_repository import (
    PgWorkspaceMemberRepository,
)
from who2be_api.services.workspace_member_service import WorkspaceMemberService
from who2be_models import WorkspaceMemberRead, WorkspaceMemberUpdate, WorkspaceRole

router = APIRouter(prefix="/members", tags=["members"])


def get_member_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> WorkspaceMemberService:
    return WorkspaceMemberService(PgWorkspaceMemberRepository(pool))


Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]
Service = Annotated[WorkspaceMemberService, Depends(get_member_service)]


@router.get("")
async def list_members(ctx: Ctx, service: Service) -> list[WorkspaceMemberRead]:
    return await service.list_members(ctx.workspace_id)


@router.patch("/{user_id}")
@limiter.limit(write_limit)
async def update_member_role(
    request: Request, user_id: UUID, data: WorkspaceMemberUpdate, ctx: Ctx, service: Service
) -> WorkspaceMemberRead:
    require_role(ctx, WorkspaceRole.admin)
    return await service.update_role(ctx.workspace_id, user_id, data.role)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(write_limit)
async def remove_member(request: Request, user_id: UUID, ctx: Ctx, service: Service) -> None:
    require_role(ctx, WorkspaceRole.admin)
    await service.remove(ctx.workspace_id, user_id)
