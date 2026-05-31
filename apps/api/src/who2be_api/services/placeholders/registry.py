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

    **Composite-aware (B1):** Hat das Playbook Kinder in `playbook_composition`,
    wird die Orchestrierungs-Sequenz angehaengt:
    - Composite-Body zuerst (wie bisher).
    - Dann eine `## Ablauf (Sub-Playbooks)`-Sektion mit nummerierten Kindern
      (nur aktive Versionen, geordnet nach `position`); inaktive/fehlende Kinder
      werden uebersprungen (kein Hard-Fail). Atomic-Pills bleiben unveraendert.
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

        # --- Composite-Erweiterung (B1) ---
        # Kinder aus playbook_composition laden (nur aktive Versionen, geordnet).
        child_rows = await db.fetch(
            """
            SELECT p.name AS child_name, pv.content AS child_content
              FROM playbook_composition pc
              JOIN playbook p ON p.id = pc.child_id
              JOIN playbook_version pv
                ON pv.playbook_id = p.id AND pv.status = 'active'
             WHERE pc.parent_id = $1
               AND pc.workspace_id = $2
             ORDER BY pc.position ASC
            """,
            playbook_id,
            ctx.workspace_id,
        )
        if child_rows:
            lines.append("\n## Ablauf (Sub-Playbooks)")
            for idx, child_row in enumerate(child_rows, start=1):
                child_content: dict[str, object] = dict(child_row["child_content"])
                child_name: str = child_row["child_name"]
                child_description = str(child_content.get("description", "")).strip()
                child_body = str(child_content.get("body", "")).strip()
                child_parts: list[str] = [f"**{child_name}**"]
                if child_description:
                    child_parts.append(child_description)
                if child_body:
                    child_parts.append(child_body)
                lines.append(f"{idx}. " + " — ".join(child_parts))

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
    """Expandiert `target_id` zu einem Persona-Feld (`name`, `description` oder `profile`).

    Targets:
    - ``name``        — Name der Persona (aus der Identity-Zeile).
    - ``description`` — Kurzbeschreibung aus dem Versions-Content (Backward-Compat).
    - ``profile``     — Volles Profil: description + BlockNote-Body (`content.blocks`)
                        + optionale Traits-Liste + Modi-Sektion (C4).
                        Liest den `current_version`-Snapshot, wie der Operator ihn sieht.

    Miss-Faelle (alle liefern unresolved_key + leeren String, damit der Render
    stabil durchlaeuft):
    - `ctx.persona_id` ist None (Agent ohne Persona — durch den NOT NULL FK in
      Migration 0023 eigentlich nicht moeglich).
    - `target_id` ist kein bekanntes Feld.
    - Persona nicht in der DB gefunden.
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

        if target_id not in ("name", "description", "profile"):
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

        # target_id in ("description", "profile"): aus dem aktuellen Versions-Snapshot.
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

        if target_id == "description":
            return ResolveResult(text=str(content.get("description", "")).strip())

        # target_id == "profile": volles Profil rendern (E1 + C4).
        return ResolveResult(text=_render_persona_profile(content))


def _render_persona_profile(content: dict[str, object]) -> str:
    """Rendert das vollstaendige Persona-Profil als Markdown-String.

    Aufbau:
    1. description (falls vorhanden)
    2. BlockNote-Body aus `content.blocks` (via `_block_plain_text`)
    3. Traits-Liste (deprecated, aber noch lesbar — nur wenn nicht leer)
    4. `## Modi`-Sektion (C4) — nur wenn `modes` vorhanden

    Gibt leeren String zurueck, wenn kein Inhalt vorhanden.
    """
    parts: list[str] = []

    # 1. description
    description = str(content.get("description", "")).strip()
    if description:
        parts.append(description)

    # 2. BlockNote-Body aus `content.content.blocks` (PersonaContent-Ebene)
    inner_content = content.get("content")
    if isinstance(inner_content, dict):
        raw_blocks = inner_content.get("blocks", [])
        blocks: list[dict[str, object]] = list(raw_blocks) if isinstance(raw_blocks, list) else []
        block_parts: list[str] = []
        for block in blocks:
            text = _block_plain_text(block)
            if text:
                block_parts.append(text)
        body_text = "\n\n".join(block_parts).strip()
        if body_text:
            parts.append(body_text)

    # 3. Traits (deprecated, aber lesbar) — nur wenn vorhanden
    raw_traits = content.get("traits", [])
    traits: list[str] = list(raw_traits) if isinstance(raw_traits, list) else []
    if traits:
        trait_lines = ["**Traits:**"]
        for trait in traits:
            trait_lines.append(f"- {trait}")
        parts.append("\n".join(trait_lines))

    # 4. Modi-Sektion (C4) — nur wenn modes vorhanden
    raw_modes = content.get("modes", [])
    modes: list[dict[str, object]] = list(raw_modes) if isinstance(raw_modes, list) else []
    if modes:
        mode_lines = ["## Modi"]
        for mode in modes:
            name = str(mode.get("name", "")).strip()
            is_default = bool(mode.get("is_default", False))
            trigger = mode.get("trigger")
            identity_add = str(mode.get("identity_add", "")).strip()
            output_style_override = str(mode.get("output_style_override", "")).strip()

            header = f"### {name}"
            if is_default:
                header += " (Default)"
            mode_lines.append(header)

            if trigger:
                mode_lines.append(f"**Trigger:** {trigger}")
            if identity_add:
                mode_lines.append(f"**Identity-Ergaenzung:** {identity_add}")
            if output_style_override:
                mode_lines.append(f"**Output-Stil:** {output_style_override}")

        parts.append("\n".join(mode_lines))

    return "\n\n".join(parts)


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
        lines.append("")
        lines.append(_TOOLS_APPLIED_NOTE)
        return ResolveResult(text="\n".join(lines))


class _ToolDoc(BaseModel):
    signature: str
    description: str


_TOOLS: list[_ToolDoc] = [
    _ToolDoc(
        signature="get_persona(identifier)",
        description=(
            "Laedt deine eigene Persona inkl. Profil und verknuepfter Playbooks. "
            "Ruf das einmal zu Beginn auf, wenn du deinen Kontext brauchst. "
            "Pruefe `content.modes`: Wenn die Persona Modi enthaelt, waehle anhand "
            "des Modus-Triggers den passenden Modus und wende dessen "
            "`identity_add` + `output_style_override` an; ohne Trigger-Match "
            "gilt der Default-Modus."
        ),
    ),
    _ToolDoc(
        signature="list_triggers()",
        description=(
            "Tabelle aller Trigger-Keywords mit dem zugehoerigen Playbook. "
            "Nutze das, um zu erkennen, ob fuer die User-Frage ein Playbook "
            "vorgesehen ist — bevor du list_playbooks oder fetch_playbook rufst. "
            "Hinweis: fest eingebettete (applied) Playbooks sind bereits im "
            "System-Prompt enthalten und erscheinen hier typischerweise nicht."
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
            "Folge den dort beschriebenen Schritten. "
            "Ist das Playbook ein Composite (Feld `composed_playbooks` nicht leer), "
            "enthaelt die Antwort eine nummerierte Sub-Playbook-Sequenz — "
            "arbeite diese der Reihe nach ab; einzelne Kinder koennen via "
            "erneutem fetch_playbook(child_id) vertieft werden."
        ),
    ),
    _ToolDoc(
        signature="list_resources(tag?)",
        description=(
            "Katalog der Resources im Workspace (Knowledge-Base-Dokumente), "
            "optional nach Tag gefiltert. Rufe das, wenn ein Playbook auf "
            "Resources verweist oder der User nach Hintergrundwissen fragt."
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

# Applied-vs-Triggered-Hinweis: Fest im System-Prompt eingebettete Playbooks
# (Pill / applied) gelten immer und sind bereits expandiert — kein MCP-Call noetig.
# Triggered Playbooks werden via list_triggers() entdeckt und nur bei
# Trigger-Match via fetch_playbook() geladen.
_TOOLS_APPLIED_NOTE = (
    "**Invocation-Wege:** Fest eingebettete Playbooks (applied, bereits im "
    "System-Prompt) gelten immer. Weitere Playbooks nur bei Trigger-Match laden "
    "— erst list_triggers(), dann fetch_playbook(id)."
)


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
