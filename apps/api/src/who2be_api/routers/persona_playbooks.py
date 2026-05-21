"""REST-Endpunkte fuer die Persona-Playbook-Verknuepfung.

Eigene Router-Datei (Prefix `/v1/personas`), damit `routers/personas.py` auf
das Persona-CRUD fokussiert bleibt.
"""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends

from who2be_api.core.db import get_pool
from who2be_api.core.security import get_current_user
from who2be_api.repositories.persona_playbook_repository import (
    PgPersonaPlaybookRepository,
)
from who2be_api.services.persona_playbook_service import PersonaPlaybookService
from who2be_models import PersonaPlaybookLinkSet, PlaybookRead

router = APIRouter(prefix="/v1/personas", tags=["persona-playbooks"])


def get_link_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> PersonaPlaybookService:
    """FastAPI-Dependency: verdrahtet den Service mit der Pg-Implementierung."""
    return PersonaPlaybookService(PgPersonaPlaybookRepository(pool))


OwnerId = Annotated[UUID, Depends(get_current_user)]
Service = Annotated[PersonaPlaybookService, Depends(get_link_service)]


@router.get("/{persona_id}/playbooks")
async def list_persona_playbooks(
    persona_id: UUID, owner_id: OwnerId, service: Service
) -> list[PlaybookRead]:
    return await service.list_links(owner_id, persona_id)


@router.put("/{persona_id}/playbooks")
async def set_persona_playbooks(
    persona_id: UUID,
    data: PersonaPlaybookLinkSet,
    owner_id: OwnerId,
    service: Service,
) -> list[PlaybookRead]:
    return await service.set_links(owner_id, persona_id, data)
