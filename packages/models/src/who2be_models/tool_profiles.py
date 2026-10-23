"""Werkzeug-Profile pro Agent (ADR-0059): Gruppen, Profile, Formel.

Single Source of Truth fuer die Frage „welche MCP-Werkzeuge blendet das
Werkzeug-Profil eines Agenten aus?". Die Rechte-Frage beantwortet weiterhin
`who2be_models.tool_requirements` (ADR-0042) — dieses Modul legt nur eine
Huelle darum (ADR-0059 §3.1):

```text
sichtbar(t) = rechte_sichtbar(t)
              UND ( t ∈ KERN  ODER  t ∈ profil_menge )

profil_menge = ( "Alle" ? alle Werkzeuge
                        : expand(profil.gruppen) ∪ profil.werkzeuge )
               ∪ agent.zusätzlich
               − agent.gesperrt
```

Hier und nur hier stehen die Werkzeuggruppen (§5.1), die Kern-Werkzeuge, die
mitgelieferten Profile (§5.2) und die Formel. MCP-Filter, System-Prompt-Block,
Workspace-Seed und `payload_report` beziehen sie von hier; die SQL-Migration
kann das Modul nicht importieren und wird per Paritaetstest dagegen geprueft
(ADR-0059 §11).

Ein Profil ist **kein Recht** (§3.3): Es geht nicht in `is_within` ein und die
API setzt es nicht durch. Es schraenkt nur ein, es erweitert nie — ein
Werkzeug, das die Rechte verbergen, macht auch `tools_added` nicht sichtbar.

„Alle" ist kein gespeichertes Profil, sondern das Fehlen eines Profils
(`ToolProfileGrant.id is None`). Menschen und ungebundene Tokens
(`unrestricted=True`) haben kein Profil; fuer sie aendert sich nichts.

Unbekannte Gruppen- oder Werkzeugnamen in einem gespeicherten Profil (etwa
nach dem Abbau eines Werkzeugs) werden bei der Auswertung uebergangen (§3.3).
Beim Speichern lehnt die API sie ab; dafuer gibt es `unknown_tools`,
`unknown_groups` und `core_tools_in`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from who2be_models.tool_policy import AgentCapability, AgentToolPolicy, MemoryMode, ReadScope
from who2be_models.tool_requirements import is_tool_visible, is_tool_visible_for
from who2be_models.workspace_member import WorkspaceRole


class ToolGroup(StrEnum):
    """Fachlich geschnittene Werkzeuggruppe (ADR-0059 §5.1).

    Jedes MCP-Werkzeug gehoert zu genau einer Gruppe — der Paritaetstest gegen
    `MCP_TOOL_REQUIREMENTS` erzwingt das. Ein neues Werkzeug braucht deshalb
    einen Eintrag im Mapping UND eine Gruppe. Die Gruppen sind nach Arbeit
    geschnitten, nicht nach Rechten (`promote_artifact` verlangt
    `resource_write`, gehoert aber zur Arbeit im Arbeitsbereich).
    """

    core = "core"
    read = "read"
    feedback_memory = "feedback_memory"
    workarea_read = "workarea_read"
    workarea_write = "workarea_write"
    content_write = "content_write"
    transition = "transition"
    agent_admin = "agent_admin"
    system_prompt = "system_prompt"
    curation = "curation"


# Reihenfolge der Gruppen und Werkzeuge = Reihenfolge in ADR-0059 §5.1 (die
# Web-Oberflaeche zeigt sie so an). `edit_content` (ADR-0058 W1-P3) liegt in
# `content_write` (§5.1).
TOOL_GROUPS: Mapping[ToolGroup, tuple[str, ...]] = {
    ToolGroup.core: ("ping", "whoami", "report_problem"),
    ToolGroup.read: (
        "get_persona",
        "list_playbooks",
        "list_triggers",
        "fetch_playbook",
        "list_resources",
        "fetch_agent",
        "list_agents",
        "get_agent",
        "fetch_resource",
        "list_resource_blocks",
        "list_external_tools",
        "get_external_tool",
        "find_usages",
        "list_versions",
        "get_version",
        "diff_versions",
        "search",
        "search_content",
    ),
    ToolGroup.feedback_memory: (
        "record_usage",
        "submit_feedback",
        "get_feedback",
        "search_memory",
        "list_memories",
        "save_memory",
        "list_test_cases",
        "submit_test_results",
        "propose_memory_change",
        "report_case",
        "submit_case_statement",
    ),
    ToolGroup.workarea_read: (
        "read_artifact",
        "list_artifacts",
        "search_workarea",
        "search_kb",
        "neighbors",
        "list_tables",
        "query_table",
        "describe_table",
        "timeline",
        "list_category_rules",
    ),
    ToolGroup.workarea_write: (
        "create_artifact",
        "append_artifact",
        "patch_artifact",
        "delete_artifact",
        "ingest",
        "create_node",
        "update_node",
        "create_edge",
        "promote_artifact",
        "create_table",
        "delete_table",
        "insert_rows",
        "save_query_result",
        "set_convention",
        "upsert_category_rule",
    ),
    ToolGroup.content_write: (
        "create_persona",
        "update_persona",
        "restore_persona",
        "set_persona_playbooks",
        "create_playbook",
        "update_playbook",
        "restore_playbook",
        "set_playbook_resource_links",
        "set_playbook_composes",
        "create_resource",
        "update_resource",
        "restore_resource",
        "set_resource_sub_resources",
        "create_external_tool",
        "update_external_tool",
        "restore_external_tool",
        "edit_content",
    ),
    ToolGroup.transition: (
        "transition_persona",
        "transition_playbook",
        "transition_resource",
        "transition_external_tool",
    ),
    ToolGroup.agent_admin: ("create_agent", "update_agent", "copy_agent"),
    ToolGroup.system_prompt: (
        "list_placeholders",
        "list_system_prompts",
        "get_system_prompt",
        "create_system_prompt",
        "update_system_prompt",
        "restore_system_prompt",
        "transition_system_prompt",
    ),
    ToolGroup.curation: (
        "resolve_feedback",
        "list_cases",
        "assign_case_elements",
        "get_case",
        "triage_case",
        "list_patterns",
        "create_test_case",
        "get_lesson",
        "convert_lesson_to_case",
        "get_dossier",
        "submit_session_protocol",
        "link_measure_draft",
        "get_follow_up",
    ),
}

# Werkzeug -> Gruppe (abgeleitet). Steht ein Werkzeug versehentlich in zwei
# Gruppen, gewinnt hier die letzte — der Paritaetstest meldet den Fehler.
TOOL_GROUP_OF: Mapping[str, ToolGroup] = {
    tool: group for group, tools in TOOL_GROUPS.items() for tool in tools
}

# Kern-Werkzeuge (§3.1): in keinem Profil abwaehlbar, auch nicht ueber
# `tools_removed` (API: 422 `core_tool_not_removable`). `report_problem` ist
# der Meldeweg aus P3a (§8). Die Rechte gehen auch hier vor: ohne
# `feedback_write` bleibt `report_problem` unsichtbar.
CORE_TOOLS: frozenset[str] = frozenset(TOOL_GROUPS[ToolGroup.core])


class BuiltinProfileKey(StrEnum):
    """Schluessel der mitgelieferten Profile (`tool_profile.builtin_key`).

    „Alle" hat keinen Schluessel — es ist das Fehlen eines Profils.
    """

    read = "read"
    author = "author"
    curator = "curator"
    builder = "builder"


class BuiltinProfile(BaseModel):
    """Lieferstand eines mitgelieferten Profils (ADR-0059 §5.2).

    `names` je Content-Sprache (`workspace.content_locale`, §4.3) — Seed und
    „Auf Lieferstand zuruecksetzen" (§7.1) lesen beides von hier.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: BuiltinProfileKey
    names: Mapping[str, str]
    groups: tuple[ToolGroup, ...]
    tools: tuple[str, ...] = ()


_READ_GROUPS: tuple[ToolGroup, ...] = (
    ToolGroup.core,
    ToolGroup.read,
    ToolGroup.feedback_memory,
    ToolGroup.workarea_read,
)

BUILTIN_PROFILES: Mapping[BuiltinProfileKey, BuiltinProfile] = {
    BuiltinProfileKey.read: BuiltinProfile(
        key=BuiltinProfileKey.read,
        names={"de": "Lesen", "en": "Read"},
        groups=_READ_GROUPS,
    ),
    BuiltinProfileKey.author: BuiltinProfile(
        key=BuiltinProfileKey.author,
        names={"de": "Autor", "en": "Author"},
        groups=(
            *_READ_GROUPS,
            ToolGroup.content_write,
            ToolGroup.transition,
            ToolGroup.workarea_write,
        ),
    ),
    BuiltinProfileKey.curator: BuiltinProfile(
        key=BuiltinProfileKey.curator,
        names={"de": "Kurator", "en": "Curator"},
        groups=(*_READ_GROUPS, ToolGroup.transition, ToolGroup.curation),
    ),
    # W59-4 (Owner 2026-10-21): „Builder" enthaelt `workarea_read`.
    BuiltinProfileKey.builder: BuiltinProfile(
        key=BuiltinProfileKey.builder,
        names={"de": "Builder", "en": "Builder"},
        groups=(
            ToolGroup.core,
            ToolGroup.read,
            ToolGroup.feedback_memory,
            ToolGroup.workarea_read,
            ToolGroup.content_write,
            ToolGroup.transition,
            ToolGroup.agent_admin,
            ToolGroup.system_prompt,
            ToolGroup.curation,
        ),
    ),
}


def _dedupe(values: Sequence[str]) -> list[str]:
    """Doppelte Eintraege entfernen, Reihenfolge erhalten."""
    return list(dict.fromkeys(values))


class ToolProfileGrant(BaseModel):
    """Das Werkzeug-Profil eines agent-gebundenen Tokens (`whoami`, §6.1).

    `id is None` heisst „Alle" (mit Ausnahmen in `tools_added`/
    `tools_removed`). Kein Profil und keine Ausnahmen liefert `whoami` als
    `tool_profile=None`. Die ausgerechnete Werkzeugliste steht bewusst NICHT
    hier — der Aufrufer rechnet sie mit `effective_tool_set` aus (§6.1).

    Gruppen und Werkzeuge sind `str`, nicht `ToolGroup`: Ein Name, den der
    Code nicht mehr kennt, darf das Lesen nicht brechen, er wird bei der
    Auswertung uebergangen (§3.3).
    """

    model_config = ConfigDict(extra="forbid")

    id: UUID | None = None
    name: str
    groups: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    tools_added: list[str] = Field(default_factory=list)
    tools_removed: list[str] = Field(default_factory=list)


class _ToolProfileFields(BaseModel):
    """Gemeinsame Eingabefelder fuer Anlegen und Aendern eines Profils."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=2_000)
    # `str` statt `ToolGroup`: unbekannte Namen prueft der Service mit
    # `unknown_groups`/`unknown_tools` und meldet sie mit eigenem Fehlercode
    # (422 `unknown_tool_group`/`unknown_tool`, ADR-0059 §7.1).
    groups: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("name must not be blank")
        return stripped

    @field_validator("groups", "tools")
    @classmethod
    def _dedupe_names(cls, value: list[str]) -> list[str]:
        return _dedupe(value)


class ToolProfileCreate(_ToolProfileFields):
    """Eingabe `POST /tool-profiles` — eigenes Profil anlegen (admin)."""


class ToolProfileUpdate(_ToolProfileFields):
    """Eingabe `PUT /tool-profiles/{id}` — Profil vollstaendig ersetzen (admin)."""


class ToolProfileRead(BaseModel):
    """Ein Werkzeug-Profil des Workspace, mit Zahl der zugeordneten Agenten."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    builtin_key: BuiltinProfileKey | None = None
    name: str
    description: str = ""
    groups: list[str]
    tools: list[str]
    agent_count: int = 0
    created_at: datetime
    updated_at: datetime


class AgentToolProfileUpdate(BaseModel):
    """Eingabe `PUT /agents/{id}/tool-profile` (editor, nur Menschen, §7.3).

    `tool_profile_id=None` stellt auf „Alle". `tools_removed` darf keine
    Kern-Werkzeuge enthalten (422 `core_tool_not_removable`).
    """

    model_config = ConfigDict(extra="forbid")

    tool_profile_id: UUID | None = None
    tools_added: list[str] = Field(default_factory=list)
    tools_removed: list[str] = Field(default_factory=list)

    @field_validator("tools_added", "tools_removed")
    @classmethod
    def _dedupe_names(cls, value: list[str]) -> list[str]:
        return _dedupe(value)


class ToolGroupRead(BaseModel):
    """Eine Gruppe im Katalog: Schluessel und ihre Werkzeuge."""

    key: ToolGroup
    tools: list[str]


class ToolCatalogRead(BaseModel):
    """Antwort `GET /tool-profiles/catalog`: Gruppen aus dem Code, Kern."""

    groups: list[ToolGroupRead]
    core_tools: list[str]


def tool_catalog() -> ToolCatalogRead:
    """Der Werkzeug-Katalog aus dem Code (Gruppen in ADR-Reihenfolge)."""
    return ToolCatalogRead(
        groups=[
            ToolGroupRead(key=group, tools=list(tools)) for group, tools in TOOL_GROUPS.items()
        ],
        core_tools=list(TOOL_GROUPS[ToolGroup.core]),
    )


def all_tools() -> frozenset[str]:
    """Alle gruppierten Werkzeuge (= die Menge hinter „Alle")."""
    return frozenset(TOOL_GROUP_OF)


def expand_groups(groups: Iterable[str]) -> frozenset[str]:
    """Werkzeuge der genannten Gruppen; unbekannte Gruppen werden uebergangen."""
    result: set[str] = set()
    for name in groups:
        if name in TOOL_GROUPS:
            result.update(TOOL_GROUPS[ToolGroup(name)])
    return frozenset(result)


def builtin_profile_tools(key: BuiltinProfileKey) -> frozenset[str]:
    """Werkzeugmenge eines mitgelieferten Profils im Lieferstand."""
    profile = BUILTIN_PROFILES[key]
    return expand_groups(profile.groups) | frozenset(profile.tools)


def effective_tool_set(grant: ToolProfileGrant | None) -> frozenset[str]:
    """`profil_menge ∪ KERN` nach ADR-0059 §3.1 — nur bekannte Werkzeuge.

    `None` (kein Profil, keine Ausnahmen) und „Alle" (`grant.id is None`)
    starten bei allen Werkzeugen. Unbekannte Namen fallen heraus (§3.3).
    Kern-Werkzeuge sind immer enthalten, auch wenn sie in `tools_removed`
    stehen. Die Rechte sind hier NICHT beruecksichtigt — dafuer die
    `*_with_profile`-Funktionen.
    """
    known = all_tools()
    if grant is None:
        return known
    if grant.id is None:
        base = known
    else:
        base = expand_groups(grant.groups) | (frozenset(grant.tools) & known)
    added = frozenset(grant.tools_added) & known
    removed = frozenset(grant.tools_removed)
    return ((base | added) - removed) | CORE_TOOLS


def is_tool_in_profile(name: str, grant: ToolProfileGrant | None) -> bool:
    """Laesst das Profil das Werkzeug `name` durch (ohne Rechte-Pruefung)?

    Liefert `False` genau dann, wenn NUR das Profil das Werkzeug verbirgt —
    der MCP-Filter unterscheidet damit die zwei Meldungen bei `tools/call`
    (ADR-0059 §8). Ein Werkzeug ohne Gruppe liegt nur in einem Profil, wenn es
    dort einzeln oder in `tools_added` steht (unter „Alle" immer).
    """
    if grant is None or name in CORE_TOOLS:
        return True
    if name in grant.tools_removed:
        return False
    if grant.id is None or name in grant.tools_added or name in grant.tools:
        return True
    group = TOOL_GROUP_OF.get(name)
    return group is not None and group.value in grant.groups


def is_tool_visible_with_profile(
    name: str,
    policy: AgentToolPolicy | None,
    grant: ToolProfileGrant | None,
) -> bool | None:
    """`is_tool_visible` (Rechte, ADR-0042) UND Profil (ADR-0059 §3.1).

    Variante fuer den API-Resolver (`tools-overview`). `None` fuer unbekannte
    Werkzeugnamen, wie `is_tool_visible` — der Aufrufer entscheidet fail-open.
    """
    by_rights = is_tool_visible(name, policy)
    if not by_rights:
        return by_rights
    return is_tool_in_profile(name, grant)


def is_tool_visible_for_with_profile(
    name: str,
    *,
    unrestricted: bool,
    role: WorkspaceRole,
    capabilities: Sequence[AgentCapability] | None,
    read_scopes: Mapping[str, ReadScope] | None,
    memory_mode: MemoryMode | None = None,
    tool_profile: ToolProfileGrant | None = None,
) -> bool | None:
    """`is_tool_visible_for` (Rechte, ADR-0042) UND Profil (ADR-0059 §3.1).

    Variante fuer den MCP-Adapter auf `whoami`-Basis. Unrestricted Principals
    (Mensch/JWT, ungebundener Token) haben kein Profil — ein mitgeliefertes
    `tool_profile` wird fuer sie ignoriert. `None` fuer unbekannte
    Werkzeugnamen (Aufrufer entscheidet fail-open).
    """
    by_rights = is_tool_visible_for(
        name,
        unrestricted=unrestricted,
        role=role,
        capabilities=capabilities,
        read_scopes=read_scopes,
        memory_mode=memory_mode,
    )
    if not by_rights or unrestricted:
        return by_rights
    return is_tool_in_profile(name, tool_profile)


def unknown_tools(names: Iterable[str]) -> list[str]:
    """Namen, die kein gruppiertes Werkzeug sind (API: 422 `unknown_tool`)."""
    return [name for name in _dedupe(list(names)) if name not in TOOL_GROUP_OF]


def unknown_groups(names: Iterable[str]) -> list[str]:
    """Namen, die keine Gruppe sind (API: 422 `unknown_tool_group`)."""
    return [name for name in _dedupe(list(names)) if name not in TOOL_GROUPS]


def core_tools_in(names: Iterable[str]) -> list[str]:
    """Kern-Werkzeuge unter `names` (API: 422 `core_tool_not_removable`)."""
    return [name for name in _dedupe(list(names)) if name in CORE_TOOLS]


# Konsistenz zum Rechte-Mapping wird im Test geprueft, nicht beim Import:
# ein Import-Fehler wuerde API und MCP gleichzeitig lahmlegen.
__all__ = [
    "BUILTIN_PROFILES",
    "CORE_TOOLS",
    "TOOL_GROUPS",
    "TOOL_GROUP_OF",
    "AgentToolProfileUpdate",
    "BuiltinProfile",
    "BuiltinProfileKey",
    "ToolCatalogRead",
    "ToolGroup",
    "ToolGroupRead",
    "ToolProfileCreate",
    "ToolProfileGrant",
    "ToolProfileRead",
    "ToolProfileUpdate",
    "all_tools",
    "builtin_profile_tools",
    "core_tools_in",
    "effective_tool_set",
    "expand_groups",
    "is_tool_in_profile",
    "is_tool_visible_for_with_profile",
    "is_tool_visible_with_profile",
    "tool_catalog",
    "unknown_groups",
    "unknown_tools",
]
