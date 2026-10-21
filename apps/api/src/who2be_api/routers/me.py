"""REST-Endpunkt `/v1/me` — Identity + Memberships + Default-Workspace (TASK-301).

`DELETE /v1/me` merkt den eigenen Account zur Loeschung vor (Soft-Delete mit
30-Tage-Grace, Track O). Der Hard-Purge inkl. GoTrue-User-Loeschung laeuft
spaeter im Job `who2be-purge`; das Frontend meldet den User nach dem Aufruf
clientseitig ab.
"""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Path, Query, Request

from who2be_api.core.db import get_pool
from who2be_api.core.rate_limit import limiter, write_limit
from who2be_api.core.security import CurrentPrincipal, get_current_principal, get_current_user
from who2be_api.repositories.account_repository import PgAccountLifecycleRepository
from who2be_api.repositories.audit_log_repository import PgAuditLogRepository
from who2be_api.repositories.me_repository import PgMeRepository
from who2be_api.repositories.tutorial_repository import PgTutorialRepository
from who2be_api.services.account_lifecycle_service import AccountLifecycleService
from who2be_api.services.audit_service import AuditService
from who2be_api.services.me_service import MeService
from who2be_api.services.tutorial_service import TutorialService
from who2be_models import AccountDeletionRead, MeRead
from who2be_models.tutorial import (
    TUTORIAL_ID_MAX_LENGTH,
    TUTORIAL_ID_PATTERN,
    TutorialPatch,
    TutorialRead,
)

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
Principal = Annotated[CurrentPrincipal, Depends(get_current_principal)]
Service = Annotated[MeService, Depends(get_me_service)]
LifecycleService = Annotated[AccountLifecycleService, Depends(get_account_lifecycle_service)]


@router.get("")
async def get_me(principal: Principal, service: Service) -> MeRead:
    return await service.fetch(principal.user_id, token_workspace_id=principal.token_workspace_id)


@router.delete("")
@limiter.limit(write_limit)
async def delete_me(
    request: Request, user_id: UserId, service: LifecycleService
) -> AccountDeletionRead:
    """Merkt den eigenen Account zur Loeschung vor (Soft-Delete, 30-Tage-Grace)."""
    return await service.request_account_deletion(user_id)


# --- Tutorials (ADR-0060) ---------------------------------------------------
# Fortschritt am Konto, nur fuer Menschen (`get_current_user` sperrt Tokens).
# `?workspace_id=` ist optional und nur fuer die abgeleiteten Schritte da; er
# wird gegen die Mitgliedschaft geprueft (fremd oder unbekannt: 404).

TutorialId = Annotated[str, Path(pattern=TUTORIAL_ID_PATTERN, max_length=TUTORIAL_ID_MAX_LENGTH)]
WorkspaceQuery = Annotated[
    UUID | None,
    Query(description="Workspace, aus dem automatische Schritte abgeleitet werden."),
]


def get_tutorial_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> TutorialService:
    return TutorialService(PgTutorialRepository(pool))


Tutorials = Annotated[TutorialService, Depends(get_tutorial_service)]


@router.get("/tutorials")
async def list_tutorials(
    user_id: UserId, service: Tutorials, workspace_id: WorkspaceQuery = None
) -> list[TutorialRead]:
    """Alle Tutorials des Katalogs mit dem Stand des eigenen Kontos."""
    return await service.list_tutorials(user_id, workspace_id)


@router.get("/tutorials/{tutorial_id}")
async def get_tutorial(
    tutorial_id: TutorialId,
    user_id: UserId,
    service: Tutorials,
    workspace_id: WorkspaceQuery = None,
) -> TutorialRead:
    return await service.get(user_id, tutorial_id, workspace_id)


@router.patch("/tutorials/{tutorial_id}")
@limiter.limit(write_limit)
async def patch_tutorial(
    request: Request,
    tutorial_id: TutorialId,
    body: TutorialPatch,
    user_id: UserId,
    service: Tutorials,
    workspace_id: WorkspaceQuery = None,
) -> TutorialRead:
    """Schritt abhaken, ueberspringen oder wieder oeffnen; Begruessung gesehen."""
    return await service.patch(user_id, tutorial_id, body, workspace_id)


@router.post("/tutorials/{tutorial_id}/restart")
@limiter.limit(write_limit)
async def restart_tutorial(
    request: Request,
    tutorial_id: TutorialId,
    user_id: UserId,
    service: Tutorials,
    workspace_id: WorkspaceQuery = None,
) -> TutorialRead:
    """Setzt den Fortschritt genau dieses Tutorials zurueck."""
    return await service.restart(user_id, tutorial_id, workspace_id)
