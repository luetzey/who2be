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
import re
from datetime import datetime
from typing import Protocol
from uuid import UUID

import asyncpg
from pydantic import BaseModel

from who2be_api.repositories.playbook_resource_link_repository import block_section_text
from who2be_models import AgentCapability, AgentToolPolicy, ReadScope

logger = logging.getLogger(__name__)

# Skills sind vorlaeufig deaktiviert ("Coming Soon", ADR-0026). Das deskriptive
# `SkillRef`-Feld wird weder in den Agenten-Briefing-Body (`get_persona` →
# `render_skills_table`) noch in die Persona-Referenz-Aufloesung
# (`_render_persona_profile`) gerendert. Der gespeicherte `skills`-Inhalt bleibt
# im Datenmodell unangetastet (Backward-Compat). Reaktivierung: Flag auf True.
SKILLS_ENABLED = False

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
    # Tool-Policy des gerenderten Agenten — filtert den `tools-overview`-Block,
    # sodass der System-Prompt nur die Tools listet, die der Agent auch nutzen
    # darf. `None` (z. B. Persona-Body-Render): nur die Read-Tools werden gezeigt
    # (Verhalten vor dem Pro-Agent-Feature).
    tool_policy: AgentToolPolicy | None = None


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
    """Expandiert `target_id` zur Active-Version einer Resource.

    Filtert auf `status='active'` — analog zu MCP-Reads im Repo. Bei nicht
    gefunden: lokalisierter Fehler-String + Miss-Key.

    **Block-Anker (B2):** `target_id` kann eine reine Resource-UUID sein oder
    ein Section-Anker der Form `"<resource_uuid>#<block_id>"`:
    - ohne `#` (oder leerer Block-Teil) → ganze Resource (Bestandsverhalten).
    - mit `#<block_id>` → nur die Section ab dem Anker-Heading (via
      `block_section_text`). Existiert der Anker-Block in der Active-Version
      nicht → sauberer Miss (leerer Body + Miss-Key).

    Der Miss-Key bleibt in allen Faellen `f"resource:{target_id}"` (inkl.
    Anker-Suffix), damit der unresolved-Tracker das Pill eindeutig wiederfindet.
    """

    async def resolve(
        self,
        target_id: str,
        ctx: RenderContext,
        db: asyncpg.Connection,
    ) -> ResolveResult:
        miss_key = f"resource:{target_id}"
        resource_part, _, block_id = target_id.partition("#")
        try:
            resource_id = UUID(resource_part)
        except ValueError:
            logger.warning("ResourceResolver: ungueltige UUID '%s'", resource_part)
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

        if block_id:
            # Section-Anker: nur die Section ab dem Anker-Heading rendern.
            section_block_ids, body_text = block_section_text(blocks, block_id)
            if not section_block_ids:
                logger.info(
                    "ResourceResolver: Anker-Block '%s' in Resource %s nicht gefunden",
                    block_id,
                    resource_id,
                )
                return ResolveResult(text="", unresolved_key=miss_key)
            lines: list[str] = [f"#### {name}"]
            if body_text:
                lines.append(body_text)
            return ResolveResult(text="\n".join(lines))

        parts: list[str] = []
        for block in blocks:
            text = _block_plain_text(block)
            if text:
                parts.append(text)
        body_text = "\n\n".join(parts).strip()
        lines = [f"#### {name}"]
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
    """Expandiert `target_id` zu einem Persona-Feld (`name`, `description`, `profile`, `modes`).

    Targets:
    - ``name``        — Name der Persona (aus der Identity-Zeile).
    - ``description`` — Kurzbeschreibung aus dem Versions-Content (Backward-Compat).
    - ``profile``     — Volles Profil: description + BlockNote-Body (`content.blocks`)
                        + optionale Traits-Liste + Modi-Sektion (C4).
                        Liest den `current_version`-Snapshot, wie der Operator ihn sieht.
    - ``profile-body``— Nur der BlockNote-Profil-Body (ohne Beschreibung/Traits/Modi).
                        Leerer Body -> leerer String (kein Miss).
    - ``modes``       — Nur die `## Modi`-Sektion (Teilmenge von `profile`). Hat die
                        Persona keine Modi, ist das Ergebnis ein leerer String (KEIN
                        Miss — Modi sind optional).

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

        if target_id not in ("name", "description", "profile", "profile-body", "modes"):
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

        if target_id == "profile-body":
            # Nur der BlockNote-Profil-Body (ohne Beschreibung/Traits/Modi).
            return ResolveResult(text=_render_profile_body(content))

        if target_id == "modes":
            # Nur die Modi-Sektion. Keine Modi -> leerer String (kein Miss).
            return ResolveResult(text=_render_modes_section(content))

        # target_id == "profile": volles Profil rendern (E1 + C4).
        return ResolveResult(text=_render_persona_profile(content))


def _render_profile_body(content: dict[str, object]) -> str:
    """Rendert nur den BlockNote-Profil-Body einer Persona als Plain-Text.

    Quelle: `content.content.blocks` (die PersonaContent-Ebene). Beschreibung,
    Traits und Modi bleiben aussen vor — das ist die „nur Profil-Inhalt"-Sicht.
    Leerer Body -> leerer String.
    """
    inner_content = content.get("content")
    if not isinstance(inner_content, dict):
        return ""
    raw_blocks = inner_content.get("blocks", [])
    blocks: list[dict[str, object]] = list(raw_blocks) if isinstance(raw_blocks, list) else []
    block_parts: list[str] = []
    for block in blocks:
        text = _block_plain_text(block)
        if text:
            block_parts.append(text)
    return "\n\n".join(block_parts).strip()


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
    body_text = _render_profile_body(content)
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
    modes_section = _render_modes_section(content)
    if modes_section:
        parts.append(modes_section)

    # 5. Skills-Sektion — nur wenn skills vorhanden UND Feature aktiv
    # (Coming Soon, ADR-0026 — derzeit deaktiviert).
    raw_skills = content.get("skills", [])
    skills: list[dict[str, object]] = list(raw_skills) if isinstance(raw_skills, list) else []
    if SKILLS_ENABLED and skills:
        skill_lines = ["## Skills"]
        for skill in skills:
            skill_name = str(skill.get("name", "")).strip()
            if not skill_name:
                continue
            note = str(skill.get("note", "")).strip()
            if note:
                skill_lines.append(f"- {skill_name}: {note}")
            else:
                skill_lines.append(f"- {skill_name}")
        # Nur anhaengen, wenn mindestens ein Skill-Eintrag (nicht nur Header) da ist.
        if len(skill_lines) > 1:
            parts.append("\n".join(skill_lines))

    return "\n\n".join(parts)


def _render_modes_section(content: dict[str, object]) -> str:
    """Rendert die `## Modi`-Sektion einer Persona als Markdown-String.

    Pro Modus: Header (mit `(Default)`-Markierung), Trigger, Identity-Ergaenzung,
    Output-Stil, Anti-Patterns und zugehoeriges Playbook — soweit vorhanden.
    `identity_add` / `output_style_override` / `anti_patterns` sind Block-Listen
    (list[ResourceBlock]) und werden via `_render_block_list` zu Plain-Text.

    Gibt einen leeren String zurueck, wenn die Persona keine Modi fuehrt — Modi
    sind optional und erzeugen in dem Fall keinen Render-Fehler.
    """
    raw_modes = content.get("modes", [])
    modes: list[dict[str, object]] = list(raw_modes) if isinstance(raw_modes, list) else []
    if not modes:
        return ""
    mode_lines = ["## Modi"]
    for mode in modes:
        if not isinstance(mode, dict):
            continue
        name = str(mode.get("name", "")).strip()
        is_default = bool(mode.get("is_default", False))
        trigger = mode.get("trigger")
        identity_add = _render_block_list(mode.get("identity_add"))
        output_style_override = _render_block_list(mode.get("output_style_override"))
        anti_patterns = _render_block_list(mode.get("anti_patterns"))
        playbook_name = str(mode.get("playbook_name", "")).strip()

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
        if anti_patterns:
            mode_lines.append(f"**Anti-Patterns:** {anti_patterns}")
        if playbook_name:
            mode_lines.append(f"**Zugehoeriges Playbook:** {playbook_name}")

    return "\n".join(mode_lines)


def _render_block_list(raw: object) -> str:
    """Rendert eine BlockNote-Block-Liste (list[ResourceBlock]) als Plain-Text.

    Pro Block wird `_block_plain_text` angewandt, leere Blocks werden
    uebersprungen, Ergebnisse mit Doppel-Newline verbunden. Nicht-Listen
    (z. B. None oder ein Alt-String, der die Koerzion nicht durchlief) liefern
    einen leeren String — so erzeugt der haeufigste Leerfall keine Zeilen.
    """
    if not isinstance(raw, list):
        return ""
    block_parts: list[str] = []
    for block in raw:
        if not isinstance(block, dict):
            continue
        text = _block_plain_text(block)
        if text:
            block_parts.append(text)
    return "\n\n".join(block_parts).strip()


class ToolsOverviewResolver:
    """Expandiert zu einer Markdown-Liste der fuer DIESEN Agenten verfuegbaren MCP-Tools.

    Inhalt ist kuratiert (DE) — der MCP-Server koennte seine Tool-Liste zwar
    introspectieren (`mcp.list_tools()`), aber die docstrings sind Englisch und
    nicht domaen-freundlich. Hier pflegen wir die Hinweise, die der LLM braucht,
    um die Werkzeuge zur richtigen Zeit zu nutzen. Erweitern: neuer Eintrag in
    `_TOOLS`.

    Pro-Agent-Filter (`ctx.tool_policy`): Es werden nur die Tools gelistet, die
    der Agent laut seiner Policy nutzen darf — Reads gemaess Scope
    (`none` blendet aus, `assigned` ergaenzt einen Hinweis), Writes gemaess
    Capability-Gruppe. Ist keine Policy gesetzt (`None`, z. B. Persona-Body),
    werden nur die Read-Tools gezeigt (Verhalten vor dem Feature).

    `target_id` bleibt ungenutzt. Nie Miss.
    """

    async def resolve(
        self,
        target_id: str,  # noqa: ARG002
        ctx: RenderContext,
        db: asyncpg.Connection,  # noqa: ARG002
    ) -> ResolveResult:
        policy = ctx.tool_policy
        lines = ["## Verfuegbare Werkzeuge", ""]
        any_write = False
        for tool in _TOOLS:
            if not tool.is_visible(policy):
                continue
            if tool.capabilities:
                any_write = True
            suffix = tool.scope_suffix(policy)
            lines.append(f"- **{tool.signature}** — {tool.description}{suffix}")
        lines.append("")
        lines.append(_TOOLS_APPLIED_NOTE)
        if any_write:
            lines.append("")
            lines.append(_TOOLS_WRITE_NOTE)
        return ResolveResult(text="\n".join(lines))


class _ToolDoc(BaseModel):
    """Ein Tool-Eintrag fuer den `tools-overview`-Block.

    Genau eines greift fuer die Sichtbarkeit:
    - `read_domain` (Read-Tool): ``"playbook"``/``"resource"`` (Scope-gefiltert)
      oder ``"persona"``/``"agent"`` (An/Aus-Flag).
    - `capabilities` (Write-Tool): nicht leer ⇒ sichtbar, sobald die Policy EINE
      davon gewaehrt.
    Read-Tools sind ohne Policy (None) sichtbar, Write-Tools nicht.
    """

    signature: str
    description: str
    read_domain: str | None = None
    capabilities: tuple[AgentCapability, ...] = ()

    def is_visible(self, policy: AgentToolPolicy | None) -> bool:
        if policy is None:
            # Vor dem Pro-Agent-Feature gab es nur Read-Tools — Verhalten halten.
            return self.read_domain is not None
        if self.capabilities:
            return any(policy.allows(cap) for cap in self.capabilities)
        if self.read_domain == "playbook":
            return policy.playbook_read != ReadScope.none
        if self.read_domain == "resource":
            return policy.resource_read != ReadScope.none
        if self.read_domain == "persona":
            return policy.persona_read
        if self.read_domain == "agent":
            return policy.agent_read
        return True

    def scope_suffix(self, policy: AgentToolPolicy | None) -> str:
        """Hinweis „(nur zugewiesene…)" bei Read-Scope `assigned`."""
        if policy is None:
            return ""
        if self.read_domain == "playbook" and policy.playbook_read == ReadScope.assigned:
            return " — **nur die dir zugewiesenen Playbooks**."
        if self.read_domain == "resource" and policy.resource_read == ReadScope.assigned:
            return " — **nur die dir zugewiesenen Resources**."
        return ""


_TOOLS: list[_ToolDoc] = [
    _ToolDoc(
        signature="get_persona(identifier)",
        read_domain="persona",
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
        read_domain="playbook",
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
        read_domain="playbook",
        description=(
            "Katalog der Playbooks im Workspace, optional gefiltert nach Tag "
            "oder Trigger. Antwortet mit Name, Beschreibung, Tags, Triggern."
        ),
    ),
    _ToolDoc(
        signature="fetch_playbook(playbook_id)",
        read_domain="playbook",
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
        read_domain="resource",
        description=(
            "Katalog der Resources im Workspace (Knowledge-Base-Dokumente), "
            "optional nach Tag gefiltert. Rufe das, wenn ein Playbook auf "
            "Resources verweist oder der User nach Hintergrundwissen fragt."
        ),
    ),
    _ToolDoc(
        signature="fetch_resource(resource_id, block_ids?)",
        read_domain="resource",
        description=(
            "Body einer Resource — optional gezielt einzelne Bloecke "
            "(z. B. ein einzelner Abschnitt)."
        ),
    ),
    _ToolDoc(
        signature="fetch_agent(agent_id)",
        read_domain="agent",
        description=(
            "Laedt einen Agenten samt Persona und fertig expandiertem "
            "System-Prompt — etwa um einen anderen Agenten zu inspizieren."
        ),
    ),
    # --- Schreib-Tools (nur sichtbar, wenn die Policy die Capability gewaehrt) ---
    _ToolDoc(
        signature="create_persona(...) / update_persona(...) / restore_persona(...)",
        capabilities=(AgentCapability.persona_write,),
        description="Personas anlegen, als neuen Draft aendern oder eine Version wiederherstellen.",
    ),
    _ToolDoc(
        signature="set_persona_playbooks(persona_id, playbook_ids)",
        capabilities=(AgentCapability.persona_write,),
        description="Die einer Persona zugeordneten Playbooks setzen (Replace-Semantik).",
    ),
    _ToolDoc(
        signature="create_playbook(...) / update_playbook(...) / restore_playbook(...)",
        capabilities=(AgentCapability.playbook_write,),
        description="Playbooks anlegen, als neuen Draft aendern oder wiederherstellen.",
    ),
    _ToolDoc(
        signature="set_playbook_resource_links(...) / set_playbook_composes(...)",
        capabilities=(AgentCapability.playbook_write,),
        description=(
            "Resource-Verweise bzw. die Sub-Playbook-Sequenz eines Composite-"
            "Playbooks setzen (Replace-Semantik)."
        ),
    ),
    _ToolDoc(
        signature="create_resource(...) / update_resource(...) / restore_resource(...)",
        capabilities=(AgentCapability.resource_write,),
        description="Resources anlegen, als neuen Draft aendern oder wiederherstellen.",
    ),
    _ToolDoc(
        signature="set_resource_sub_resources(resource_id, links)",
        capabilities=(AgentCapability.resource_write,),
        description="Die Sub-Resources einer Resource setzen (Replace-Semantik).",
    ),
    _ToolDoc(
        signature="create_agent(...) / update_agent(...) / copy_agent(...)",
        capabilities=(AgentCapability.agent_write,),
        description="Agenten anlegen, aendern oder duplizieren.",
    ),
    _ToolDoc(
        signature="transition_persona/playbook/resource(id, version, to, note?)",
        capabilities=(
            AgentCapability.promote_retire,
            AgentCapability.persona_write,
            AgentCapability.playbook_write,
            AgentCapability.resource_write,
        ),
        description=(
            "Eine Version in einen neuen Status schalten. Nach `draft`/`review` "
            "genuegt die jeweilige Schreib-Capability; nach `active`/`inactive` "
            "(veroeffentlichen/zurueckziehen) ist die Capability `promote_retire` noetig."
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

# Erscheint nur, wenn dem Agenten mindestens ein Schreib-Tool freigeschaltet ist.
_TOOLS_WRITE_NOTE = (
    "**Schreibzugriff:** Die oben gelisteten Schreib-Tools sind fuer dich "
    "freigeschaltet. Tools, die hier nicht stehen, sind fuer diesen Agenten "
    "gesperrt und werden serverseitig abgelehnt — versuche sie nicht."
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


class PersonaRefResolver:
    """Expandiert zu einer **Anweisung**, die Persona per MCP selbst zu laden.

    Im Gegensatz zum `persona-field`-Resolver (der Inhalt einbettet) rendert
    dieser Resolver eine handlungsorientierte Briefing-Zeile: Der Agent erfaehrt
    Name + ID seiner Persona und die Aufforderung, sie zu Beginn der Sitzung via
    `get_persona(...)` zu laden und ihre Modi anzuwenden. So holt sich der Agent
    den Inhalt dynamisch zur Laufzeit, statt einen Snapshot fest im Prompt zu
    tragen.

    `target_id` ist heute ungenutzt (parameterlos) — reserviert fuer kuenftige
    Varianten (z. B. Laden per Name statt ID).

    Miss-Faelle (leerer String + Miss-Key, damit der Render stabil durchlaeuft):
    - `ctx.persona_id` ist None.
    - Persona nicht in der DB gefunden.
    """

    async def resolve(
        self,
        target_id: str,
        ctx: RenderContext,
        db: asyncpg.Connection,
    ) -> ResolveResult:
        miss_key = f"persona-ref:{target_id}"
        if ctx.persona_id is None:
            logger.warning("PersonaRefResolver: ctx.persona_id ist None — Miss")
            return ResolveResult(text="", unresolved_key=miss_key)

        row = await db.fetchrow(
            "SELECT name FROM persona WHERE id = $1 AND workspace_id = $2",
            ctx.persona_id,
            ctx.workspace_id,
        )
        if row is None:
            logger.warning("PersonaRefResolver: Persona %s nicht gefunden", ctx.persona_id)
            return ResolveResult(text="", unresolved_key=miss_key)

        name = str(row["name"])
        text = (
            f"Deine Persona ist **{name}** (id: `{ctx.persona_id}`). "
            f"Lade dein vollstaendiges Profil und deine Modi zu Beginn der Sitzung via "
            f'MCP-Tool `get_persona("{ctx.persona_id}")`. '
            "Pruefe danach `content.modes`: Waehle anhand des Modus-`trigger` den "
            "passenden Modus und wende dessen `identity_add` + `output_style_override` "
            "an; ohne Trigger-Match gilt der Default-Modus."
        )
        return ResolveResult(text=text)


def _table_cell(value: str) -> str:
    """Macht einen String tabellen-tauglich: Newlines zu Leerzeichen, Pipe escapen."""
    return value.replace("\n", " ").replace("\r", " ").replace("|", "\\|").strip()


def _normalize_triggers(raw: str | None) -> str:
    """Zerlegt die freitext-Trigger-Spalte (Komma/Newline) zu ``"t1, t2"``."""
    if not raw:
        return ""
    tokens = [t.strip() for t in re.split(r"[,\n]", raw) if t.strip()]
    return ", ".join(tokens)


class PlaybooksCatalogResolver:
    """Expandiert zu einer Briefing-**Tabelle** der dem Agenten zugeordneten Playbooks.

    Quelle: die der Persona des Agenten verknuepften Playbooks (`persona_playbook`),
    jeweils Active-Version (`status='active'`) — konsistent mit den MCP-Reads und
    der Applied-Pill.

    `target_id` steuert den Filter (Pill-Setting):
    - ``"triggered"`` → nur Playbooks mit nicht-leerem Trigger-Feld.
    - ``""`` / ``"all"`` / sonstiges → alle verknuepften aktiven Playbooks.

    Spalten: **Playbook | Trigger | Aufruf | Beschreibung**. Die `Aufruf`-Spalte
    enthaelt den konkreten MCP-Call (`fetch_playbook("<id>")`), damit der Agent
    unmittelbar handlungsfaehig ist.

    Verhalten:
    - `ctx.persona_id` ist None → Miss (im Editor-Preview ohne Persona-Kontext
      zeigt das den Laufzeit-Hinweis; nie eine irrefuehrend leere Tabelle).
    - Persona vorhanden, aber keine (passenden) Playbooks → kurzer Hinweistext
      (kein Miss).
    """

    async def resolve(
        self,
        target_id: str,
        ctx: RenderContext,
        db: asyncpg.Connection,
    ) -> ResolveResult:
        miss_key = f"playbooks-catalog:{target_id}"
        if ctx.persona_id is None:
            logger.info("PlaybooksCatalogResolver: ctx.persona_id ist None — Miss")
            return ResolveResult(text="", unresolved_key=miss_key)

        only_triggered = target_id == "triggered"

        rows = await db.fetch(
            """
            SELECT p.id, p.name, p.triggers, pv.content
              FROM persona_playbook pp
              JOIN playbook p ON p.id = pp.playbook_id
              JOIN playbook_version pv
                ON pv.playbook_id = p.id AND pv.status = 'active'
             WHERE pp.persona_id = $1
               AND p.workspace_id = $2
             ORDER BY p.created_at DESC
            """,
            ctx.persona_id,
            ctx.workspace_id,
        )

        entries: list[tuple[str, str, str, str]] = []
        for row in rows:
            triggers = _normalize_triggers(row["triggers"])
            if only_triggered and not triggers:
                continue
            content: dict[str, object] = dict(row["content"]) if row["content"] else {}
            description = str(content.get("description", "")).strip()
            entries.append(
                (
                    str(row["name"]),
                    triggers,
                    f'fetch_playbook("{row["id"]}")',
                    description,
                )
            )

        if not entries:
            if only_triggered:
                return ResolveResult(
                    text="_Dir sind aktuell keine Playbooks mit Triggern zugeordnet._"
                )
            return ResolveResult(text="_Dir sind aktuell keine Playbooks zugeordnet._")

        lines = [
            "## Deine Playbooks",
            (
                "Diese Playbooks stehen dir zur Verfuegung. Wenn der Nutzer eines der "
                "Trigger-Stichworte anspricht, lade das Playbook ueber die Aufruf-Spalte "
                "(`fetch_playbook(...)`) und folge seinen Schritten."
            ),
            "",
            "| Playbook | Trigger | Aufruf | Beschreibung |",
            "|---|---|---|---|",
        ]
        for name, triggers, call, description in entries:
            lines.append(
                f"| {_table_cell(name)} | {_table_cell(triggers)} "
                f"| `{call}` | {_table_cell(description)} |"
            )
        return ResolveResult(text="\n".join(lines))


class ResourcesCatalogResolver:
    """Expandiert zu einer Briefing-**Tabelle** der aktiven Resources des Workspace.

    Quelle: alle Resources des Workspace in ihrer Active-Version
    (`status='active'`) — konsistent mit `list_resources` und den MCP-Reads.
    Im Gegensatz zur `playbooks-catalog`-Pill ist **kein** Persona-Kontext noetig
    (Resources haengen nicht an der Persona), daher gibt es hier nie einen
    Persona-Miss.

    `target_id` steuert den Filter (Pill-Setting):
    - ``""`` / ``"all"`` → alle aktiven Resources.
    - sonst → nur Resources, deren `content.tags` den Wert (exakt) enthalten.

    Spalten: **Resource | Tags | Aufruf | Beschreibung**. Die `Aufruf`-Spalte
    enthaelt den konkreten MCP-Call (`fetch_resource("<id>")`), damit der Agent
    unmittelbar handlungsfaehig ist.

    Verhalten:
    - Keine (passenden) Resources → kurzer Hinweistext (kein Miss).
    """

    async def resolve(
        self,
        target_id: str,
        ctx: RenderContext,
        db: asyncpg.Connection,
    ) -> ResolveResult:
        tag = target_id.strip()
        tag_filter = None if tag in ("", "all") else tag

        # Deckel gegen aufgeblaehte Agenten-Prompts (Self-DoS): bei mehr aktiven
        # Resources als `_CATALOG_LIMIT` werden nur die juengsten gelistet und ein
        # „… und N weitere"-Hinweis angehaengt. `+ 1`-Peek erkennt den Overflow.
        rows = await db.fetch(
            """
            SELECT r.id, r.name, rv.content
              FROM resource r
              JOIN resource_version rv
                ON rv.resource_id = r.id AND rv.status = 'active'
             WHERE r.workspace_id = $1
               AND ($2::text IS NULL OR $2 = ANY(
                   SELECT jsonb_array_elements_text(rv.content->'tags')))
             ORDER BY r.created_at DESC
             LIMIT $3
            """,
            ctx.workspace_id,
            tag_filter,
            _CATALOG_LIMIT + 1,
        )
        overflow = len(rows) > _CATALOG_LIMIT
        rows = rows[:_CATALOG_LIMIT]

        entries: list[tuple[str, str, str, str]] = []
        for row in rows:
            content: dict[str, object] = dict(row["content"]) if row["content"] else {}
            description = str(content.get("description", "")).strip()
            raw_tags = content.get("tags", [])
            tags_list = [str(t) for t in raw_tags] if isinstance(raw_tags, list) else []
            entries.append(
                (
                    str(row["name"]),
                    ", ".join(tags_list),
                    f'fetch_resource("{row["id"]}")',
                    description,
                )
            )

        if not entries:
            if tag_filter is not None:
                return ResolveResult(text=f"_Keine aktiven Resources mit dem Tag „{tag_filter}“._")
            return ResolveResult(text="_Im Workspace gibt es aktuell keine aktiven Resources._")

        scope_note = (
            f"Wissens-Resources mit dem Tag „{tag_filter}“."
            if tag_filter is not None
            else "Diese Wissens-Resources stehen dir im Workspace zur Verfuegung."
        )
        lines = [
            "## Verfuegbare Resources",
            (
                f"{scope_note} Lade eine Resource ueber die Aufruf-Spalte "
                "(`fetch_resource(...)`), wenn du ihren Inhalt brauchst."
            ),
            "",
            "| Resource | Tags | Aufruf | Beschreibung |",
            "|---|---|---|---|",
        ]
        for name, tags_str, call, description in entries:
            lines.append(
                f"| {_table_cell(name)} | {_table_cell(tags_str)} "
                f"| `{call}` | {_table_cell(description)} |"
            )
        if overflow:
            lines.append("")
            lines.append(
                f"_… und weitere — gefiltert auf die {_CATALOG_LIMIT} juengsten Resources. "
                "Nutze `list_resources(tag?)` fuer den vollstaendigen Katalog._"
            )
        return ResolveResult(text="\n".join(lines))


# Obergrenze fuer Katalog-Tabellen (DoS-Schutz gegen riesige Agenten-Prompts).
_CATALOG_LIMIT = 100


def render_skills_table(raw_skills: object) -> str:
    """Rendert die Skills einer Persona als Markdown-Tabelle **Skill | Hinweis**.

    Quelle: `PersonaVersionContent.skills` (`list[SkillRef{name, note}]`), als
    rohe Liste von Dicts oder Pydantic-Dumps uebergeben. Leere/namens-lose
    Eintraege werden uebersprungen. Gibt einen leeren String zurueck, wenn keine
    Skills vorhanden sind — der Aufrufer haengt die Sektion dann nicht an.

    Single-Source fuer den Agenten-Render (`get_persona`) und — gespiegelt — die
    Web-Detail-Page. Zellen escapen `|` und kollabieren Newlines via `_table_cell`.

    Skills sind derzeit deaktiviert (Coming Soon, ADR-0026): bei `SKILLS_ENABLED
    is False` liefert die Funktion immer `""`, sodass nichts an den
    Briefing-Body angehaengt wird.
    """
    if not SKILLS_ENABLED:
        return ""
    skills: list[dict[str, object]] = list(raw_skills) if isinstance(raw_skills, list) else []
    rows: list[tuple[str, str]] = []
    for skill in skills:
        if not isinstance(skill, dict):
            continue
        name = str(skill.get("name", "")).strip()
        if not name:
            continue
        note = str(skill.get("note", "")).strip()
        rows.append((name, note))
    if not rows:
        return ""
    lines = ["## Skills", "", "| Skill | Hinweis |", "|---|---|"]
    for name, note in rows:
        lines.append(f"| {_table_cell(name)} | {_table_cell(note)} |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Registry-Dict — Neuen Placeholder: Resolver-Klasse + Eintrag hier.
# ---------------------------------------------------------------------------

REGISTRY: dict[str, PlaceholderResolver] = {
    "playbook": PlaybookResolver(),
    "resource": ResourceResolver(),
    "persona-field": PersonaFieldResolver(),
    "persona-ref": PersonaRefResolver(),
    "playbooks-catalog": PlaybooksCatalogResolver(),
    "resources-catalog": ResourcesCatalogResolver(),
    "date": DateResolver(),
    "tools-overview": ToolsOverviewResolver(),
}
