"""Fall (ADR-0053 Abschnitt 3.3, Lernschleife Phase D, Paket D1a).

Spiegel der Tabellen `agent_case`, `agent_case_event`, `agent_case_element`
und `agent_case_statement` aus
`apps/api/src/who2be_api/migrations/0100_agent_case.sql`.

- **Fall** (`agent_case`): Einzelrueckmeldung zum Verhalten eines Agenten
  (Situation, Verhalten, Folge, erwartetes Verhalten). Der Inhalt ist nach dem
  Anlegen unveraenderlich; Ergaenzungen sind Events.
- **Status** ist keine Spalte. Er kommt aus dem juengsten Status-Event
  (`status_for_event`); `reported` bedeutet `open`. Muster
  `feedback_resolution`.
- **Zuordnung** (`agent_case_element`): n:m zu Elementen; `entity_id` ist
  genau bei `tool_policy` und `model_limit` leer.
- **Schilderung** (`agent_case_statement`): nur der betroffene Agent,
  append-only; die neueste gilt in der Anzeige.

Melden und Einordnen sind getrennt (PM-Entscheidung Q2, 2026-10-07):
`CaseCreate` nimmt keine Zuordnung an.

Wer melden, lesen, triagieren oder schildern darf (3.3, Tabelle „Rechte“), und
welche Uebergaenge erlaubt sind, prueft der Service (D2). Die Modelle spiegeln
nur Form und Laengen.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from who2be_models.feedback import FeedbackSignal
from who2be_models.status_history import EntityType

# Laengen-Deckel, gespiegelt aus den CHECKs der Migration 0100 (ADR 3.3,
# Anhang B: 4 000 fuer Situation/Verhalten sind eine gesetzte Annahme, 2 000
# ist von `FeedbackCreate.note` uebernommen).
CASE_SITUATION_MAX_LENGTH = 4_000
CASE_BEHAVIOR_MAX_LENGTH = 4_000
CASE_IMPACT_MAX_LENGTH = 2_000
CASE_EXPECTED_MAX_LENGTH = 2_000
CASE_SOURCE_REF_MAX_LENGTH = 500
CASE_NOTE_MAX_LENGTH = 2_000
CASE_STATEMENT_FIELD_MAX_LENGTH = 2_000


class CaseStatus(StrEnum):
    """Abgeleiteter Status eines Falls (3.3, Zustandsdiagramm)."""

    open = "open"
    triaged = "triaged"
    in_progress = "in_progress"
    addressed = "addressed"
    verified = "verified"
    reopened = "reopened"
    dismissed = "dismissed"


class CaseEventKind(StrEnum):
    """Ereignisse im Verlauf eines Falls.

    Die Status-Events tragen den Namen des Zielstatus; `reported` ist das
    Anlege-Event (Status `open`). Die drei uebrigen aendern den Status nicht.
    """

    reported = "reported"
    triaged = "triaged"
    in_progress = "in_progress"
    addressed = "addressed"
    verified = "verified"
    reopened = "reopened"
    dismissed = "dismissed"
    element_assigned = "element_assigned"
    element_unassigned = "element_unassigned"
    statement = "statement"


# Status-Event -> Status. Events ausserhalb dieser Tabelle aendern den Status nicht.
CASE_STATUS_EVENTS: dict[CaseEventKind, CaseStatus] = {
    CaseEventKind.reported: CaseStatus.open,
    CaseEventKind.triaged: CaseStatus.triaged,
    CaseEventKind.in_progress: CaseStatus.in_progress,
    CaseEventKind.addressed: CaseStatus.addressed,
    CaseEventKind.verified: CaseStatus.verified,
    CaseEventKind.reopened: CaseStatus.reopened,
    CaseEventKind.dismissed: CaseStatus.dismissed,
}


def status_for_event(event: CaseEventKind) -> CaseStatus | None:
    """Status, den ein Event setzt; None bei Events ohne Statuswirkung."""
    return CASE_STATUS_EVENTS.get(event)


class CaseReporterKind(StrEnum):
    """Wer den Fall gemeldet hat (3.3)."""

    human = "human"
    agent = "agent"
    builder = "builder"
    pattern = "pattern"


class CaseSeverity(StrEnum):
    """Schwere eines Falls, Default `medium`."""

    low = "low"
    medium = "medium"
    high = "high"


class CaseActorKind(StrEnum):
    """Wer ein Event ausgeloest hat. `system` z. B. fuer `addressed` bei Aktivierung (F3)."""

    human = "human"
    agent = "agent"
    system = "system"


class CaseAssignedByKind(StrEnum):
    """Wer eine Zuordnung gesetzt hat (Mensch oder Builder mit `case_triage`)."""

    human = "human"
    agent = "agent"


class CaseTarget(StrEnum):
    """Ziel einer Zuordnung (3.3)."""

    persona = "persona"
    playbook = "playbook"
    resource = "resource"
    external_tool = "external_tool"
    system_prompt_template = "system_prompt_template"
    tool_policy = "tool_policy"
    memory = "memory"
    model_limit = "model_limit"


# Ziele ohne `entity_id`: `tool_policy` haengt am Agenten, `model_limit` ist
# „Modellgrenze, keine Aenderung sinnvoll“. Gleiche Regel als DB-CHECK.
CASE_TARGETS_WITHOUT_ENTITY: frozenset[CaseTarget] = frozenset(
    {CaseTarget.tool_policy, CaseTarget.model_limit}
)


class CaseCreate(BaseModel):
    """Eingabe fuer einen neuen Fall.

    Melder (`reporter_*`) und Herkunft (`source_feedback_id`,
    `source_memory_id`) setzt der Server aus dem Aufrufweg; sie sind deshalb
    nicht Teil dieses Modells. Keine Zuordnung (Q2).
    """

    model_config = ConfigDict(extra="forbid")

    agent_id: UUID
    situation: str = Field(min_length=1, max_length=CASE_SITUATION_MAX_LENGTH)
    behavior: str = Field(min_length=1, max_length=CASE_BEHAVIOR_MAX_LENGTH)
    impact: str | None = Field(default=None, min_length=1, max_length=CASE_IMPACT_MAX_LENGTH)
    expected_behavior: str = Field(min_length=1, max_length=CASE_EXPECTED_MAX_LENGTH)
    severity: CaseSeverity = CaseSeverity.medium
    signal: FeedbackSignal | None = None
    source_ref: str | None = Field(
        default=None, min_length=1, max_length=CASE_SOURCE_REF_MAX_LENGTH
    )


class CaseConvertRequest(BaseModel):
    """Eingabe fuer „Lernvorschlag -> Fall“ (`convert`, ADR-0053 6.4).

    Die Fall-Felder aus `CaseCreate` ohne `agent_id`: der Agent kommt aus dem
    Lernvorschlag (ein Lernvorschlag ist die Lehre eines Agenten ueber sich
    selbst, 3.1.6; der Composite-FK aus 0100 verlangt denselben Agenten).
    """

    model_config = ConfigDict(extra="forbid")

    situation: str = Field(min_length=1, max_length=CASE_SITUATION_MAX_LENGTH)
    behavior: str = Field(min_length=1, max_length=CASE_BEHAVIOR_MAX_LENGTH)
    impact: str | None = Field(default=None, min_length=1, max_length=CASE_IMPACT_MAX_LENGTH)
    expected_behavior: str = Field(min_length=1, max_length=CASE_EXPECTED_MAX_LENGTH)
    severity: CaseSeverity = CaseSeverity.medium
    signal: FeedbackSignal | None = None
    source_ref: str | None = Field(
        default=None, min_length=1, max_length=CASE_SOURCE_REF_MAX_LENGTH
    )

    def for_agent(self, agent_id: UUID) -> CaseCreate:
        """Dieselben Felder als `CaseCreate` fuer den Agenten des Lernvorschlags."""
        return CaseCreate(agent_id=agent_id, **self.model_dump())


class CaseRead(BaseModel):
    """Ein Fall mit abgeleitetem Status."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    agent_id: UUID
    reporter_kind: CaseReporterKind
    reporter_user_id: UUID | None
    reporter_agent_id: UUID | None
    situation: str
    behavior: str
    impact: str | None
    expected_behavior: str
    severity: CaseSeverity
    signal: FeedbackSignal | None
    source_ref: str | None
    source_feedback_id: UUID | None
    source_memory_id: UUID | None
    status: CaseStatus
    created_at: datetime


class CaseElementInput(BaseModel):
    """Eine Zuordnung im Request (Replace-Semantik von `PUT /cases/{id}/elements`)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target: CaseTarget
    entity_id: UUID | None = None

    @model_validator(mode="after")
    def _check_entity(self) -> CaseElementInput:
        """Spiegelt den CHECK `agent_case_element_entity_check`."""
        if (self.entity_id is None) != (self.target in CASE_TARGETS_WITHOUT_ENTITY):
            raise ValueError("entity_id ist bei tool_policy und model_limit leer, sonst Pflicht.")
        return self


class CaseElementRead(BaseModel):
    """Eine gespeicherte Zuordnung."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    target: CaseTarget
    entity_id: UUID | None
    assigned_by_kind: CaseAssignedByKind
    assigned_by: UUID
    created_at: datetime


class CaseEventCreate(BaseModel):
    """Ein Status-Event. Element- und Schilderungs-Events schreibt das Repository selbst."""

    model_config = ConfigDict(extra="forbid")

    event: CaseEventKind
    note: str | None = Field(default=None, min_length=1, max_length=CASE_NOTE_MAX_LENGTH)
    version_entity_type: EntityType | None = None
    version_id: UUID | None = None
    measure_id: UUID | None = None

    @model_validator(mode="after")
    def _check_shape(self) -> CaseEventCreate:
        """Spiegelt die Form-CHECKs der Migration (Paar, Pflichtfelder je Event)."""
        if self.event not in CASE_STATUS_EVENTS:
            raise ValueError("Nur Status-Events; Zuordnung und Schilderung haben eigene Wege.")
        if (self.version_entity_type is None) != (self.version_id is None):
            raise ValueError("version_entity_type und version_id nur gemeinsam angeben.")
        if self.event is CaseEventKind.addressed and self.version_id is None:
            raise ValueError("addressed verlangt eine Version.")
        if (
            self.event in (CaseEventKind.in_progress, CaseEventKind.verified)
            and self.measure_id is None
        ):
            raise ValueError("in_progress und verified verlangen eine Massnahme.")
        if self.event in (CaseEventKind.reopened, CaseEventKind.dismissed) and self.note is None:
            raise ValueError("reopened und dismissed verlangen eine Begruendung.")
        return self


class CaseEventRead(BaseModel):
    """Ein Event aus dem Verlauf (append-only)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    event: CaseEventKind
    actor_kind: CaseActorKind
    actor_id: UUID | None
    note: str | None
    version_entity_type: EntityType | None
    version_id: UUID | None
    measure_id: UUID | None
    element_target: CaseTarget | None
    element_entity_id: UUID | None
    created_at: datetime


class CaseStatementCreate(BaseModel):
    """Schilderung des betroffenen Agenten, ohne Selbstnote (3.3)."""

    model_config = ConfigDict(extra="forbid")

    followed_instruction: str = Field(max_length=CASE_STATEMENT_FIELD_MAX_LENGTH)
    missing_information: str = Field(max_length=CASE_STATEMENT_FIELD_MAX_LENGTH)
    conflict: str = Field(max_length=CASE_STATEMENT_FIELD_MAX_LENGTH)


class CaseStatementRead(BaseModel):
    """Eine gespeicherte Schilderung."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    agent_id: UUID
    followed_instruction: str
    missing_information: str
    conflict: str
    created_at: datetime


class CaseDetail(BaseModel):
    """Fall mit Verlauf, Zuordnungen und Schilderungen (fuer `GET /cases/{id}`, D2)."""

    case: CaseRead
    events: list[CaseEventRead]
    elements: list[CaseElementRead]
    statements: list[CaseStatementRead]
