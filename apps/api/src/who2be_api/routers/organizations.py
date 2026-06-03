"""REST-Endpunkte fuer Organizations (`/v1/organizations`, TASK-301)."""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Request, status

from who2be_api.core.db import get_pool
from who2be_api.core.rate_limit import limiter, write_limit
from who2be_api.core.security import get_current_user
from who2be_api.repositories.account_repository import PgAccountLifecycleRepository
from who2be_api.repositories.organization_repository import PgOrganizationRepository
from who2be_api.repositories.workspace_repository import PgWorkspaceRepository
from who2be_api.services.account_lifecycle_service import AccountLifecycleService
from who2be_api.services.organization_service import OrganizationService
from who2be_api.services.workspace_service import WorkspaceService
from who2be_models import (
    OrganizationCreate,
    OrganizationDeletionRead,
    OrganizationRead,
    WorkspaceCreate,
    WorkspaceRead,
)

router = APIRouter(prefix="/v1/organizations", tags=["organizations"])


def get_organization_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> OrganizationService:
    return OrganizationService(PgOrganizationRepository(pool))


def get_workspace_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> WorkspaceService:
    return WorkspaceService(PgWorkspaceRepository(pool), PgOrganizationRepository(pool))


def get_account_lifecycle_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> AccountLifecycleService:
    return AccountLifecycleService(PgAccountLifecycleRepository(pool))


UserId = Annotated[UUID, Depends(get_current_user)]
OrgSvc = Annotated[OrganizationService, Depends(get_organization_service)]
WsSvc = Annotated[WorkspaceService, Depends(get_workspace_service)]
LifecycleSvc = Annotated[AccountLifecycleService, Depends(get_account_lifecycle_service)]


@router.get("")
async def list_organizations(user_id: UserId, service: OrgSvc) -> list[OrganizationRead]:
    return await service.list_for_user(user_id)


@router.post("", status_code=status.HTTP_201_CREATED)
@limiter.limit(write_limit)
async def create_organization(
    request: Request, data: OrganizationCreate, user_id: UserId, service: OrgSvc
) -> OrganizationRead:
    return await service.create(user_id, data)


@router.delete("/{organization_id}")
@limiter.limit(write_limit)
async def delete_organization(
    request: Request,
    organization_id: UUID,
    user_id: UserId,
    service: LifecycleSvc,
) -> OrganizationDeletionRead:
    """Merkt eine Company-Org zur Loeschung vor (Soft-Delete, 30-Tage-Grace).

    Nur der Org-Owner darf das; Personal-Orgs laufen ueber die Konto-Loeschung.
    """
    return await service.delete_organization(user_id, organization_id)


@router.get("/{organization_id}/workspaces")
async def list_organization_workspaces(
    organization_id: UUID, user_id: UserId, service: WsSvc
) -> list[WorkspaceRead]:
    return await service.list_for_org(organization_id, user_id)


@router.post("/{organization_id}/workspaces", status_code=status.HTTP_201_CREATED)
@limiter.limit(write_limit)
async def create_organization_workspace(
    request: Request,
    organization_id: UUID,
    data: WorkspaceCreate,
    user_id: UserId,
    service: WsSvc,
) -> WorkspaceRead:
    return await service.create(organization_id, user_id, data)
