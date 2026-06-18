"""REST-Endpunkte fuer die Playbook-Composition-Relation (GAP 2.1, ADR-0024).

Eigene Router-Datei (Prefix `/playbooks`, mounted unter
`/v1/workspaces/{workspace_id}`), damit `routers/playbooks.py` auf das
Playbook-CRUD fokussiert bleibt.
"""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Request

from who2be_api.core.db import get_pool
from who2be_api.core.rate_limit import limiter, write_limit
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.repositories.playbook_composition_repository import (
    PgPlaybookCompositionRepository,
)
from who2be_api.services.playbook_composition_service import PlaybookCompositionService
from who2be_models import PlaybookCompositionLinkSet, PlaybookRead, PlaybookRef

router = APIRouter(prefix="/playbooks", tags=["playbook-composition"])


def get_composition_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> PlaybookCompositionService:
    """FastAPI-Dependency: verdrahtet den Service mit der Pg-Implementierung."""
    return PlaybookCompositionService(PgPlaybookCompositionRepository(pool), pool)


Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]
Service = Annotated[PlaybookCompositionService, Depends(get_composition_service)]


@router.get("/{playbook_id}/composes")
async def list_playbook_composes(
    playbook_id: UUID, ctx: Ctx, service: Service
) -> list[PlaybookRead]:
    """Gibt die geordneten Sub-Playbooks des Composite zurueck."""
    return await service.list_children(ctx, playbook_id)


@router.put("/{playbook_id}/composes")
@limiter.limit(write_limit)
async def set_playbook_composes(
    request: Request,
    playbook_id: UUID,
    data: PlaybookCompositionLinkSet,
    ctx: Ctx,
    service: Service,
) -> list[PlaybookRead]:
    """Ersetzt die Sub-Playbook-Liste vollstaendig (Set-Replace).

    Reihenfolge der `child_ids` bestimmt `position`. Leere Liste loest alle
    Kinder-Verknuepfungen. Erfordert Rolle `editor` oder hoeher.
    """
    return await service.set_composition(ctx, playbook_id, data)


@router.get("/{playbook_id}/composed_by")
async def list_playbook_composed_by(
    playbook_id: UUID, ctx: Ctx, service: Service
) -> list[PlaybookRef]:
    """Gibt die Parent-Playbooks zurueck, die dieses Playbook als Kind enthalten."""
    return await service.list_parents(ctx, playbook_id)
