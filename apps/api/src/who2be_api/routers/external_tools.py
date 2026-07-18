"""REST-Endpunkte fuer ExternalTools (`/v1/workspaces/{workspace_id}/external_tools`).

WP-1 Backend-Fundament (Blueprint
`.claude/plan/2026-07-18-1315_external-tools-tool-ref.md`): CRUD +
Status-Transition + Restore + Einzel-Export, Aufbau analog `routers/resources.py`.
"""

from typing import Annotated, Literal
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Request, Response, status

from who2be_api.core.db import get_pool
from who2be_api.core.locale import LocaleQuery
from who2be_api.core.pagination import DEFAULT_LIMIT, PageCursor, PageLimit
from who2be_api.core.rate_limit import limiter, write_limit
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.repositories.external_tool_repository import PgExternalToolRepository
from who2be_api.repositories.status_history_repository import PgStatusHistoryRepository
from who2be_api.routers._export import ExportResult, export_entity
from who2be_api.services.entity_export_service import EntityExportService
from who2be_api.services.entity_quota_service import enforce_entity_quota
from who2be_api.services.external_tool_service import ExternalToolService
from who2be_api.services.mcp_limit_service import enforce_mcp_read_limit
from who2be_api.services.status_history_service import StatusHistoryService
from who2be_api.services.version_status import VersionStatusService
from who2be_models import (
    ExternalToolCreate,
    ExternalToolRead,
    ExternalToolUpdate,
    ExternalToolVersionRead,
    StatusHistoryEntry,
    VersionTransitionRequest,
)

router = APIRouter(prefix="/external_tools", tags=["external_tools"])


def get_external_tool_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> ExternalToolService:
    """FastAPI-Dependency: verdrahtet den Service mit der Pg-Implementierung."""
    return ExternalToolService(PgExternalToolRepository(pool))


def get_version_status_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> VersionStatusService:
    return VersionStatusService(pool, StatusHistoryService(PgStatusHistoryRepository()))


def get_export_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> EntityExportService:
    return EntityExportService(pool)


Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]
Service = Annotated[ExternalToolService, Depends(get_external_tool_service)]
StatusService = Annotated[VersionStatusService, Depends(get_version_status_service)]
ExportService = Annotated[EntityExportService, Depends(get_export_service)]


@router.get("", dependencies=[Depends(enforce_mcp_read_limit)])
async def list_external_tools(
    ctx: Ctx,
    service: Service,
    response: Response,
    cursor: PageCursor,
    locale: LocaleQuery,
    limit: PageLimit = DEFAULT_LIMIT,
) -> list[ExternalToolRead]:
    items, next_cursor = await service.list_all(ctx, limit, cursor, locale=locale)
    if next_cursor is not None:
        response.headers["X-Next-Cursor"] = next_cursor
    return items


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(enforce_entity_quota)],
)
@limiter.limit(write_limit)
async def create_external_tool(
    request: Request, data: ExternalToolCreate, ctx: Ctx, service: Service
) -> ExternalToolRead:
    return await service.create(ctx, data)


@router.get("/{tool_id}", dependencies=[Depends(enforce_mcp_read_limit)])
async def get_external_tool(
    tool_id: UUID, ctx: Ctx, service: Service, locale: LocaleQuery
) -> ExternalToolRead:
    return await service.get(ctx, tool_id, locale=locale)


@router.put("/{tool_id}")
@limiter.limit(write_limit)
async def update_external_tool(
    request: Request,
    tool_id: UUID,
    data: ExternalToolUpdate,
    ctx: Ctx,
    service: Service,
    locale: LocaleQuery,
) -> ExternalToolRead:
    return await service.update(ctx, tool_id, data, locale=locale)


@router.delete("/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(write_limit)
async def delete_external_tool(
    request: Request, tool_id: UUID, ctx: Ctx, service: Service
) -> Response:
    """Hard-Delete des externen Tools (editor+)."""
    await service.delete(ctx, tool_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# response_model=None: der Union-Rueckgabetyp (Response | dict) ist kein
# Pydantic-Feld — FastAPI soll kein Response-Model daraus generieren.
@router.get("/{tool_id}/export", response_model=None)
@limiter.limit(write_limit)
async def export_external_tool(
    request: Request,
    tool_id: UUID,
    ctx: Ctx,
    export_service: ExportService,
    response: Response,
    format: Literal["json", "markdown"] = "json",
) -> ExportResult:
    """Einzel-Export des externen Tools als JSON (alle Versionen) oder Markdown
    (aktive Version gerendert). Lesen ist fuer Viewer offen (kein require_role)."""
    return await export_entity(
        export_service, ctx.workspace_id, "external_tool", tool_id, format, response
    )


@router.patch("/{tool_id}/draft")
@limiter.limit(write_limit)
async def update_external_tool_draft(
    request: Request,
    tool_id: UUID,
    data: ExternalToolUpdate,
    ctx: Ctx,
    service: Service,
    locale: LocaleQuery,
) -> ExternalToolRead:
    """Auto-Save-Pfad — upsertet die Draft-Version ohne Versions-Increment."""
    return await service.update_draft(ctx, tool_id, data, locale=locale)


@router.get("/{tool_id}/versions")
async def list_external_tool_versions(
    tool_id: UUID, ctx: Ctx, service: Service, locale: LocaleQuery
) -> list[ExternalToolVersionRead]:
    return await service.list_versions(ctx, tool_id, locale)


@router.get("/{tool_id}/versions/{version}")
async def get_external_tool_version(
    tool_id: UUID, version: int, ctx: Ctx, service: Service, locale: LocaleQuery
) -> ExternalToolVersionRead:
    return await service.get_version(ctx, tool_id, version, locale)


@router.post("/{tool_id}/versions/{version}/transition")
@limiter.limit(write_limit)
async def transition_external_tool_version(
    request: Request,
    tool_id: UUID,
    version: int,
    data: VersionTransitionRequest,
    ctx: Ctx,
    status_service: StatusService,
    locale: LocaleQuery,
) -> ExternalToolVersionRead:
    return await status_service.transition_external_tool_version(
        ctx, tool_id, version, data.to, data.note, locale=locale
    )


@router.post("/{tool_id}/versions/{version}/restore", status_code=status.HTTP_201_CREATED)
@limiter.limit(write_limit)
async def restore_external_tool_version(
    request: Request,
    tool_id: UUID,
    version: int,
    ctx: Ctx,
    service: Service,
    locale: LocaleQuery,
) -> ExternalToolRead:
    """Stellt Version `version` als neue Draft wieder her (non-destruktiv)."""
    return await service.restore(ctx, tool_id, version, locale=locale)


@router.get("/{tool_id}/versions/{version}/provenance")
async def provenance_external_tool_version(
    tool_id: UUID,
    version: int,
    ctx: Ctx,
    status_service: StatusService,
) -> list[StatusHistoryEntry]:
    """Status-Historie dieser Version ("warum aktiv")."""
    return await status_service.provenance_external_tool(ctx, tool_id, version)
