"""REST-Endpunkte fuer Agents inkl. Render.

Pfad: ``/v1/workspaces/{workspace_id}/agents``.

Render-Endpoint ``GET .../{id}/render?format=plain|markdown|html`` ist die
Single Source of Truth fuer die Placeholder-Aufloesung. Default-Format
``plain`` deckt den UI-Copy-Button ohne Query-Param ab.
"""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from who2be_api.core.agent_scope import agent_read_restrict
from who2be_api.core.db import get_pool
from who2be_api.core.pagination import DEFAULT_LIMIT, PageCursor, PageLimit
from who2be_api.core.rate_limit import limiter, write_limit
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.repositories.agent_repository import PgAgentRepository
from who2be_api.repositories.persona_repository import PgPersonaRepository
from who2be_api.repositories.system_prompt_template_repository import (
    PgSystemPromptTemplateRepository,
)
from who2be_api.services.agent_fetch_rendered_service import AgentFetchRenderedService
from who2be_api.services.agent_render_service import AgentRenderService
from who2be_api.services.agent_service import AgentService
from who2be_api.services.entity_quota_service import enforce_entity_quota
from who2be_api.services.mcp_limit_service import enforce_mcp_read_limit
from who2be_models import (
    AgentCopy,
    AgentCreate,
    AgentRead,
    AgentRenderResponse,
    AgentUpdate,
    AgentWithRenderedPrompt,
    RenderFormat,
)

router = APIRouter(prefix="/agents", tags=["agents"])


def get_agent_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> AgentService:
    return AgentService(PgAgentRepository(pool))


def get_agent_render_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> AgentRenderService:
    return AgentRenderService(
        pool,
        PgAgentRepository(pool),
        PgSystemPromptTemplateRepository(pool),
    )


def get_agent_fetch_rendered_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> AgentFetchRenderedService:
    return AgentFetchRenderedService(
        pool,
        PgAgentRepository(pool),
        PgPersonaRepository(pool),
        PgSystemPromptTemplateRepository(pool),
    )


Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]
Service = Annotated[AgentService, Depends(get_agent_service)]
RenderService = Annotated[AgentRenderService, Depends(get_agent_render_service)]
FetchRenderedService = Annotated[
    AgentFetchRenderedService, Depends(get_agent_fetch_rendered_service)
]


@router.get("")
async def list_agents(
    ctx: Ctx,
    service: Service,
    response: Response,
    cursor: PageCursor,
    limit: PageLimit = DEFAULT_LIMIT,
) -> list[AgentRead]:
    items, next_cursor = await service.list_all(ctx, limit, cursor)
    if next_cursor is not None:
        response.headers["X-Next-Cursor"] = next_cursor
    return items


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(enforce_entity_quota)],
)
@limiter.limit(write_limit)
async def create_agent(
    request: Request, data: AgentCreate, ctx: Ctx, service: Service
) -> AgentRead:
    return await service.create(ctx, data)


@router.get("/{agent_id}")
async def get_agent(agent_id: UUID, ctx: Ctx, service: Service) -> AgentRead:
    return await service.get(ctx, agent_id)


@router.put("/{agent_id}")
@limiter.limit(write_limit)
async def update_agent(
    request: Request,
    agent_id: UUID,
    data: AgentUpdate,
    ctx: Ctx,
    service: Service,
) -> AgentRead:
    return await service.update(ctx, agent_id, data)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(write_limit)
async def delete_agent(request: Request, agent_id: UUID, ctx: Ctx, service: Service) -> Response:
    await service.delete(ctx, agent_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{agent_id}/copy", status_code=status.HTTP_201_CREATED)
@limiter.limit(write_limit)
async def copy_agent(
    request: Request,
    agent_id: UUID,
    data: AgentCopy,
    ctx: Ctx,
    service: Service,
) -> AgentRead:
    """Dupliziert einen Agent unter neuem Namen.

    409, wenn der Quell-Agent nicht aktivierbar ist (Persona oder Template
    fehlt ODER die Persona hat keine aktive Version) — eine solche Kopie waere
    selbst nicht einsetzbar.
    """
    return await service.copy(ctx, agent_id, data)


@router.get("/{agent_id}/render")
async def render_agent(
    agent_id: UUID,
    ctx: Ctx,
    render_service: RenderService,
    output_format: Annotated[RenderFormat, Query(alias="format")] = "plain",
) -> AgentRenderResponse:
    return await render_service.render(ctx.workspace_id, agent_id, output_format)


@router.get("/{agent_id}/rendered", dependencies=[Depends(enforce_mcp_read_limit)])
async def fetch_agent_rendered(
    agent_id: UUID,
    ctx: Ctx,
    fetch_rendered_service: FetchRenderedService,
) -> AgentWithRenderedPrompt:
    """Laedt Agent + Persona + expandierten System-Prompt (Placeholder bereits aufgeloest).

    Track B (Nur-BlockNote): Placeholder-Inline-Bloecke des BlockNote-Bodys
    werden serverseitig expandiert und als Plain-Text geliefert.

    Wird vom MCP-Tool `fetch_agent` genutzt; kann auch direkt von der UI
    fuer einen Copy-Button eingesetzt werden.
    """
    # `agent_read=none` => Tool aus (403). Der Scope `assigned`/`all` aendert hier
    # nichts: Render bleibt fuer agent-gebundene Tokens IMMER self-only (s. u.) —
    # `all` schaltet nur die Metadaten-Tools (list/get) workspace-weit frei.
    agent_read_restrict(ctx)
    # Confinement (Security-Review MEDIUM-3): Ein agent-gebundener Token darf nur
    # seinen EIGENEN Agenten rendern. `fetch_rendered` expandiert den Body mit der
    # Policy des ZIEL-Agenten — fetchte ein `assigned`-Agent einen breiter
    # gescopten (`all`) Agenten, leakte dessen System-Prompt Inhalte ausserhalb
    # des eigenen Read-Scopes. Menschen/JWT (tool_policy is None) behalten die
    # Workspace-weite Sicht (UI-Inspektion/Copy-Button).
    if ctx.tool_policy is not None and agent_id != ctx.agent_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent nicht gefunden.")
    return await fetch_rendered_service.fetch_rendered(ctx.workspace_id, agent_id)
