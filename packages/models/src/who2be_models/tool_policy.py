"""Pro-Agent-Policy fuer MCP-Tool-Zugriff (Capability-Gruppen + Read-Scoping).

Single Source of Truth fuer die Frage „welche MCP-Tools darf dieser Agent?":
- **Reads** (`playbook_read`/`resource_read`/`agent_read`) sind als `ReadScope`
  granular — `all` (ganzer Workspace), `assigned` (nur Zugewiesenes; fuer
  `agent_read` heisst das **nur der eigene Agent**) oder `none` (Tool nicht
  verfuegbar). `persona_read` ist ein einfacher An/Aus-Schalter.
- **Writes** sind Capability-Gruppen (Default aus): Persona/Playbook/Resource/Agent
  schreiben sowie `promote_retire` (Versionen aktiv/inaktiv schalten).

Die Default-Instanz ist „secure by default": Reads auf `assigned` (nur
Zugewiesenes bzw. der eigene Agent), keine Writes — neu angelegte Agenten sehen
nur ihren eigenen Scope und veraendern nichts, bis der Owner es freischaltet.

Genutzt von API (Durchsetzung am Endpoint, System-Prompt-Filter) und — als
geteiltes Modell — vom MCP-Adapter. Ueber MCP gibt es kein Delete (ADR-0030),
daher kennt die Policy keine Delete-Capability.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class ReadScope(StrEnum):
    """Sichtbarkeitsumfang eines lesenden Tools.

    - ``all``: der gesamte Workspace („alles sehen").
    - ``assigned``: nur die dem Agenten ueber seine Persona zugewiesenen
      Playbooks bzw. die daraus erreichbaren Resources (Default — least
      privilege/„secure by default").
    - ``none``: das Tool ist fuer diesen Agenten gar nicht verfuegbar.
    """

    all = "all"
    assigned = "assigned"
    none = "none"


# Lese-Domains, deren Sichtbarkeit ueber `ReadScope` abgestuft ist. `agent_read`
# nutzt denselben Enum: `assigned` = „nur der eigene Agent".
_SCOPED_READ_FIELDS = ("playbook_read", "resource_read", "agent_read")


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
    system_prompt_write = "system_prompt_write"
    feedback_write = "feedback_write"
    promote_retire = "promote_retire"


class AgentToolPolicy(BaseModel):
    """Welche MCP-Tools ein Agent nutzen darf.

    Wird als JSONB auf `agent.tool_policy` persistiert. Ein leeres JSON-Objekt
    (`{}`) deserialisiert zur Default-Policy unten — so erben Bestands-Agenten
    ohne expliziten Eintrag das „nur Zugewiesenes lesen, keine Writes"-Verhalten
    (least privilege/„secure by default").
    """

    model_config = ConfigDict(extra="forbid")

    # Reads — Default: nur Zugewiesenes (secure by default). Owner kann pro Agent
    # auf `all` (ganzer Workspace) oder `none` (Tool aus) hochstufen. Fuer
    # `agent_read` bedeutet `assigned` „nur der eigene Agent" — ein Agent sieht
    # standardmaessig keine fremden Agenten; nur ein Verwalter (z. B. der Builder)
    # bekommt `all`.
    playbook_read: ReadScope = ReadScope.assigned
    resource_read: ReadScope = ReadScope.assigned
    agent_read: ReadScope = ReadScope.assigned
    persona_read: bool = True

    # Writes — Default: nichts.
    persona_write: bool = False
    playbook_write: bool = False
    resource_write: bool = False
    agent_write: bool = False
    # System-Prompt-Templates verfassen + zur Review einreichen (ADR-0040). Das
    # Aktivieren (→active) bleibt serverseitig fuer agent-gebundene Tokens hart
    # gesperrt — diese Capability schaltet es NICHT frei.
    system_prompt_write: bool = False
    # Usage-/Feedback-Flywheel (ADR-0038). Default True, abweichend vom
    # secure-by-default-Writes-Prinzip: append-only Telemetrie ist risikoarm und
    # der Zweck des Flywheels; der Owner kann sie pro Agent abschalten.
    feedback_write: bool = True
    promote_retire: bool = False

    def allows(self, capability: AgentCapability) -> bool:
        """True, wenn die Policy die gegebene Schreib-Capability gewaehrt."""
        return bool(getattr(self, capability.value))

    def granted_capabilities(self) -> list[AgentCapability]:
        """Die gewaehrten Schreib-Capabilities, in Enum-Reihenfolge.

        Additiver Lister fuer Introspektion (z. B. der `whoami`-Endpunkt, #253):
        spiegelt genau die Capabilities, fuer die `allows` True liefert. Reine
        Lese-Scopes (`*_read`) sind hier bewusst NICHT enthalten — sie sind ueber
        `ReadScope` abgestuft und werden separat ausgegeben.
        """
        return [cap for cap in AgentCapability if self.allows(cap)]

    def read_scopes(self) -> dict[str, ReadScope]:
        """Die effektiven Read-Scopes pro Domain als Mapping.

        `persona_read` ist ein An/Aus-Schalter und wird auf `all`/`none`
        normalisiert, damit alle vier Domains denselben `ReadScope`-Wertebereich
        tragen; die drei granular gescopten Reads geben ihren `ReadScope` direkt
        aus. Fuer die Introspektion via `whoami` (#253).
        """
        return {
            "persona": ReadScope.all if self.persona_read else ReadScope.none,
            "playbook": self.playbook_read,
            "resource": self.resource_read,
            "agent": self.agent_read,
        }

    def is_within(self, other: AgentToolPolicy) -> bool:
        """True, wenn diese Policy nichts gewaehrt, was `other` nicht auch gewaehrt.

        Anti-Escalation-Vergleich: ein agent-gebundener Aufrufer darf via
        `agent_write` keinen Agenten anlegen/aendern, dessen Rechte die eigenen
        uebersteigen. Reads vergleichen den Scope-Rang (`none<assigned<all`),
        Writes/Bool-Reads die Teilmengen-Beziehung (`self ⇒ other`).
        """
        for field in _SCOPED_READ_FIELDS:
            if _SCOPE_RANK[getattr(self, field)] > _SCOPE_RANK[getattr(other, field)]:
                return False
        bool_fields = (
            "persona_read",
            "persona_write",
            "playbook_write",
            "resource_write",
            "agent_write",
            "system_prompt_write",
            "feedback_write",
            "promote_retire",
        )
        return all(not getattr(self, name) or getattr(other, name) for name in bool_fields)


# Scope-Rang fuer den Teilmengen-Vergleich (`is_within`): mehr Sicht = hoeher.
_SCOPE_RANK: dict[ReadScope, int] = {
    ReadScope.none: 0,
    ReadScope.assigned: 1,
    ReadScope.all: 2,
}
