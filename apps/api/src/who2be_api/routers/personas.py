"""REST-Endpunkte fuer Personae (`/v1/personas`)."""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, status

from who2be_api.core.db import get_pool
from who2be_api.core.security import get_current_user
from who2be_api.repositories.persona_repository import PgPersonaRepository
from who2be_api.services.persona_service import PersonaService
from who2be_models import (
    PersonaCreate,
    PersonaRead,
    PersonaUpdate,
    PersonaVersionRead,
)

router = APIRouter(prefix="/v1/personas", tags=["personas"])


def get_persona_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> PersonaService:
    """FastAPI-Dependency: verdrahtet den Service mit der Pg-Implementierung."""
    return PersonaService(PgPersonaRepository(pool))


OwnerId = Annotated[UUID, Depends(get_current_user)]
Service = Annotated[PersonaService, Depends(get_persona_service)]


@router.get("")
async def list_personas(owner_id: OwnerId, service: Service) -> list[PersonaRead]:
    return await service.list_all(owner_id)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_persona(
    data: PersonaCreate, owner_id: OwnerId, service: Service
) -> PersonaRead:
    return await service.create(owner_id, data)


@router.get("/{persona_id}")
async def get_persona(
    persona_id: UUID, owner_id: OwnerId, service: Service
) -> PersonaRead:
    return await service.get(owner_id, persona_id)


@router.put("/{persona_id}")
async def update_persona(
    persona_id: UUID, data: PersonaUpdate, owner_id: OwnerId, service: Service
) -> PersonaRead:
    return await service.update(owner_id, persona_id, data)


@router.get("/{persona_id}/versions")
async def list_persona_versions(
    persona_id: UUID, owner_id: OwnerId, service: Service
) -> list[PersonaVersionRead]:
    return await service.list_versions(owner_id, persona_id)


@router.get("/{persona_id}/versions/{version}")
async def get_persona_version(
    persona_id: UUID, version: int, owner_id: OwnerId, service: Service
) -> PersonaVersionRead:
    return await service.get_version(owner_id, persona_id, version)
