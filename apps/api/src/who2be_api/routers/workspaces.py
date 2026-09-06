"""REST-Endpunkte fuer Workspaces (`/v1/workspaces/{workspace_id}`, TASK-301).

Anlage haengt am Pfad `/v1/organizations/{org_id}/workspaces` (siehe
`organizations.py`), weil sie zur Org-Mitgliedschaft gehoert. Hier nur
Read/Update fuer existierende Workspaces — Membership erzwingt
`get_current_workspace`.
"""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Request, status

from who2be_api.core.db import get_pool
from who2be_api.core.rate_limit import limiter, write_limit
from who2be_api.core.security import (
    WorkspaceContext,
    get_current_workspace,
    require_role,
)
from who2be_api.repositories.organization_repository import PgOrganizationRepository
from who2be_api.repositories.workspace_repository import PgWorkspaceRepository
from who2be_api.services.workspace_service import WorkspaceService
from who2be_models import ApiErrorBody, WorkspaceRead, WorkspaceRole, WorkspaceUpdate

router = APIRouter(prefix="/v1/workspaces", tags=["workspaces"])


def get_workspace_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> WorkspaceService:
    return WorkspaceService(PgWorkspaceRepository(pool), PgOrganizationRepository(pool))


Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]
Service = Annotated[WorkspaceService, Depends(get_workspace_service)]


@router.get("/{workspace_id}")
async def get_workspace(workspace_id: UUID, ctx: Ctx, service: Service) -> WorkspaceRead:
    # `ctx` erzwingt Membership im angefragten Workspace via Dependency.
    _ = ctx
    return await service.fetch(workspace_id)


@router.patch("/{workspace_id}")
@limiter.limit(write_limit)
async def update_workspace(
    request: Request, workspace_id: UUID, data: WorkspaceUpdate, ctx: Ctx, service: Service
) -> WorkspaceRead:
    require_role(ctx, WorkspaceRole.admin)
    return await service.update(workspace_id, data)


@router.delete(
    "/{workspace_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    # ADR-0051: der Fehler-Body ist Teil des Vertrags, also steht er im
    # Schema. Nur deklarativ — den `reason` setzt die Service-Stelle, nie
    # der Router.
    responses={409: {"model": ApiErrorBody, "description": "reason: last_workspace_undeletable"}},
)
@limiter.limit(write_limit)
async def delete_workspace(
    request: Request, workspace_id: UUID, ctx: Ctx, service: Service
) -> None:
    # Danger-Zone (Track C): nur Admins; der letzte Workspace einer Org ist
    # geschuetzt (Service → 409). `ctx` erzwingt Membership im Ziel-Workspace.
    require_role(ctx, WorkspaceRole.admin)
    await service.delete(workspace_id)
