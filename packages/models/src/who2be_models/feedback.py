"""Usage-/Feedback-Flywheel-Models (ADR-0038).

Der Rueckkanal einer AgentDB: konsumierende Agenten melden, WAS sie genutzt haben
(`UsageEventCreate`) und WIE gut es war (`FeedbackCreate`). Beide sind
append-only Telemetrie — sie fliessen NIE in einen gerenderten System-Prompt
(kein Injection-Vektor), sondern speisen nur Kurations-Aggregate
(`FeedbackSummary`).

`entity_type` ist auf die vier konsumierbaren Wissensobjekte beschraenkt (Persona,
Playbook, Resource, ExternalTool WP-3) — Agenten/Templates sind keine
konsumierbaren Wissensobjekte.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# `external_tool` (WP-3, Blueprint `.claude/plan/2026-07-18-1315_external-tools-
# tool-ref.md`) additiv ergaenzt — kein DB-CHECK-Constraint betroffen:
# `agent_feedback`/`usage_event` (Migration 0053/0059) validieren `entity_type`
# nicht per SQL-CHECK, nur ueber diesen Pydantic-Literal + `_ENTITY_TABLE`
# (`feedback_repository.py`).
FeedbackTarget = Literal["persona", "playbook", "resource", "external_tool"]
# Read-/Speicher-seitiger Typ: Inhalts-Feedback (persona/playbook/resource/
# external_tool) PLUS zielloses System-Feedback ("system" — technische/MCP-
# Probleme an der Plattform selbst, ohne Inhalts-Bezug).
FeedbackEntityType = Literal["persona", "playbook", "resource", "external_tool", "system"]


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
    # Nutzung U1: getrennt statt des vermischten `last_activity_at` —
    # `last_used_at` nur aus der Server-Aufzeichnung (Auslieferung an einen
    # Agenten), `last_feedback_at` nur aus `agent_feedback`.
    last_used_at: datetime | None = None
    last_feedback_at: datetime | None = None


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


# --- Nutzungszaehler (Konzept W5, Paket U1) ---------------------------------

# Elemente, deren Auslieferung an einen Agenten der Server aufzeichnet
# (`record_server_usage`, ADR-0053 3.4). External Tools haben noch keine
# Schreibstelle (Paket U2) und fehlen deshalb bewusst.
UsageEntityType = Literal["persona", "playbook", "resource"]

# Zaehlbeginn: Deploy der Server-Aufzeichnung (D3, #856, Migration 0101). Aeltere
# Zeilen sind Selbstauskunft (`agent_report`) und zaehlen nicht als Nutzung —
# ohne diesen Hinweis wirkt alles davor ungenutzt.
USAGE_COUNTING_SINCE = date(2026, 10, 8)


class UsageDay(BaseModel):
    """Auslieferungen an einem Kalendertag (UTC)."""

    model_config = ConfigDict(from_attributes=True)

    day: date
    uses: int = Field(ge=0, default=0)


class UsageStats(BaseModel):
    """Nutzungszaehler eines Elements (`GET …/usage/{entity_type}/{entity_id}`).

    Gezaehlt werden nur Auslieferungen an agent-gebundene Tokens (Owner-Weiche
    Z1a). Die Fenster sind Kalendertage in UTC einschliesslich heute, darum gilt
    `uses_30d == sum(daily.uses)`. `last_used_at` ist die juengste Auslieferung
    ueberhaupt, nicht nur im Fenster. `daily` traegt in der Einzelsicht genau 30
    Tage (aeltester zuerst, Luecken mit 0) und bleibt in Listen leer.
    """

    model_config = ConfigDict(from_attributes=True)

    entity_type: UsageEntityType
    entity_id: UUID
    name: str | None = None
    uses_7d: int = Field(ge=0, default=0)
    uses_30d: int = Field(ge=0, default=0)
    last_used_at: datetime | None = None
    distinct_agents_30d: int = Field(ge=0, default=0)
    daily: list[UsageDay] = Field(default_factory=list)
    counting_since: date = USAGE_COUNTING_SINCE


class UsageList(BaseModel):
    """Nutzungszaehler fuer Listen (`GET …/usage`), je Element eine Zeile."""

    model_config = ConfigDict(from_attributes=True)

    items: list[UsageStats] = Field(default_factory=list)
    counting_since: date = USAGE_COUNTING_SINCE


# --- Nutzungszaehler Agent und Arbeitsbereich (Konzept W5, Paket U2) --------


class UsageByType(BaseModel):
    """Auslieferungen an einen Agenten im 30-Tage-Fenster je Elementart."""

    model_config = ConfigDict(from_attributes=True)

    persona: int = Field(ge=0, default=0)
    playbook: int = Field(ge=0, default=0)
    resource: int = Field(ge=0, default=0)


class AccessDay(BaseModel):
    """Zugriffslog-Eintraege an einem Kalendertag."""

    model_config = ConfigDict(from_attributes=True)

    day: date
    accesses: int = Field(ge=0, default=0)


class AgentWorkAreaUsage(BaseModel):
    """Zugriffe eines Agenten auf einen Arbeitsbereich (aus `agent_access_log`).

    Das Log kennt je (Agent, Element, Operation) nur den Tag, darum ist
    `last_access_on` ein Datum ohne Uhrzeit.
    """

    model_config = ConfigDict(from_attributes=True)

    area_id: UUID
    access_days_30d: int = Field(ge=0, default=0)
    last_access_on: date | None = None


class AgentUsageStats(BaseModel):
    """Nutzungszaehler eines Agenten (`GET …/agents/{agent_id}/usage`).

    Owner-Weiche Z2a: nur aus vorhandenen Daten, kein `fetch_agent`-Zaehler.
    `uses_*`, `active_days_30d`, `last_used_at` und `daily` kommen aus den
    Auslieferungen an diesen Agenten (`usage_event`, `source='server'`),
    Fenster wie bei `UsageStats`. `last_active_at` ist der juengste
    Token-Aufruf des Agenten (`max(api_token.last_used_at)`), auch wenn dabei
    nichts ausgeliefert wurde. `work_areas` nennt die fuer den Aufrufer
    sichtbaren Arbeitsbereiche mit Zugriffen dieses Agenten.
    """

    model_config = ConfigDict(from_attributes=True)

    agent_id: UUID
    uses_7d: int = Field(ge=0, default=0)
    uses_30d: int = Field(ge=0, default=0)
    uses_by_type_30d: UsageByType = Field(default_factory=UsageByType)
    active_days_30d: int = Field(ge=0, le=30, default=0)
    last_used_at: datetime | None = None
    last_active_at: datetime | None = None
    daily: list[UsageDay] = Field(default_factory=list)
    work_areas: list[AgentWorkAreaUsage] = Field(default_factory=list)
    counting_since: date = USAGE_COUNTING_SINCE


class WorkAreaUsageStats(BaseModel):
    """Zugriffszaehler eines Arbeitsbereichs (`GET …/work-areas/{area_id}/usage`).

    Quelle ist das Zugriffslog (`agent_access_log`, ein Eintrag je Agent,
    Element, Operation und Tag) fuer Artifacts und Tabellen des Bereichs.
    `accesses_30d` zaehlt diese Eintraege, `access_days_30d` die Tage mit
    mindestens einem Eintrag. Keine Uhrzeit, keine Agent-Namen.
    """

    model_config = ConfigDict(from_attributes=True)

    area_id: UUID
    access_days_30d: int = Field(ge=0, le=30, default=0)
    accesses_30d: int = Field(ge=0, default=0)
    reads_30d: int = Field(ge=0, default=0)
    writes_30d: int = Field(ge=0, default=0)
    distinct_agents_30d: int = Field(ge=0, default=0)
    last_access_on: date | None = None
    daily: list[AccessDay] = Field(default_factory=list)
