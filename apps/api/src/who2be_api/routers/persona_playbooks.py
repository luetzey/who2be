"""REST-Endpunkte fuer die Persona-Playbook-Verknuepfung.

Eigene Router-Datei (Prefix `/personas`, mounted unter
`/v1/workspaces/{workspace_id}`), damit `routers/personas.py` auf das
Persona-CRUD fokussiert bleibt.
"""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends

from who2be_api.core.db import get_pool
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.repositories.persona_playbook_repository import (
    PgPersonaPlaybookRepository,
)
from who2be_api.services.persona_playbook_service import PersonaPlaybookService
from who2be_models import PersonaPlaybookLinkSet, PlaybookRead

router = APIRouter(prefix="/personas", tags=["persona-playbooks"])


def get_link_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> PersonaPlaybookService:
    """FastAPI-Dependency: verdrahtet den Service mit der Pg-Implementierung."""
    return PersonaPlaybookService(PgPersonaPlaybookRepository(pool))


Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]
Service = Annotated[PersonaPlaybookService, Depends(get_link_service)]


@router.get("/{persona_id}/playbooks")
async def list_persona_playbooks(
    persona_id: UUID, ctx: Ctx, service: Service
) -> list[PlaybookRead]:
    return await service.list_links(ctx, persona_id)


@router.put("/{persona_id}/playbooks")
async def set_persona_playbooks(
    persona_id: UUID,
    data: PersonaPlaybookLinkSet,
    ctx: Ctx,
    service: Service,
) -> list[PlaybookRead]:
    return await service.set_links(ctx, persona_id, data)
