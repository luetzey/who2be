"""Foundation-Layer der Placeholder-Engine: Typen, Protocol, geteilte Helfer.

Diese Schicht kennt keine konkreten Resolver — sie haengt nur nach „unten"
(stdlib, pydantic, Modelle). Resolver (`resolvers/*`) und die Registry-Fassade
(`registry.py`) bauen darauf auf (Abhaengigkeiten verlaufen nach innen,
Architektur-Standards: Clean-Architecture-Abhaengigkeitsregel).

`SKILLS_ENABLED` lebt hier als Single-Source des Feature-Flags. Resolver lesen
es zur Laufzeit als `_core.SKILLS_ENABLED` (nicht als gebundenen Import), damit
Tests es an genau einer Stelle monkeypatchen koennen.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

import asyncpg
from pydantic import BaseModel

from who2be_models import AgentToolPolicy

# Skills sind vorlaeufig deaktiviert ("Coming Soon", ADR-0026). Das deskriptive
# `SkillRef`-Feld wird weder in den Agenten-Briefing-Body (`get_persona` →
# `render_skills_table`) noch in die Persona-Referenz-Aufloesung
# (`_render_persona_profile`) gerendert. Der gespeicherte `skills`-Inhalt bleibt
# im Datenmodell unangetastet (Backward-Compat). Reaktivierung: Flag auf True.
SKILLS_ENABLED = False


class RenderContext(BaseModel):
    """Laufzeit-Kontext fuer die Placeholder-Expansion.

    `persona_id` ist None, wenn der Agent keine Persona hat (unwahrscheinlich
    durch FK-Constraint, aber defensiv abgesichert). Der PersonaFieldResolver
    liefert in dem Fall einen Miss statt einer Exception.
    """

    workspace_id: UUID
    persona_id: UUID | None
    now: datetime
    locale: str = "de-DE"
    # Tool-Policy des gerenderten Agenten — filtert den `tools-overview`-Block,
    # sodass der System-Prompt nur die Tools listet, die der Agent auch nutzen
    # darf. `None` (z. B. Persona-Body-Render): nur die Read-Tools werden gezeigt
    # (Verhalten vor dem Pro-Agent-Feature).
    tool_policy: AgentToolPolicy | None = None
    # ID des gerenderten Agenten — noetig fuers Read-Scoping der Inhalts-/
    # Katalog-Resolver (`assigned`-Scope filtert eingebettete Resource-Pills und
    # den Resource-Katalog auf die sichtbare Menge). `None` ausserhalb des
    # Agent-Render-Pfads (Persona-/Preview-/Export-Render) → kein Scoping.
    agent_id: UUID | None = None


class ResolveResult(BaseModel):
    """Ergebnis eines Resolver-Aufrufs.

    `text` enthaelt den expandierten String (bei Miss: lokalisierten Fallback).
    `unresolved_key` ist gesetzt, wenn der Resolver keinen gueltigen Wert
    finden konnte, z. B. `"playbook:abc-uuid"` oder `"persona-field:name"`.
    """

    text: str
    unresolved_key: str | None = None


class PlaceholderResolver(Protocol):
    """Interface fuer alle Resolver. Ein Resolver pro Placeholder-Kind."""

    async def resolve(
        self,
        target_id: str,
        ctx: RenderContext,
        db: asyncpg.Connection,
    ) -> ResolveResult: ...


def block_plain_text(block: dict[str, object]) -> str:
    """Extrahiert Plain-Text aus einem einzelnen BlockNote-Block-Dict.

    Deckt paragraph/heading/bulletListItem/numberedListItem/checkListItem ab.
    Nested children werden rekursiv prozessiert. Inline-Content (type='text')
    wird konkateniert.
    """
    parts: list[str] = []
    inline_content: list[dict[str, object]] = block.get("content", [])  # type: ignore[assignment]
    for inline in inline_content:
        if inline.get("type") == "text":
            parts.append(str(inline.get("text", "")))
    text = "".join(parts).strip()

    children: list[dict[str, object]] = block.get("children", [])  # type: ignore[assignment]
    child_texts: list[str] = []
    for child in children:
        child_text = block_plain_text(child)
        if child_text:
            child_texts.append(child_text)

    all_parts: list[str] = []
    if text:
        all_parts.append(text)
    all_parts.extend(child_texts)
    return "\n".join(all_parts)


def table_cell(value: str) -> str:
    """Macht einen String tabellen-tauglich: Newlines zu Leerzeichen, Pipe escapen."""
    return value.replace("\n", " ").replace("\r", " ").replace("|", "\\|").strip()
