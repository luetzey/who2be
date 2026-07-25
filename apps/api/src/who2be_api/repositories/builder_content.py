"""Sprach-Content-Packs fuer die ausgerollten Standard-/Builder-Inhalte (WP7).

Kuenftige SSoT der ausgerollten Inhalte, EIN Pack pro Sprache: die sechs
Default-Templates, die Builder-Persona (inkl. Modi), die sechs Builder-
Playbooks und die Builder-Resource „Agent-Bau-Konventionen" sowie die beiden
Builder-Agent-Beschreibungen (Builder/Builder-Lite). Bewusst NUR Definition +
Sidecar-Referenzen — keine Verdrahtung: `workspace_repository.py` (Seeding via
`_seed_default_templates`/`_seed_default_agents`, Sync via
`sync_managed_builder_content`) bleibt in diesem Arbeitspaket unangetastet und
verwendet weiterhin ihre eigenen (deutschen) Modul-Konstanten. Das DE-Pack
hier ist daher eine BEWUSSTE Kopie der heutigen Konstanten aus
`workspace_repository.py` — keine Refaktorierung, keine gemeinsame Quelle.
Die Aufloesung (Seeding/Sync liest ueber `get_content_pack(workspace.locale)`
statt eigener Konstanten) ist WP8 vorbehalten; siehe Plan
`.claude/plan/2026-07-24-1900_sprache-vertiefen-ein-element-eine-sprache.md`.

Cross-Locale-Schluessel: Namen sind pro Sprache uebersetzt und daher NICHT als
Schluessel geeignet. Stabil bleiben: der Template-`slug`, der Resource-`slug`
(rein technisch, bleibt ueber alle Sprachen identisch) und ein expliziter
`key` je Builder-Playbook (Reihenfolge + `key` sind pack-uebergreifend fix).

`_builder_tool_policy()` (Tool-Policy des Meta-Agenten) ist locale-unabhaengig
(reine Capability-Flags, keine Prosa) und lebt bewusst NUR in
`workspace_repository.py` — hier NICHT dupliziert.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

# Offenes, aber an dieser Stelle bewusst eng gehaltenes Sprach-Set (analog
# ADR-0027/Plan-Punkt 5: DB/Modell-Schicht bleibt offen, die App-Schicht
# startet mit de/en und erweitert zentral hier).
SUPPORTED_LOCALES: Final[tuple[str, ...]] = ("de", "en")

_SIDECAR_ROOT: Final[Path] = Path(__file__).parent


def load_sidecar(filename: str, locale: str) -> str:
    """Laedt eine Sidecar-Datei fuer die angegebene Sprache.

    DE liegt (heutiger, unveraenderter Stand) flach neben diesem Modul; jede
    andere Sprache liegt im gleichnamigen Unterordner (z. B.
    `en/builder_persona_content.json`) mit IDENTISCHEM Dateinamen — nur der
    Pfad-Praefix wechselt.
    """
    subdir = "" if locale == "de" else locale
    return (_SIDECAR_ROOT / subdir / filename).read_text(encoding="utf-8")


@dataclass(frozen=True, slots=True)
class TemplateDef:
    """Ein Default-System-Prompt-Template (BlockNote-Body als Sidecar)."""

    slug: str
    name: str
    sidecar: str

    def load_body(self, locale: str) -> str:
        return load_sidecar(self.sidecar, locale)


@dataclass(frozen=True, slots=True)
class PersonaDef:
    """Die Builder-Persona (Profil-Body + Modi je als Sidecar)."""

    name: str
    description: str
    traits: tuple[str, ...]
    tags: tuple[str, ...]
    content_sidecar: str
    modes_sidecar: str

    def load_content(self, locale: str) -> str:
        return load_sidecar(self.content_sidecar, locale)

    def load_modes(self, locale: str) -> str:
        return load_sidecar(self.modes_sidecar, locale)


@dataclass(frozen=True, slots=True)
class PlaybookDef:
    """Eines der sechs Builder-Playbooks."""

    key: str
    name: str
    type: str
    triggers: str
    tags: tuple[str, ...]
    description: str
    sidecar: str

    def load_body(self, locale: str) -> str:
        return load_sidecar(self.sidecar, locale)


@dataclass(frozen=True, slots=True)
class ResourceDef:
    """Die Builder-Resource „Agent-Bau-Konventionen" (slug bleibt technisch)."""

    name: str
    slug: str
    description: str
    tags: tuple[str, ...]
    sidecar: str

    def load_body(self, locale: str) -> str:
        return load_sidecar(self.sidecar, locale)


@dataclass(frozen=True, slots=True)
class AgentDef:
    """Ein Builder-Agent (Builder bzw. Builder-Lite) — nur Name + Beschreibung."""

    name: str
    description: str


@dataclass(frozen=True, slots=True)
class ContentPack:
    """Alle ausgerollten Builder-/Default-Inhalte einer Sprache."""

    locale: str
    templates: tuple[TemplateDef, ...]
    persona: PersonaDef
    playbooks: tuple[PlaybookDef, ...]
    resource: ResourceDef
    agent: AgentDef
    agent_lite: AgentDef


# ---------------------------------------------------------------------------
# DE-Pack — 1:1-Kopie der heutigen Konstanten aus `workspace_repository.py`
# (`_DEFAULT_TEMPLATES`, `_BUILDER_PERSONA_*`, `_BUILDER_PLAYBOOKS`,
# `_BUILDER_RESOURCE_*`, `_BUILDER_*_AGENT_DESCRIPTION`). Duplikation ist
# beabsichtigt (siehe Modul-Docstring); Aenderungen an den DE-Originalen
# muessen bis WP8 an BEIDEN Stellen nachgezogen werden.
# ---------------------------------------------------------------------------

_DE_TEMPLATES: Final[tuple[TemplateDef, ...]] = (
    TemplateDef("customer-support-agent", "Customer-Support-Agent", "customer_support_body.json"),
    TemplateDef("knowledge-worker", "Knowledge-Worker", "knowledge_worker_body.json"),
    TemplateDef("conversational-coach", "Conversational-Coach", "conversational_coach_body.json"),
    TemplateDef("workflow-starter", "Workflow-Starter", "workflow_starter_body.json"),
    TemplateDef("agent-builder", "Agent-Builder", "agent_builder_body.json"),
    TemplateDef("agent-builder-lite", "Agent-Builder-Lite", "agent_builder_lite_body.json"),
)

_DE_PERSONA: Final[PersonaDef] = PersonaDef(
    name="Builder",
    description=(
        "Meta-Agent, der Personas, Playbooks, Resources und Agenten im Workspace "
        "anlegt und pflegt — der Agent, der Agenten baut."
    ),
    traits=("strukturell", "kritisch", "phasen-orientiert", "trade-offs-explizit"),
    tags=("meta-agent", "agent-building", "crud"),
    content_sidecar="builder_persona_content.json",
    modes_sidecar="builder_persona_modes.json",
)

# Trigger-Hygiene (siehe `workspace_repository.py` ~Zeile 410): keine
# generischen Woerter, die fremde Domaenen matchen (Kollisions-Historie:
# "pruefen"/"qualitaetscheck" zogen Code-/Repo-Audit-Anfragen auf den
# Drift-Check); "aufraeumen" ist vom Vault-Playbook „Aufraeumen &
# Deduplizieren" belegt und bleibt hier bewusst ungenutzt (nur qualifiziert
# als "library aufraeumen" verwendet).
_DE_PLAYBOOKS: Final[tuple[PlaybookDef, ...]] = (
    PlaybookDef(
        key="persona",
        name="Persona anlegen & pflegen",
        type="workflow",
        triggers="persona anlegen, persona bearbeiten, persona pflegen, neue persona",
        tags=("persona", "crud", "agent-building"),
        description=(
            "Eine Persona via MCP-Write-Tools anlegen, als Draft aendern und nach active schalten."
        ),
        sidecar="builder_playbook_persona_body.json",
    ),
    PlaybookDef(
        key="playbook",
        name="Playbook anlegen & pflegen",
        type="workflow",
        triggers="playbook anlegen, playbook bearbeiten, composite, neues playbook",
        tags=("playbook", "crud", "agent-building"),
        description=(
            "Playbooks anlegen und pflegen — inkl. Resource-Verweisen und Composite-Sequenzen."
        ),
        sidecar="builder_playbook_playbook_body.json",
    ),
    PlaybookDef(
        key="agent",
        name="Agent anlegen & pflegen",
        type="workflow",
        triggers=(
            "agent anlegen, agent konfigurieren, agent bearbeiten, tool policy, agent kopieren"
        ),
        tags=("agent", "crud", "agent-building"),
        description=(
            "Einen Agenten konfigurieren: Persona + Template verdrahten, "
            "Tool-Policy setzen, kopieren."
        ),
        sidecar="builder_playbook_agent_body.json",
    ),
    PlaybookDef(
        key="consistency",
        name="Konsistenz- & Drift-Check",
        type="checklist",
        triggers=(
            "konsistenz, drift, agenten pruefen, library pruefen, agent-drift, "
            "aktivierbar, activatable"
        ),
        tags=("konsistenz", "qa", "agent-building"),
        description=(
            "Read-only-Pruefung der Agent-Library auf Aktivierbarkeit, aktive "
            "Versionen, Prompt-Rendering und strukturelle Zusammenhaenge — kein "
            "Code-/Repo-Audit."
        ),
        sidecar="builder_playbook_consistency_body.json",
    ),
    PlaybookDef(
        key="maintenance",
        name="Library-Pflege & Feedback-Lauf",
        type="workflow",
        triggers=(
            "library pflegen, pflege-lauf, feedback abarbeiten, feedback umsetzen, "
            "library aufraeumen, wartungslauf, kuratieren"
        ),
        tags=("pflege", "feedback", "qa", "agent-building"),
        description=(
            "Feedback-getriebener Pflege-Lauf ueber die Agent-Library: Feedback "
            "sammeln, triagieren, Zusammenhaenge und Luecken pruefen, Fixes nach "
            "Freigabe als Drafts umsetzen."
        ),
        sidecar="builder_playbook_maintenance_body.json",
    ),
    PlaybookDef(
        key="external_tool",
        name="External Tool anlegen & pflegen",
        type="workflow",
        triggers=(
            "external tool anlegen, external tool pflegen, tool-bindung anlegen, "
            "tool-bindung pflegen, tool anbinden, tool wechseln, tool-ref"
        ),
        tags=("external-tool", "crud", "agent-building"),
        description=(
            "External-Tool-Bindungen (ADR-0043) anlegen, pflegen und rebinden — "
            "Alias-Vertrag, instruktiver Content, tool-ref-Pills und "
            "Policy-Vergabe an Fach-Agenten."
        ),
        sidecar="builder_playbook_external_tool_body.json",
    ),
)

_DE_RESOURCE: Final[ResourceDef] = ResourceDef(
    name="Agent-Bau-Konventionen",
    slug="agent-bau-konventionen",
    description=(
        "Verbindliche Konventionen fuer den Agent-Bau: Trigger-Hygiene, "
        "Modi-Regel, Naming, Tool-Policy-Muster und Managed/409-Grenzen — "
        "Single-Source fuer die Builder-Playbooks."
    ),
    tags=("konventionen", "agent-building", "meta"),
    sidecar="builder_resource_conventions_body.json",
)

_DE_AGENT: Final[AgentDef] = AgentDef(
    name="Builder",
    description=(
        "Standard-Meta-Agent zum Anlegen und Pflegen von Personas, Playbooks, "
        "Resources und Agenten."
    ),
)

_DE_AGENT_LITE: Final[AgentDef] = AgentDef(
    name="Builder-Lite",
    description=(
        "Schlanke Builder-Variante mit kompaktem System-Prompt — fuer LLMs mit "
        "kleinem System-Prompt-Budget. Gleiche Persona und Schreib-Policy wie "
        "der Builder."
    ),
)

_DE_PACK: Final[ContentPack] = ContentPack(
    locale="de",
    templates=_DE_TEMPLATES,
    persona=_DE_PERSONA,
    playbooks=_DE_PLAYBOOKS,
    resource=_DE_RESOURCE,
    agent=_DE_AGENT,
    agent_lite=_DE_AGENT_LITE,
)


# ---------------------------------------------------------------------------
# EN-Pack — Uebersetzung der Anzeigetexte (Namen/Trigger/Tags/Beschreibungen).
# Technische Schluessel (Template-`slug`, Resource-`slug`, Playbook-`key`)
# bleiben unveraendert; der Persona-Name „Builder" und der Agent-Name
# „Builder-Lite" sind keine deutschen Woerter und bleiben ebenfalls stehen.
# Sidecars liegen unter `repositories/en/` (gleicher Dateiname wie DE); ein
# Teil davon ist zum Zeitpunkt dieses Arbeitspakets noch nicht uebersetzt
# (parallele Arbeit an anderen WP7-Teilen) — siehe Test-Modul.
# ---------------------------------------------------------------------------

_EN_TEMPLATES: Final[tuple[TemplateDef, ...]] = (
    TemplateDef("customer-support-agent", "Customer Support Agent", "customer_support_body.json"),
    TemplateDef("knowledge-worker", "Knowledge Worker", "knowledge_worker_body.json"),
    TemplateDef("conversational-coach", "Conversational Coach", "conversational_coach_body.json"),
    TemplateDef("workflow-starter", "Workflow Starter", "workflow_starter_body.json"),
    TemplateDef("agent-builder", "Agent Builder", "agent_builder_body.json"),
    TemplateDef("agent-builder-lite", "Agent Builder Lite", "agent_builder_lite_body.json"),
)

_EN_PERSONA: Final[PersonaDef] = PersonaDef(
    name="Builder",
    description=(
        "Meta-agent that creates and maintains personas, playbooks, resources, "
        "and agents in the workspace — the agent that builds agents."
    ),
    traits=("structured", "critical", "phase-oriented", "trade-offs-explicit"),
    tags=("meta-agent", "agent-building", "crud"),
    content_sidecar="builder_persona_content.json",
    modes_sidecar="builder_persona_modes.json",
)

# Trigger-Hygiene analog DE (siehe Kommentar oben): keine generischen
# Einzelwoerter, die fremde Domaenen matchen wuerden; Phrasen bleiben
# domaenen-qualifiziert (z. B. "clean up library" statt blossem "clean up").
_EN_PLAYBOOKS: Final[tuple[PlaybookDef, ...]] = (
    PlaybookDef(
        key="persona",
        name="Create & Maintain Persona",
        type="workflow",
        triggers="create persona, edit persona, maintain persona, new persona",
        tags=("persona", "crud", "agent-building"),
        description=(
            "Create a persona via MCP write tools, edit it as a draft, and transition it to active."
        ),
        sidecar="builder_playbook_persona_body.json",
    ),
    PlaybookDef(
        key="playbook",
        name="Create & Maintain Playbook",
        type="workflow",
        triggers="create playbook, edit playbook, composite, new playbook",
        tags=("playbook", "crud", "agent-building"),
        description=(
            "Create and maintain playbooks — including resource references and composite sequences."
        ),
        sidecar="builder_playbook_playbook_body.json",
    ),
    PlaybookDef(
        key="agent",
        name="Create & Maintain Agent",
        type="workflow",
        triggers="create agent, configure agent, edit agent, tool policy, copy agent",
        tags=("agent", "crud", "agent-building"),
        description=(
            "Configure an agent: wire up persona + template, set the tool policy, copy it."
        ),
        sidecar="builder_playbook_agent_body.json",
    ),
    PlaybookDef(
        key="consistency",
        name="Consistency & Drift Check",
        type="checklist",
        triggers=(
            "consistency, drift, check agents, check library, agent drift, activatable, launchable"
        ),
        tags=("consistency", "qa", "agent-building"),
        description=(
            "Read-only review of the agent library for activatability, active "
            "versions, prompt rendering, and structural relationships — not a "
            "code/repo audit."
        ),
        sidecar="builder_playbook_consistency_body.json",
    ),
    PlaybookDef(
        key="maintenance",
        name="Library Maintenance & Feedback Run",
        type="workflow",
        triggers=(
            "maintain library, maintenance run, process feedback, address "
            "feedback, clean up library, curate library"
        ),
        tags=("maintenance", "feedback", "qa", "agent-building"),
        description=(
            "Feedback-driven maintenance run across the agent library: collect "
            "feedback, triage it, check relationships and gaps, and implement "
            "approved fixes as drafts."
        ),
        sidecar="builder_playbook_maintenance_body.json",
    ),
    PlaybookDef(
        key="external_tool",
        name="Create & Maintain External Tool",
        type="workflow",
        triggers=(
            "create external tool, maintain external tool, create tool binding, "
            "maintain tool binding, connect tool, switch tool, tool-ref"
        ),
        tags=("external-tool", "crud", "agent-building"),
        description=(
            "Create, maintain, and rebind external tool bindings (ADR-0043) — "
            "alias contract, instructive content, tool-ref pills, and policy "
            "grants to domain agents."
        ),
        sidecar="builder_playbook_external_tool_body.json",
    ),
)

_EN_RESOURCE: Final[ResourceDef] = ResourceDef(
    name="Agent-Building Conventions",
    slug="agent-bau-konventionen",
    description=(
        "Binding conventions for agent building: trigger hygiene, the modes "
        "rule, naming, tool-policy patterns, and managed/409 boundaries — the "
        "single source for the builder playbooks."
    ),
    tags=("conventions", "agent-building", "meta"),
    sidecar="builder_resource_conventions_body.json",
)

_EN_AGENT: Final[AgentDef] = AgentDef(
    name="Builder",
    description=(
        "Standard meta-agent for creating and maintaining personas, playbooks, "
        "resources, and agents."
    ),
)

_EN_AGENT_LITE: Final[AgentDef] = AgentDef(
    name="Builder-Lite",
    description=(
        "Lean Builder variant with a compact system prompt — for LLMs with a "
        "small system-prompt budget. Same persona and write policy as the "
        "Builder."
    ),
)

_EN_PACK: Final[ContentPack] = ContentPack(
    locale="en",
    templates=_EN_TEMPLATES,
    persona=_EN_PERSONA,
    playbooks=_EN_PLAYBOOKS,
    resource=_EN_RESOURCE,
    agent=_EN_AGENT,
    agent_lite=_EN_AGENT_LITE,
)


_PACKS: Final[dict[str, ContentPack]] = {"de": _DE_PACK, "en": _EN_PACK}


def get_content_pack(locale: str) -> ContentPack:
    """Liefert das ContentPack der angegebenen Sprache.

    Reine Metadaten-Aufloesung (keine Sidecar-Reads) — Sidecar-Inhalte werden
    erst ueber `TemplateDef.load_body`/`PersonaDef.load_content`/etc. bei
    Bedarf gelesen. So bleibt `get_content_pack` auch fuer noch unvollstaendig
    uebersetzte Sprachen (fehlende Sidecar-Dateien) nebenwirkungsfrei nutzbar.

    Wirft `ValueError` fuer nicht unterstuetzte Sprachen (z. B. `'fr'`).
    """
    try:
        return _PACKS[locale]
    except KeyError as exc:
        raise ValueError(
            f"Nicht unterstuetzte Sprache: {locale!r} (unterstuetzt: {SUPPORTED_LOCALES})"
        ) from exc
