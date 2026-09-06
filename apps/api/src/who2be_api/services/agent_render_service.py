"""Render-Service: expandiert einen BlockNote-Template-Body zu einem Prompt.

Single Source of Truth fuer die Placeholder-Aufloesung — der UI-Copy-Button
ruft `/agents/{id}/render`, das MCP-Tool `fetch_agent` nutzt denselben Renderer.

Track B (Nur-BlockNote): Template-Bodies sind immer stringifiziertes BlockNote-
JSON. Die Aufloesung der Inline-Pills (playbook, resource, persona-field,
playbooks-catalog, date, tools-overview) laeuft ueber `services/placeholders/`.
Output-Formate: `plain`/`markdown` liefern den expandierten Text unveraendert,
`html` jagt ihn durch markdown-it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
from fastapi import HTTPException, status
from markdown_it import MarkdownIt

from who2be_api.core.errors import ApiError
from who2be_api.repositories.agent_repository import AgentRepository
from who2be_api.repositories.system_prompt_template_repository import (
    SystemPromptTemplateRepository,
)
from who2be_api.services.agent_language import append_language_instruction, date_locale
from who2be_api.services.agent_service import AgentService
from who2be_api.services.placeholders import (
    RenderContext as PlaceholderRenderContext,
)
from who2be_api.services.placeholders import render_template_body
from who2be_models import AgentRenderResponse, RenderFormat


def _agent_render_inactive() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Agent ist deaktiviert.",
    )


def _template_inactive() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=("Das verlinkte Template hat keine aktive Version — bitte erst veroeffentlichen."),
    )


def _agent_incomplete() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=("Agent ist eine unvollstaendige Huelle ohne Template — nichts zu rendern."),
    )


class AgentRenderService:
    """Expandiert den BlockNote-Body der aktiven Template-Version eines Agents."""

    def __init__(
        self,
        pool: asyncpg.Pool,
        agent_repo: AgentRepository,
        template_repo: SystemPromptTemplateRepository,
    ) -> None:
        self._pool = pool
        self._agent_repo = agent_repo
        self._template_repo = template_repo

    async def render(
        self,
        workspace_id: UUID,
        agent_id: UUID,
        output_format: RenderFormat = "plain",
    ) -> AgentRenderResponse:
        agent = await self._agent_repo.fetch(workspace_id, agent_id)
        if agent is None:
            raise ApiError(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent nicht gefunden.",
                reason="agent_not_found",
            )
        if AgentService.is_disabled(agent):
            raise _agent_render_inactive()
        if agent.system_prompt_template_id is None:
            # Unvollstaendige Huelle: ohne Template gibt es keinen Body.
            raise _agent_incomplete()
        template_content = await self._template_repo.fetch_active_content(
            workspace_id, agent.system_prompt_template_id
        )
        if template_content is None:
            raise _template_inactive()
        template_locale = await self._template_repo.fetch_locale(
            workspace_id, agent.system_prompt_template_id
        )

        render_ctx = PlaceholderRenderContext(
            workspace_id=workspace_id,
            persona_id=agent.persona_id,
            now=datetime.now(UTC),
            locale=date_locale(template_locale),
            tool_policy=agent.tool_policy,
            agent_id=agent.id,
        )
        async with self._pool.acquire() as conn:
            substituted, unresolved = await render_template_body(
                template_content.body, render_ctx, conn
            )
        # Sprachanweisung zentral anhaengen (WP5) — genau EIN Aufrufort pro
        # Render-Pfad, VOR der HTML-Konvertierung (damit sie mit-formatiert wird).
        substituted = append_language_instruction(substituted, template_locale)
        if output_format == "html":
            renderer = MarkdownIt("commonmark", {"html": False, "breaks": True})
            substituted = renderer.render(substituted)
        return AgentRenderResponse(
            content=substituted,
            unresolved_placeholders=unresolved,
            format=output_format,
        )


__all__ = ["AgentRenderService"]
