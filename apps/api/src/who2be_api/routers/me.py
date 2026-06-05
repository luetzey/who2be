"""REST-Endpunkt `/v1/me` — Identity + Memberships + Default-Workspace (TASK-301).

`DELETE /v1/me` merkt den eigenen Account zur Loeschung vor (Soft-Delete mit
30-Tage-Grace, Track O). Der Hard-Purge inkl. GoTrue-User-Loeschung laeuft
spaeter im Job `who2be-purge`; das Frontend meldet den User nach dem Aufruf
clientseitig ab.
"""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Request

from who2be_api.core.db import get_pool
from who2be_api.core.rate_limit import limiter, write_limit
from who2be_api.core.security import get_current_user
from who2be_api.repositories.account_repository import PgAccountLifecycleRepository
from who2be_api.repositories.audit_log_repository import PgAuditLogRepository
from who2be_api.repositories.me_repository import PgMeRepository
from who2be_api.services.account_lifecycle_service import AccountLifecycleService
from who2be_api.services.audit_service import AuditService
from who2be_api.services.me_service import MeService
from who2be_models import AccountDeletionRead, MeRead

router = APIRouter(prefix="/v1/me", tags=["me"])


def get_me_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> MeService:
    return MeService(PgMeRepository(pool))


def get_account_lifecycle_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> AccountLifecycleService:
    return AccountLifecycleService(
        PgAccountLifecycleRepository(pool),
        audit_service=AuditService(PgAuditLogRepository()),
        pool=pool,
    )


UserId = Annotated[UUID, Depends(get_current_user)]
Service = Annotated[MeService, Depends(get_me_service)]
LifecycleService = Annotated[AccountLifecycleService, Depends(get_account_lifecycle_service)]


@router.get("")
async def get_me(user_id: UserId, service: Service) -> MeRead:
    return await service.fetch(user_id)


@router.delete("")
@limiter.limit(write_limit)
async def delete_me(
    request: Request, user_id: UserId, service: LifecycleService
) -> AccountDeletionRead:
    """Merkt den eigenen Account zur Loeschung vor (Soft-Delete, 30-Tage-Grace)."""
    return await service.request_account_deletion(user_id)
