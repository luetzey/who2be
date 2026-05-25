"""REST-Endpunkte fuer Playbooks (`/v1/playbooks`)."""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Request, status

from who2be_api.core.db import get_pool
from who2be_api.core.rate_limit import limiter, write_limit
from who2be_api.core.security import get_current_user
from who2be_api.repositories.playbook_repository import PgPlaybookRepository
from who2be_api.services.playbook_service import PlaybookService
from who2be_models import (
    PlaybookCreate,
    PlaybookRead,
    PlaybookUpdate,
    PlaybookVersionRead,
)

router = APIRouter(prefix="/v1/playbooks", tags=["playbooks"])


def get_playbook_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> PlaybookService:
    """FastAPI-Dependency: verdrahtet den Service mit der Pg-Implementierung."""
    return PlaybookService(PgPlaybookRepository(pool))


OwnerId = Annotated[UUID, Depends(get_current_user)]
Service = Annotated[PlaybookService, Depends(get_playbook_service)]


@router.get("")
async def list_playbooks(
    owner_id: OwnerId,
    service: Service,
    tag: str | None = None,
    trigger: str | None = None,
) -> list[PlaybookRead]:
    return await service.list_all(owner_id, tag, trigger)


@router.post("", status_code=status.HTTP_201_CREATED)
@limiter.limit(write_limit)
async def create_playbook(
    request: Request, data: PlaybookCreate, owner_id: OwnerId, service: Service
) -> PlaybookRead:
    return await service.create(owner_id, data)


@router.get("/{playbook_id}")
async def get_playbook(playbook_id: UUID, owner_id: OwnerId, service: Service) -> PlaybookRead:
    return await service.get(owner_id, playbook_id)


@router.put("/{playbook_id}")
@limiter.limit(write_limit)
async def update_playbook(
    request: Request,
    playbook_id: UUID,
    data: PlaybookUpdate,
    owner_id: OwnerId,
    service: Service,
) -> PlaybookRead:
    return await service.update(owner_id, playbook_id, data)


@router.get("/{playbook_id}/versions")
async def list_playbook_versions(
    playbook_id: UUID, owner_id: OwnerId, service: Service
) -> list[PlaybookVersionRead]:
    return await service.list_versions(owner_id, playbook_id)


@router.get("/{playbook_id}/versions/{version}")
async def get_playbook_version(
    playbook_id: UUID, version: int, owner_id: OwnerId, service: Service
) -> PlaybookVersionRead:
    return await service.get_version(owner_id, playbook_id, version)
