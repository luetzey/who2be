"""REST-Endpunkte fuer Resources (`/v1/workspaces/{workspace_id}/resources`)."""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Request, Response, status

from who2be_api.core.db import get_pool
from who2be_api.core.pagination import DEFAULT_LIMIT, PageCursor, PageLimit
from who2be_api.core.rate_limit import limiter, write_limit
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.repositories.resource_repository import PgResourceRepository
from who2be_api.repositories.status_history_repository import PgStatusHistoryRepository
from who2be_api.services.resource_service import ResourceService
from who2be_api.services.status_history_service import StatusHistoryService
from who2be_api.services.version_status import VersionStatusService
from who2be_models import (
    ResourceCreate,
    ResourceRead,
    ResourceUpdate,
    ResourceVersionRead,
    VersionTransitionRequest,
)

router = APIRouter(prefix="/resources", tags=["resources"])


def get_resource_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> ResourceService:
    """FastAPI-Dependency: verdrahtet den Service mit der Pg-Implementierung."""
    return ResourceService(PgResourceRepository(pool))


def get_version_status_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> VersionStatusService:
    return VersionStatusService(pool, StatusHistoryService(PgStatusHistoryRepository()))


Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]
Service = Annotated[ResourceService, Depends(get_resource_service)]
StatusService = Annotated[VersionStatusService, Depends(get_version_status_service)]


@router.get("")
async def list_resources(
    ctx: Ctx,
    service: Service,
    response: Response,
    cursor: PageCursor,
    limit: PageLimit = DEFAULT_LIMIT,
) -> list[ResourceRead]:
    items, next_cursor = await service.list_all(ctx, limit, cursor)
    if next_cursor is not None:
        response.headers["X-Next-Cursor"] = next_cursor
    return items


@router.post("", status_code=status.HTTP_201_CREATED)
@limiter.limit(write_limit)
async def create_resource(
    request: Request, data: ResourceCreate, ctx: Ctx, service: Service
) -> ResourceRead:
    return await service.create(ctx, data)


@router.get("/{resource_id}")
async def get_resource(resource_id: UUID, ctx: Ctx, service: Service) -> ResourceRead:
    return await service.get(ctx, resource_id)


@router.put("/{resource_id}")
@limiter.limit(write_limit)
async def update_resource(
    request: Request,
    resource_id: UUID,
    data: ResourceUpdate,
    ctx: Ctx,
    service: Service,
) -> ResourceRead:
    return await service.update(ctx, resource_id, data)


@router.patch("/{resource_id}/draft")
@limiter.limit(write_limit)
async def update_resource_draft(
    request: Request,
    resource_id: UUID,
    data: ResourceUpdate,
    ctx: Ctx,
    service: Service,
) -> ResourceRead:
    """Auto-Save-Pfad — upsertet die Draft-Version ohne Versions-Increment."""
    return await service.update_draft(ctx, resource_id, data)


@router.get("/{resource_id}/versions")
async def list_resource_versions(
    resource_id: UUID, ctx: Ctx, service: Service
) -> list[ResourceVersionRead]:
    return await service.list_versions(ctx, resource_id)


@router.get("/{resource_id}/versions/{version}")
async def get_resource_version(
    resource_id: UUID, version: int, ctx: Ctx, service: Service
) -> ResourceVersionRead:
    return await service.get_version(ctx, resource_id, version)


@router.post("/{resource_id}/versions/{version}/transition")
@limiter.limit(write_limit)
async def transition_resource_version(
    request: Request,
    resource_id: UUID,
    version: int,
    data: VersionTransitionRequest,
    ctx: Ctx,
    status_service: StatusService,
) -> ResourceVersionRead:
    return await status_service.transition_resource_version(
        ctx, resource_id, version, data.to, data.note
    )
