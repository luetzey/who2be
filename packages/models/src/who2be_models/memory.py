"""Agent-Memory-Models (ADR-0044) — kuratiertes Langzeitgedaechtnis.

Agenten schlagen Fakten vor (`MemoryCreate` via MCP `save_memory`); je nach
`AgentToolPolicy.memory_mode` landen sie als `pending` (suggest — erst nach
menschlicher Triage retrieval-sichtbar) oder direkt `active` (auto). Nur
`active`-Memories sind ueber `search_memory`/`list_memories` abrufbar.
`rejected` bleibt als Zeile bestehen: der Dedup-Waechter prueft neue
Vorschlaege auch dagegen, sonst schlaegt der Agent denselben Fakt in der
naechsten Session erneut vor.

`context` ist reine Triage-Hilfe (1 Satz Begruendung des Agenten) — er wird
NUR in der Verwaltungs-UI angezeigt und fliesst NIE in Retrieval-Antworten
oder gerenderte Prompts (kein Injection-Vektor).

Kein agent-seitiges Update/Delete in v1: beides wuerde die Freigabe-Schleuse
umgehen. Editieren/Loeschen/Triage sind human-only (REST, editor+).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# Serverseitige Deckel (Waechter laufen in jedem Modus, ADR-0044).
MEMORY_FACT_MAX_LENGTH = 300
MEMORY_CONTEXT_MAX_LENGTH = 200
MEMORY_TRIAGE_NOTE_MAX_LENGTH = 500
MEMORY_MAX_PER_AGENT = 500
# Vorschlaege unterhalb dieser Importance lehnt der Server ab (Kap. 10.2 des
# Memory-Konzepts: konservativ speichern, Ballast gar nicht erst aufnehmen).
MEMORY_MIN_IMPORTANCE = 5
# Anzahl Top-Memories, die `get_persona` zur Laufzeit in `body_rendered`
# einbettet (WP-6: der System-Prompt wird nicht live aktualisiert — die
# Persona-Antwort ist der zuverlaessige Laufzeit-Injektionspunkt).
MEMORY_PERSONA_TOP_N = 5


class MemoryStatus(StrEnum):
    """Lebenszyklus eines Memorys (Kurations-Schleuse).

    `pending` (Vorschlag, retrieval-unsichtbar) → `active` (freigegeben,
    einziger abrufbarer Zustand) bzw. `rejected` (abgelehnt; bleibt als
    Dedup-Basis erhalten, bis der Mensch es endgueltig loescht).
    """

    pending = "pending"
    active = "active"
    rejected = "rejected"


class MemoryCategory(StrEnum):
    """Fachliche Einordnung eines Fakts (Kap. 10.5 des Memory-Konzepts)."""

    preference = "preference"
    fact = "fact"
    project = "project"
    instruction = "instruction"
    entity = "entity"
    general = "general"


class MemoryTriageAction(StrEnum):
    """Menschliche Triage-Entscheidung ueber einen `pending`-Vorschlag."""

    approve = "approve"
    reject = "reject"


class MemoryCreate(BaseModel):
    """Eingabe von `save_memory`: ein vorgeschlagener Fakt.

    `context` (optional): 1 Satz, WORAUS der Agent den Fakt geschlossen hat —
    nur fuer die Triage-Ansicht, nie im Retrieval.
    """

    model_config = ConfigDict(extra="forbid")

    fact: str = Field(min_length=1, max_length=MEMORY_FACT_MAX_LENGTH)
    category: MemoryCategory = MemoryCategory.general
    importance: int = Field(default=MEMORY_MIN_IMPORTANCE, ge=1, le=10)
    context: str | None = Field(default=None, max_length=MEMORY_CONTEXT_MAX_LENGTH)


class MemoryUpdate(BaseModel):
    """Menschliche Bearbeitung eines Memorys (UI, editor+) — Teilupdate."""

    model_config = ConfigDict(extra="forbid")

    fact: str | None = Field(default=None, min_length=1, max_length=MEMORY_FACT_MAX_LENGTH)
    category: MemoryCategory | None = None
    importance: int | None = Field(default=None, ge=1, le=10)


class MemoryTriage(BaseModel):
    """Triage eines `pending`-Vorschlags: freigeben oder ablehnen.

    `fact` erlaubt das Editieren-vor-Freigabe in einem Schritt; `note` haelt
    die Begruendung fest (v. a. bei Ablehnung).
    """

    model_config = ConfigDict(extra="forbid")

    action: MemoryTriageAction
    fact: str | None = Field(default=None, min_length=1, max_length=MEMORY_FACT_MAX_LENGTH)
    note: str | None = Field(default=None, max_length=MEMORY_TRIAGE_NOTE_MAX_LENGTH)


class MemoryRead(BaseModel):
    """Ein persistiertes Memory (read-only, Verwaltungs-Sicht).

    `retrieval_count`/`last_retrieved_at` sind das Nutzungs-Log: sie zeigen,
    ob und wann das Gedaechtnis real abgerufen wurde (Transparenz-Anforderung
    ADR-0044). Retrieval-Antworten an Agenten nutzen NICHT dieses Modell —
    sie liefern nur id/fact/category (ohne context/triage_note).
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_id: UUID
    status: MemoryStatus
    fact: str
    context: str | None = None
    category: MemoryCategory
    importance: int
    source: str
    triage_note: str | None = None
    retrieval_count: int
    last_retrieved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class MemoryHit(BaseModel):
    """Ein Retrieval-Treffer fuer Agenten (bewusst schmal).

    Nur id (Kurzform fuer Referenzen), Fakt und Kategorie — kein `context`,
    keine Triage-Metadaten (Injection-/Leak-Minimierung).
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    fact: str
    category: MemoryCategory
