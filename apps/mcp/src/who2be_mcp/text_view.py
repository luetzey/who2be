"""Markdown-Darstellung der lesenden MCP-Antworten (ADR-0056, Option B).

Unter `format="text"` liefern die lesenden Werkzeuge kein JSON-Objekt, sondern
ein Markdown-Dokument: oben ein kompakter Kopf mit den Metadaten, die ein
Agent fuer Folgeaufrufe braucht (id, Version, Status, Sprache, Tags, …),
darunter der Inhalt als Klartext. Weil die Antwort ein String ist, kommt sie
ohne JSON-Escaping beim Modell an (kein `\\n`, kein `\\"`).

Dieses Modul rendert nur. Es ruft keine API und kennt keine Werkzeuge; die
Werkzeuge in `server.py` reichen ihre bereits geladenen Modelle herein. Das
haelt die Darstellung ohne Netz testbar und erlaubt es, die Werkzeuge einzeln
umzustellen.

Woher der Text kommt:

- Gerenderte Bodies (`body_rendered`, `system_prompt_rendered`) stammen aus
  dem Server-Render und werden unveraendert uebernommen.
- Alles andere (Resource-Bloecke, Template-Bodies, `usage_notes`,
  Modus-Felder, Versions-Snapshots) laeuft ueber die kanonische
  Klartext-Serialisierung `who2be_models.blocknote_text`. Placeholder-Pills
  erscheinen dort als `{{kind:target_id}}`.

Jedes Dokument traegt den Schreiber-Hinweis `FULL_FORMAT_HINT`: die
`update_*`-Werkzeuge ersetzen den Inhalt vollstaendig (PUT), und die Vorlage
dafuer liefert nur `format="full"`.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from who2be_mcp.client import AnyVersionRead
from who2be_models import (
    AgentWithRenderedPrompt,
    ExternalToolContent,
    ExternalToolRead,
    PersonaRead,
    PersonaVersionContent,
    PlaybookContent,
    PlaybookRead,
    ResourceBlockAnchor,
    ResourceContent,
    ResourceLinkRead,
    ResourceRead,
    SystemPromptTemplateContent,
    SystemPromptTemplateRead,
    VersionDiff,
)
from who2be_models.blocknote_text import (
    blocknote_body_text,
    blocks_plain_text,
    placeholder_token_inline,
)
from who2be_models.persona import PersonaMode
from who2be_models.resource import ResourceBlock

FULL_FORMAT_HINT = (
    '> Lesefassung. Vorlage fuer `update_*` (PUT, ersetzt den Inhalt): `format="full"`.'
)


# ---------------------------------------------------------------------------
# Bausteine
# ---------------------------------------------------------------------------


def _meta(pairs: Iterable[tuple[str, object]]) -> str:
    """Metadaten-Kopf als `- schluessel: wert`-Liste; leere Werte entfallen.

    Listen werden komma-separiert, `None`/leere Strings/leere Listen fallen
    weg, damit der Kopf nur traegt, was es gibt.
    """
    lines: list[str] = []
    for key, value in pairs:
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            if not value:
                continue
            rendered = ", ".join(str(item) for item in value)
        else:
            rendered = str(value).strip()
            if not rendered:
                continue
        lines.append(f"- {key}: {rendered}")
    return "\n".join(lines)


def _join(parts: Iterable[str]) -> str:
    """Verbindet nicht-leere Teile mit Leerzeile; Ergebnis endet mit Newline."""
    return "\n\n".join(part.strip("\n") for part in parts if part and part.strip()) + "\n"


def _section(title: str, body: str, level: int = 2) -> str:
    """Ueberschrift + Inhalt; leerer Inhalt → leerer Abschnitt (entfaellt)."""
    if not body.strip():
        return ""
    return f"{'#' * level} {title}\n\n{body.strip()}"


def _blocks_text(blocks: Sequence[ResourceBlock]) -> str:
    """Block-Modelle → Klartext (Pills als `{{kind:target_id}}`)."""
    raw = [block.model_dump(mode="json") for block in blocks]
    return blocks_plain_text(raw, placeholder_token_inline)


def _status(value: object) -> str:
    """Enum-Status als Klartext (`active` statt `VersionStatus.active`)."""
    return str(getattr(value, "value", value))


# ---------------------------------------------------------------------------
# Inhalts-Formen (je Content-Modell genau eine Darstellung)
# ---------------------------------------------------------------------------


def _mode_text(mode: PersonaMode, level: int) -> str:
    title = f"{mode.name} (Default)" if mode.is_default else mode.name
    fields = [
        ("Trigger", mode.trigger or ""),
        ("Identitaet ergaenzt", _blocks_text(mode.identity_add)),
        ("Output-Stil ersetzt", _blocks_text(mode.output_style_override)),
        ("Anti-Patterns", _blocks_text(mode.anti_patterns)),
        ("Playbook", mode.playbook_name),
    ]
    lines = [f"**{label}:** {value.strip()}" for label, value in fields if value.strip()]
    return _section(title, "\n\n".join(lines) or "-", level)


def _modes_text(modes: Sequence[PersonaMode], level: int) -> str:
    if not modes:
        return ""
    rendered = "\n\n".join(_mode_text(mode, level + 1) for mode in modes)
    return f"{'#' * level} Modi\n\n{rendered}"


def persona_content_text(
    content: PersonaVersionContent, *, profile: str | None = None, level: int = 2
) -> str:
    """Persona-Inhalt: Beschreibung, Profil, Traits, Modi.

    `profile` ist der bereits gerenderte Profiltext (`body_rendered`); fehlt
    er (Versions-Snapshot), wird das Profil aus den Bloecken serialisiert.
    """
    if profile is None:
        inner = content.content
        profile = _blocks_text(inner.blocks) if inner is not None else ""
    traits = "\n".join(f"- {trait}" for trait in content.traits)
    return _join(
        [
            content.description,
            _section("Profil", profile, level),
            _section("Traits", traits, level),
            _modes_text(content.modes, level),
        ]
    )


def playbook_content_text(content: PlaybookContent, level: int = 2) -> str:
    """Playbook-Inhalt aus dem Snapshot: Beschreibung + Body."""
    return _join(
        [
            content.description,
            _section("Prozedur", blocknote_body_text(content.body), level),
        ]
    )


def resource_content_text(content: ResourceContent, level: int = 2) -> str:
    """Resource-Inhalt: Beschreibung + Bloecke."""
    return _join([content.description, _section("Inhalt", _blocks_text(content.blocks), level)])


def system_prompt_content_text(content: SystemPromptTemplateContent, level: int = 2) -> str:
    """System-Prompt-Template-Inhalt: Beschreibung + Body (Pills als Token)."""
    return _join([content.description, _section("Body", blocknote_body_text(content.body), level)])


def external_tool_content_text(content: ExternalToolContent, level: int = 2) -> str:
    """Externe Tool-Bindung: Felder + Nutzungshinweise."""
    head = _meta(
        [
            ("Anzeigename", content.display_name),
            ("MCP-Server", content.mcp_server_name),
            ("Tools", content.tool_names),
            ("Tags", content.tags),
        ]
    )
    return _join(
        [
            head,
            _section("Nutzungshinweise", blocknote_body_text(content.usage_notes), level),
            _section("Fallback", content.fallback_note or "", level),
        ]
    )


def _version_content_text(version: AnyVersionRead, level: int) -> str:
    content = version.content
    if isinstance(content, PersonaVersionContent):
        return persona_content_text(content, level=level)
    if isinstance(content, PlaybookContent):
        return playbook_content_text(content, level)
    if isinstance(content, ResourceContent):
        return resource_content_text(content, level)
    if isinstance(content, SystemPromptTemplateContent):
        return system_prompt_content_text(content, level)
    return external_tool_content_text(content, level)


# ---------------------------------------------------------------------------
# Dokumente je Werkzeug
# ---------------------------------------------------------------------------


def persona_text(
    persona: PersonaRead,
    *,
    body_rendered: str,
    playbooks: Sequence[PlaybookRead],
    mode: str | None,
) -> str:
    """`get_persona`: Kopf, Profil (gerendert), Modi, verknuepfte Playbooks."""
    head = _meta(
        [
            ("id", persona.id),
            ("version", persona.current_version),
            ("status", _status(persona.current_status)),
            ("locale", persona.locale),
            ("tags", persona.content.tags),
            ("aktiver Modus", mode),
        ]
    )
    catalog = "\n".join(
        f"- {playbook.name} (`{playbook.id}`)"
        + (f" — Trigger: {playbook.triggers}" if playbook.triggers else "")
        for playbook in playbooks
    )
    return _join(
        [
            f"# Persona: {persona.name}",
            FULL_FORMAT_HINT,
            head,
            persona_content_text(persona.content, profile=body_rendered),
            _section("Playbooks", catalog),
        ]
    )


def agent_text(agent: AgentWithRenderedPrompt) -> str:
    """`fetch_agent`: Kopf + gerenderter System-Prompt (enthaelt das Profil)."""
    head = _meta(
        [
            ("id", agent.id),
            ("persona", f"{agent.persona.name} ({agent.persona.id})"),
            ("system_prompt_template_id", agent.system_prompt_template_id),
            ("locale", agent.locale),
            ("ungeloeste Platzhalter", agent.unresolved_placeholders),
        ]
    )
    return _join(
        [
            f"# Agent: {agent.name}",
            FULL_FORMAT_HINT,
            head,
            _section("System-Prompt", agent.system_prompt_rendered),
            _modes_text(agent.persona.content.modes, 2),
        ]
    )


def _playbook_head(playbook: PlaybookRead) -> str:
    return _meta(
        [
            ("id", playbook.id),
            ("version", playbook.current_version),
            ("status", _status(playbook.current_status)),
            ("locale", playbook.locale),
            ("typ", playbook.type),
            ("tags", playbook.tags),
            ("trigger", playbook.triggers),
            ("composite", "ja" if playbook.is_composite else None),
            ("kinder", [f"{child.name} ({child.id})" for child in playbook.compose_children]),
        ]
    )


def playbook_list_text(playbooks: Sequence[PlaybookRead]) -> str:
    """`list_playbooks`: je Eintrag Kopf + Beschreibung, kein Body."""
    entries = [
        _join([f"## {playbook.name}", _playbook_head(playbook), playbook.content.description])
        for playbook in playbooks
    ]
    return _join([f"# Playbooks ({len(playbooks)})", FULL_FORMAT_HINT, *entries])


def _sections_text(sections: Sequence[ResourceBlockAnchor]) -> str:
    return "\n".join(
        f"{'  ' * max(section.level - 1, 0)}- {section.text} (`{section.block_id}`)"
        for section in sections
    )


def _links_text(links: Sequence[ResourceLinkRead]) -> str:
    lines: list[str] = []
    for link in links:
        target = f"{link.resource_name} (`{link.resource_id}`)"
        if link.block_id:
            target += f", Block `{link.block_id}`"
        flags: list[str] = [link.embedding_mode]
        if not link.available:
            flags.append("nicht verfuegbar")
        lines.append(f"- {target} [{', '.join(flags)}]")
    return "\n".join(lines)


def playbook_text(
    playbook: PlaybookRead,
    *,
    body_rendered: str | None,
    sections: Sequence[ResourceBlockAnchor],
    linked_blocks: Sequence[ResourceLinkRead] = (),
    linked_resources: Sequence[ResourceRead] = (),
    composed_playbooks: Sequence[PlaybookRead] = (),
) -> str:
    """`fetch_playbook`: Kopf, Gliederung, Prozedur, Verweise, Kinder.

    `body_rendered=None` ist der `outline`-Zuschnitt: Gliederung ohne Prozedur.
    Inline-Resources und Sub-Playbooks stehen als eigene Abschnitte darunter,
    ebenfalls als Klartext.
    """
    composed = [
        _join(
            [
                f"### {child.name} (`{child.id}`)",
                child.content.description,
                blocknote_body_text(child.content.body),
            ]
        )
        for child in composed_playbooks
    ]
    inline = [
        _join(
            [
                f"### {resource.name} (`{resource.id}`)",
                resource_content_text(resource.content, level=4),
            ]
        )
        for resource in linked_resources
    ]
    return _join(
        [
            f"# Playbook: {playbook.name}",
            FULL_FORMAT_HINT,
            _playbook_head(playbook),
            playbook.content.description,
            _section("Gliederung (block_id fuer block_ids)", _sections_text(sections)),
            _section("Prozedur", body_rendered or ""),
            _section("Verweise", _links_text(linked_blocks)),
            _section("Eingebettete Resources", "\n\n".join(inline)),
            _section("Sub-Playbooks (in dieser Reihenfolge)", "\n\n".join(composed)),
        ]
    )


def resource_text(resource: ResourceRead) -> str:
    """`fetch_resource`: Kopf, Inhalt, Sub-Resource-Pointer, Inline-Kinder."""
    head = _meta(
        [
            ("id", resource.id),
            ("slug", resource.slug),
            ("version", resource.current_version),
            ("status", _status(resource.current_status)),
            ("locale", resource.locale),
            ("tags", resource.content.tags),
        ]
    )
    subs = "\n".join(
        f"- {sub.name} [{sub.link_scope}, {sub.embedding_mode}]"
        + (f", Block `{sub.block_id}`" if sub.block_id else "")
        + f": `{sub.fetch_call}`"
        for sub in resource.sub_resources
    )
    inline = [
        _join(
            [
                f"### {child.name} (`{child.id}`)",
                resource_content_text(child.content, level=4),
            ]
        )
        for child in resource.inline_sub_resources
    ]
    return _join(
        [
            f"# Resource: {resource.name}",
            FULL_FORMAT_HINT,
            head,
            resource_content_text(resource.content),
            _section("Sub-Resources", subs),
            _section("Eingebettete Sub-Resources", "\n\n".join(inline)),
        ]
    )


def _system_prompt_head(template: SystemPromptTemplateRead) -> str:
    return _meta(
        [
            ("id", template.id),
            ("slug", template.slug),
            ("version", template.current_version),
            ("status", _status(template.current_status)),
            ("locale", template.locale),
            ("agenten", template.agent_count),
        ]
    )


def system_prompt_text(template: SystemPromptTemplateRead) -> str:
    """`get_system_prompt`: Kopf + Body (Pills als `{{kind:target_id}}`)."""
    return _join(
        [
            f"# System-Prompt: {template.name}",
            FULL_FORMAT_HINT,
            _system_prompt_head(template),
            system_prompt_content_text(template.content),
        ]
    )


def system_prompt_list_text(templates: Sequence[SystemPromptTemplateRead]) -> str:
    """`list_system_prompts`: je Eintrag Kopf + Beschreibung, kein Body."""
    entries = [
        _join([f"## {t.name}", _system_prompt_head(t), t.content.description]) for t in templates
    ]
    return _join([f"# System-Prompts ({len(templates)})", FULL_FORMAT_HINT, *entries])


def _external_tool_head(tool: ExternalToolRead) -> str:
    return _meta(
        [
            ("id", tool.id),
            ("alias", tool.alias),
            ("version", tool.current_version),
            ("status", _status(tool.current_status)),
            ("locale", tool.locale),
        ]
    )


def external_tool_text(tool: ExternalToolRead) -> str:
    """`get_external_tool`: Kopf, Felder, Nutzungshinweise als Klartext."""
    return _join(
        [
            f"# Externes Tool: {tool.name}",
            FULL_FORMAT_HINT,
            _external_tool_head(tool),
            external_tool_content_text(tool.content),
        ]
    )


def external_tool_list_text(tools: Sequence[ExternalToolRead]) -> str:
    """`list_external_tools`: je Eintrag Kopf + Felder, ohne Nutzungshinweise."""
    entries = [
        _join(
            [
                f"## {tool.name}",
                _external_tool_head(tool),
                _meta(
                    [
                        ("Anzeigename", tool.content.display_name),
                        ("MCP-Server", tool.content.mcp_server_name),
                        ("Tools", tool.content.tool_names),
                        ("Tags", tool.content.tags),
                    ]
                ),
            ]
        )
        for tool in tools
    ]
    return _join([f"# Externe Tools ({len(tools)})", FULL_FORMAT_HINT, *entries])


def _version_head(version: AnyVersionRead) -> str:
    return _meta(
        [
            ("version", version.version),
            ("status", _status(version.status)),
            ("locale", version.locale),
            ("erstellt", version.created_at.isoformat()),
            ("von", version.created_by),
        ]
    )


def version_text(entity_type: str, entity_id: str, version: AnyVersionRead) -> str:
    """`get_version`: Kopf + Snapshot-Inhalt als Klartext."""
    return _join(
        [
            f"# {entity_type} `{entity_id}`, Version {version.version}",
            FULL_FORMAT_HINT,
            _version_head(version),
            _version_content_text(version, 2),
        ]
    )


def version_list_text(entity_type: str, entity_id: str, versions: Sequence[AnyVersionRead]) -> str:
    """`list_versions`: je Version nur der Kopf (Inhalt via `get_version`)."""
    entries = [_join([f"## Version {v.version}", _version_head(v)]) for v in versions]
    return _join(
        [
            f"# Versionen von {entity_type} `{entity_id}` ({len(versions)})",
            FULL_FORMAT_HINT,
            *entries,
        ]
    )


def diff_text(entity_type: str, entity_id: str, diff: VersionDiff) -> str:
    """`diff_versions`: Kopf, Aenderungspfade, Klartext vorher/nachher.

    Die Rohwerte `before`/`after` der `changes` entfallen (Editor-JSON); der
    lesbare Vergleich steht in `before_text`/`after_text`.
    """
    against = diff.against
    if diff.against_version is not None:
        against = f"{diff.against} (Version {diff.against_version})"
    head = _meta(
        [
            ("version", diff.version),
            ("gegen", against),
            ("identisch", "ja" if diff.identical else "nein"),
        ]
    )
    changes = "\n".join(f"- {_status(change.op)} `{change.path}`" for change in diff.changes)
    return _join(
        [
            f"# Diff {entity_type} `{entity_id}`",
            FULL_FORMAT_HINT,
            head,
            _section("Aenderungen", changes),
            _section("Vorher", diff.before_text or ""),
            _section("Nachher", diff.after_text or ""),
        ]
    )


__all__ = [
    "FULL_FORMAT_HINT",
    "agent_text",
    "diff_text",
    "external_tool_content_text",
    "external_tool_list_text",
    "external_tool_text",
    "persona_content_text",
    "persona_text",
    "playbook_content_text",
    "playbook_list_text",
    "playbook_text",
    "resource_content_text",
    "resource_text",
    "system_prompt_content_text",
    "system_prompt_list_text",
    "system_prompt_text",
    "version_list_text",
    "version_text",
]
