"""REST-Endpunkte fuer Playbooks (`/v1/workspaces/{workspace_id}/playbooks`)."""

from typing import Annotated, Any, Literal
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from who2be_api.core.agent_scope import visible_playbook_ids
from who2be_api.core.db import get_pool
from who2be_api.core.locale import LocaleQuery
from who2be_api.core.pagination import DEFAULT_LIMIT, PageCursor, PageLimit
from who2be_api.core.rate_limit import limiter, write_limit
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.repositories.playbook_composition_repository import (
    PgPlaybookCompositionRepository,
)
from who2be_api.repositories.playbook_repository import PgPlaybookRepository
from who2be_api.repositories.playbook_resource_link_repository import (
    PgPlaybookResourceLinkRepository,
)
from who2be_api.repositories.status_history_repository import PgStatusHistoryRepository
from who2be_api.repositories.usage_repository import PgUsageRepository
from who2be_api.services.entity_export_service import EntityExportService
from who2be_api.services.entity_quota_service import enforce_entity_quota
from who2be_api.services.mcp_limit_service import enforce_mcp_read_limit
from who2be_api.services.playbook_composition_service import PlaybookCompositionService
from who2be_api.services.playbook_resource_link_service import PlaybookResourceLinkService
from who2be_api.services.playbook_service import PlaybookRenderResponse, PlaybookService
from who2be_api.services.status_history_service import StatusHistoryService
from who2be_api.services.version_status import VersionStatusService
from who2be_models import (
    PlaybookCreate,
    PlaybookRead,
    PlaybookUpdate,
    PlaybookVersionRead,
    StatusHistoryEntry,
    TriggerOverview,
    VersionDiff,
    VersionTransitionRequest,
)

router = APIRouter(prefix="/playbooks", tags=["playbooks"])


def get_playbook_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> PlaybookService:
    """FastAPI-Dependency: verdrahtet den Service mit der Pg-Implementierung.

    Der Pool wird fuer den Render-Pfad (B5) injiziert; die Composition-/
    Resource-Link-Services treiben den Save-Sync „Body treibt" (B3).
    """
    return PlaybookService(
        PgPlaybookRepository(pool),
        pool,
        PlaybookCompositionService(PgPlaybookCompositionRepository(pool)),
        PlaybookResourceLinkService(PgPlaybookResourceLinkRepository(pool)),
        PgUsageRepository(pool),
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
Service = Annotated[PlaybookService, Depends(get_playbook_service)]
StatusService = Annotated[VersionStatusService, Depends(get_version_status_service)]
ExportService = Annotated[EntityExportService, Depends(get_export_service)]
ExportFormat = Annotated[Literal["json", "markdown"], Query()]
# `against` waehlt den Diff-Vergleichsstand: 'active' oder eine Versions-Nummer.
DiffAgainst = Annotated[str, Query(max_length=20)]


@router.get("", dependencies=[Depends(enforce_mcp_read_limit)])
async def list_playbooks(
    ctx: Ctx,
    service: Service,
    response: Response,
    cursor: PageCursor,
    locale: LocaleQuery,
    tag: Annotated[str | None, Query(max_length=100)] = None,
    trigger: Annotated[str | None, Query(max_length=200)] = None,
    limit: PageLimit = DEFAULT_LIMIT,
) -> list[PlaybookRead]:
    items, next_cursor = await service.list_all(ctx, tag, trigger, limit, cursor, locale=locale)
    if next_cursor is not None:
        response.headers["X-Next-Cursor"] = next_cursor
    return items


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(enforce_entity_quota)],
)
@limiter.limit(write_limit)
async def create_playbook(
    request: Request, data: PlaybookCreate, ctx: Ctx, service: Service
) -> PlaybookRead:
    return await service.create(ctx, data)


@router.get("/tags")
async def list_playbook_tags(ctx: Ctx, service: Service, locale: LocaleQuery) -> list[str]:
    """DISTINCT-Tags des Workspaces fuer den Tag-Picker im Playbook-Form."""
    return await service.list_tags(ctx, locale)


@router.get("/triggers")
async def list_playbook_triggers(ctx: Ctx, service: Service) -> list[TriggerOverview]:
    """Welle 5: Discovery-Aggregat — deduplizierte Trigger mit Playbook-Verweis.

    Datenquelle fuer den MCP-Tool `list_triggers`, den der LLM in Templates
    nutzt (Slash-Pill `/MCP-Tools`), um vor `list_playbooks`/`fetch_playbook`
    die passende Anfrage einzugrenzen.
    """
    return await service.list_triggers(ctx)


@router.get("/{playbook_id}", dependencies=[Depends(enforce_mcp_read_limit)])
async def get_playbook(
    playbook_id: UUID, ctx: Ctx, service: Service, locale: LocaleQuery
) -> PlaybookRead:
    return await service.get(ctx, playbook_id, locale=locale)


@router.put("/{playbook_id}")
@limiter.limit(write_limit)
async def update_playbook(
    request: Request,
    playbook_id: UUID,
    data: PlaybookUpdate,
    ctx: Ctx,
    service: Service,
    locale: LocaleQuery,
) -> PlaybookRead:
    return await service.update(ctx, playbook_id, data, locale=locale)


@router.delete("/{playbook_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(write_limit)
async def delete_playbook(
    request: Request, playbook_id: UUID, ctx: Ctx, service: Service
) -> Response:
    """Hard-Delete des Playbooks (editor+).

    409, wenn Personas es verlinken oder Eltern-Composites es einbetten.
    """
    await service.delete(ctx, playbook_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{playbook_id}/export")
@limiter.limit(write_limit)
async def export_playbook(
    request: Request,
    playbook_id: UUID,
    ctx: Ctx,
    export_service: ExportService,
    response: Response,
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
    format: ExportFormat = "json",
) -> Any:
    """Einzel-Export des Playbooks als JSON (alle Versionen) oder Markdown (aktive
    Version gerendert). Lesen ist fuer Viewer offen (kein require_role); ein
    `assigned`-Agent darf aber nur ihm zugewiesene Playbooks exportieren."""
    scope = await visible_playbook_ids(pool, ctx)
    if scope is not None and playbook_id not in scope:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Playbook nicht gefunden."
        )
    if format == "markdown":
        rendered = await export_service.export_markdown(ctx.workspace_id, "playbook", playbook_id)
        if rendered is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Playbook nicht gefunden."
            )
        return Response(
            content=rendered,
            media_type="text/markdown",
            headers={
                "Content-Disposition": (f'attachment; filename="who2be-playbook-{playbook_id}.md"')
            },
        )
    bundle = await export_service.export_json(ctx.workspace_id, "playbook", playbook_id)
    if bundle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Playbook nicht gefunden."
        )
    response.headers["Content-Disposition"] = (
        f'attachment; filename="who2be-playbook-{playbook_id}.json"'
    )
    return bundle


@router.patch("/{playbook_id}/draft")
@limiter.limit(write_limit)
async def update_playbook_draft(
    request: Request,
    playbook_id: UUID,
    data: PlaybookUpdate,
    ctx: Ctx,
    service: Service,
    locale: LocaleQuery,
) -> PlaybookRead:
    """Auto-Save-Pfad — upsertet die Draft-Version ohne Versions-Increment."""
    return await service.update_draft(ctx, playbook_id, data, locale=locale)


@router.get("/{playbook_id}/rendered")
async def render_playbook(
    playbook_id: UUID, ctx: Ctx, service: Service, locale: LocaleQuery
) -> PlaybookRenderResponse:
    """Liefert den durch den Placeholder-Renderer expandierten Playbook-Body (B5).

    Track B (Nur-BlockNote): Inline-Pills (playbook/resource/…) werden
    serverseitig zu Plain-Text expandiert. Wird vom MCP-Tool `fetch_playbook`
    genutzt.
    """
    return await service.render(ctx, playbook_id, locale=locale)


@router.get("/{playbook_id}/versions")
async def list_playbook_versions(
    playbook_id: UUID, ctx: Ctx, service: Service, locale: LocaleQuery
) -> list[PlaybookVersionRead]:
    return await service.list_versions(ctx, playbook_id, locale)


@router.get("/{playbook_id}/versions/{version}")
async def get_playbook_version(
    playbook_id: UUID, version: int, ctx: Ctx, service: Service, locale: LocaleQuery
) -> PlaybookVersionRead:
    return await service.get_version(ctx, playbook_id, version, locale)


@router.post("/{playbook_id}/versions/{version}/transition")
@limiter.limit(write_limit)
async def transition_playbook_version(
    request: Request,
    playbook_id: UUID,
    version: int,
    data: VersionTransitionRequest,
    ctx: Ctx,
    status_service: StatusService,
    locale: LocaleQuery,
) -> PlaybookVersionRead:
    return await status_service.transition_playbook_version(
        ctx, playbook_id, version, data.to, data.note, locale=locale
    )


@router.post("/{playbook_id}/versions/{version}/restore", status_code=status.HTTP_201_CREATED)
@limiter.limit(write_limit)
async def restore_playbook_version(
    request: Request,
    playbook_id: UUID,
    version: int,
    ctx: Ctx,
    service: Service,
    locale: LocaleQuery,
) -> PlaybookRead:
    """Stellt Version `version` als neue Draft wieder her (non-destruktiv)."""
    return await service.restore(ctx, playbook_id, version, locale=locale)


@router.get("/{playbook_id}/versions/{version}/diff")
async def diff_playbook_version(
    playbook_id: UUID,
    version: int,
    ctx: Ctx,
    service: Service,
    locale: LocaleQuery,
    against: DiffAgainst = "active",
) -> VersionDiff:
    """Strukturierter Feld-/Block-Diff der Version gegen `against` (read-only)."""
    return await service.diff(ctx, playbook_id, version, against, locale=locale)


@router.get("/{playbook_id}/versions/{version}/provenance")
async def provenance_playbook_version(
    playbook_id: UUID,
    version: int,
    ctx: Ctx,
    status_service: StatusService,
) -> list[StatusHistoryEntry]:
    """Status-Historie dieser Version ("warum aktiv")."""
    return await status_service.provenance_playbook(ctx, playbook_id, version)
