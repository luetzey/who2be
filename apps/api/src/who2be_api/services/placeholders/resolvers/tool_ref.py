"""Tool-Referenz-Resolver: expandiert `target_id` (Faehigkeits-Alias) zur
aktiven Bindung eines ExternalTool (WP-2, Blueprint
`.claude/plan/2026-07-18-1315_external-tools-tool-ref.md`).

Filtert auf `status='active'` — analog zu Playbook-/Resource-Resolver
(`resolvers/content.py`) und den MCP-Reads im Repo. Anders als dort ist
`target_id` KEINE UUID, sondern der workspace-eindeutige, stabile
Faehigkeits-Alias (`external_tool.alias`, Migration 0065): ein Re-Binding
(ein komplett neues Tool-Objekt uebernimmt denselben Alias) bricht damit
keine `tool-ref`-Referenzen — genau der Fetch-Time-Expansion-Vertrag des
Blueprints (Entscheidung 4).

Locale: wie `PlaybookResolver`/`ResourceResolver` wird NICHT nach
`ctx.locale` gefiltert — es zaehlt irgendeine aktive Version des Tools
(Default-Locale-Track, identisches Verhalten zu den bestehenden Resolvern;
mehrsprachige Tool-Bindungen sind kein WP-2-Scope).

Read-Scoping (WP-3): Policy-Domain `external_tool` (`AgentToolPolicy.
external_tool_read`). `none` blendet den Pill komplett aus (Miss,
`unresolved_key`) — analog `_scope.render_visible_playbook_ids`/
`render_visible_resource_ids`, nur ohne DB-Roundtrip (`external_tool_ref_
visible`, reines Policy-Feld). `assigned` verhaelt sich wie `all`: es gibt
fuer das ExternalTool-Aggregat (flacher Workspace-Katalog) keine sinnvolle
"nur Zugewiesenes"-Teilmenge.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import asyncpg

from who2be_api.services.placeholders._core import (
    RenderContext,
    ResolveResult,
    blocks_plain_text,
)
from who2be_api.services.placeholders._scope import external_tool_ref_visible

logger = logging.getLogger(__name__)


def _usage_notes_plain_text(usage_notes: str) -> str:
    """Serialisiert `usage_notes` (stringifiziertes BlockNote-JSON, analog
    `PlaybookContent.body`/`SystemPromptTemplateContent.body`) zu Klartext.

    Single-Source ist `blocks_plain_text` (`placeholders._core`) — dieselbe
    Funktion, die `ResourceResolver` fuer `content.blocks` nutzt. Akzeptiert
    beide BlockNote-JSON-Shapes (Top-Level-Array bzw. `{"content": [...]}`-
    Wrapper, analog `render_template_body`/`content_text.blocknote_body_text`).
    Kein gueltiges JSON (Alt-Bestand/Plain-Text-Eingabe, siehe Tests) -> Rohwert
    getrimmt zurueck. Anders als `content_text.blocknote_body_text` werden
    eingebettete Placeholder-Pills NICHT als `{{kind:target_id}}`-Token
    gerendert (kein Diff-Zweck hier) — der Default-Inline-Renderer liefert nur
    reinen Text, Pills innerhalb der usage_notes verschwinden (kein rekursives
    Aufloesen von Placeholdern innerhalb eines Placeholder-Resolvers).
    """
    stripped = usage_notes.strip()
    if not stripped:
        return ""
    try:
        parsed: Any = json.loads(stripped)
    except json.JSONDecodeError:
        return stripped
    if isinstance(parsed, list):
        blocks: list[Any] = parsed
    elif isinstance(parsed, dict):
        nested = parsed.get("content", [])
        blocks = nested if isinstance(nested, list) else []
    else:
        # Skalar-JSON (Zahl/Bool) — als Rohtext behandeln.
        return stripped
    return blocks_plain_text(blocks)


class ToolRefResolver:
    """Expandiert `target_id` (Faehigkeits-Alias) zum Anweisungsblock der
    aktiven Version des ExternalTool mit diesem Alias im Workspace.

    Kein Tool mit diesem Alias (unbekannter Alias) ODER keine aktive Version
    (nur Draft/Review) -> lokalisierter Fehler-String + Miss-Key, analog
    `PlaybookResolver`/`ResourceResolver`.
    """

    async def resolve(
        self,
        target_id: str,
        ctx: RenderContext,
        db: asyncpg.Connection,
    ) -> ResolveResult:
        miss_key = f"tool-ref:{target_id}"
        alias = target_id.strip()
        if not alias:
            logger.warning("ToolRefResolver: leerer Alias")
            return ResolveResult(text="<Tool nicht verfuegbar>", unresolved_key=miss_key)

        if not external_tool_ref_visible(ctx):
            logger.info(
                "ToolRefResolver: external_tool_read=none, Alias '%s' fuer Agent %s ausgeblendet",
                alias,
                ctx.agent_id,
            )
            return ResolveResult(text="<Tool nicht verfuegbar>", unresolved_key=miss_key)

        row = await db.fetchrow(
            """
            SELECT t.alias, tv.content
              FROM external_tool t
              JOIN external_tool_version tv
                ON tv.external_tool_id = t.id AND tv.status = 'active'
             WHERE t.alias = $1
               AND t.workspace_id = $2
            """,
            alias,
            ctx.workspace_id,
        )
        if row is None:
            logger.info(
                "ToolRefResolver: kein aktives Tool mit Alias '%s' (Workspace %s)",
                alias,
                ctx.workspace_id,
            )
            return ResolveResult(text="<Tool nicht verfuegbar>", unresolved_key=miss_key)

        content: dict[str, object] = dict(row["content"])
        display_name = str(content.get("display_name", "")).strip() or alias
        mcp_server_name = str(content.get("mcp_server_name", "")).strip()
        raw_tool_names = content.get("tool_names", [])
        tool_names: list[str] = list(raw_tool_names) if isinstance(raw_tool_names, list) else []
        usage_notes = _usage_notes_plain_text(str(content.get("usage_notes", "")))
        fallback_note = str(content.get("fallback_note") or "").strip()

        tools_part = (
            ", ".join(f"`{name}`" for name in tool_names) if tool_names else "keine gelistet"
        )
        server_clause = (
            f"Nutze den MCP-Server „{mcp_server_name}“"
            if mcp_server_name
            else "Nutze den zugeordneten MCP-Server"
        )
        header = (
            f"**Faehigkeit „{alias}“ → {display_name}.** {server_clause} (Tools: {tools_part})."
        )

        lines: list[str] = [header]
        if usage_notes:
            lines.append(usage_notes)
        if fallback_note:
            lines.append(f"Fallback: {fallback_note}")

        return ResolveResult(text="\n\n".join(lines))
