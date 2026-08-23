"""REST-Endpunkte fuer Personae (`/v1/workspaces/{workspace_id}/personas`)."""

from typing import Annotated, Literal
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query, Request, Response, status

from who2be_api.core.db import get_pool
from who2be_api.core.locale import LocaleFilterQuery
from who2be_api.core.pagination import DEFAULT_LIMIT, PageCursor, PageLimit
from who2be_api.core.rate_limit import limiter, write_limit
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.repositories.persona_repository import PgPersonaRepository
from who2be_api.repositories.status_history_repository import PgStatusHistoryRepository
from who2be_api.repositories.usage_repository import PgUsageRepository
from who2be_api.repositories.workspace_repository import PgWorkspaceRepository
from who2be_api.routers._export import ExportResult, export_entity
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
    return PersonaService(
        PgPersonaRepository(pool),
        pool,
        PgUsageRepository(pool),
        PgWorkspaceRepository(pool),
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
    locale: LocaleFilterQuery,
    agent: Annotated[UUID | None, Query()] = None,
    name: Annotated[str | None, Query(max_length=200)] = None,
    limit: PageLimit = DEFAULT_LIMIT,
) -> list[PersonaRead]:
    """Listet Personae; `?locale=` filtert auf die Element-Sprache (ADR-0045),
    `?agent=` filtert auf die Persona des Agenten (WP-B), `?name=` auf den
    exakten Namen (Issue #415 — damit die Aufloesung per Name nicht die ganze
    Library laedt, nur um einen String zu vergleichen)."""
    items, next_cursor = await service.list_all(
        ctx, limit, cursor, locale=locale, agent=agent, name=name
    )
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
async def list_persona_tags(ctx: Ctx, service: Service) -> list[str]:
    """DISTINCT-Tags des Workspaces fuer den Tag-Picker im Persona-Form."""
    return await service.list_tags(ctx)


@router.get("/{persona_id}", dependencies=[Depends(enforce_mcp_read_limit)])
async def get_persona(persona_id: UUID, ctx: Ctx, service: Service) -> PersonaRead:
    return await service.get(ctx, persona_id)


@router.post("/{persona_id}/duplicate", status_code=status.HTTP_201_CREATED)
@limiter.limit(write_limit)
async def duplicate_persona(
    request: Request,
    persona_id: UUID,
    ctx: Ctx,
    service: Service,
) -> PersonaRead:
    """Dupliziert eine Persona als frische Draft (Deep-Copy des Inhalts, editor+)."""
    return await service.duplicate(ctx, persona_id)


@router.get("/{persona_id}/rendered", dependencies=[Depends(enforce_mcp_read_limit)])
async def render_persona(
    persona_id: UUID,
    ctx: Ctx,
    service: Service,
    mode: Annotated[str | None, Query(max_length=100)] = None,
) -> PersonaRenderResponse:
    """Liefert den durch den Placeholder-Renderer expandierten Profil-Body (Track F).

    Die Katalog-Pills (`playbooks-catalog`/`resources-catalog`) und Slash-Refs
    werden fetch-time gegen die aktiven Playbooks/Resources des Workspace
    aufgeloest; eine Skills-Tabelle wird angehaengt. Wird vom MCP-Tool
    `get_persona` genutzt.

    `?mode=` (WP-F, additiv) waehlt einen benannten Persona-Modus aus
    `content.modes` (case-insensitiv) — der Body traegt dann die
    Aktiver-Modus-Sektion, `mode` in der Antwort den kanonischen Namen.
    Unbekannter Modus → 422 mit der Liste der verfuegbaren Modi.
    """
    return await service.render(ctx, persona_id, mode=mode)


@router.put("/{persona_id}")
@limiter.limit(write_limit)
async def update_persona(
    request: Request,
    persona_id: UUID,
    data: PersonaUpdate,
    ctx: Ctx,
    service: Service,
) -> PersonaRead:
    return await service.update(ctx, persona_id, data)


@router.delete("/{persona_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(write_limit)
async def delete_persona(
    request: Request, persona_id: UUID, ctx: Ctx, service: Service
) -> Response:
    """Hard-Delete der Persona (editor+). 409, wenn Agenten sie noch nutzen."""
    await service.delete(ctx, persona_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# response_model=None: der Union-Rueckgabetyp (Response | dict) ist kein
# Pydantic-Feld — FastAPI soll kein Response-Model daraus generieren.
@router.get("/{persona_id}/export", response_model=None)
@limiter.limit(write_limit)
async def export_persona(
    request: Request,
    persona_id: UUID,
    ctx: Ctx,
    export_service: ExportService,
    response: Response,
    format: ExportFormat = "json",
) -> ExportResult:
    """Einzel-Export der Persona als JSON (alle Versionen) oder Markdown (aktive
    Version gerendert). Lesen ist fuer Viewer offen (kein require_role)."""
    return await export_entity(
        export_service, ctx.workspace_id, "persona", persona_id, format, response
    )


@router.patch("/{persona_id}/draft")
@limiter.limit(write_limit)
async def update_persona_draft(
    request: Request,
    persona_id: UUID,
    data: PersonaUpdate,
    ctx: Ctx,
    service: Service,
) -> PersonaRead:
    """Auto-Save-Pfad — upsertet die Draft-Version ohne Versions-Increment."""
    return await service.update_draft(ctx, persona_id, data)


@router.get("/{persona_id}/versions")
async def list_persona_versions(
    persona_id: UUID, ctx: Ctx, service: Service
) -> list[PersonaVersionRead]:
    return await service.list_versions(ctx, persona_id)


@router.get("/{persona_id}/versions/{version}")
async def get_persona_version(
    persona_id: UUID, version: int, ctx: Ctx, service: Service
) -> PersonaVersionRead:
    return await service.get_version(ctx, persona_id, version)


@router.post("/{persona_id}/versions/{version}/transition")
@limiter.limit(write_limit)
async def transition_persona_version(
    request: Request,
    persona_id: UUID,
    version: int,
    data: VersionTransitionRequest,
    ctx: Ctx,
    status_service: StatusService,
) -> PersonaVersionRead:
    return await status_service.transition_persona_version(
        ctx, persona_id, version, data.to, data.note
    )


@router.post("/{persona_id}/versions/{version}/restore", status_code=status.HTTP_201_CREATED)
@limiter.limit(write_limit)
async def restore_persona_version(
    request: Request,
    persona_id: UUID,
    version: int,
    ctx: Ctx,
    service: Service,
) -> PersonaRead:
    """Stellt Version `version` als neue Draft wieder her (non-destruktiv)."""
    return await service.restore(ctx, persona_id, version)


@router.get("/{persona_id}/versions/{version}/diff")
async def diff_persona_version(
    persona_id: UUID,
    version: int,
    ctx: Ctx,
    service: Service,
    against: DiffAgainst = "active",
) -> VersionDiff:
    """Strukturierter Feld-/Block-Diff der Version gegen `against` (read-only)."""
    return await service.diff(ctx, persona_id, version, against)


@router.get("/{persona_id}/versions/{version}/provenance")
async def provenance_persona_version(
    persona_id: UUID,
    version: int,
    ctx: Ctx,
    status_service: StatusService,
) -> list[StatusHistoryEntry]:
    """Status-Historie dieser Version ("warum aktiv")."""
    return await status_service.provenance_persona(ctx, persona_id, version)
