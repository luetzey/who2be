"""Usage-/Feedback-Flywheel-Models (ADR-0038).

Der Rueckkanal einer AgentDB: konsumierende Agenten melden, WAS sie genutzt haben
(`UsageEventCreate`) und WIE gut es war (`FeedbackCreate`). Beide sind
append-only Telemetrie — sie fliessen NIE in einen gerenderten System-Prompt
(kein Injection-Vektor), sondern speisen nur Kurations-Aggregate
(`FeedbackSummary`).

`entity_type` ist auf die drei Kern-Inhaltselemente beschraenkt (Persona,
Playbook, Resource) — Agenten/Templates sind keine konsumierbaren Wissensobjekte.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

FeedbackTarget = Literal["persona", "playbook", "resource"]


class UsageOutcome(StrEnum):
    """Ergebnis einer Nutzung — quantitatives Signal."""

    applied = "applied"
    skipped = "skipped"
    error = "error"


class FeedbackSignal(StrEnum):
    """Qualitatives Feedback-Signal eines Agenten zu einem Element."""

    helpful = "helpful"
    outdated = "outdated"
    incorrect = "incorrect"
    unclear = "unclear"


class UsageEventCreate(BaseModel):
    """Eingabe von `record_usage`: ein Nutzungs-Ereignis."""

    model_config = ConfigDict(extra="forbid")

    entity_type: FeedbackTarget
    entity_id: UUID
    version: int | None = Field(default=None, ge=1)
    outcome: UsageOutcome | None = None


class FeedbackCreate(BaseModel):
    """Eingabe von `submit_feedback`: ein qualitatives Signal + optionale Notiz."""

    model_config = ConfigDict(extra="forbid")

    entity_type: FeedbackTarget
    entity_id: UUID
    version: int | None = Field(default=None, ge=1)
    signal: FeedbackSignal
    note: str | None = Field(default=None, max_length=2_000)


class UsageEventRead(BaseModel):
    """Ein persistiertes Nutzungs-Ereignis (read-only)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    entity_type: FeedbackTarget
    entity_id: UUID
    version: int | None = None
    outcome: UsageOutcome | None = None
    agent_id: UUID | None = None
    created_at: datetime


class AgentFeedbackRead(BaseModel):
    """Ein persistiertes Feedback (read-only)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    entity_type: FeedbackTarget
    entity_id: UUID
    version: int | None = None
    signal: FeedbackSignal
    note: str | None = None
    agent_id: UUID | None = None
    created_at: datetime


class FeedbackSummary(BaseModel):
    """Aggregat fuer `get_feedback` — Kurations-Sicht auf ein Element.

    `usage_count` = Anzahl Nutzungs-Ereignisse; `by_outcome`/`by_signal` zaehlen
    pro Auspraegung; `recent_notes` traegt die juengsten Freitext-Notizen
    (escaped im UI angezeigt). Leere Maps/Listen, wenn noch nichts vorliegt.
    """

    model_config = ConfigDict(from_attributes=True)

    entity_type: FeedbackTarget
    entity_id: UUID
    usage_count: int = Field(ge=0, default=0)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    by_signal: dict[str, int] = Field(default_factory=dict)
    recent_notes: list[str] = Field(default_factory=list)
