"""Placeholder-Registry: Protocol + Resolver-Klassen + REGISTRY-Dict.

Neuen Placeholder hinzufuegen = einen Resolver + einen Eintrag im REGISTRY-
Dict. Kein weiterer Umbau am Renderer noetig.

Resolver-Regeln (aus der Spec):
- playbook:      target_id ist UUID; sucht Active-Version im Workspace.
                 Nicht gefunden -> Miss (unresolved_key gesetzt).
- resource:      analog zu playbook.
- persona-field: target_id in {"name", "description"}; bei persona_id=None,
                 unbekanntem Feld oder Persona nicht gefunden -> Miss.
- date:          target_id ist Format-Slug ("" -> ISO-8601, "human" ->
                 "31. Mai 2026"). Standardisiert auf ctx.locale = 'de-DE'.
                 Nie Miss.
- tools-overview: statische Markdown-Liste. Nie Miss.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Protocol
from uuid import UUID

import asyncpg
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Deutsche Monatsnamen (kein babel im Repo — simple Map, einfach zu warten).
_DE_MONTHS = [
    "Januar",
    "Februar",
    "März",
    "April",
    "Mai",
    "Juni",
    "Juli",
    "August",
    "September",
    "Oktober",
    "November",
    "Dezember",
]


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


# ---------------------------------------------------------------------------
# Resolver-Implementierungen
# ---------------------------------------------------------------------------


class PlaybookResolver:
    """Expandiert `target_id` (UUID) zum Body der Active-Version des Playbooks.

    Filtert auf `status='active'` — analog zu MCP-Reads im Repo. Bei nicht
    gefunden: lokalisierter Fehler-String + Miss-Key.
    """

    async def resolve(
        self,
        target_id: str,
        ctx: RenderContext,
        db: asyncpg.Connection,
    ) -> ResolveResult:
        miss_key = f"playbook:{target_id}"
        try:
            playbook_id = UUID(target_id)
        except ValueError:
            logger.warning("PlaybookResolver: ungueltige UUID '%s'", target_id)
            return ResolveResult(text="<Playbook nicht verfuegbar>", unresolved_key=miss_key)

        row = await db.fetchrow(
            """
            SELECT p.name, pv.content
              FROM playbook p
              JOIN playbook_version pv
                ON pv.playbook_id = p.id AND pv.status = 'active'
             WHERE p.id = $1
               AND p.workspace_id = $2
            """,
            playbook_id,
            ctx.workspace_id,
        )
        if row is None:
            logger.info(
                "PlaybookResolver: Playbook %s nicht gefunden (Workspace %s)",
                playbook_id,
                ctx.workspace_id,
            )
            return ResolveResult(text="<Playbook nicht verfuegbar>", unresolved_key=miss_key)

        content: dict[str, object] = dict(row["content"])
        name: str = row["name"]
        description = str(content.get("description", "")).strip()
        body = str(content.get("body", "")).strip()
        lines: list[str] = [f"### {name}"]
        if description:
            lines.append(description)
        if body:
            lines.append(body)
        return ResolveResult(text="\n".join(lines))


class ResourceResolver:
    """Expandiert `target_id` (UUID) zum Body der Active-Version der Resource.

    Filtert auf `status='active'` — analog zu MCP-Reads im Repo. Bei nicht
    gefunden: lokalisierter Fehler-String + Miss-Key.
    """

    async def resolve(
        self,
        target_id: str,
        ctx: RenderContext,
        db: asyncpg.Connection,
    ) -> ResolveResult:
        miss_key = f"resource:{target_id}"
        try:
            resource_id = UUID(target_id)
        except ValueError:
            logger.warning("ResourceResolver: ungueltige UUID '%s'", target_id)
            return ResolveResult(text="<Resource nicht verfuegbar>", unresolved_key=miss_key)

        row = await db.fetchrow(
            """
            SELECT r.name, rv.content
              FROM resource r
              JOIN resource_version rv
                ON rv.resource_id = r.id AND rv.status = 'active'
             WHERE r.id = $1
               AND r.workspace_id = $2
            """,
            resource_id,
            ctx.workspace_id,
        )
        if row is None:
            logger.info(
                "ResourceResolver: Resource %s nicht gefunden (Workspace %s)",
                resource_id,
                ctx.workspace_id,
            )
            return ResolveResult(text="<Resource nicht verfuegbar>", unresolved_key=miss_key)

        content: dict[str, object] = dict(row["content"])
        name: str = row["name"]
        # BlockNote-JSON: content.blocks Liste von Block-Dicts -> Plaintext
        raw_blocks = content.get("blocks", [])
        blocks: list[dict[str, object]] = list(raw_blocks) if isinstance(raw_blocks, list) else []
        parts: list[str] = []
        for block in blocks:
            text = _block_plain_text(block)
            if text:
                parts.append(text)
        body_text = "\n\n".join(parts).strip()
        lines: list[str] = [f"#### {name}"]
        if body_text:
            lines.append(body_text)
        return ResolveResult(text="\n".join(lines))


def _block_plain_text(block: dict[str, object]) -> str:
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
        child_text = _block_plain_text(child)
        if child_text:
            child_texts.append(child_text)

    all_parts: list[str] = []
    if text:
        all_parts.append(text)
    all_parts.extend(child_texts)
    return "\n".join(all_parts)


class PersonaFieldResolver:
    """Expandiert `target_id` zu einem Persona-Feld (`name` oder `description`).

    Miss-Faelle (alle liefern unresolved_key):
    - `ctx.persona_id` ist None
    - `target_id` ist kein bekanntes Feld
    - Persona nicht in der DB gefunden
    """

    async def resolve(
        self,
        target_id: str,
        ctx: RenderContext,
        db: asyncpg.Connection,
    ) -> ResolveResult:
        miss_key = f"persona-field:{target_id}"

        if ctx.persona_id is None:
            logger.warning(
                "PersonaFieldResolver: ctx.persona_id ist None — Miss fuer '%s'",
                target_id,
            )
            return ResolveResult(text="", unresolved_key=miss_key)

        if target_id not in ("name", "description"):
            logger.warning(
                "PersonaFieldResolver: unbekanntes Feld '%s' — Miss",
                target_id,
            )
            return ResolveResult(text="", unresolved_key=miss_key)

        if target_id == "name":
            row = await db.fetchrow(
                "SELECT name FROM persona WHERE id = $1 AND workspace_id = $2",
                ctx.persona_id,
                ctx.workspace_id,
            )
            if row is None:
                logger.warning(
                    "PersonaFieldResolver: Persona %s nicht gefunden",
                    ctx.persona_id,
                )
                return ResolveResult(text="", unresolved_key=miss_key)
            return ResolveResult(text=str(row["name"]))

        # target_id == "description": aus dem aktuellen Versions-Snapshot lesen.
        # Wir nehmen den current_version-Snapshot (analog zum Render-Endpoint),
        # nicht die active-only-Variante — der Operator kann Drafts einsehen.
        row = await db.fetchrow(
            """
            SELECT pv.content
              FROM persona p
              JOIN persona_version pv
                ON pv.persona_id = p.id AND pv.version = p.current_version
             WHERE p.id = $1
               AND p.workspace_id = $2
            """,
            ctx.persona_id,
            ctx.workspace_id,
        )
        if row is None:
            logger.warning(
                "PersonaFieldResolver: Persona %s nicht gefunden",
                ctx.persona_id,
            )
            return ResolveResult(text="", unresolved_key=miss_key)
        content: dict[str, object] = dict(row["content"])
        return ResolveResult(text=str(content.get("description", "")).strip())


class ToolsOverviewResolver:
    """Expandiert zu einer Markdown-Liste aller verfuegbaren MCP-Tools.

    Inhalt ist statisch — der MCP-Server kann seine Tool-Liste introspectieren
    (`mcp.list_tools()`), aber die docstrings sind Englisch + nicht
    domaen-freundlich. Hier pflegen wir eine kuratierte DE-Variante, die genau
    die Hinweise enthaelt, die der LLM braucht, um die Werkzeuge zur
    richtigen Zeit zu nutzen. Erweitern: neuer Eintrag in `_TOOLS`.

    `target_id` ist heute ungenutzt — Future-Use fuer Filter (z. B. nur
    Read-Tools vs. alle), aktuell wird er ignoriert.

    Nie Miss.
    """

    async def resolve(
        self,
        target_id: str,  # noqa: ARG002
        ctx: RenderContext,  # noqa: ARG002
        db: asyncpg.Connection,  # noqa: ARG002
    ) -> ResolveResult:
        lines = ["## Verfuegbare Werkzeuge", ""]
        for tool in _TOOLS:
            lines.append(f"- **{tool.signature}** — {tool.description}")
        return ResolveResult(text="\n".join(lines))


class _ToolDoc(BaseModel):
    signature: str
    description: str


_TOOLS: list[_ToolDoc] = [
    _ToolDoc(
        signature="get_persona(identifier)",
        description=(
            "Laedt deine eigene Persona inkl. Profil und verknuepfter Playbooks. "
            "Ruf das einmal zu Beginn auf, wenn du deinen Kontext brauchst."
        ),
    ),
    _ToolDoc(
        signature="list_triggers()",
        description=(
            "Tabelle aller Trigger-Keywords mit dem zugehoerigen Playbook. "
            "Nutze das, um zu erkennen, ob fuer die User-Frage ein Playbook "
            "vorgesehen ist — bevor du list_playbooks oder fetch_playbook rufst."
        ),
    ),
    _ToolDoc(
        signature="list_playbooks(tag?, trigger?)",
        description=(
            "Katalog der Playbooks im Workspace, optional gefiltert nach Tag "
            "oder Trigger. Antwortet mit Name, Beschreibung, Tags, Triggern."
        ),
    ),
    _ToolDoc(
        signature="fetch_playbook(playbook_id)",
        description=(
            "Vollstaendiger Body eines Playbooks (Schritte, Anweisungen). "
            "Folge den dort beschriebenen Schritten."
        ),
    ),
    _ToolDoc(
        signature="list_resources()",
        description=(
            "Katalog der Resources im Workspace (Knowledge-Base-Dokumente). "
            "Rufe das, wenn ein Playbook auf Resources verweist oder der User "
            "nach Hintergrundwissen fragt."
        ),
    ),
    _ToolDoc(
        signature="fetch_resource(resource_id, block_ids?)",
        description=(
            "Body einer Resource — optional gezielt einzelne Bloecke "
            "(z. B. ein einzelner Abschnitt)."
        ),
    ),
]


class DateResolver:
    """Expandiert das aktuelle Datum gemaess `target_id`-Format-Slug.

    Unterstuetzte Slugs:
    - ``""`` (leer) -> ISO-8601: "2026-05-31"
    - ``"human"``   -> "31. Mai 2026" (Deutsch, via _DE_MONTHS-Map)

    Unbekannte Slugs werden wie ``""`` behandelt; ein Warning wird geloggt.
    Kein babel im Repo — einfache Map. Nie Miss.
    """

    async def resolve(
        self,
        target_id: str,
        ctx: RenderContext,
        db: asyncpg.Connection,  # noqa: ARG002  (nicht benoetigt, aber Teil des Protokolls)
    ) -> ResolveResult:
        now = ctx.now
        if target_id == "human":
            day = now.day
            month_name = _DE_MONTHS[now.month - 1]
            year = now.year
            return ResolveResult(text=f"{day}. {month_name} {year}")
        if target_id != "":
            logger.warning(
                "DateResolver: unbekannter Format-Slug '%s' — verwende ISO-8601",
                target_id,
            )
        return ResolveResult(text=now.strftime("%Y-%m-%d"))


# ---------------------------------------------------------------------------
# Registry-Dict — Neuen Placeholder: Resolver-Klasse + Eintrag hier.
# ---------------------------------------------------------------------------

REGISTRY: dict[str, PlaceholderResolver] = {
    "playbook": PlaybookResolver(),
    "resource": ResourceResolver(),
    "persona-field": PersonaFieldResolver(),
    "date": DateResolver(),
    "tools-overview": ToolsOverviewResolver(),
}
