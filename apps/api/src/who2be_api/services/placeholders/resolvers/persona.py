"""Persona-Resolver: Feld-/Profil-Expansion, Persona-Referenz, Skills-Tabelle.

`SKILLS_ENABLED` wird bewusst als `_core.SKILLS_ENABLED` zur Laufzeit gelesen
(nicht als gebundener Import), damit Tests das Flag an einer Stelle
(`_core.SKILLS_ENABLED`) monkeypatchen koennen.
"""

from __future__ import annotations

import logging

import asyncpg

from who2be_api.services.placeholders import _core
from who2be_api.services.placeholders._core import (
    RenderContext,
    ResolveResult,
    blocks_plain_text,
    table_cell,
)

logger = logging.getLogger(__name__)


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
        return ResolveResult(text=render_persona_profile(content))


def _render_profile_body(content: dict[str, object]) -> str:
    """Rendert nur den BlockNote-Profil-Body einer Persona als Plain-Text.

    Quelle: `content.content.blocks` (die PersonaContent-Ebene). Beschreibung,
    Traits und Modi bleiben aussen vor — das ist die „nur Profil-Inhalt"-Sicht.
    Leerer Body -> leerer String.
    """
    inner_content = content.get("content")
    if not isinstance(inner_content, dict):
        return ""
    return blocks_plain_text(inner_content.get("blocks", []))


def render_persona_profile(content: dict[str, object]) -> str:
    """Rendert das vollstaendige Persona-Profil als Markdown-String.

    Aufbau:
    1. description (falls vorhanden)
    2. BlockNote-Body aus `content.blocks` (via `block_plain_text`)
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
    if _core.SKILLS_ENABLED and skills:
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
    (list[ResourceBlock]) und werden via `blocks_plain_text` zu Plain-Text.

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

        header = f"### {name}"
        if is_default:
            header += " (Default)"
        mode_lines.append(header)
        mode_lines.extend(_mode_field_lines(mode))

    return "\n".join(mode_lines)


def _mode_field_lines(mode: dict[str, object]) -> list[str]:
    """Feld-Zeilen eines einzelnen Modus (Trigger/Identity/Output/Anti/Playbook).

    Single-Source fuer die `## Modi`-Uebersicht (`_render_modes_section`) und
    die Aktiver-Modus-Sektion des Render-Pfads (`render_active_mode_section`,
    WP-F) — gleiche Labels, gleiche Reihenfolge, leere Felder entfallen.
    """
    lines: list[str] = []
    trigger = mode.get("trigger")
    identity_add = blocks_plain_text(mode.get("identity_add"))
    output_style_override = blocks_plain_text(mode.get("output_style_override"))
    anti_patterns = blocks_plain_text(mode.get("anti_patterns"))
    playbook_name = str(mode.get("playbook_name", "")).strip()

    if trigger:
        lines.append(f"**Trigger:** {trigger}")
    if identity_add:
        lines.append(f"**Identity-Ergaenzung:** {identity_add}")
    if output_style_override:
        lines.append(f"**Output-Stil:** {output_style_override}")
    if anti_patterns:
        lines.append(f"**Anti-Patterns:** {anti_patterns}")
    if playbook_name:
        lines.append(f"**Zugehoeriges Playbook:** {playbook_name}")
    return lines


def render_active_mode_section(mode: dict[str, object]) -> str:
    """Rendert die Sektion des serverseitig angewendeten Modus (WP-F).

    Wird von `PersonaService.render(mode=…)` an den gerenderten Profil-Body
    angehaengt, wenn der Aufrufer einen Modus waehlt. Nutzt dieselben
    Feld-Zeilen wie die `## Modi`-Uebersicht (`_mode_field_lines`), stellt aber
    eine Anwendungszeile voran, die die Semantik der Felder explizit macht:
    `identity_add` ergaenzt die Basis-Identitaet, `output_style_override`
    ersetzt den Basis-Output-Stil, `anti_patterns` gelten zusaetzlich.
    """
    name = str(mode.get("name", "")).strip()
    header = f"## Aktiver Modus: {name}"
    if bool(mode.get("is_default", False)):
        header += " (Default)"
    lines = [
        header,
        (
            "Dieser Modus ist aktiv: die Identity-Ergaenzung erweitert deine "
            "Basis-Identitaet, der Output-Stil ERSETZT den Basis-Output-Stil "
            "aus dem Profil, die Anti-Patterns gelten zusaetzlich."
        ),
    ]
    lines.extend(_mode_field_lines(mode))
    return "\n".join(lines)


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
            "an; ohne Trigger-Match gilt der Default-Modus. "
            f'Alternativ liefert `get_persona("{ctx.persona_id}", mode="<Modus-Name>")` '
            "das Profil bereits serverseitig im gewaehlten Modus (identity_add "
            "angehaengt, Output-Stil ersetzt, Anti-Patterns ergaenzt)."
        )
        return ResolveResult(text=text)


def render_skills_table(raw_skills: object) -> str:
    """Rendert die Skills einer Persona als Markdown-Tabelle **Skill | Hinweis**.

    Quelle: `PersonaVersionContent.skills` (`list[SkillRef{name, note}]`), als
    rohe Liste von Dicts oder Pydantic-Dumps uebergeben. Leere/namens-lose
    Eintraege werden uebersprungen. Gibt einen leeren String zurueck, wenn keine
    Skills vorhanden sind — der Aufrufer haengt die Sektion dann nicht an.

    Single-Source fuer den Agenten-Render (`get_persona`) und — gespiegelt — die
    Web-Detail-Page. Zellen escapen `|` und kollabieren Newlines via `table_cell`.

    Skills sind derzeit deaktiviert (Coming Soon, ADR-0026): bei `SKILLS_ENABLED
    is False` liefert die Funktion immer `""`, sodass nichts an den
    Briefing-Body angehaengt wird.
    """
    if not _core.SKILLS_ENABLED:
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
        lines.append(f"| {table_cell(name)} | {table_cell(note)} |")
    return "\n".join(lines)
