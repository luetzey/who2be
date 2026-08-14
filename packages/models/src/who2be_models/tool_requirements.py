"""Geteiltes MCP-Tool-Sichtbarkeits-Mapping (Tool-Name → Anforderung, ADR-0042).

Single Source of Truth fuer die Frage „welche MCP-Tools sieht dieser
Principal?": genutzt vom MCP-Adapter (per-Request-Filterung von `tools/list`)
und vom API-Prompt-Resolver (`tools-overview`-Placeholder) — ein Mapping,
kein Drift zwischen beschreibender Tool-Liste im System-Prompt und der
tatsaechlich angebotenen Tool-Liste des Servers.

Das ist bewusst KEINE Security-Grenze: Die autoritative Durchsetzung bleibt
serverseitig bei der API (ADR-0039). Die Sichtbarkeits-Filterung ist
UX-/Kontext-Hygiene plus Defense-in-Depth — ein ausgeblendetes Tool wuerde
bei direktem Aufruf ohnehin von der API abgelehnt.

Zwei Prueffunktionen fuer die zwei Caller-Welten:
- `is_tool_visible(name, policy)` — auf `AgentToolPolicy`-Basis (API-Resolver,
  Semantik identisch zur bisherigen `_ToolDoc.is_visible`-Referenz).
- `is_tool_visible_for(name, ...)` — auf `whoami`-Feld-Basis (MCP-Adapter, der
  kein Policy-Objekt hat, sondern `unrestricted`/`role`/`capabilities`/
  `read_scopes` aus `WhoAmIRead`).

Beide liefern `None` fuer unbekannte Tool-Namen — der Caller entscheidet
fail-open (Tool sichtbar lassen + Warn-Log), damit ein neues Tool ohne
Mapping-Eintrag nie stillschweigend verschwindet.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict

from who2be_models.tool_policy import AgentCapability, AgentToolPolicy, MemoryMode, ReadScope
from who2be_models.workspace_member import WorkspaceRole

# Lese-Domain eines Read-Tools. „search" ist die Multi-Domain-Sonderrolle:
# sichtbar, sobald der Principal mindestens EINE der Inhalts-Domains
# persona/playbook/resource lesen darf (Discovery-Tools dispatchen ueber alle).
# `external_tool` (WP-3) ist eine EIGENE Domain, bewusst NICHT Teil der
# `search`-Gruppe: `list_external_tools`/`get_external_tool` haben ihre eigenen
# Tools, waehrend `search`/`find_usages`/`list_versions`/`get_version`/
# `diff_versions` weiterhin nur ueber persona/playbook/resource dispatchen (ihre
# Sichtbarkeit als GRUPPE aendert sich durch WP-3 nicht — entity_type=
# 'external_tool' ist bei list_versions/get_version trotzdem ein gueltiger Wert,
# das ist eine reine Laufzeit-Frage der Tools, keine SSoT-Sichtbarkeitsfrage).
ReadDomain = Literal[
    "persona",
    "playbook",
    "resource",
    "agent",
    "search",
    "external_tool",
    # WorkArea/KB (ADR-0047): eigene Domains ohne `ReadScope`-Abstufung —
    # die Sichtbarkeit haengt an dynamischen Area-Grants, siehe `_read_visible`.
    "workarea",
    "kb",
]

# Die Inhalts-Domains, ueber die „search"-artige Tools dispatchen.
_CONTENT_READ_DOMAINS: tuple[str, ...] = ("persona", "playbook", "resource")


class ToolRequirement(BaseModel):
    """Sichtbarkeits-Anforderung eines MCP-Tools.

    Genau EINE der vier Achsen greift pro Tool, Prioritaet
    ``always > capabilities > memory > read_domain``:
    - ``always=True``: immer sichtbar (Ping/Introspektion), unabhaengig von
      Policy oder Rolle.
    - ``capabilities`` nicht leer (Write-Tool): sichtbar, sobald die Policy
      EINE der Capabilities gewaehrt (Oder-Logik, z. B. Transition-Tools:
      Schreib-Capability ODER ``promote_retire``).
    - ``memory`` gesetzt (Memory-Tool, ADR-0044): sichtbar, sobald der
      `memory_mode` der Policy MINDESTENS diese Stufe gewaehrt (geordnete
      Stufen off < read_only < suggest < auto). Anders als Reads sind
      Memory-Tools OHNE Agent-Bindung nie sichtbar — es gibt keinen
      Memory-Namespace ohne Agent.
    - ``read_domain`` gesetzt (Read-Tool): sichtbar nach Read-Scope der Domain
      (``none`` blendet aus); ``"search"`` siehe `ReadDomain`.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    read_domain: ReadDomain | None = None
    capabilities: tuple[AgentCapability, ...] = ()
    memory: MemoryMode | None = None
    always: bool = False


# Geteilte, eingefrorene Instanzen — haelt das Mapping unten lesbar.
_ALWAYS = ToolRequirement(always=True)
_PERSONA_READ = ToolRequirement(read_domain="persona")
_PLAYBOOK_READ = ToolRequirement(read_domain="playbook")
_RESOURCE_READ = ToolRequirement(read_domain="resource")
_AGENT_READ = ToolRequirement(read_domain="agent")
_SEARCH_READ = ToolRequirement(read_domain="search")
_EXTERNAL_TOOL_READ = ToolRequirement(read_domain="external_tool")
_PERSONA_WRITE = ToolRequirement(capabilities=(AgentCapability.persona_write,))
_PLAYBOOK_WRITE = ToolRequirement(capabilities=(AgentCapability.playbook_write,))
_RESOURCE_WRITE = ToolRequirement(capabilities=(AgentCapability.resource_write,))
_AGENT_WRITE = ToolRequirement(capabilities=(AgentCapability.agent_write,))
_SYSTEM_PROMPT_WRITE = ToolRequirement(capabilities=(AgentCapability.system_prompt_write,))
_FEEDBACK_WRITE = ToolRequirement(capabilities=(AgentCapability.feedback_write,))
_EXTERNAL_TOOL_WRITE = ToolRequirement(capabilities=(AgentCapability.external_tool_write,))
_MEMORY_READ = ToolRequirement(memory=MemoryMode.read_only)
_MEMORY_SUGGEST = ToolRequirement(memory=MemoryMode.suggest)
# WorkArea (ADR-0047, WP8): Writes hinter `workarea_write`; Reads ueber die
# grant-dynamische Domain "workarea" (kein `ReadScope` — siehe `_read_visible`).
_WORKAREA_READ = ToolRequirement(read_domain="workarea")
_WORKAREA_WRITE = ToolRequirement(capabilities=(AgentCapability.workarea_write,))
# Knowledge Base (ADR-0047, WP9): Node-Writes hinter `kb_write`, Kanten hinter
# der eigenen `kb_edge_write` (Kanten-Semantik = Kurations-Macht); Reads ueber
# die grant-dynamische Domain "kb" (kein `ReadScope` — siehe `_read_visible`).
_KB_READ = ToolRequirement(read_domain="kb")
_KB_WRITE = ToolRequirement(capabilities=(AgentCapability.kb_write,))
_KB_EDGE_WRITE = ToolRequirement(capabilities=(AgentCapability.kb_edge_write,))


# Alle in `apps/mcp/src/who2be_mcp/server.py` registrierten Tools (Quelle: die
# `@with_tool_log("<name>")`-Dekoratoren). Ein neues Tool MUSS hier eingetragen
# werden — der Paritaetstest in `apps/mcp` bricht sonst (fail-open zur Laufzeit,
# aber CI-rot).
MCP_TOOL_REQUIREMENTS: dict[str, ToolRequirement] = {
    # --- Immer sichtbar (Konnektivitaet/Introspektion) ---
    "ping": _ALWAYS,
    "whoami": _ALWAYS,
    # --- Reads nach Domain-Scope ---
    "get_persona": _PERSONA_READ,
    "list_playbooks": _PLAYBOOK_READ,
    "list_triggers": _PLAYBOOK_READ,
    "fetch_playbook": _PLAYBOOK_READ,
    "list_resources": _RESOURCE_READ,
    "fetch_resource": _RESOURCE_READ,
    "list_resource_blocks": _RESOURCE_READ,
    "list_agents": _AGENT_READ,
    "get_agent": _AGENT_READ,
    "fetch_agent": _AGENT_READ,
    # --- ExternalTool-Aggregat (WP-3) — eigene Domain, siehe `ReadDomain` ---
    "list_external_tools": _EXTERNAL_TOOL_READ,
    "get_external_tool": _EXTERNAL_TOOL_READ,
    # Multi-Domain-Discovery-/Versions-Tools: dispatchen ueber
    # persona/playbook/resource — sichtbar, sobald EINE dieser Inhalts-Domains
    # lesbar ist (gleiche Regel wie `search` im Prompt-Resolver).
    "search": _SEARCH_READ,
    # Passage-Suche (ADR-0046). Teilt die Sichtbarkeitsregel mit `search`:
    # sichtbar, sobald der Principal MINDESTENS eine Inhalts-Domain lesen darf.
    # Die feinere Auswahl (welche Typen tatsaechlich durchsucht werden) trifft
    # `readable_content_scope` zur Laufzeit.
    "search_content": _SEARCH_READ,
    "find_usages": _SEARCH_READ,
    "list_versions": _SEARCH_READ,
    "get_version": _SEARCH_READ,
    "diff_versions": _SEARCH_READ,
    # --- Writes nach Capability-Gruppe ---
    "create_persona": _PERSONA_WRITE,
    "update_persona": _PERSONA_WRITE,
    "restore_persona": _PERSONA_WRITE,
    "set_persona_playbooks": _PERSONA_WRITE,
    "create_playbook": _PLAYBOOK_WRITE,
    "update_playbook": _PLAYBOOK_WRITE,
    "restore_playbook": _PLAYBOOK_WRITE,
    "set_playbook_resource_links": _PLAYBOOK_WRITE,
    "set_playbook_composes": _PLAYBOOK_WRITE,
    "create_resource": _RESOURCE_WRITE,
    "update_resource": _RESOURCE_WRITE,
    "restore_resource": _RESOURCE_WRITE,
    "set_resource_sub_resources": _RESOURCE_WRITE,
    "create_agent": _AGENT_WRITE,
    "update_agent": _AGENT_WRITE,
    "copy_agent": _AGENT_WRITE,
    # Transition-Tools (Oder-Logik): nach draft/review genuegt die jeweilige
    # Schreib-Capability, nach active/inactive braucht es `promote_retire` —
    # sichtbar, sobald EINE der beiden gewaehrt ist (wie im Prompt-Resolver).
    "transition_persona": ToolRequirement(
        capabilities=(AgentCapability.promote_retire, AgentCapability.persona_write)
    ),
    "transition_playbook": ToolRequirement(
        capabilities=(AgentCapability.promote_retire, AgentCapability.playbook_write)
    ),
    "transition_resource": ToolRequirement(
        capabilities=(AgentCapability.promote_retire, AgentCapability.resource_write)
    ),
    # --- ExternalTool-Writes (WP-3) — Muster identisch zu Persona/Playbook/
    #     Resource: Draft/Review via `external_tool_write`, Transition
    #     zusaetzlich per Oder-Logik mit `promote_retire`.
    "create_external_tool": _EXTERNAL_TOOL_WRITE,
    "update_external_tool": _EXTERNAL_TOOL_WRITE,
    "restore_external_tool": _EXTERNAL_TOOL_WRITE,
    "transition_external_tool": ToolRequirement(
        capabilities=(AgentCapability.promote_retire, AgentCapability.external_tool_write)
    ),
    # --- System-Prompt-Templates (ADR-0040) — nur mit `system_prompt_write` ---
    "list_system_prompts": _SYSTEM_PROMPT_WRITE,
    "get_system_prompt": _SYSTEM_PROMPT_WRITE,
    "list_placeholders": _SYSTEM_PROMPT_WRITE,
    "create_system_prompt": _SYSTEM_PROMPT_WRITE,
    "update_system_prompt": _SYSTEM_PROMPT_WRITE,
    "restore_system_prompt": _SYSTEM_PROMPT_WRITE,
    "transition_system_prompt": _SYSTEM_PROMPT_WRITE,
    # --- Usage-/Feedback-Flywheel (ADR-0038) — `feedback_write` (Default an) ---
    "record_usage": _FEEDBACK_WRITE,
    "submit_feedback": _FEEDBACK_WRITE,
    "report_problem": _FEEDBACK_WRITE,
    "get_feedback": _FEEDBACK_WRITE,
    # --- Feedback-Triage — `feedback_resolve` (Default aus): Signale schliessen
    #     ist Kurations-Macht, getrennt vom blossen Melden (`feedback_write`).
    "resolve_feedback": ToolRequirement(capabilities=(AgentCapability.feedback_resolve,)),
    # --- Agent-Memory (ADR-0044) — nach `memory_mode`-Stufe (Default off):
    #     Lesen ab `read_only`, Vorschlagen ab `suggest`. Bei `off` erscheinen
    #     die Tools gar nicht erst in tools/list.
    "search_memory": _MEMORY_READ,
    "list_memories": _MEMORY_READ,
    "save_memory": _MEMORY_SUGGEST,
    # --- WorkArea (ADR-0047, WP8) — Rohmaterial-Tools aus `tools/workarea.py`:
    #     Writes verlangen `workarea_write` (Default aus); die Reads sind
    #     grant-dynamisch immer gelistet, die API/`core/workarea_scope.py`
    #     bleibt die Autoritaet (leere Treffer statt Existenz-Leak).
    "create_artifact": _WORKAREA_WRITE,
    "append_artifact": _WORKAREA_WRITE,
    "patch_artifact": _WORKAREA_WRITE,
    "read_artifact": _WORKAREA_READ,
    "list_artifacts": _WORKAREA_READ,
    "delete_artifact": _WORKAREA_WRITE,
    "ingest": _WORKAREA_WRITE,
    "search_workarea": _WORKAREA_READ,
    # --- Knowledge Base (ADR-0047, WP9) — kuratierte Wissensschicht aus
    #     `tools/kb.py`: Reads grant-dynamisch immer gelistet (API bleibt die
    #     Autoritaet), Node-Writes hinter `kb_write`, Kanten hinter
    #     `kb_edge_write`. `promote_artifact` folgt erst mit WP14
    #     (REST-Route + Registrierung; Requirement dann: resource_write).
    "search_kb": _KB_READ,
    "create_node": _KB_WRITE,
    "update_node": _KB_WRITE,
    "create_edge": _KB_EDGE_WRITE,
    "neighbors": _KB_READ,
}


def _read_visible(domain: ReadDomain | None, policy: AgentToolPolicy) -> bool:
    """Read-Sichtbarkeit gegen eine `AgentToolPolicy` (Semantik: `_ToolDoc`)."""
    if domain == "persona":
        return policy.persona_read
    if domain == "playbook":
        return policy.playbook_read != ReadScope.none
    if domain == "resource":
        return policy.resource_read != ReadScope.none
    if domain == "agent":
        return policy.agent_read != ReadScope.none
    if domain == "external_tool":
        return policy.external_tool_read != ReadScope.none
    if domain in ("workarea", "kb"):
        # WorkArea/KB (ADR-0047): fuer agent-gebundene Identitaeten immer
        # sichtbar — Area-Grants sind dynamisch (`work_area_grant`) und werden
        # serverseitig durchgesetzt (`core/workarea_scope.py`); der
        # PolicyFilter ist ohnehin fail-open, die API bleibt die Autoritaet.
        return True
    if domain == "search":
        return (
            policy.persona_read
            or policy.playbook_read != ReadScope.none
            or policy.resource_read != ReadScope.none
        )
    return True


def is_tool_visible(name: str, policy: AgentToolPolicy | None) -> bool | None:
    """Ist das Tool `name` fuer die gegebene `AgentToolPolicy` sichtbar?

    `None` fuer unbekannte Tool-Namen — der Caller entscheidet fail-open.
    Policy `None` (z. B. Persona-Body ohne Agent-Kontext) zeigt nur Read-Tools
    (Verhalten vor dem Pro-Agent-Feature); `always`-Tools sind immer sichtbar.
    """
    requirement = MCP_TOOL_REQUIREMENTS.get(name)
    if requirement is None:
        return None
    if requirement.always:
        return True
    if requirement.capabilities:
        return policy is not None and any(policy.allows(cap) for cap in requirement.capabilities)
    if requirement.memory is not None:
        # Memory-Tools brauchen einen Agenten-Kontext (Policy) — ohne Agent
        # gibt es keinen Memory-Namespace, daher bei policy=None NIE sichtbar
        # (bewusst anders als Read-Tools).
        return policy is not None and policy.memory_at_least(requirement.memory)
    if policy is None:
        return True
    return _read_visible(requirement.read_domain, policy)


def _scoped_read_visible(domain: ReadDomain | None, scopes: Mapping[str, ReadScope]) -> bool:
    """Read-Sichtbarkeit gegen `whoami`-Read-Scopes (fehlender Key = sichtbar)."""
    if domain in ("workarea", "kb"):
        # WorkArea/KB (ADR-0047): sichtbar fuer agent-gebundene Identitaeten
        # wie fuer unrestricted Menschen — es gibt keinen `ReadScope` fuer
        # diese Domains; die Area-Grants sind dynamisch und werden
        # serverseitig durchgesetzt (PolicyFilter fail-open, API = Autoritaet).
        return True
    if domain == "search":
        return any(scopes.get(d, ReadScope.all) != ReadScope.none for d in _CONTENT_READ_DOMAINS)
    if domain is not None:
        # Fehlender Domain-Key defensiv als sichtbar werten (fail-open) —
        # `whoami` liefert normal alle vier Domains, inkl. normalisiertem
        # persona-Scope (all/none).
        return scopes.get(domain, ReadScope.all) != ReadScope.none
    return True


def is_tool_visible_for(
    name: str,
    *,
    unrestricted: bool,
    role: WorkspaceRole,
    capabilities: Sequence[AgentCapability] | None,
    read_scopes: Mapping[str, ReadScope] | None,
    memory_mode: MemoryMode | None = None,
) -> bool | None:
    """Ist das Tool `name` fuer diesen `whoami`-Principal sichtbar?

    Variante fuer den MCP-Adapter, der kein `AgentToolPolicy`-Objekt hat,
    sondern die `WhoAmIRead`-Felder. `None` fuer unbekannte Tool-Namen
    (Caller entscheidet fail-open).

    - `unrestricted=True` (Mensch/JWT oder ungebundener Token): Reads immer
      sichtbar; Write-Tools nur, wenn die Rolle nicht `viewer` ist (das
      Rollen-Gate wuerde sie ohnehin ablehnen). Memory-Tools sind fuer
      Unrestricted NIE sichtbar — ohne Agent-Bindung gibt es keinen
      Memory-Namespace (die API lehnt den Call ohnehin ab).
    - `unrestricted=False` (agent-gebundener Token): Write-Tools nach
      Schnittmenge mit den gewaehrten `capabilities` (Oder-Logik), Memory-Tools
      nach `memory_mode`-Stufe, Read-Tools nach `read_scopes` (fehlender Key
      defensiv sichtbar, fail-open).
    """
    requirement = MCP_TOOL_REQUIREMENTS.get(name)
    if requirement is None:
        return None
    if requirement.always:
        return True
    if requirement.capabilities:
        if unrestricted:
            return role != WorkspaceRole.viewer
        granted = frozenset(capabilities or ())
        return any(cap in granted for cap in requirement.capabilities)
    if requirement.memory is not None:
        if unrestricted or memory_mode is None:
            return False
        return _MEMORY_RANK[memory_mode] >= _MEMORY_RANK[requirement.memory]
    if unrestricted:
        return True
    return _scoped_read_visible(requirement.read_domain, read_scopes or {})


# Lokale Modus-Ordnung fuer den whoami-Pfad (kein Policy-Objekt zur Hand);
# identisch zur `memory_at_least`-Ordnung in `tool_policy`.
_MEMORY_RANK: dict[MemoryMode, int] = {
    MemoryMode.off: 0,
    MemoryMode.read_only: 1,
    MemoryMode.suggest: 2,
    MemoryMode.auto: 3,
}
