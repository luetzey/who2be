"""Pro-Agent-Policy fuer MCP-Tool-Zugriff (Capability-Gruppen + Read-Scoping).

Single Source of Truth fuer die Frage „welche MCP-Tools darf dieser Agent?":
- **Reads** (`playbook_read`/`resource_read`) sind als `ReadScope` granular —
  `all` (ganzer Workspace), `assigned` (nur die der eigenen Persona zugewiesenen
  Playbooks/Resources) oder `none` (Tool nicht verfuegbar). `persona_read`/
  `agent_read` sind einfache An/Aus-Schalter.
- **Writes** sind Capability-Gruppen (Default aus): Persona/Playbook/Resource/Agent
  schreiben sowie `promote_retire` (Versionen aktiv/inaktiv schalten).

Die Default-Instanz entspricht „Read-All, keine Writes" — neu angelegte Agenten
duerfen alles lesen, aber nichts veraendern, bis der Owner es freischaltet.

Genutzt von API (Durchsetzung am Endpoint, System-Prompt-Filter) und — als
geteiltes Modell — vom MCP-Adapter. Ueber MCP gibt es kein Delete (ADR-0030),
daher kennt die Policy keine Delete-Capability.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class ReadScope(StrEnum):
    """Sichtbarkeitsumfang eines lesenden Tools.

    - ``all``: der gesamte Workspace (Default — „alles sehen").
    - ``assigned``: nur die dem Agenten ueber seine Persona zugewiesenen
      Playbooks bzw. die daraus erreichbaren Resources.
    - ``none``: das Tool ist fuer diesen Agenten gar nicht verfuegbar.
    """

    all = "all"
    assigned = "assigned"
    none = "none"


class AgentCapability(StrEnum):
    """Schreib-Capabilities, die einem Agenten einzeln zugestanden werden.

    Jede MCP-Mutation mappt auf genau eine dieser Capabilities (siehe
    ``AgentToolPolicy.allows``). ``promote_retire`` deckt das Schalten von
    Versionen auf ``active``/``inactive`` ab — orthogonal zur reinen
    Schreib-Capability der jeweiligen Domain (Draft anlegen/aendern).
    """

    persona_write = "persona_write"
    playbook_write = "playbook_write"
    resource_write = "resource_write"
    agent_write = "agent_write"
    promote_retire = "promote_retire"


class AgentToolPolicy(BaseModel):
    """Welche MCP-Tools ein Agent nutzen darf.

    Wird als JSONB auf `agent.tool_policy` persistiert. Ein leeres JSON-Objekt
    (`{}`) deserialisiert zur Default-Policy unten — so erben Bestands-Agenten
    ohne expliziten Eintrag das „Read-All, keine Writes"-Verhalten.
    """

    model_config = ConfigDict(extra="forbid")

    # Reads — Default: alles sehen.
    playbook_read: ReadScope = ReadScope.all
    resource_read: ReadScope = ReadScope.all
    persona_read: bool = True
    agent_read: bool = True

    # Writes — Default: nichts.
    persona_write: bool = False
    playbook_write: bool = False
    resource_write: bool = False
    agent_write: bool = False
    promote_retire: bool = False

    def allows(self, capability: AgentCapability) -> bool:
        """True, wenn die Policy die gegebene Schreib-Capability gewaehrt."""
        return bool(getattr(self, capability.value))

    def is_within(self, other: AgentToolPolicy) -> bool:
        """True, wenn diese Policy nichts gewaehrt, was `other` nicht auch gewaehrt.

        Anti-Escalation-Vergleich: ein agent-gebundener Aufrufer darf via
        `agent_write` keinen Agenten anlegen/aendern, dessen Rechte die eigenen
        uebersteigen. Reads vergleichen den Scope-Rang (`none<assigned<all`),
        Writes/Bool-Reads die Teilmengen-Beziehung (`self ⇒ other`).
        """
        if _SCOPE_RANK[self.playbook_read] > _SCOPE_RANK[other.playbook_read]:
            return False
        if _SCOPE_RANK[self.resource_read] > _SCOPE_RANK[other.resource_read]:
            return False
        bool_fields = (
            "persona_read",
            "agent_read",
            "persona_write",
            "playbook_write",
            "resource_write",
            "agent_write",
            "promote_retire",
        )
        return all(not getattr(self, name) or getattr(other, name) for name in bool_fields)


# Scope-Rang fuer den Teilmengen-Vergleich (`is_within`): mehr Sicht = hoeher.
_SCOPE_RANK: dict[ReadScope, int] = {
    ReadScope.none: 0,
    ReadScope.assigned: 1,
    ReadScope.all: 2,
}
