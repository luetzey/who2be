"""Render-Service: befuellt einen Template-Body mit Agent-Kontext.

Single Source of Truth fuer die Placeholder-Aufloesung — der UI-Copy-Button
ruft `/agents/{id}/render`, ein kuenftiges MCP-Tool nutzt denselben Service.

Sieben Placeholders (Phase 3 Runde 3 Track 3, `persona.system_prompt` ist
deprecated und NICHT mehr in der Liste):

* ``{{ persona.name }}`` — Persona-Name
* ``{{ persona.description }}`` — Persona-Description
* ``{{ persona.profile }}`` — Persona-Profilblocks als Plaintext
* ``{{ persona.tags }}`` — Komma-getrennte Tag-Liste
* ``{{ playbooks }}`` — Block ``### NAME\\nDESCRIPTION\\nBODY`` pro
  verknuepftem Playbook
* ``{{ triggers }}`` — Komma-getrennte, deduplizierte Trigger-Keywords
* ``{{ resources }}`` — deduplizierte Section-Snippets aus
  Playbook-Resource-Block-Refs

Unbekannte Placeholders bleiben im Output stehen, sind aber mit
``⚠ {{ … }}`` markiert. Der Aufrufer bekommt sie zusaetzlich strukturiert
ueber ``AgentRenderResponse.unresolved_placeholders``.

Output-Formate:

* ``plain`` (Default) — rohe Substitution, Block-Headings als ``### ``-Praefix.
* ``markdown`` — Sections via ``##``, Listen via ``-``, Trigger als Bulletliste.
* ``html`` — Markdown-Pass durch ``markdown-it-py``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import asyncpg
from fastapi import HTTPException, status
from markdown_it import MarkdownIt

from who2be_api.repositories.agent_repository import AgentRepository
from who2be_api.repositories.persona_playbook_repository import (
    PersonaPlaybookRepository,
)
from who2be_api.repositories.persona_repository import PersonaRepository
from who2be_api.repositories.playbook_resource_link_repository import (
    PlaybookResourceLinkRepository,
    block_plain_text,
    block_section_text,
)
from who2be_api.repositories.system_prompt_template_repository import (
    SystemPromptTemplateRepository,
)
from who2be_api.services.agent_service import AgentService
from who2be_api.services.placeholders import (
    RenderContext as PlaceholderRenderContext,
)
from who2be_api.services.placeholders import render_template_body
from who2be_models import (
    AgentRenderResponse,
    PersonaContent,
    PersonaVersionContent,
    PlaybookRead,
    RenderFormat,
    ResourceLinkRead,
)

# Liquid-Style ``{{ … }}`` Platzhalter. Whitespace innerhalb der Klammern wird
# beim Matching ignoriert, sodass ``{{persona.name}}`` und
# ``{{ persona.name }}`` identisch ankommen.
_PLACEHOLDER_RE = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")


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


@dataclass(frozen=True)
class _AgentRenderContext:
    persona_name: str
    persona_description: str
    persona_profile_text: str
    persona_tags: list[str]
    playbooks: list[PlaybookRead]
    triggers: list[str]
    resource_snippets: list[str]


def _persona_profile_text(content: PersonaVersionContent) -> str:
    """Wandelt den BlockNote-Profil-Inhalt einer Persona in Plaintext um.

    Wir nutzen denselben Walker wie der Resource-Section-Snippet
    (`block_plain_text`), um Konsistenz zwischen Persona-Profil und Resource-
    Bloecken zu wahren. Mehrere Bloecke werden mit Leerzeilen verbunden.
    """
    profile: PersonaContent | None = content.content
    if profile is None or not profile.blocks:
        return ""
    parts: list[str] = []
    for block in profile.blocks:
        block_dict = block.model_dump(mode="json")
        text = block_plain_text(block_dict)
        if text:
            parts.append(text)
    return "\n\n".join(parts)


def _split_triggers(playbook: PlaybookRead) -> list[str]:
    """Zerlegt die freitext-Trigger-Spalte des Playbooks in Einzel-Keywords."""
    raw = playbook.triggers
    if not raw:
        return []
    # Erlauben sowohl Komma- als auch Newline-separierte Trigger; Whitespace
    # wird getrimmt, leere Tokens fallen raus.
    parts = re.split(r"[,\n]", raw)
    return [token.strip() for token in parts if token.strip()]


def _format_playbook_block(playbook: PlaybookRead) -> str:
    """Rendert ein Playbook als ``### NAME\\nDESCRIPTION\\nBODY``-Block."""
    description = playbook.content.description.strip()
    body = playbook.content.body.strip()
    lines: list[str] = [f"### {playbook.name}"]
    if description:
        lines.append(description)
    if body:
        lines.append(body)
    return "\n".join(lines)


def _dedup_in_order(values: list[str]) -> list[str]:
    """Erhaelt die Reihenfolge, entfernt Duplikate (case-sensitive)."""
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _resource_snippets(
    links: list[ResourceLinkRead], full_blocks: dict[UUID, list[dict[str, Any]]]
) -> list[str]:
    """Sammelt Section-Snippets fuer alle Block-Refs, dedupliziert.

    'resource'-Scope-Links liefern den gesamten Resource-Inhalt als
    Plaintext-Praefix mit Resource-Name; 'block'-Scope-Links die Section
    ab dem Anker-Heading bis (exklusive) zum naechsten Heading desselben
    Levels. Duplikate (gleicher Anker in mehreren Playbooks) fallen via
    `_dedup_in_order` heraus.
    """
    snippets: list[str] = []
    for link in links:
        if not link.available:
            continue
        if link.link_scope == "resource":
            blocks = full_blocks.get(link.resource_id, [])
            text = "\n\n".join(t for block in blocks if (t := block_plain_text(block))).strip()
            if text:
                snippets.append(f"#### {link.resource_name}\n{text}")
            continue
        # block-Scope: bevorzugt vorberechnetes section_preview, sonst frisch
        # aus den vollen Bloecken ableiten.
        if link.section_preview:
            snippets.append(f"#### {link.resource_name}\n{link.section_preview.strip()}")
            continue
        if link.block_id is None:
            continue
        blocks = full_blocks.get(link.resource_id, [])
        _, text = block_section_text(blocks, link.block_id)
        if text:
            snippets.append(f"#### {link.resource_name}\n{text.strip()}")
    return _dedup_in_order(snippets)


class AgentRenderService:
    """Verknuepft Agent-Kontext und Template-Body zu einem fertigen Prompt."""

    def __init__(
        self,
        pool: asyncpg.Pool,
        agent_repo: AgentRepository,
        persona_repo: PersonaRepository,
        template_repo: SystemPromptTemplateRepository,
        persona_playbook_repo: PersonaPlaybookRepository,
        playbook_resource_link_repo: PlaybookResourceLinkRepository,
    ) -> None:
        self._pool = pool
        self._agent_repo = agent_repo
        self._persona_repo = persona_repo
        self._template_repo = template_repo
        self._persona_playbook_repo = persona_playbook_repo
        self._playbook_resource_link_repo = playbook_resource_link_repo

    async def render(
        self,
        workspace_id: UUID,
        agent_id: UUID,
        output_format: RenderFormat = "plain",
    ) -> AgentRenderResponse:
        agent = await self._agent_repo.fetch(workspace_id, agent_id)
        if agent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Agent nicht gefunden."
            )
        if AgentService.is_disabled(agent):
            raise _agent_render_inactive()
        if agent.system_prompt_template_id is None:
            # Unvollstaendige Huelle: ohne Template gibt es keinen Body.
            raise _agent_incomplete()
        active = await self._template_repo.fetch_active_content_with_format(
            workspace_id, agent.system_prompt_template_id
        )
        if active is None:
            raise _template_inactive()
        template_content, body_format = active

        # Welle 5: BlockNote-Templates laufen ueber den Placeholder-Renderer
        # (services/placeholders/), der Custom-Inline-Blocks (playbook,
        # resource, persona-field, date, tools-overview) zu echtem Text
        # expandiert. Liquid-Tokens wuerden in der JSON-Repraesentation
        # sowieso nicht greifen — daher zaehlen sie hier nicht als
        # `unresolved_placeholders`.
        if body_format == "blocknote":
            render_ctx = PlaceholderRenderContext(
                workspace_id=workspace_id,
                persona_id=agent.persona_id,
                now=datetime.now(UTC),
            )
            async with self._pool.acquire() as conn:
                substituted, unresolved_blocknote = await render_template_body(
                    template_content.body, body_format, render_ctx, conn
                )
            if output_format == "html":
                renderer = MarkdownIt("commonmark", {"html": False, "breaks": True})
                substituted = renderer.render(substituted)
            return AgentRenderResponse(
                content=substituted,
                unresolved_placeholders=unresolved_blocknote,
                format=output_format,
            )

        ctx = await self._collect_context(workspace_id, agent.persona_id)
        substituted, unresolved = _substitute(template_content.body, ctx, output_format)
        return AgentRenderResponse(
            content=substituted,
            unresolved_placeholders=unresolved,
            format=output_format,
        )

    async def _collect_context(
        self, workspace_id: UUID, persona_id: UUID | None
    ) -> _AgentRenderContext:
        persona = (
            await self._persona_repo.fetch(workspace_id, persona_id)
            if persona_id is not None
            else None
        )
        if persona is None:
            # Persona-Huelle (persona_id is None) oder zwischenzeitlich
            # geloeschte Persona: leerer Kontext, der Render laeuft weiter und
            # die Persona-Placeholder bleiben unaufgeloest.
            return _AgentRenderContext(
                persona_name="",
                persona_description="",
                persona_profile_text="",
                persona_tags=[],
                playbooks=[],
                triggers=[],
                resource_snippets=[],
            )
        # Playbooks der Persona laden (active_only=False — Render passiert im
        # JWT-Pfad, der Operator soll Drafts ebenso einsetzen koennen wie ein
        # Live-Playbook).
        playbooks = await self._persona_playbook_repo.list_linked(persona.id, active_only=False)
        triggers: list[str] = []
        for playbook in playbooks:
            triggers.extend(_split_triggers(playbook))
        triggers = _dedup_in_order(triggers)

        # Resource-Links pro Playbook ziehen + Bloecke laden, damit auch
        # 'resource'-Scope-Links sinnvolle Snippets bekommen.
        resource_links: list[ResourceLinkRead] = []
        resource_ids: set[UUID] = set()
        for playbook in playbooks:
            links = (
                await self._playbook_resource_link_repo.list_links(workspace_id, playbook.id) or []
            )
            resource_links.extend(links)
            for link in links:
                resource_ids.add(link.resource_id)
        full_blocks = await self._playbook_resource_link_repo.load_resource_blocks(
            workspace_id, list(resource_ids)
        )
        resource_snippets = _resource_snippets(resource_links, full_blocks)

        return _AgentRenderContext(
            persona_name=persona.name,
            persona_description=persona.content.description,
            persona_profile_text=_persona_profile_text(persona.content),
            persona_tags=list(persona.content.tags),
            playbooks=playbooks,
            triggers=triggers,
            resource_snippets=resource_snippets,
        )


def _resolve_placeholder(
    key: str, ctx: _AgentRenderContext, output_format: RenderFormat
) -> str | None:
    """Liefert den Klartext fuer einen bekannten Placeholder, sonst ``None``.

    Markdown- und HTML-Formate beeinflussen die Block-Strukturen
    (Playbook-Listen, Trigger-Bulletlisten, Resource-Snippets). HTML wird im
    Anschluss durch markdown-it gejagt, daher reicht es, hier die Markdown-
    Variante zu erzeugen.
    """
    if key == "persona.name":
        return ctx.persona_name
    if key == "persona.description":
        return ctx.persona_description
    if key == "persona.profile":
        return ctx.persona_profile_text
    if key == "persona.tags":
        return ", ".join(ctx.persona_tags)
    if key == "playbooks":
        if not ctx.playbooks:
            return ""
        if output_format in ("markdown", "html"):
            blocks: list[str] = []
            for playbook in ctx.playbooks:
                description = playbook.content.description.strip()
                body = playbook.content.body.strip()
                pieces: list[str] = [f"## {playbook.name}"]
                if description:
                    pieces.append(description)
                if body:
                    pieces.append(body)
                blocks.append("\n\n".join(pieces))
            return "\n\n".join(blocks)
        return "\n\n".join(_format_playbook_block(p) for p in ctx.playbooks)
    if key == "triggers":
        if not ctx.triggers:
            return ""
        if output_format in ("markdown", "html"):
            return "\n".join(f"- {trigger}" for trigger in ctx.triggers)
        return ", ".join(ctx.triggers)
    if key == "resources":
        if not ctx.resource_snippets:
            return ""
        if output_format in ("markdown", "html"):
            # Snippets stehen schon als ``#### Name\n…``; in Markdown wickeln
            # wir den Body in ein Blockquote, damit der LLM die Quelle visuell
            # vom umgebenden Template trennen kann.
            md_blocks: list[str] = []
            for snippet in ctx.resource_snippets:
                lines = snippet.split("\n")
                head, *body_lines = lines
                if body_lines:
                    quoted = "\n".join(f"> {line}" for line in body_lines)
                    md_blocks.append(f"{head}\n{quoted}")
                else:
                    md_blocks.append(head)
            return "\n\n".join(md_blocks)
        return "\n\n".join(ctx.resource_snippets)
    return None


def _substitute(
    body: str, ctx: _AgentRenderContext, output_format: RenderFormat
) -> tuple[str, list[str]]:
    """Ersetzt alle bekannten Placeholders, sammelt unbekannte als Liste.

    Unbekannte Placeholders bleiben im Output als ``⚠ {{ key }}`` stehen, damit
    der Operator sofort sieht, was unbefuellt blieb. Das macht das Markdown/
    HTML-Output bewusst etwas „lauter" — der Default-Plain-Fall behaelt das
    Verhalten ebenfalls bei.
    """
    unresolved: list[str] = []
    seen_unresolved: set[str] = set()

    def _replace(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        resolved = _resolve_placeholder(key, ctx, output_format)
        if resolved is None:
            if key not in seen_unresolved:
                seen_unresolved.add(key)
                unresolved.append(key)
            return f"⚠ {{{{ {key} }}}}"
        return resolved

    substituted = _PLACEHOLDER_RE.sub(_replace, body)
    if output_format == "html":
        renderer = MarkdownIt("commonmark", {"html": False, "breaks": True})
        substituted = renderer.render(substituted)
    return substituted, unresolved


__all__ = ["AgentRenderService"]
