"""REST-Endpunkte fuer Personae (`/v1/workspaces/{workspace_id}/personas`)."""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Request, Response, status

from who2be_api.core.db import get_pool
from who2be_api.core.pagination import DEFAULT_LIMIT, PageCursor, PageLimit
from who2be_api.core.rate_limit import limiter, write_limit
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.repositories.persona_repository import PgPersonaRepository
from who2be_api.services.persona_service import PersonaService
from who2be_models import (
    PersonaCreate,
    PersonaRead,
    PersonaUpdate,
    PersonaVersionRead,
)

router = APIRouter(prefix="/personas", tags=["personas"])


def get_persona_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> PersonaService:
    """FastAPI-Dependency: verdrahtet den Service mit der Pg-Implementierung."""
    return PersonaService(PgPersonaRepository(pool))


Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]
Service = Annotated[PersonaService, Depends(get_persona_service)]


@router.get("")
async def list_personas(
    ctx: Ctx,
    service: Service,
    response: Response,
    cursor: PageCursor,
    limit: PageLimit = DEFAULT_LIMIT,
) -> list[PersonaRead]:
    items, next_cursor = await service.list_all(ctx, limit, cursor)
    if next_cursor is not None:
        response.headers["X-Next-Cursor"] = next_cursor
    return items


@router.post("", status_code=status.HTTP_201_CREATED)
@limiter.limit(write_limit)
async def create_persona(
    request: Request, data: PersonaCreate, ctx: Ctx, service: Service
) -> PersonaRead:
    return await service.create(ctx, data)


@router.get("/{persona_id}")
async def get_persona(persona_id: UUID, ctx: Ctx, service: Service) -> PersonaRead:
    return await service.get(ctx, persona_id)


@router.put("/{persona_id}")
@limiter.limit(write_limit)
async def update_persona(
    request: Request,
    persona_id: UUID,
    data: PersonaUpdate,
    ctx: Ctx,
    service: Service,
) -> PersonaRead:
    return await service.update(ctx, persona_id, data)


@router.get("/{persona_id}/versions")
async def list_persona_versions(
    persona_id: UUID, ctx: Ctx, service: Service
) -> list[PersonaVersionRead]:
    return await service.list_versions(ctx, persona_id)


@router.get("/{persona_id}/versions/{version}")
async def get_persona_version(
    persona_id: UUID, version: int, ctx: Ctx, service: Service
) -> PersonaVersionRead:
    return await service.get_version(ctx, persona_id, version)
