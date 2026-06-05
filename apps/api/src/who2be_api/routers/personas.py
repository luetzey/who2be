"""REST-Endpunkte fuer Personae (`/v1/workspaces/{workspace_id}/personas`)."""

from typing import Annotated, Any, Literal
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from who2be_api.core.db import get_pool
from who2be_api.core.locale import LocaleQuery
from who2be_api.core.pagination import DEFAULT_LIMIT, PageCursor, PageLimit
from who2be_api.core.rate_limit import limiter, write_limit
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.repositories.persona_repository import PgPersonaRepository
from who2be_api.repositories.status_history_repository import PgStatusHistoryRepository
from who2be_api.repositories.usage_repository import PgUsageRepository
from who2be_api.services.entity_export_service import EntityExportService
from who2be_api.services.entity_quota_service import enforce_entity_quota
from who2be_api.services.mcp_limit_service import enforce_mcp_read_limit
from who2be_api.services.persona_service import PersonaRenderResponse, PersonaService
from who2be_api.services.status_history_service import StatusHistoryService
from who2be_api.services.version_status import VersionStatusService
from who2be_models import (
    PersonaCreate,
    PersonaRead,
    PersonaUpdate,
    PersonaVersionRead,
    StatusHistoryEntry,
    VersionDiff,
    VersionTransitionRequest,
)

router = APIRouter(prefix="/personas", tags=["personas"])


def get_persona_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> PersonaService:
    """FastAPI-Dependency: verdrahtet den Service mit der Pg-Implementierung.

    Der Pool wird zusaetzlich durchgereicht (Track F: Render-Pfad braucht eine
    Connection fuer die fetch-time-Expansion der Katalog-Pills).
    """
    return PersonaService(PgPersonaRepository(pool), pool, PgUsageRepository(pool))


def get_version_status_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> VersionStatusService:
    return VersionStatusService(pool, StatusHistoryService(PgStatusHistoryRepository()))


def get_export_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> EntityExportService:
    return EntityExportService(pool)


Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]
Service = Annotated[PersonaService, Depends(get_persona_service)]
StatusService = Annotated[VersionStatusService, Depends(get_version_status_service)]
ExportService = Annotated[EntityExportService, Depends(get_export_service)]
ExportFormat = Annotated[Literal["json", "markdown"], Query()]
# `against` waehlt den Diff-Vergleichsstand: 'active' oder eine Versions-Nummer.
DiffAgainst = Annotated[str, Query(max_length=20)]


@router.get("")
async def list_personas(
    ctx: Ctx,
    service: Service,
    response: Response,
    cursor: PageCursor,
    locale: LocaleQuery,
    limit: PageLimit = DEFAULT_LIMIT,
) -> list[PersonaRead]:
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
async def create_persona(
    request: Request, data: PersonaCreate, ctx: Ctx, service: Service
) -> PersonaRead:
    return await service.create(ctx, data)


@router.get("/tags")
async def list_persona_tags(ctx: Ctx, service: Service, locale: LocaleQuery) -> list[str]:
    """DISTINCT-Tags des Workspaces fuer den Tag-Picker im Persona-Form."""
    return await service.list_tags(ctx, locale)


@router.get("/{persona_id}", dependencies=[Depends(enforce_mcp_read_limit)])
async def get_persona(
    persona_id: UUID, ctx: Ctx, service: Service, locale: LocaleQuery
) -> PersonaRead:
    return await service.get(ctx, persona_id, locale=locale)


@router.get("/{persona_id}/rendered", dependencies=[Depends(enforce_mcp_read_limit)])
async def render_persona(
    persona_id: UUID, ctx: Ctx, service: Service, locale: LocaleQuery
) -> PersonaRenderResponse:
    """Liefert den durch den Placeholder-Renderer expandierten Profil-Body (Track F).

    Die Katalog-Pills (`playbooks-catalog`/`resources-catalog`) und Slash-Refs
    werden fetch-time gegen die aktiven Playbooks/Resources des Workspace
    aufgeloest; eine Skills-Tabelle wird angehaengt. Wird vom MCP-Tool
    `get_persona` genutzt.
    """
    return await service.render(ctx, persona_id, locale=locale)


@router.put("/{persona_id}")
@limiter.limit(write_limit)
async def update_persona(
    request: Request,
    persona_id: UUID,
    data: PersonaUpdate,
    ctx: Ctx,
    service: Service,
    locale: LocaleQuery,
) -> PersonaRead:
    return await service.update(ctx, persona_id, data, locale=locale)


@router.delete("/{persona_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(write_limit)
async def delete_persona(
    request: Request, persona_id: UUID, ctx: Ctx, service: Service
) -> Response:
    """Hard-Delete der Persona (editor+). 409, wenn Agenten sie noch nutzen."""
    await service.delete(ctx, persona_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{persona_id}/export")
@limiter.limit(write_limit)
async def export_persona(
    request: Request,
    persona_id: UUID,
    ctx: Ctx,
    export_service: ExportService,
    response: Response,
    format: ExportFormat = "json",
) -> Any:
    """Einzel-Export der Persona als JSON (alle Versionen) oder Markdown (aktive
    Version gerendert). Lesen ist fuer Viewer offen (kein require_role)."""
    if format == "markdown":
        rendered = await export_service.export_markdown(ctx.workspace_id, "persona", persona_id)
        if rendered is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Persona nicht gefunden."
            )
        return Response(
            content=rendered,
            media_type="text/markdown",
            headers={
                "Content-Disposition": (f'attachment; filename="who2be-persona-{persona_id}.md"')
            },
        )
    bundle = await export_service.export_json(ctx.workspace_id, "persona", persona_id)
    if bundle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona nicht gefunden.")
    response.headers["Content-Disposition"] = (
        f'attachment; filename="who2be-persona-{persona_id}.json"'
    )
    return bundle


@router.patch("/{persona_id}/draft")
@limiter.limit(write_limit)
async def update_persona_draft(
    request: Request,
    persona_id: UUID,
    data: PersonaUpdate,
    ctx: Ctx,
    service: Service,
    locale: LocaleQuery,
) -> PersonaRead:
    """Auto-Save-Pfad — upsertet die Draft-Version ohne Versions-Increment."""
    return await service.update_draft(ctx, persona_id, data, locale=locale)


@router.get("/{persona_id}/versions")
async def list_persona_versions(
    persona_id: UUID, ctx: Ctx, service: Service, locale: LocaleQuery
) -> list[PersonaVersionRead]:
    return await service.list_versions(ctx, persona_id, locale)


@router.get("/{persona_id}/versions/{version}")
async def get_persona_version(
    persona_id: UUID, version: int, ctx: Ctx, service: Service, locale: LocaleQuery
) -> PersonaVersionRead:
    return await service.get_version(ctx, persona_id, version, locale)


@router.post("/{persona_id}/versions/{version}/transition")
@limiter.limit(write_limit)
async def transition_persona_version(
    request: Request,
    persona_id: UUID,
    version: int,
    data: VersionTransitionRequest,
    ctx: Ctx,
    status_service: StatusService,
    locale: LocaleQuery,
) -> PersonaVersionRead:
    return await status_service.transition_persona_version(
        ctx, persona_id, version, data.to, data.note, locale=locale
    )


@router.post("/{persona_id}/versions/{version}/restore", status_code=status.HTTP_201_CREATED)
@limiter.limit(write_limit)
async def restore_persona_version(
    request: Request,
    persona_id: UUID,
    version: int,
    ctx: Ctx,
    service: Service,
    locale: LocaleQuery,
) -> PersonaRead:
    """Stellt Version `version` als neue Draft wieder her (non-destruktiv)."""
    return await service.restore(ctx, persona_id, version, locale=locale)


@router.get("/{persona_id}/versions/{version}/diff")
async def diff_persona_version(
    persona_id: UUID,
    version: int,
    ctx: Ctx,
    service: Service,
    locale: LocaleQuery,
    against: DiffAgainst = "active",
) -> VersionDiff:
    """Strukturierter Feld-/Block-Diff der Version gegen `against` (read-only)."""
    return await service.diff(ctx, persona_id, version, against, locale=locale)


@router.get("/{persona_id}/versions/{version}/provenance")
async def provenance_persona_version(
    persona_id: UUID,
    version: int,
    ctx: Ctx,
    status_service: StatusService,
) -> list[StatusHistoryEntry]:
    """Status-Historie dieser Version ("warum aktiv")."""
    return await status_service.provenance_persona(ctx, persona_id, version)
