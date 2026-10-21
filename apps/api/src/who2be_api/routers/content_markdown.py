"""Markdown-Schreibweg fuer Agenten (ADR-0058 §5.1, §6, Paket P2).

Ein Router fuer alle fuenf Elementarten statt fuenf (ADR-0058 §9 P2.3):

- `GET  …/{entity_type}/{id}/markdown?format=source` liest die Quellfassung
  mit dem Konflikt-Token `base_rev` im Kopf.
- `GET  …/{entity_type}/{id}/versions/{version}/markdown?format=source` liest
  einen Versions-Snapshot als Vorlage fuer eine Wiederherstellung.
- `POST …/{entity_type}/markdown` legt ein Element aus Markdown an.
- `PUT  …/{entity_type}/{id}/markdown` schreibt den Vollstand (PUT-Semantik
  wie `update_*`).
- `PATCH …/{entity_type}/{id}/markdown` aendert einen Abschnitt (Anker) oder
  ein Feld im offenen Draft; `base_rev` ist Pflicht.

Die Routen rufen dieselben Service-Methoden wie der JSON-Weg; Rechte,
Tag-Scope, verwaltete Inhalte und Versionsregeln gelten dadurch unveraendert.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query, Request, status

from who2be_api.core.db import get_pool
from who2be_api.core.rate_limit import limiter, write_limit
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.repositories.external_tool_repository import PgExternalToolRepository
from who2be_api.repositories.persona_repository import PgPersonaRepository
from who2be_api.repositories.playbook_repository import PgPlaybookRepository
from who2be_api.repositories.resource_repository import PgResourceRepository
from who2be_api.repositories.system_prompt_template_repository import (
    PgSystemPromptTemplateRepository,
)
from who2be_api.routers.external_tools import get_external_tool_service
from who2be_api.routers.personas import get_persona_service
from who2be_api.routers.playbooks import get_playbook_service
from who2be_api.routers.resources import get_resource_service
from who2be_api.routers.system_prompts import get_template_service
from who2be_api.services.content_markdown_service import ContentMarkdownService
from who2be_api.services.entity_quota_service import enforce_entity_quota
from who2be_api.services.mcp_limit_service import enforce_mcp_read_limit
from who2be_models.content_markdown import (
    ContentEdit,
    MarkdownCreate,
    MarkdownEntityType,
    MarkdownSource,
    MarkdownWrite,
    MarkdownWriteResult,
)

router = APIRouter(tags=["content-markdown"])

#: Elementarten mit Entity-Kontingent beim Anlegen (ohne System-Prompt, der
#: im JSON-Weg auch nicht gezaehlt wird).
QuotaEntityType = Literal["personas", "playbooks", "resources", "external_tools"]

_CONFLICT_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_409_CONFLICT: {
        "description": (
            "`version_conflict` (base_rev veraltet; `params.current_version`, "
            "`params.current_base_rev`), `draft_conflict` oder `review_conflict`."
        )
    },
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        "description": (
            "`markdown_unsupported`, `block_not_representable`, `anchor_unknown`, "
            "`anchor_duplicate` (`params.field`, `params.line`, `params.block_id`, "
            "`params.construct`) oder Validierungsfehler."
        )
    },
}


def get_content_markdown_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> ContentMarkdownService:
    """FastAPI-Dependency: die fuenf Services wie in ihren Routern verdrahtet."""
    return ContentMarkdownService(
        pool,
        personas=get_persona_service(pool),
        playbooks=get_playbook_service(pool),
        resources=get_resource_service(pool),
        system_prompts=get_template_service(pool),
        external_tools=get_external_tool_service(pool),
        base_rev_repos={
            "personas": PgPersonaRepository(pool),
            "playbooks": PgPlaybookRepository(pool),
            "resources": PgResourceRepository(pool),
            "system-prompts": PgSystemPromptTemplateRepository(pool),
            "external_tools": PgExternalToolRepository(pool),
        },
    )


Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]
Service = Annotated[ContentMarkdownService, Depends(get_content_markdown_service)]
SourceFormat = Annotated[
    Literal["source"],
    Query(description="Quellfassung: Markdown-Normalform mit Ankern und Pill-Tokens."),
]


@router.get(
    "/{entity_type}/{entity_id}/markdown",
    dependencies=[Depends(enforce_mcp_read_limit)],
)
async def get_markdown_source(
    entity_type: MarkdownEntityType,
    entity_id: UUID,
    ctx: Ctx,
    service: Service,
    format: SourceFormat = "source",
) -> MarkdownSource:
    """Quellfassung (`format=source`, ADR-0058 §5.1 B) mit `base_rev` im Kopf.

    `base_rev` ist `null`, wenn die gelieferte Version nicht das Schreibziel
    ist (Leser sieht nur die aktive Version, waehrend ein Draft offen ist).
    """
    return await service.source(ctx, entity_type, entity_id)


@router.get(
    "/{entity_type}/{entity_id}/versions/{version}/markdown",
    dependencies=[Depends(enforce_mcp_read_limit)],
)
async def get_version_markdown_source(
    entity_type: MarkdownEntityType,
    entity_id: UUID,
    version: int,
    ctx: Ctx,
    service: Service,
    format: SourceFormat = "source",
) -> MarkdownSource:
    """Quellfassung eines Versions-Snapshots (Vorlage fuer eine Wiederherstellung)."""
    return await service.version_source(ctx, entity_type, entity_id, version)


# Der System-Prompt hat eine eigene Anlege-Route: der JSON-Weg zaehlt ihn nicht
# gegen das Entity-Kontingent, der Markdown-Weg auch nicht. Registriert vor
# der generischen Route, damit `system-prompts` nicht dort landet.
@router.post(
    "/system-prompts/markdown",
    status_code=status.HTTP_201_CREATED,
    responses=_CONFLICT_RESPONSES,
)
@limiter.limit(write_limit)
async def create_system_prompt_markdown(
    request: Request, data: MarkdownCreate, ctx: Ctx, service: Service
) -> MarkdownWriteResult:
    """Legt einen System-Prompt aus Markdown an (ohne Entity-Kontingent wie der JSON-Weg)."""
    return await service.create(ctx, "system-prompts", data)


@router.post(
    "/{entity_type}/markdown",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(enforce_entity_quota)],
    responses=_CONFLICT_RESPONSES,
)
@limiter.limit(write_limit)
async def create_markdown(
    request: Request,
    entity_type: QuotaEntityType,
    data: MarkdownCreate,
    ctx: Ctx,
    service: Service,
) -> MarkdownWriteResult:
    """Legt ein Element aus Markdown an. Anker sind beim Anlegen unbekannt."""
    return await service.create(ctx, entity_type, data)


@router.put("/{entity_type}/{entity_id}/markdown", responses=_CONFLICT_RESPONSES)
@limiter.limit(write_limit)
async def put_markdown(
    request: Request,
    entity_type: MarkdownEntityType,
    entity_id: UUID,
    data: MarkdownWrite,
    ctx: Ctx,
    service: Service,
) -> MarkdownWriteResult:
    """Vollstand per Markdown; PUT-Semantik wie `update_*` (offener Draft = 409).

    Ist `base_rev` gesetzt, wird er unter der Zeilensperre geprueft.
    """
    return await service.put(ctx, entity_type, entity_id, data)


@router.patch("/{entity_type}/{entity_id}/markdown", responses=_CONFLICT_RESPONSES)
@limiter.limit(write_limit)
async def patch_markdown(
    request: Request,
    entity_type: MarkdownEntityType,
    entity_id: UUID,
    data: ContentEdit,
    ctx: Ctx,
    service: Service,
) -> MarkdownWriteResult:
    """Teilaenderung an einem Ueberschriften-Anker oder Feld (ADR-0058 §6.2).

    Schreibt in den offenen Draft, sonst entsteht einer. `base_rev` ist Pflicht.
    """
    return await service.edit(ctx, entity_type, entity_id, data)
