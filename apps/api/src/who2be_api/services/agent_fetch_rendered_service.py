"""Service fuer den `GET .../agents/{id}/rendered`-Endpoint (Welle 5).

Liefert einen Agent zusammen mit seiner Persona und dem bereits expandierten
System-Prompt als Plain-Text. Der Placeholder-Renderer (services/placeholders/)
wird mit einem eigenen DB-Handle aufgerufen, das aus dem Pool gezogen wird.

Warum ein eigener Endpoint (statt direkt im MCP)?
- Alle Workspace-/Auth-Gates greifen automatisch.
- Renderer braucht DB-Zugriff fuer Playbook/Resource-Lookups; im MCP-Kontext
  ist DB-Zugriff durch den API-Client gekapselt — saubere Trennung.
- MCP ruft nur diesen Endpoint auf; kein eigener DB-Pool im MCP-Server.

Hinweis zur Agent-Persona-Invariante: Migration 0023 setzt `persona_id NOT NULL`
als Composite-FK. Ein Agent ohne Persona ist auf DB-Ebene ausgeschlossen. Wir
behandeln den theoretischen `None`-Fall trotzdem defensiv (RenderContext mit
persona_id=None), um bei einer kuenftigen Schema-Aenderung kein 500 zu erzeugen.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
from fastapi import HTTPException, status

from who2be_api.repositories.agent_repository import AgentRepository
from who2be_api.repositories.persona_repository import PersonaRepository
from who2be_api.repositories.system_prompt_template_repository import (
    SystemPromptTemplateRepository,
)
from who2be_api.services.agent_service import AgentService
from who2be_api.services.placeholders import RenderContext, render_template_body
from who2be_models import AgentWithRenderedPrompt


def _agent_disabled() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Agent ist deaktiviert.",
    )


def _template_not_active() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            "Das verlinkte System-Prompt-Template hat keine aktive Version — "
            "bitte erst veroeffentlichen."
        ),
    )


def _agent_incomplete() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            "Agent ist eine unvollstaendige Huelle (Persona oder Template fehlt) — "
            "der System-Prompt kann nicht gerendert werden."
        ),
    )


class AgentFetchRenderedService:
    """Laedt einen Agent + Persona und rendert den System-Prompt via Placeholder-Renderer."""

    def __init__(
        self,
        pool: asyncpg.Pool,
        agent_repo: AgentRepository,
        persona_repo: PersonaRepository,
        template_repo: SystemPromptTemplateRepository,
    ) -> None:
        self._pool = pool
        self._agent_repo = agent_repo
        self._persona_repo = persona_repo
        self._template_repo = template_repo

    async def fetch_rendered(
        self,
        workspace_id: UUID,
        agent_id: UUID,
    ) -> AgentWithRenderedPrompt:
        """Hauptpfad: Agent holen, validieren, System-Prompt expandieren."""
        agent = await self._agent_repo.fetch(workspace_id, agent_id)
        if agent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent nicht gefunden.",
            )
        if AgentService.is_disabled(agent):
            raise _agent_disabled()
        if agent.persona_id is None or agent.system_prompt_template_id is None:
            # Eine Huelle hat keine vollstaendige Persona/Template-Kette; die
            # Antwort verlangt aber eine Persona — daher 409 statt 500.
            raise _agent_incomplete()

        # Persona laden — durch den Huellen-Guard hier garantiert gesetzt.
        persona = await self._persona_repo.fetch(workspace_id, agent.persona_id)
        if persona is None:
            # Defensive: sollte durch FK nicht eintreten, aber kein 500.
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Agent-Persona nicht gefunden (FK-Konsistenzproblem).",
            )

        # Template-Active-Content laden (Track B: Body ist immer BlockNote).
        template_content = await self._template_repo.fetch_active_content(
            workspace_id, agent.system_prompt_template_id
        )
        if template_content is None:
            raise _template_not_active()

        # Render-Kontext aufbauen. `tool_policy` des gerenderten Agenten filtert
        # den `tools-overview`-Block: der System-Prompt listet nur die Tools, die
        # genau dieser Agent nutzen darf.
        ctx = RenderContext(
            workspace_id=workspace_id,
            persona_id=agent.persona_id,
            now=datetime.now(UTC),
            tool_policy=agent.tool_policy,
        )

        # Renderer braucht eine einzelne Connection fuer DB-Lookups.
        async with self._pool.acquire() as conn:
            rendered, unresolved = await render_template_body(
                template_content.body,
                ctx,
                conn,
            )

        return AgentWithRenderedPrompt(
            id=agent.id,
            name=agent.name,
            persona=persona,
            system_prompt_rendered=rendered,
            system_prompt_template_id=agent.system_prompt_template_id,
            unresolved_placeholders=unresolved,
        )
