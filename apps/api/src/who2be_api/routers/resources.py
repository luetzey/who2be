"""REST-Endpunkte fuer Resources (`/v1/workspaces/{workspace_id}/resources`)."""

from typing import Annotated, Literal
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query, Request, Response, status

from who2be_api.core.agent_scope import visible_resource_ids
from who2be_api.core.db import get_pool
from who2be_api.core.locale import LocaleQuery
from who2be_api.core.pagination import DEFAULT_LIMIT, PageCursor, PageLimit
from who2be_api.core.rate_limit import limiter, write_limit
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.repositories.resource_repository import PgResourceRepository
from who2be_api.repositories.status_history_repository import PgStatusHistoryRepository
from who2be_api.repositories.usage_repository import PgUsageRepository
from who2be_api.routers._export import ExportResult, export_entity
from who2be_api.services.entity_export_service import EntityExportService
from who2be_api.services.entity_quota_service import enforce_entity_quota
from who2be_api.services.mcp_limit_service import enforce_mcp_read_limit
from who2be_api.services.resource_service import ResourceService
from who2be_api.services.status_history_service import StatusHistoryService
from who2be_api.services.version_status import VersionStatusService
from who2be_models import (
    ResourceBlockAnchor,
    ResourceCreate,
    ResourceRead,
    ResourceUpdate,
    ResourceVersionRead,
    StatusHistoryEntry,
    VersionDiff,
    VersionTransitionRequest,
)

router = APIRouter(prefix="/resources", tags=["resources"])


def get_resource_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> ResourceService:
    """FastAPI-Dependency: verdrahtet den Service mit der Pg-Implementierung."""
    return ResourceService(
        PgResourceRepository(pool), pool=pool, usage_repo=PgUsageRepository(pool)
    )


def get_version_status_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> VersionStatusService:
    return VersionStatusService(pool, StatusHistoryService(PgStatusHistoryRepository()))


def get_export_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> EntityExportService:
    return EntityExportService(pool)


Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]
Service = Annotated[ResourceService, Depends(get_resource_service)]
StatusService = Annotated[VersionStatusService, Depends(get_version_status_service)]
ExportService = Annotated[EntityExportService, Depends(get_export_service)]
ExportFormat = Annotated[Literal["json", "markdown"], Query()]
# `against` waehlt den Diff-Vergleichsstand: 'active' oder eine Versions-Nummer.
DiffAgainst = Annotated[str, Query(max_length=20)]


@router.get("", dependencies=[Depends(enforce_mcp_read_limit)])
async def list_resources(
    ctx: Ctx,
    service: Service,
    response: Response,
    cursor: PageCursor,
    locale: LocaleQuery,
    tag: Annotated[str | None, Query(max_length=100)] = None,
    agent: Annotated[UUID | None, Query()] = None,
    limit: PageLimit = DEFAULT_LIMIT,
) -> list[ResourceRead]:
    """Listet Resources; `?agent=` filtert auf die aus den zugewiesenen Playbooks
    erreichbaren Resources inkl. Sub-Resource-Closure (WP-B), kombinierbar mit `tag`."""
    items, next_cursor = await service.list_all(ctx, tag, limit, cursor, locale=locale, agent=agent)
    if next_cursor is not None:
        response.headers["X-Next-Cursor"] = next_cursor
    return items


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(enforce_entity_quota)],
)
@limiter.limit(write_limit)
async def create_resource(
    request: Request, data: ResourceCreate, ctx: Ctx, service: Service
) -> ResourceRead:
    return await service.create(ctx, data)


@router.get("/tags")
async def list_resource_tags(ctx: Ctx, service: Service, locale: LocaleQuery) -> list[str]:
    """Track E3: DISTINCT-Tags des Workspaces fuer den Tag-Picker im Resource-Form.

    Bewusst VOR `/{resource_id}` deklariert, sonst faengt der Pfad-Parameter
    `tags` als resource_id ab (Route-Shadowing).
    """
    return await service.list_tags(ctx, locale)


@router.get("/{resource_id}", dependencies=[Depends(enforce_mcp_read_limit)])
async def get_resource(
    resource_id: UUID, ctx: Ctx, service: Service, locale: LocaleQuery
) -> ResourceRead:
    return await service.get(ctx, resource_id, locale=locale)


@router.get("/{resource_id}/blocks")
async def list_resource_blocks(
    resource_id: UUID, ctx: Ctx, service: Service, locale: LocaleQuery
) -> list[ResourceBlockAnchor]:
    """WP-6: linkbare Heading-Anker einer Resource (id/level/text).

    Read-only, Viewer-offen — gleiche Scoping-/Locale-/Active-Draft-Semantik wie
    `GET /{resource_id}`. Datenquelle fuer den Block-Picker beim Setzen von
    Playbook-Resource-Block-Refs (ADR-0021, Heading-Only-Anker).
    """
    return await service.list_blocks(ctx, resource_id, locale)


@router.put("/{resource_id}")
@limiter.limit(write_limit)
async def update_resource(
    request: Request,
    resource_id: UUID,
    data: ResourceUpdate,
    ctx: Ctx,
    service: Service,
    locale: LocaleQuery,
) -> ResourceRead:
    return await service.update(ctx, resource_id, data, locale=locale)


@router.delete("/{resource_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(write_limit)
async def delete_resource(
    request: Request, resource_id: UUID, ctx: Ctx, service: Service
) -> Response:
    """Hard-Delete der Resource (editor+).

    409, wenn Playbooks Bloecke referenzieren oder Eltern-Composites sie einbetten.
    """
    await service.delete(ctx, resource_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# response_model=None: der Union-Rueckgabetyp (Response | dict) ist kein
# Pydantic-Feld — FastAPI soll kein Response-Model daraus generieren.
@router.get("/{resource_id}/export", response_model=None)
@limiter.limit(write_limit)
async def export_resource(
    request: Request,
    resource_id: UUID,
    ctx: Ctx,
    export_service: ExportService,
    response: Response,
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
    format: ExportFormat = "json",
) -> ExportResult:
    """Einzel-Export der Resource als JSON (alle Versionen) oder Markdown (aktive
    Version gerendert). Lesen ist fuer Viewer offen (kein require_role); ein
    `assigned`-Agent darf aber nur ihm zugewiesene Resources exportieren."""
    return await export_entity(
        export_service,
        ctx.workspace_id,
        "resource",
        resource_id,
        format,
        response,
        scope=await visible_resource_ids(pool, ctx),
    )


@router.patch("/{resource_id}/draft")
@limiter.limit(write_limit)
async def update_resource_draft(
    request: Request,
    resource_id: UUID,
    data: ResourceUpdate,
    ctx: Ctx,
    service: Service,
    locale: LocaleQuery,
) -> ResourceRead:
    """Auto-Save-Pfad — upsertet die Draft-Version ohne Versions-Increment."""
    return await service.update_draft(ctx, resource_id, data, locale=locale)


@router.get("/{resource_id}/versions")
async def list_resource_versions(
    resource_id: UUID, ctx: Ctx, service: Service, locale: LocaleQuery
) -> list[ResourceVersionRead]:
    return await service.list_versions(ctx, resource_id, locale)


@router.get("/{resource_id}/versions/{version}")
async def get_resource_version(
    resource_id: UUID, version: int, ctx: Ctx, service: Service, locale: LocaleQuery
) -> ResourceVersionRead:
    return await service.get_version(ctx, resource_id, version, locale)


@router.post("/{resource_id}/versions/{version}/transition")
@limiter.limit(write_limit)
async def transition_resource_version(
    request: Request,
    resource_id: UUID,
    version: int,
    data: VersionTransitionRequest,
    ctx: Ctx,
    status_service: StatusService,
    locale: LocaleQuery,
) -> ResourceVersionRead:
    return await status_service.transition_resource_version(
        ctx, resource_id, version, data.to, data.note, locale=locale
    )


@router.post("/{resource_id}/versions/{version}/restore", status_code=status.HTTP_201_CREATED)
@limiter.limit(write_limit)
async def restore_resource_version(
    request: Request,
    resource_id: UUID,
    version: int,
    ctx: Ctx,
    service: Service,
    locale: LocaleQuery,
) -> ResourceRead:
    """Stellt Version `version` als neue Draft wieder her (non-destruktiv)."""
    return await service.restore(ctx, resource_id, version, locale=locale)


@router.get("/{resource_id}/versions/{version}/diff")
async def diff_resource_version(
    resource_id: UUID,
    version: int,
    ctx: Ctx,
    service: Service,
    locale: LocaleQuery,
    against: DiffAgainst = "active",
) -> VersionDiff:
    """Strukturierter Feld-/Block-Diff der Version gegen `against` (read-only)."""
    return await service.diff(ctx, resource_id, version, against, locale=locale)


@router.get("/{resource_id}/versions/{version}/provenance")
async def provenance_resource_version(
    resource_id: UUID,
    version: int,
    ctx: Ctx,
    status_service: StatusService,
) -> list[StatusHistoryEntry]:
    """Status-Historie dieser Version ("warum aktiv")."""
    return await status_service.provenance_resource(ctx, resource_id, version)
