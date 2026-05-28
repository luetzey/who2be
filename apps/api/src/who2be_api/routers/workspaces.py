"""REST-Endpunkte fuer Workspaces (`/v1/workspaces/{workspace_id}`, TASK-301).

Anlage haengt am Pfad `/v1/organizations/{org_id}/workspaces` (siehe
`organizations.py`), weil sie zur Org-Mitgliedschaft gehoert. Hier nur
Read/Update fuer existierende Workspaces — Membership erzwingt
`get_current_workspace`.
"""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends

from who2be_api.core.db import get_pool
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.repositories.organization_repository import PgOrganizationRepository
from who2be_api.repositories.workspace_repository import PgWorkspaceRepository
from who2be_api.services.workspace_service import WorkspaceService
from who2be_models import WorkspaceRead, WorkspaceUpdate

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
async def update_workspace(
    workspace_id: UUID, data: WorkspaceUpdate, ctx: Ctx, service: Service
) -> WorkspaceRead:
    _ = ctx
    return await service.update(workspace_id, data)
