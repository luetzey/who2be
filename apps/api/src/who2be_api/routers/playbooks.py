"""REST-Endpunkte fuer Playbooks (`/v1/workspaces/{workspace_id}/playbooks`)."""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query, Request, Response, status

from who2be_api.core.db import get_pool
from who2be_api.core.pagination import DEFAULT_LIMIT, PageCursor, PageLimit
from who2be_api.core.rate_limit import limiter, write_limit
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.repositories.playbook_repository import PgPlaybookRepository
from who2be_api.services.playbook_service import PlaybookService
from who2be_models import (
    PlaybookCreate,
    PlaybookRead,
    PlaybookUpdate,
    PlaybookVersionRead,
)

router = APIRouter(prefix="/playbooks", tags=["playbooks"])


def get_playbook_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> PlaybookService:
    """FastAPI-Dependency: verdrahtet den Service mit der Pg-Implementierung."""
    return PlaybookService(PgPlaybookRepository(pool))


Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]
Service = Annotated[PlaybookService, Depends(get_playbook_service)]


@router.get("")
async def list_playbooks(
    ctx: Ctx,
    service: Service,
    response: Response,
    cursor: PageCursor,
    tag: Annotated[str | None, Query(max_length=100)] = None,
    trigger: Annotated[str | None, Query(max_length=200)] = None,
    limit: PageLimit = DEFAULT_LIMIT,
) -> list[PlaybookRead]:
    items, next_cursor = await service.list_all(ctx, tag, trigger, limit, cursor)
    if next_cursor is not None:
        response.headers["X-Next-Cursor"] = next_cursor
    return items


@router.post("", status_code=status.HTTP_201_CREATED)
@limiter.limit(write_limit)
async def create_playbook(
    request: Request, data: PlaybookCreate, ctx: Ctx, service: Service
) -> PlaybookRead:
    return await service.create(ctx, data)


@router.get("/{playbook_id}")
async def get_playbook(playbook_id: UUID, ctx: Ctx, service: Service) -> PlaybookRead:
    return await service.get(ctx, playbook_id)


@router.put("/{playbook_id}")
@limiter.limit(write_limit)
async def update_playbook(
    request: Request,
    playbook_id: UUID,
    data: PlaybookUpdate,
    ctx: Ctx,
    service: Service,
) -> PlaybookRead:
    return await service.update(ctx, playbook_id, data)


@router.get("/{playbook_id}/versions")
async def list_playbook_versions(
    playbook_id: UUID, ctx: Ctx, service: Service
) -> list[PlaybookVersionRead]:
    return await service.list_versions(ctx, playbook_id)


@router.get("/{playbook_id}/versions/{version}")
async def get_playbook_version(
    playbook_id: UUID, version: int, ctx: Ctx, service: Service
) -> PlaybookVersionRead:
    return await service.get_version(ctx, playbook_id, version)
