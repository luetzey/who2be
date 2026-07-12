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
# Read-/Speicher-seitiger Typ: Inhalts-Feedback (persona/playbook/resource) PLUS
# zielloses System-Feedback ("system" — technische/MCP-Probleme an der Plattform
# selbst, ohne Inhalts-Bezug). `FeedbackTarget` bleibt bewusst auf die drei
# konsumierbaren Inhaltselemente beschraenkt (Usage/Per-Element-Reads).
FeedbackEntityType = Literal["persona", "playbook", "resource", "system"]


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


class SystemFeedbackCategory(StrEnum):
    """Kategorie eines System-/Plattform-Problems (zielloses Feedback).

    Anders als `FeedbackSignal` (Qualitaet eines Inhalts-Elements) klassifiziert
    dies ein Problem an der Plattform selbst: `technical` (allgemeiner Bug/Fehler
    in der App), `mcp` (Problem am MCP-Server/-Tooling), `performance` (zu
    langsam/haengt) oder `other`. Wird in derselben `agent_feedback`-Spalte
    `signal` gespeichert (entity_type='system', entity_id=NULL) und fliesst in
    den gemeinsamen Kurations-Posteingang.
    """

    technical = "technical"
    mcp = "mcp"
    performance = "performance"
    other = "other"


class FeedbackResolution(StrEnum):
    """Triage-Status eines Feedback-Eintrags (ADR-0038, append-only).

    Kuratoren markieren einzelne Signale: `addressed` (umgesetzt), `in_progress`
    (in Bearbeitung) oder `dismissed` (bewusst verworfen). Der „aktuelle" Status
    ist das juengste Resolution-Event — die Feedback-Zeile selbst bleibt
    unveraendert (append-only).
    """

    addressed = "addressed"
    in_progress = "in_progress"
    dismissed = "dismissed"


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


class SystemFeedbackCreate(BaseModel):
    """Eingabe von `report_problem`: ein zielloses System-/MCP-Problem.

    Kein `entity_*` — das Problem haengt an der Plattform, nicht an einem Inhalt.
    `category` klassifiziert es, `note` beschreibt es (Pflicht — ein Report ohne
    Beschreibung ist nutzlos).
    """

    model_config = ConfigDict(extra="forbid")

    category: SystemFeedbackCategory
    note: str = Field(min_length=1, max_length=2_000)


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


class FeedbackResolutionCreate(BaseModel):
    """Eingabe von `set_feedback_resolution`: ein Triage-Ereignis."""

    model_config = ConfigDict(extra="forbid")

    resolution: FeedbackResolution
    note: str | None = Field(default=None, max_length=2_000)


class AgentFeedbackRead(BaseModel):
    """Ein persistiertes Feedback (read-only).

    `resolution` traegt den aktuellen Triage-Status (juengstes Resolution-Event)
    oder None, solange das Feedback nicht triagiert wurde.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    # 'system' fuer zielloses Plattform-/MCP-Feedback (dann entity_id=None und
    # signal traegt eine SystemFeedbackCategory).
    entity_type: FeedbackEntityType
    entity_id: UUID | None = None
    version: int | None = None
    signal: FeedbackSignal | SystemFeedbackCategory
    note: str | None = None
    agent_id: UUID | None = None
    created_at: datetime
    resolution: FeedbackResolution | None = None


class FeedbackItem(BaseModel):
    """Ein einzelnes Feedback workspace-weit, angereichert um den Element-Namen.

    Das Ruckgrat des zentralen Feedback-Posteingangs (`GET …/feedback-items`):
    jedes qualitative Feedback mit Element-Bezug, Triage-Status und Metadaten —
    damit Kuratoren ALLE Feedbacks an einem Ort sehen und abarbeiten koennen.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    # 'system' = zielloses Plattform-/MCP-Feedback: dann entity_id=None, `name`
    # traegt ein Label ("System") und `signal` eine SystemFeedbackCategory.
    entity_type: FeedbackEntityType
    entity_id: UUID | None = None
    name: str
    version: int | None = None
    signal: FeedbackSignal | SystemFeedbackCategory
    note: str | None = None
    agent_id: UUID | None = None
    created_at: datetime
    resolution: FeedbackResolution | None = None


class FeedbackResolutionEvent(BaseModel):
    """Ein einzelnes Triage-Ereignis aus der `feedback_resolution`-Historie.

    Append-only: pro Kurations-Handlung eine Zeile. Der „aktuelle" Status eines
    Feedbacks ist das juengste Event; die vollstaendige Historie (aelteste→
    juengste) traegt `FeedbackDetailRead.history` fuer die Einzel-Feedback-
    Detailsicht.
    """

    model_config = ConfigDict(from_attributes=True)

    resolution: FeedbackResolution
    actor_id: UUID | None = None
    note: str | None = None
    created_at: datetime


class FeedbackDetailRead(FeedbackItem):
    """Detailsicht auf EIN Feedback (`GET …/feedback/{feedback_id}`).

    Erweitert `FeedbackItem` (id, entity_type/-id, Element-`name`, version,
    signal, note, agent_id, created_at, aktuelle `resolution`) um den menschlichen
    Absender (`actor_id`) und die vollstaendige, chronologische Triage-Historie
    (`history`, aelteste→juengste) — die Datengrundlage fuer die
    Einzel-Feedback-Detailseite.
    """

    actor_id: UUID | None = None
    history: list[FeedbackResolutionEvent] = Field(default_factory=list)


class FeedbackItemCounts(BaseModel):
    """Status-Verteilung ueber ALLE Feedbacks (speist die KPI-Leiste)."""

    model_config = ConfigDict(from_attributes=True)

    open: int = Field(ge=0, default=0)
    in_progress: int = Field(ge=0, default=0)
    addressed: int = Field(ge=0, default=0)
    dismissed: int = Field(ge=0, default=0)


class FeedbackItems(BaseModel):
    """Workspace-weiter Feedback-Posteingang: Eintraege + Status-Zaehler."""

    model_config = ConfigDict(from_attributes=True)

    items: list[FeedbackItem] = Field(default_factory=list)
    counts: FeedbackItemCounts = Field(default_factory=FeedbackItemCounts)


class FeedbackSummaryItem(BaseModel):
    """Ein einzelnes Feedback im `get_feedback`-Aggregat (Triage-Grundlage).

    Traegt die `id` (adressierbar fuer `resolve_feedback`/den Resolution-
    Endpoint) und den aktuellen Triage-Status (`resolution` = juengstes
    Resolution-Event oder None = offen) — damit ein Agent aus dem Aggregat
    heraus gezielt einzelne Signale schliessen kann.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    signal: FeedbackSignal | SystemFeedbackCategory
    note: str | None = None
    resolution: FeedbackResolution | None = None
    created_at: datetime


class FeedbackSummary(BaseModel):
    """Aggregat fuer `get_feedback` — Kurations-Sicht auf ein Element.

    `usage_count` = Anzahl Nutzungs-Ereignisse; `by_outcome`/`by_signal` zaehlen
    pro Auspraegung; `recent_notes` traegt die juengsten Freitext-Notizen
    (escaped im UI angezeigt). `recent_feedback` ergaenzt additiv die juengsten
    Einzel-Feedbacks mit `id` + Triage-Status (`resolution`) — adressierbar fuer
    die Triage; `recent_notes` bleibt fuer Back-Compat unveraendert. Leere
    Maps/Listen, wenn noch nichts vorliegt.
    """

    model_config = ConfigDict(from_attributes=True)

    entity_type: FeedbackTarget
    entity_id: UUID
    usage_count: int = Field(ge=0, default=0)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    by_signal: dict[str, int] = Field(default_factory=dict)
    recent_notes: list[str] = Field(default_factory=list)
    recent_feedback: list[FeedbackSummaryItem] = Field(default_factory=list)


class FeedbackEvents(BaseModel):
    """Drill-down fuer `get_feedback_events` — die juengsten Einzel-Ereignisse.

    Im Gegensatz zu `FeedbackSummary` (reine Zaehler) traegt dies die einzelnen
    Feedback- und Usage-Eintraege mit Akteur/Zeit/Version/Signal — die Kuratoren-
    Detailsicht. Beide Listen sind chronologisch absteigend und serverseitig
    gekappt.
    """

    model_config = ConfigDict(from_attributes=True)

    entity_type: FeedbackTarget
    entity_id: UUID
    feedback: list[AgentFeedbackRead] = Field(default_factory=list)
    usage: list[UsageEventRead] = Field(default_factory=list)


class FeedbackOverviewItem(BaseModel):
    """Eine Zeile der workspace-weiten Feedback-Uebersicht.

    Pro Element (mit mindestens einem Usage-/Feedback-Ereignis) die Kennzahlen,
    aus denen sich die Kurations-Prioritaeten ableiten: `usage_count` (wie oft
    genutzt), `negative_count` (Summe aus `outdated`/`incorrect`/`unclear` —
    Handlungsbedarf), `helpful_count` und der Zeitpunkt der letzten Aktivitaet.
    """

    model_config = ConfigDict(from_attributes=True)

    entity_type: FeedbackTarget
    entity_id: UUID
    name: str
    usage_count: int = Field(ge=0, default=0)
    feedback_count: int = Field(ge=0, default=0)
    negative_count: int = Field(ge=0, default=0)
    helpful_count: int = Field(ge=0, default=0)
    last_activity_at: datetime | None = None


class FeedbackOverview(BaseModel):
    """Workspace-weite Kurations-Uebersicht — speist Dashboard-Kacheln + Seite."""

    model_config = ConfigDict(from_attributes=True)

    items: list[FeedbackOverviewItem] = Field(default_factory=list)


class FeedbackUnusedItem(BaseModel):
    """Ein veroeffentlichtes, aber ungenutztes Element.

    „Ungenutzt" = das Element hat eine aktive Version (Agenten KOENNTEN es nutzen),
    aber bisher kein einziges Usage- oder Feedback-Ereignis. Das ist das
    handlungsrelevante Stale-Signal: publiziert, aber niemand greift darauf zu.
    """

    model_config = ConfigDict(from_attributes=True)

    entity_type: FeedbackTarget
    entity_id: UUID
    name: str


class FeedbackUnused(BaseModel):
    """Liste veroeffentlichter, aber ungenutzter Elemente (Stale-Kandidaten)."""

    model_config = ConfigDict(from_attributes=True)

    items: list[FeedbackUnusedItem] = Field(default_factory=list)
