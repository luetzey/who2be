"""REST-Endpunkt `/v1/me` — Identity + Memberships + Default-Workspace (TASK-301)."""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends

from who2be_api.core.db import get_pool
from who2be_api.core.security import get_current_user
from who2be_api.repositories.me_repository import PgMeRepository
from who2be_api.services.me_service import MeService
from who2be_models import MeRead

router = APIRouter(prefix="/v1/me", tags=["me"])


def get_me_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> MeService:
    return MeService(PgMeRepository(pool))


UserId = Annotated[UUID, Depends(get_current_user)]
Service = Annotated[MeService, Depends(get_me_service)]


@router.get("")
async def get_me(user_id: UserId, service: Service) -> MeRead:
    return await service.fetch(user_id)
