"""Gespraechsprotokoll und Massnahme (ADR-0053 3.5, 3.6; Lernschleife Phase E, Paket E2a-1).

Spiegel der Tabellen `feedback_session`, `feedback_session_case`, `measure`,
`measure_case` und `measure_event` aus
`apps/api/src/who2be_api/migrations/0103_feedback_session_measure.sql`.

- **Protokoll** (`feedback_session`): Ergebnis eines Feedback-Gespraechs zu
  EINEM Agenten. Wird in einem Aufruf samt Faellen und Massnahmen eingereicht
  und ist danach unveraenderlich; eine Korrektur ist ein neues Protokoll mit
  `supersedes_id`.
- **Massnahme** (`measure`): die kleinste Aenderung an einem Element, immer
  mit Pruefall (`test_case_id` Pflicht) und mindestens einem Fall.
- **Zustand** einer Massnahme ist keine Spalte: er kommt aus dem juengsten
  Event (`measure_state_for`). Ohne Event ist die Massnahme `agreed`
  (beschlossen).

Wer einreichen, verknuepfen oder einstufen darf und welche Event-Folgen
erlaubt sind, prueft der Service (E2b). Die Modelle spiegeln Form und
Laengen; die Form-Regeln der Events stehen zusaetzlich als DB-CHECK.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from who2be_models.status_history import EntityType

# Laengen-Deckel, gespiegelt aus den CHECKs der Migration 0103 (ADR 3.5/3.6;
# Anhang B: 2 000 „Freitextfelder Fall/Massnahme“).
SESSION_SUMMARY_MAX_LENGTH = 4_000
MEASURE_CHANGE_SUMMARY_MAX_LENGTH = 2_000
MEASURE_SUCCESS_CRITERION_MAX_LENGTH = 1_000
MEASURE_COUNTERPOSITION_MAX_LENGTH = 1_000
MEASURE_EVENT_NOTE_MAX_LENGTH = 2_000
# Eintraege in `participants`, `decisions`, `dissent` (jsonb ohne DB-Deckel):
# gleiche Grenze wie die Notiz eines Events, damit ein Protokoll kein
# Transkript wird.
SESSION_ITEM_TEXT_MAX_LENGTH = 2_000
SESSION_PARTICIPANT_ROLE_MAX_LENGTH = 200
SESSION_STANDARD_REF_MAX_LENGTH = 500


class SessionTrigger(StrEnum):
    """Anlass eines Gespraechs (3.5)."""

    threshold = "threshold"
    scheduled = "scheduled"
    manual = "manual"


class SessionParticipantKind(StrEnum):
    """Wer am Gespraech teilnahm (3.5 `participants.kind`)."""

    human = "human"
    agent = "agent"
    builder = "builder"


class SessionSubmitterKind(StrEnum):
    """Wer das Protokoll eingereicht hat: ein Mensch oder ein Agent (Builder)."""

    human = "human"
    agent = "agent"


class MeasureTarget(StrEnum):
    """Element einer Massnahme (3.6): wie `CaseTarget`, ohne `model_limit`."""

    persona = "persona"
    playbook = "playbook"
    resource = "resource"
    external_tool = "external_tool"
    system_prompt_template = "system_prompt_template"
    tool_policy = "tool_policy"
    memory = "memory"


# `tool_policy` haengt am Agenten und hat keine `entity_id`. Gleiche Regel
# als DB-CHECK `measure_entity_check`.
MEASURE_TARGETS_WITHOUT_ENTITY: frozenset[MeasureTarget] = frozenset({MeasureTarget.tool_policy})


class MeasureEventKind(StrEnum):
    """Ereignisse im Verlauf einer Massnahme (3.6, Tabelle)."""

    draft_linked = "draft_linked"
    activated = "activated"
    follow_up_prepared = "follow_up_prepared"
    reviewed = "reviewed"
    withdrawn = "withdrawn"


class MeasureVerdict(StrEnum):
    """Einstufung der Nachschau (3.6 `reviewed`); nur ein Mensch."""

    effective = "effective"
    ineffective = "ineffective"
    not_measurable = "not_measurable"


class MeasureActorKind(StrEnum):
    """Wer ein Massnahmen-Event ausgeloest hat."""

    human = "human"
    agent = "agent"
    system = "system"


class MeasureState(StrEnum):
    """Abgeleiteter Zustand einer Massnahme (juengstes Event).

    `agreed` heisst: beschlossen, noch kein Event. Die drei Einstufungen
    sind eigene Zustaende, damit eine Liste ohne zweites Feld filtern kann.
    """

    agreed = "agreed"
    draft_linked = "draft_linked"
    activated = "activated"
    follow_up_prepared = "follow_up_prepared"
    effective = "effective"
    ineffective = "ineffective"
    not_measurable = "not_measurable"
    withdrawn = "withdrawn"


# Abgeschlossene Zustaende: hier ist keine Nachschau mehr faellig (PM-3).
MEASURE_CLOSED_STATES: frozenset[MeasureState] = frozenset(
    {
        MeasureState.effective,
        MeasureState.ineffective,
        MeasureState.not_measurable,
        MeasureState.withdrawn,
    }
)

# Events, die eine Version tragen (DB-CHECK `measure_event_version_check`).
MEASURE_VERSION_EVENTS: frozenset[MeasureEventKind] = frozenset(
    {MeasureEventKind.draft_linked, MeasureEventKind.activated}
)


def measure_state_for(
    event: MeasureEventKind | None, verdict: MeasureVerdict | None
) -> MeasureState:
    """Zustand aus dem juengsten Event; None = noch kein Event (`agreed`)."""
    if event is None:
        return MeasureState.agreed
    if event is MeasureEventKind.reviewed:
        if verdict is None:
            raise ValueError("reviewed ohne verdict")
        return MeasureState(verdict.value)
    return MeasureState(event.value)


# --- Bestandteile des Protokolls ---------------------------------------------


class SessionParticipant(BaseModel):
    """Ein Teilnehmer `{kind, id, role}` (3.5).

    `id`: Nutzer-ID bei `human`, Agent-ID bei `agent`/`builder`. `role` ist
    Freitext (z. B. „Moderation“) und wird nicht uebersetzt.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: SessionParticipantKind
    id: UUID
    role: str = Field(min_length=1, max_length=SESSION_PARTICIPANT_ROLE_MAX_LENGTH)


class SessionDecision(BaseModel):
    """Ein entschiedener Widerspruch `{text, standard_ref?}` (3.5)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str = Field(min_length=1, max_length=SESSION_ITEM_TEXT_MAX_LENGTH)
    standard_ref: str | None = Field(
        default=None, min_length=1, max_length=SESSION_STANDARD_REF_MAX_LENGTH
    )


class SessionDissent(BaseModel):
    """Eine abweichende Meinung `{participant_kind, participant_id, text}` (3.5)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    participant_kind: SessionParticipantKind
    participant_id: UUID
    text: str = Field(min_length=1, max_length=SESSION_ITEM_TEXT_MAX_LENGTH)


# --- Massnahme -----------------------------------------------------------------


class MeasureCreate(BaseModel):
    """Eine Massnahme im Protokoll (6.6 `measures[]`).

    `case_ids` mindestens ein Eintrag (3.6 „>= 1“); dass die Faelle zum
    Protokoll gehoeren, prueft der Service.
    """

    model_config = ConfigDict(extra="forbid")

    case_ids: list[UUID] = Field(min_length=1)
    target: MeasureTarget
    entity_id: UUID | None = None
    change_summary: str = Field(min_length=1, max_length=MEASURE_CHANGE_SUMMARY_MAX_LENGTH)
    test_case_id: UUID
    success_criterion: str = Field(min_length=1, max_length=MEASURE_SUCCESS_CRITERION_MAX_LENGTH)
    counterposition: str = Field(min_length=1, max_length=MEASURE_COUNTERPOSITION_MAX_LENGTH)
    follow_up_at: date | None = None

    @model_validator(mode="after")
    def _check_shape(self) -> MeasureCreate:
        """Spiegelt `measure_entity_check`; Dubletten in `case_ids` einmal."""
        if (self.entity_id is None) != (self.target in MEASURE_TARGETS_WITHOUT_ENTITY):
            raise ValueError("entity_id ist bei tool_policy leer, sonst Pflicht.")
        self.case_ids = list(dict.fromkeys(self.case_ids))
        return self


class MeasureEventCreate(BaseModel):
    """Ein Massnahmen-Event. Akteur setzt der Server aus dem Aufrufweg."""

    model_config = ConfigDict(extra="forbid")

    event: MeasureEventKind
    version_entity_type: EntityType | None = None
    version_id: UUID | None = None
    verdict: MeasureVerdict | None = None
    metrics: dict[str, Any] | None = None
    note: str | None = Field(default=None, min_length=1, max_length=MEASURE_EVENT_NOTE_MAX_LENGTH)

    @model_validator(mode="after")
    def _check_shape(self) -> MeasureEventCreate:
        """Spiegelt die Form-CHECKs von `measure_event` (Migration 0103)."""
        if (self.version_entity_type is None) != (self.version_id is None):
            raise ValueError("version_entity_type und version_id nur gemeinsam angeben.")
        if (self.event in MEASURE_VERSION_EVENTS) != (self.version_id is not None):
            raise ValueError("Eine Version gehoert genau zu draft_linked und activated.")
        if (self.event is MeasureEventKind.follow_up_prepared) != (self.metrics is not None):
            raise ValueError("metrics gehoert genau zu follow_up_prepared.")
        if (self.event is MeasureEventKind.reviewed) != (self.verdict is not None):
            raise ValueError("verdict gehoert genau zu reviewed.")
        needs_reason = (
            self.event is MeasureEventKind.withdrawn or self.verdict is MeasureVerdict.ineffective
        )
        if needs_reason and self.note is None:
            raise ValueError("withdrawn und ineffective verlangen eine Begruendung.")
        return self


class MeasureEventRead(BaseModel):
    """Ein Event aus dem Verlauf einer Massnahme (append-only)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    measure_id: UUID
    event: MeasureEventKind
    actor_kind: MeasureActorKind
    actor_id: UUID | None
    version_entity_type: EntityType | None
    version_id: UUID | None
    verdict: MeasureVerdict | None
    metrics: dict[str, Any] | None
    note: str | None
    created_at: datetime


class MeasureRead(BaseModel):
    """Eine Massnahme mit Faellen, abgeleitetem Zustand und Verlauf (aelteste zuerst)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    agent_id: UUID
    session_id: UUID
    case_ids: list[UUID]
    target: MeasureTarget
    entity_id: UUID | None
    change_summary: str
    test_case_id: UUID
    success_criterion: str
    counterposition: str
    follow_up_at: date | None
    state: MeasureState
    events: list[MeasureEventRead]
    created_at: datetime


# --- Protokoll -----------------------------------------------------------------


class SessionCreate(BaseModel):
    """Protokoll samt Faellen und Massnahmen (6.6 `submit_session_protocol`).

    Einreicher (`submitted_by_*`) setzt der Server aus dem Aufrufweg.
    """

    model_config = ConfigDict(extra="forbid")

    agent_id: UUID
    trigger: SessionTrigger
    participants: list[SessionParticipant] = Field(default_factory=list)
    case_ids: list[UUID] = Field(default_factory=list)
    summary: str = Field(min_length=1, max_length=SESSION_SUMMARY_MAX_LENGTH)
    decisions: list[SessionDecision] = Field(default_factory=list)
    dissent: list[SessionDissent] = Field(default_factory=list)
    follow_up_at: date
    measures: list[MeasureCreate] = Field(default_factory=list)
    supersedes_id: UUID | None = None

    @model_validator(mode="after")
    def _dedupe_cases(self) -> SessionCreate:
        """Dubletten in `case_ids` einmal (Primaerschluessel je Sitzung und Fall)."""
        self.case_ids = list(dict.fromkeys(self.case_ids))
        return self


class SessionRead(BaseModel):
    """Ein Protokoll ohne Massnahmen (Liste)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    agent_id: UUID
    trigger: SessionTrigger
    participants: list[SessionParticipant]
    summary: str
    decisions: list[SessionDecision]
    dissent: list[SessionDissent]
    follow_up_at: date
    supersedes_id: UUID | None
    submitted_by_kind: SessionSubmitterKind
    submitted_by: UUID
    case_ids: list[UUID]
    created_at: datetime


class SessionDetail(BaseModel):
    """Protokoll mit eingebetteten Massnahmen (QE1 = a)."""

    session: SessionRead
    measures: list[MeasureRead]
