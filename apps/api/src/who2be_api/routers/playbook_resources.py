"""REST-Endpunkte fuer Playbook->Resource-Block-Refs.

Eigene Router-Datei (Prefix `/playbooks`, mounted unter
`/v1/workspaces/{workspace_id}`), damit `routers/playbooks.py` auf das
Playbook-CRUD fokussiert bleibt — analog `persona_playbooks.py`.
"""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Request

from who2be_api.core.db import get_pool
from who2be_api.core.rate_limit import limiter, write_limit
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.repositories.playbook_resource_link_repository import (
    PgPlaybookResourceLinkRepository,
)
from who2be_api.services.playbook_resource_link_service import (
    PlaybookResourceLinkService,
)
from who2be_models import ResourceLinkRead, ResourceLinkSet

router = APIRouter(prefix="/playbooks", tags=["playbook-resources"])


def get_link_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> PlaybookResourceLinkService:
    """FastAPI-Dependency: verdrahtet den Service mit der Pg-Implementierung."""
    return PlaybookResourceLinkService(PgPlaybookResourceLinkRepository(pool), pool)


Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]
Service = Annotated[PlaybookResourceLinkService, Depends(get_link_service)]


@router.get("/{playbook_id}/resource_links")
async def list_playbook_resource_links(
    playbook_id: UUID, ctx: Ctx, service: Service
) -> list[ResourceLinkRead]:
    return await service.list_links(ctx, playbook_id)


@router.put("/{playbook_id}/resource_links")
@limiter.limit(write_limit)
async def set_playbook_resource_links(
    request: Request,
    playbook_id: UUID,
    data: ResourceLinkSet,
    ctx: Ctx,
    service: Service,
) -> list[ResourceLinkRead]:
    return await service.set_links(ctx, playbook_id, data)
