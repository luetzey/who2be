"""REST-Endpunkte fuer SystemPromptTemplates.

Pfad: ``/v1/workspaces/{workspace_id}/system-prompts``.

Versions-Logik spiegelt Persona/Playbook: ``PUT`` legt eine neue Draft-/
Inactive-Version an (Draft-on-Edit bei Active), ``POST .../transition``
verschiebt eine Version durch die State-Machine.
"""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query, Request, Response, status

from who2be_api.core.db import get_pool
from who2be_api.core.pagination import DEFAULT_LIMIT, PageCursor, PageLimit
from who2be_api.core.rate_limit import limiter, write_limit
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.repositories.status_history_repository import PgStatusHistoryRepository
from who2be_api.repositories.system_prompt_template_repository import (
    PgSystemPromptTemplateRepository,
)
from who2be_api.services.status_history_service import StatusHistoryService
from who2be_api.services.system_prompt_template_service import (
    SystemPromptTemplateService,
)
from who2be_api.services.version_status import VersionStatusService
from who2be_models import (
    StatusHistoryEntry,
    SystemPromptTemplateCreate,
    SystemPromptTemplateRead,
    SystemPromptTemplateUpdate,
    SystemPromptTemplateVersionRead,
    VersionDiff,
    VersionTransitionRequest,
)

router = APIRouter(prefix="/system-prompts", tags=["system-prompts"])


def get_template_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> SystemPromptTemplateService:
    return SystemPromptTemplateService(PgSystemPromptTemplateRepository(pool))


def get_version_status_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> VersionStatusService:
    return VersionStatusService(pool, StatusHistoryService(PgStatusHistoryRepository()))


Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]
Service = Annotated[SystemPromptTemplateService, Depends(get_template_service)]
StatusService = Annotated[VersionStatusService, Depends(get_version_status_service)]
# `against` waehlt den Diff-Vergleichsstand: 'active' oder eine Versions-Nummer.
DiffAgainst = Annotated[str, Query(max_length=20)]


@router.get("")
async def list_templates(
    ctx: Ctx,
    service: Service,
    response: Response,
    cursor: PageCursor,
    limit: PageLimit = DEFAULT_LIMIT,
) -> list[SystemPromptTemplateRead]:
    items, next_cursor = await service.list_all(ctx, limit, cursor)
    if next_cursor is not None:
        response.headers["X-Next-Cursor"] = next_cursor
    return items


@router.post("", status_code=status.HTTP_201_CREATED)
@limiter.limit(write_limit)
async def create_template(
    request: Request,
    data: SystemPromptTemplateCreate,
    ctx: Ctx,
    service: Service,
) -> SystemPromptTemplateRead:
    return await service.create(ctx, data)


@router.get("/{template_id}")
async def get_template(template_id: UUID, ctx: Ctx, service: Service) -> SystemPromptTemplateRead:
    return await service.get(ctx, template_id)


@router.post("/{template_id}/duplicate", status_code=status.HTTP_201_CREATED)
@limiter.limit(write_limit)
async def duplicate_template(
    request: Request,
    template_id: UUID,
    ctx: Ctx,
    service: Service,
) -> SystemPromptTemplateRead:
    """Dupliziert ein System-Prompt-Template als frische Draft mit eigenem Slug (editor+)."""
    return await service.duplicate(ctx, template_id)


@router.put("/{template_id}")
@limiter.limit(write_limit)
async def update_template(
    request: Request,
    template_id: UUID,
    data: SystemPromptTemplateUpdate,
    ctx: Ctx,
    service: Service,
) -> SystemPromptTemplateRead:
    return await service.update(ctx, template_id, data)


@router.get("/{template_id}/versions")
async def list_template_versions(
    template_id: UUID, ctx: Ctx, service: Service
) -> list[SystemPromptTemplateVersionRead]:
    return await service.list_versions(ctx, template_id)


@router.get("/{template_id}/versions/{version}")
async def get_template_version(
    template_id: UUID, version: int, ctx: Ctx, service: Service
) -> SystemPromptTemplateVersionRead:
    return await service.get_version(ctx, template_id, version)


@router.post("/{template_id}/versions/{version}/transition")
@limiter.limit(write_limit)
async def transition_template_version(
    request: Request,
    template_id: UUID,
    version: int,
    data: VersionTransitionRequest,
    ctx: Ctx,
    status_service: StatusService,
) -> SystemPromptTemplateVersionRead:
    return await status_service.transition_system_prompt_template_version(
        ctx, template_id, version, data.to, data.note
    )


@router.post("/{template_id}/versions/{version}/restore", status_code=status.HTTP_201_CREATED)
@limiter.limit(write_limit)
async def restore_template_version(
    request: Request,
    template_id: UUID,
    version: int,
    ctx: Ctx,
    service: Service,
) -> SystemPromptTemplateRead:
    """Stellt Version `version` als neue Draft wieder her (non-destruktiv)."""
    return await service.restore(ctx, template_id, version)


@router.get("/{template_id}/versions/{version}/diff")
async def diff_template_version(
    template_id: UUID,
    version: int,
    ctx: Ctx,
    service: Service,
    against: DiffAgainst = "active",
) -> VersionDiff:
    """Strukturierter Feld-Diff der Version gegen `against` (read-only)."""
    return await service.diff(ctx, template_id, version, against)


@router.get("/{template_id}/versions/{version}/provenance")
async def provenance_template_version(
    template_id: UUID,
    version: int,
    ctx: Ctx,
    status_service: StatusService,
) -> list[StatusHistoryEntry]:
    """Status-Historie dieser Version ("warum aktiv")."""
    return await status_service.provenance_system_prompt_template(ctx, template_id, version)
