"""REST-Endpunkte fuer die Sub-Resource-Relation (Track E, §3.3).

Eigene Router-Datei (Prefix `/resources`, mounted unter
`/v1/workspaces/{workspace_id}`), damit `routers/resources.py` auf das
Resource-CRUD fokussiert bleibt — analog `playbook_composition.py`.
"""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Request

from who2be_api.core.db import get_pool
from who2be_api.core.rate_limit import limiter, write_limit
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.repositories.resource_composition_repository import (
    PgResourceCompositionRepository,
)
from who2be_api.services.resource_composition_service import ResourceCompositionService
from who2be_models import ResourceRef, SubResourceLinkSet, SubResourceRead

router = APIRouter(prefix="/resources", tags=["resource-composition"])


def get_resource_composition_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> ResourceCompositionService:
    """FastAPI-Dependency: verdrahtet den Service mit der Pg-Implementierung."""
    return ResourceCompositionService(PgResourceCompositionRepository(pool))


Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]
Service = Annotated[ResourceCompositionService, Depends(get_resource_composition_service)]


@router.get("/{resource_id}/sub_resources")
async def list_resource_sub_resources(
    resource_id: UUID, ctx: Ctx, service: Service
) -> list[SubResourceRead]:
    """Gibt die geordneten direkten Sub-Resources zurueck (keine Expansion)."""
    return await service.list_children(ctx, resource_id)


@router.put("/{resource_id}/sub_resources")
@limiter.limit(write_limit)
async def set_resource_sub_resources(
    request: Request,
    resource_id: UUID,
    data: SubResourceLinkSet,
    ctx: Ctx,
    service: Service,
) -> list[SubResourceRead]:
    """Ersetzt die Sub-Resource-Liste vollstaendig (Set-Replace).

    Reihenfolge der `links` bestimmt `position`. Leere Liste loest alle
    Sub-Resource-Verknuepfungen. Erfordert Rolle `editor` oder hoeher.
    """
    return await service.set_links(ctx, resource_id, data)


@router.get("/{resource_id}/used_by")
async def list_resource_used_by(
    resource_id: UUID, ctx: Ctx, service: Service
) -> list[ResourceRef]:
    """Gibt die Parent-Resources zurueck, die diese Resource als Sub-Resource fuehren."""
    return await service.list_parents(ctx, resource_id)
