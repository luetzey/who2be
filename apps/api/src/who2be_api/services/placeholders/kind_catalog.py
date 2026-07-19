"""Statischer Placeholder-Kind-Katalog (WP-A, praezisiert ADR-0025/0040).

Macht das Placeholder-Format zur Laufzeit entdeckbar (REST-Endpoint
`GET /v1/workspaces/{ws_id}/placeholders` + MCP-Tool `list_placeholders`),
statt es nur im Frontend-Code (`PlaceholderBlock.tsx`) und den Resolver-
Docstrings zu dokumentieren. Pro Kind: Beschreibung, `target_id`-Vertrag
(Semantik + ggf. abschliessende Werteliste) und ein gueltiges Beispiel-Inline.

Vollstaendigkeits-Invariante: die Katalog-Kinds muessen exakt die Keys der
Resolver-`REGISTRY` sein — der Test `test_placeholder_catalog.py` bricht,
wenn ein neuer Resolver ohne Katalog-Eintrag registriert wird (oder umgekehrt).
"""

from __future__ import annotations

from who2be_models import (
    PlaceholderCatalog,
    PlaceholderInlineExample,
    PlaceholderInlineProps,
    PlaceholderKindInfo,
)


def _example(kind: str, target_id: str, label: str) -> PlaceholderInlineExample:
    return PlaceholderInlineExample(
        props=PlaceholderInlineProps(kind=kind, target_id=target_id, label=label)
    )


# Reihenfolge = Reihenfolge der Resolver-REGISTRY (stabile Ausgabe fuer Agenten).
_CATALOG: tuple[PlaceholderKindInfo, ...] = (
    PlaceholderKindInfo(
        kind="playbook",
        description=(
            "Bettet den Body der aktiven Version eines Playbooks in den gerenderten "
            "System-Prompt ein. Nicht gefundenes/inaktives Playbook rendert als "
            "Fallback-Hinweis (Miss), nie als Fehler."
        ),
        target_id_semantics="UUID eines Playbooks im Workspace.",
        target_id_values=[],
        example=_example(
            "playbook", "3f6c1f2e-0000-4000-8000-000000000001", "Playbook: Reset-Mail"
        ),
    ),
    PlaceholderKindInfo(
        kind="resource",
        description=(
            "Bettet die aktive Version einer Resource ein — wahlweise das ganze "
            "Dokument oder nur eine Sektion (Block-Anker)."
        ),
        target_id_semantics=(
            "UUID einer Resource, optional mit Sektions-Anker '<uuid>#<block_id>' "
            "(dann wird nur die Sektion ab diesem Block eingebettet)."
        ),
        target_id_values=[],
        example=_example(
            "resource", "9a2b7c1d-0000-4000-8000-000000000002", "Resource: Tonalitaet"
        ),
    ),
    PlaceholderKindInfo(
        kind="persona-field",
        description=(
            "Bettet ein Feld der Persona des gerenderten Agenten ein: 'name', "
            "'description', 'profile' (Beschreibung + Profil-Body + Traits + Modi), "
            "'profile-body' (nur der BlockNote-Profil-Body) oder 'modes' (nur die "
            "Modi-Sektion; leere Modi ergeben einen leeren String)."
        ),
        target_id_semantics="Feldname der Persona (abschliessende Liste).",
        target_id_values=["name", "description", "profile", "profile-body", "modes"],
        example=_example("persona-field", "profile", "Persona: Profil"),
    ),
    PlaceholderKindInfo(
        kind="persona-ref",
        description=(
            "Rendert eine Anweisung an den Agenten, seine Persona zu Beginn der "
            "Sitzung selbst via get_persona(...) zu laden (dynamischer Verweis statt "
            "eingebettetem Snapshot)."
        ),
        target_id_semantics="Ungenutzt — leerer String.",
        target_id_values=[""],
        example=_example("persona-ref", "", "Persona laden"),
    ),
    PlaceholderKindInfo(
        kind="playbooks-catalog",
        description=(
            "Rendert eine Briefing-Tabelle der der Agent-Persona verknuepften aktiven "
            "Playbooks (Spalten: Playbook | Trigger | Aufruf | Beschreibung)."
        ),
        target_id_semantics=(
            "Filter: '' oder 'all' = alle verknuepften aktiven Playbooks; "
            "'triggered' = nur Playbooks mit nicht-leerem Trigger-Feld."
        ),
        target_id_values=["", "all", "triggered"],
        example=_example("playbooks-catalog", "triggered", "Playbook-Katalog: getriggert"),
    ),
    PlaceholderKindInfo(
        kind="resources-catalog",
        description=(
            "Rendert eine Briefing-Tabelle der aktiven Resources des Workspace "
            "(Spalten: Resource | Tags | Aufruf | Beschreibung)."
        ),
        target_id_semantics=(
            "Filter: '' oder 'all' = alle aktiven Resources; jeder andere Wert wird "
            "als exakter Tag-Filter interpretiert."
        ),
        target_id_values=[],
        example=_example("resources-catalog", "all", "Resource-Katalog"),
    ),
    PlaceholderKindInfo(
        kind="date",
        description="Rendert das aktuelle Datum (Render-Zeitpunkt). Nie ein Miss.",
        target_id_semantics=(
            "Format-Slug: '' = ISO-8601 (2026-05-31); 'human' = deutsches Langformat "
            "(31. Mai 2026). Unbekannte Slugs fallen auf ISO-8601 zurueck."
        ),
        target_id_values=["", "human"],
        example=_example("date", "human", "Datum"),
    ),
    PlaceholderKindInfo(
        kind="tools-overview",
        description=(
            "Rendert die kuratierte Liste der MCP-Tools, gefiltert auf die "
            "tool_policy des gerenderten Agenten. Nie ein Miss."
        ),
        target_id_semantics="Ungenutzt — leerer String.",
        target_id_values=[""],
        example=_example("tools-overview", "", "MCP-Tools"),
    ),
    PlaceholderKindInfo(
        kind="memory",
        description=(
            "Rendert den Gedaechtnis-Hinweis passend zum memory_mode des "
            "gerenderten Agenten (ADR-0044): nur-lesend / mit Freigabe / "
            "automatisch, plus Verbindlichkeits-Zeile gemaess memory_directive. "
            "memory_mode 'off' (oder Render ohne Agent-Kontext) rendert leer — "
            "nie ein Miss, nie ein Fehler. Ohne diesen Placeholder haengt "
            "tools-overview den Hinweis automatisch an; mit ihm bestimmt die "
            "Position im Template."
        ),
        target_id_semantics="Ungenutzt — leerer String.",
        target_id_values=[""],
        example=_example("memory", "", "Gedaechtnis"),
    ),
    PlaceholderKindInfo(
        kind="tool-ref",
        description=(
            "Bettet die aktive Bindung eines externen MCP-Server/Tools "
            "(`external_tool`) ein: Anzeigename, Server-Name, Tool-Namen und "
            "Nutzungshinweise als kompakter Anweisungsblock. Nicht "
            "gefundener/inaktiver Alias rendert als Fallback-Hinweis (Miss), "
            "nie als Fehler."
        ),
        target_id_semantics="Faehigkeits-Alias eines externen Tools (z. B. 'todo').",
        target_id_values=[],
        example=_example("tool-ref", "todo", "Tool: To-do-Liste"),
    ),
)


def placeholder_catalog() -> PlaceholderCatalog:
    """Der statische Placeholder-Katalog (workspace-unabhaengig, unsensibel)."""
    return PlaceholderCatalog(kinds=list(_CATALOG))
