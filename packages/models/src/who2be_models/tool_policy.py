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


_TRANSITION_DOMAINS = ("persona", "playbook", "resource")


class TransitionGrant(BaseModel):
    """Pro-Domain-Verfeinerung von `promote_retire` (ADR-0039).

    Wirkt NUR als Einschraenkung: greift ausschliesslich, wenn der Agent
    `promote_retire` haelt. Ist fuer eine Domain ein Eintrag gesetzt, sind nur die
    explizit gewaehrten Richtungen erlaubt — so laesst sich „darf Playbooks
    promoten, aber keine Personas; nie retiren" abbilden, ohne `promote_retire`
    aufzuweiten. Fehlt der Domain-Eintrag, gilt die ungeteilte `promote_retire`.
    """

    model_config = ConfigDict(extra="forbid")

    promote: bool = True
    retire: bool = True


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
    # Optionale Pro-Domain-Verfeinerung von `promote_retire` (ADR-0039).
    # Leer = ungeteilt (Backward-Compat). Keys: persona/playbook/resource.
    transition_grants: dict[str, TransitionGrant] = {}
    # Optionales Tag-Praedikat-Write-Scoping (ADR-0039). Pro Domain
    # (persona/playbook/resource) eine Liste erlaubter Tags: ist sie gesetzt UND
    # nicht leer, darf der Agent in dieser Domain nur Inhalte schreiben, deren
    # Tags die erlaubte Menge schneiden ("darf nur `support`-Playbooks editieren").
    # Fehlender/leerer Eintrag = keine Tag-Einschraenkung (Backward-Compat).
    write_tags: dict[str, list[str]] = {}

    def allows(self, capability: AgentCapability) -> bool:
        """True, wenn die Policy die gegebene Schreib-Capability gewaehrt."""
        return bool(getattr(self, capability.value))

    def write_tags_for(self, domain: str) -> list[str] | None:
        """Erlaubte Tags fuer Writes in `domain`, oder None (keine Einschraenkung)."""
        tags = self.write_tags.get(domain)
        return tags if tags else None

    def tags_permitted(self, domain: str, target_tags: list[str]) -> bool:
        """Darf der Agent Inhalte mit `target_tags` in `domain` schreiben?

        Ohne Tag-Einschraenkung immer True; sonst muss die Schnittmenge der
        Ziel-Tags mit der erlaubten Menge nicht leer sein.
        """
        allowed = self.write_tags_for(domain)
        if allowed is None:
            return True
        return bool(set(target_tags) & set(allowed))

    def can_transition(self, domain: str, *, promote: bool) -> bool:
        """Darf der Agent in `domain` promoten (`promote=True`) bzw. retiren?

        Verlangt `promote_retire`; ein `transition_grants`-Eintrag fuer die Domain
        schraenkt zusaetzlich pro Richtung ein. Ohne Eintrag gilt die ungeteilte
        `promote_retire`.
        """
        if not self.promote_retire:
            return False
        grant = self.transition_grants.get(domain)
        if grant is None:
            return True
        return grant.promote if promote else grant.retire

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
        if not all(not getattr(self, name) or getattr(other, name) for name in bool_fields):
            return False
        # Effektive Transition-Rechte (promote_retire + transition_grants) duerfen
        # die des Verwalters pro Domain/Richtung nicht uebersteigen.
        for domain in _TRANSITION_DOMAINS:
            for promote in (True, False):
                if self.can_transition(domain, promote=promote) and not other.can_transition(
                    domain, promote=promote
                ):
                    return False
        # Write-Tag-Scope: `self` darf in keiner Domain breiter schreiben als
        # `other`. `other` unrestricted (None) erlaubt jeden self-Scope; ist
        # `other` eingeschraenkt, muss `self` ebenfalls eingeschraenkt sein und
        # eine Teilmenge bilden.
        for domain in _TRANSITION_DOMAINS:
            other_tags = other.write_tags_for(domain)
            if other_tags is None:
                continue
            self_tags = self.write_tags_for(domain)
            if self_tags is None or not set(self_tags) <= set(other_tags):
                return False
        return True


# Scope-Rang fuer den Teilmengen-Vergleich (`is_within`): mehr Sicht = hoeher.
_SCOPE_RANK: dict[ReadScope, int] = {
    ReadScope.none: 0,
    ReadScope.assigned: 1,
    ReadScope.all: 2,
}
