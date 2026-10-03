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
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Serverseitige Deckel (Waechter laufen in jedem Modus, ADR-0044).
MEMORY_FACT_MAX_LENGTH = 300
MEMORY_CONTEXT_MAX_LENGTH = 200
MEMORY_TRIAGE_NOTE_MAX_LENGTH = 500
# Freitext eines Historien-Ereignisses (DB-CHECK in 0091, ADR-0053 3.1.2).
MEMORY_EVENT_REASON_MAX_LENGTH = 500
# Begruendung eines Aenderungs-/Loeschvorschlags (DB-CHECK 0096, ADR-0053 3.1.4).
MEMORY_PROPOSAL_REASON_MAX_LENGTH = 200
MEMORY_MAX_PER_AGENT = 500
# Obergrenze des Nutzergedaechtnisses je (workspace_id, subject_user_id),
# gezaehlt ueber alle Status wie MEMORY_MAX_PER_AGENT (ADR-0053 3.1.1).
# Gesetzte Annahme (ADR-0053 Anhang B): gleich der Agentengrenze, weil ein
# Nutzergedaechtnis ueber alle Profile desselben Besitzers geteilt wird.
# Die Pruefung selbst baut Paket C2a.
MEMORY_MAX_PER_USER = 500
# Eigene Obergrenze fuer Arbeitsnotizen (`kind='agent_note'`) je Agent,
# getrennt von MEMORY_MAX_PER_AGENT, damit Notizen die Nutzerfakten nicht
# verdraengen (ADR-0053 3.1.5; gesetzte Annahme, Anhang B: 40 % von 500).
MEMORY_MAX_NOTES_PER_AGENT = 200
# Verfall unbestaetigter, automatisch aktivierter Eintraege:
# `expires_at = created_at + 30 Tage` (ADR-0053 3.1.3, Anhang B).
MEMORY_UNCONFIRMED_TTL_DAYS = 30
# Vorschlaege unterhalb dieser Importance lehnt der Server ab (Kap. 10.2 des
# Memory-Konzepts: konservativ speichern, Ballast gar nicht erst aufnehmen).
MEMORY_MIN_IMPORTANCE = 5
# Anzahl Top-Memories, die `get_persona` zur Laufzeit in `body_rendered`
# einbettet (WP-6: der System-Prompt wird nicht live aktualisiert — die
# Persona-Antwort ist der zuverlaessige Laufzeit-Injektionspunkt).
MEMORY_PERSONA_TOP_N = 5


class MemoryGuardMode(StrEnum):
    """Modus des workspace-weiten Injection-Waechters (ADR-0044-Addendum).

    - ``standard``: Built-in-Filter (Default).
    - ``custom``: Built-in-Filter + workspace-eigene Allow-/Block-Phrasen.
    - ``off``: kein Injection-Filter — bewusste Owner-Entscheidung (gilt auch
      fuer auto-Agenten); Importance/Dedup/Cap/Rate-Limit bleiben immer aktiv.
    """

    standard = "standard"
    custom = "custom"
    off = "off"


MEMORY_GUARD_PHRASE_MIN = 2
MEMORY_GUARD_PHRASE_MAX = 100
MEMORY_GUARD_PHRASES_MAX = 50


class MemoryGuardConfig(BaseModel):
    """Workspace-Konfiguration des Injection-Waechters (JSONB `workspace.memory_guard`).

    `{}` deserialisiert zu den Defaults (Konvention wie `agent.tool_policy`).
    Bewusst LITERALE Phrasen statt Regex (kein ReDoS, keine Validierungs-
    Sandbox). `allow_phrases` uebersteuern einen Built-in-Treffer nur, wenn
    der Treffer vollstaendig INNERHALB eines Phrasen-Vorkommens liegt —
    verhindert den trivialen Bypass „Allow-Phrase irgendwo anhaengen".
    """

    model_config = ConfigDict(extra="forbid")

    mode: MemoryGuardMode = MemoryGuardMode.standard
    allow_phrases: list[str] = Field(default_factory=list, max_length=MEMORY_GUARD_PHRASES_MAX)
    block_phrases: list[str] = Field(default_factory=list, max_length=MEMORY_GUARD_PHRASES_MAX)

    @field_validator("allow_phrases", "block_phrases")
    @classmethod
    def _clean_phrases(cls, phrases: list[str]) -> list[str]:
        """Trimmen, Laengen pruefen, case-insensitiv deduplizieren."""
        cleaned: list[str] = []
        seen: set[str] = set()
        for phrase in phrases:
            stripped = phrase.strip()
            if not (MEMORY_GUARD_PHRASE_MIN <= len(stripped) <= MEMORY_GUARD_PHRASE_MAX):
                raise ValueError(
                    f"Phrasen muessen {MEMORY_GUARD_PHRASE_MIN}-{MEMORY_GUARD_PHRASE_MAX} "
                    "Zeichen lang sein."
                )
            key = stripped.casefold()
            if key not in seen:
                seen.add(key)
                cleaned.append(stripped)
        return cleaned


class MemoryStatus(StrEnum):
    """Lebenszyklus eines Memorys (Kurations-Schleuse, ADR-0044/ADR-0053 3.1).

    `pending` (Vorschlag, retrieval-unsichtbar) → `active` (freigegeben,
    einziger abrufbarer Zustand) bzw. `rejected` (abgelehnt; bleibt als
    Dedup-Basis erhalten, bis der Mensch es endgueltig loescht).
    `expired`: unbestaetigt verfallen (3.1.3), bleibt Dedup-Basis.
    `converted`: ein Lernvorschlag wurde zu einem Fall (nur mit
    `converted_case_id`, DB-CHECK).
    """

    pending = "pending"
    active = "active"
    rejected = "rejected"
    expired = "expired"
    converted = "converted"


class MemoryKind(StrEnum):
    """Art eines Gedaechtniseintrags (ADR-0053 3.1, DB-CHECK).

    `lesson` kann in der Datenbank nie `active` werden (DB-CHECK) und
    fliesst damit nie in einen Abruf.
    """

    user_fact = "user_fact"
    agent_note = "agent_note"
    lesson = "lesson"


class MemoryScope(StrEnum):
    """Geltungsbereich: Gedaechtnis eines Agenten oder Nutzergedaechtnis.

    `user` gilt je `(workspace_id, subject_user_id)` (ADR-0053 3.1.1) und
    traegt `agent_id IS NULL` (DB-CHECK).
    """

    agent = "agent"
    user = "user"


class MemoryOrigin(StrEnum):
    """Vom Agenten deklarierte Herkunft (Weiche M8); Bestand `legacy_unknown`."""

    user_stated = "user_stated"
    inferred = "inferred"
    external_content = "external_content"
    legacy_unknown = "legacy_unknown"


class MemorySource(StrEnum):
    """Vom Server aus dem Aufrufweg gesetzter Kanal (Weiche M8)."""

    agent = "agent"
    human = "human"
    import_ = "import"


class MemoryEventKind(StrEnum):
    """Ereignisse der Historie `agent_memory_event` (ADR-0053 3.1.2)."""

    created = "created"
    auto_activated = "auto_activated"
    approved = "approved"
    rejected = "rejected"
    edited = "edited"
    confirmed = "confirmed"
    expired = "expired"
    reactivated = "reactivated"
    change_proposed = "change_proposed"
    delete_proposed = "delete_proposed"
    proposal_accepted = "proposal_accepted"
    proposal_rejected = "proposal_rejected"
    rolled_back = "rolled_back"
    converted = "converted"
    merged = "merged"
    # Not-Aus (ADR-0053 6.4.1): automatisch Aktiviertes zurueck nach `pending`.
    auto_revoked = "auto_revoked"


class MemoryActorKind(StrEnum):
    """Wer ein Historien-Ereignis ausgeloest hat (`system`: Verfallsjob, Matrix)."""

    human = "human"
    agent = "agent"
    system = "system"


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

    `origin` ist fachlich Pflicht (Weiche M8): der Agent deklariert die
    Herkunft. Das Feld ist im Schema optional, damit der Server das Fehlen
    mit dem stabilen Grund `memory_origin_required` beantworten kann statt
    mit einem generischen Validierungsfehler. `legacy_unknown` ist kein
    deklarierbarer Wert (nur Bestand). Den Kanal (`source`) setzt der Server
    aus dem Aufrufweg; ein Feld dafuer gibt es bewusst nicht.
    """

    model_config = ConfigDict(extra="forbid")

    fact: str = Field(min_length=1, max_length=MEMORY_FACT_MAX_LENGTH)
    category: MemoryCategory = MemoryCategory.general
    importance: int = Field(default=MEMORY_MIN_IMPORTANCE, ge=1, le=10)
    context: str | None = Field(default=None, max_length=MEMORY_CONTEXT_MAX_LENGTH)
    origin: MemoryOrigin | None = None
    kind: MemoryKind = MemoryKind.user_fact
    scope: MemoryScope = MemoryScope.agent


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
    # NULL nur bei `scope='user'` (DB-CHECK); Agentengedaechtnis traegt ihn immer.
    agent_id: UUID | None
    status: MemoryStatus
    fact: str
    context: str | None = None
    category: MemoryCategory
    importance: int
    source: MemorySource
    triage_note: str | None = None
    retrieval_count: int
    last_retrieved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    # Gedaechtnis 2.0 (ADR-0053 3.1). Defaults bilden den Bestand ab (5.1).
    kind: MemoryKind = MemoryKind.user_fact
    scope: MemoryScope = MemoryScope.agent
    subject_user_id: UUID | None = None
    origin: MemoryOrigin = MemoryOrigin.legacy_unknown
    created_by_agent_id: UUID | None = None
    # Menschliche Bestaetigung; automatisch aktiv heisst aktiv, aber unbestaetigt.
    confirmed_at: datetime | None = None
    confirmed_by: UUID | None = None
    expires_at: datetime | None = None
    occurrence_count: int = 1
    converted_case_id: UUID | None = None


class MemorySaveResult(MemoryRead):
    """Antwort von `save_memory` (ADR-0053 6.4).

    `auto_activated`: die Freigabematrix hat den Eintrag automatisch aktiv
    gesetzt — aktiv, aber unbestaetigt, mit Verfallszeitpunkt.
    `merged_into`: ein `lesson`-Vorschlag traf einen bestehenden
    Lernvorschlag desselben Agenten (3.1.6); die Antwort ist dann dieser
    Treffer mit erhoehtem `occurrence_count` und unveraendertem Status.
    """

    auto_activated: bool = False
    merged_into: UUID | None = None


class MemoryAutoRow(StrEnum):
    """Zeile der Freigabematrix Art x Herkunft (ADR-0053 4.2).

    `user_fact` meint Kategorien ohne Verhaltenswirkung (alles ausser
    `instruction`); `proposal` steht fuer Aenderungs-/Loeschvorschlaege.
    """

    user_fact = "user_fact"
    user_fact_instruction = "user_fact_instruction"
    agent_note = "agent_note"
    lesson = "lesson"
    proposal = "proposal"


class MemoryAutoCell(BaseModel):
    """Eine Zelle der Freigabematrix: Zeile x deklarierte Herkunft."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    row: MemoryAutoRow
    origin: MemoryOrigin


# Die EINZIGE schaltbare Zelle (Owner 2026-09-28): `user_fact` (Kategorie
# ohne Verhaltenswirkung) x `user_stated`. Alles andere ist „nie"; der
# Server ignoriert eine entsprechende Einstellung beim Schreiben UND beim
# Auswerten (ADR-0053 4.2).
MEMORY_AUTO_SWITCHABLE_CELLS: frozenset[MemoryAutoCell] = frozenset(
    {MemoryAutoCell(row=MemoryAutoRow.user_fact, origin=MemoryOrigin.user_stated)}
)


class MemoryAutoPolicy(BaseModel):
    """Workspace-Einstellung der Freigabematrix (JSONB `workspace.memory_auto_policy`).

    `{}` (Spalten-Default) = keine Zelle eingeschaltet (Weiche M3): ein Agent
    mit `memory_mode=auto` wirkt dann wie `suggest`. Eingeschaltete
    Nie-Zellen werden nicht abgelehnt, sondern ignoriert (4.2).
    """

    model_config = ConfigDict(extra="forbid")

    enabled_cells: list[MemoryAutoCell] = Field(default_factory=list, max_length=50)

    def effective(self) -> frozenset[MemoryAutoCell]:
        """Eingeschaltete Zellen, die tatsaechlich schaltbar sind."""
        return frozenset(self.enabled_cells) & MEMORY_AUTO_SWITCHABLE_CELLS


class MemoryAutoPolicyRead(BaseModel):
    """Antwort von `GET/PUT /memory-auto-policy`.

    `enabled_cells` ist die wirksame Einstellung (Nie-Zellen sind bereits
    herausgefiltert); `switchable_cells` nennt, was ueberhaupt schaltbar ist
    — eine Quelle fuer die Oberflaeche (C6) statt einer zweiten Kopie.
    """

    enabled_cells: list[MemoryAutoCell]
    switchable_cells: list[MemoryAutoCell]


class MemoryEventCreate(BaseModel):
    """Ein neues Historien-Ereignis (append-only, ADR-0053 3.1.2).

    `before`/`after` sind Schnappschuesse von `fact, category, importance,
    status, kind, origin` — nie `context` oder `triage_note`.
    """

    model_config = ConfigDict(extra="forbid")

    memory_id: UUID
    event: MemoryEventKind
    actor_kind: MemoryActorKind
    actor_id: UUID | None = None
    agent_id: UUID | None = None
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    reason: str | None = Field(default=None, max_length=MEMORY_EVENT_REASON_MAX_LENGTH)


class MemoryEventRead(BaseModel):
    """Ein persistiertes Historien-Ereignis (read-only)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    memory_id: UUID
    event: MemoryEventKind
    actor_kind: MemoryActorKind
    actor_id: UUID | None = None
    agent_id: UUID | None = None
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    reason: str | None = None
    created_at: datetime


class MemoryProposalAction(StrEnum):
    """Art eines Agenten-Vorschlags zu einem bestehenden Eintrag (ADR-0053 3.1.4)."""

    change = "change"
    delete = "delete"


class MemoryProposalStatus(StrEnum):
    """Status eines Vorschlags. Es gibt keinen Weg zu `accepted` ohne Menschen."""

    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"


class MemoryProposalCreate(BaseModel):
    """Aenderungs- oder Loeschvorschlag eines Agenten (MCP `propose_memory_change`).

    `new_fact` genau bei `action=change` (DB-CHECK 0096). Der Text durchlaeuft
    serverseitig dieselben Waechter wie `save_memory` (Secret-Scan,
    Injection-Waechter); `reason` ebenfalls, weil er einem Menschen gezeigt
    wird.
    """

    model_config = ConfigDict(extra="forbid")

    memory_id: UUID
    action: MemoryProposalAction
    reason: str = Field(min_length=1, max_length=MEMORY_PROPOSAL_REASON_MAX_LENGTH)
    new_fact: str | None = Field(default=None, min_length=1, max_length=MEMORY_FACT_MAX_LENGTH)

    @model_validator(mode="after")
    def _new_fact_matches_action(self) -> MemoryProposalCreate:
        if (self.action == MemoryProposalAction.change) != (self.new_fact is not None):
            raise ValueError("`new_fact` ist bei action=change Pflicht und sonst nicht erlaubt.")
        return self


class MemoryProposalRead(BaseModel):
    """Ein persistierter Vorschlag (read-only)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    memory_id: UUID
    agent_id: UUID
    action: MemoryProposalAction
    new_fact: str | None = None
    reason: str
    status: MemoryProposalStatus
    decided_by: UUID | None = None
    decided_at: datetime | None = None
    created_at: datetime


class MemoryProposalDecision(BaseModel):
    """Entscheidung eines Menschen ueber einen Vorschlag (`POST .../decide`)."""

    model_config = ConfigDict(extra="forbid")

    accept: bool
    note: str | None = Field(default=None, max_length=MEMORY_EVENT_REASON_MAX_LENGTH)


class MemoryRollback(BaseModel):
    """Body von `POST .../rollback`: das Ereignis, dessen `before` gilt (3.1.2)."""

    model_config = ConfigDict(extra="forbid")

    event_id: UUID


# Vorschau des Not-Aus: hoechstens so viele sichtbare Eintraege (ADR-0053 6.4.1).
MEMORY_REVOKE_SAMPLE_SIZE = 5


class MemoryRevokeAuto(BaseModel):
    """Body von `POST /memories/revoke-auto` — Not-Aus (ADR-0053 6.4.1).

    Betroffen sind aktive, unbestaetigte Eintraege mit einem Ereignis
    `auto_activated` im halboffenen Zeitraum `since <= t < until`. `agent_id`
    filtert auf den einreichenden Agenten, `origin` auf die Herkunft (Liste).
    Ohne `dry_run` ist `expected_count` Pflicht: die Zahl, die ein Mensch in
    der Vorschau gesehen und bestaetigt hat.
    """

    model_config = ConfigDict(extra="forbid")

    since: datetime
    until: datetime | None = None
    agent_id: UUID | None = None
    origin: list[MemoryOrigin] | None = Field(default=None, min_length=1)
    include_other_users: bool = False
    dry_run: bool = False
    expected_count: int | None = Field(default=None, ge=0)

    @field_validator("since", "until")
    @classmethod
    def _aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("Zeitpunkt braucht eine Zeitzone.")
        return value

    @model_validator(mode="after")
    def _consistent(self) -> MemoryRevokeAuto:
        if self.until is not None and self.until <= self.since:
            raise ValueError("`until` muss nach `since` liegen.")
        if not self.dry_run and self.expected_count is None:
            raise ValueError("`expected_count` ist ohne dry_run Pflicht.")
        return self


class MemoryRevokeAutoPreview(BaseModel):
    """Antwort mit `dry_run=true`: nichts geaendert.

    `count` ist die Zahl aller Treffer, `hidden_count` ihr Anteil aus dem
    Nutzergedaechtnis anderer Personen (nur bei `include_other_users`, also
    nur beim Admin groesser als null). `sample` nennt hoechstens
    `MEMORY_REVOKE_SAMPLE_SIZE` Eintraege, die der Aufrufer sehen darf —
    fremdes Nutzergedaechtnis erscheint nie, auch nicht mit seiner ID.
    """

    count: int
    hidden_count: int
    sample: list[MemoryRead]


class MemoryBatchItemResult(BaseModel):
    """Ergebnis je Eintrag einer Sammelaktion (`batch`, `revoke-auto`, ADR-0053 6.4.1)."""

    id: UUID
    ok: bool
    reason: str | None = None
    params: dict[str, Any] | None = None


class MemoryRevokeAutoResult(BaseModel):
    """Antwort ohne `dry_run`: alle Treffer zurueckgenommen (alle oder keiner).

    `results` nennt nur sichtbare Eintraege; zurueckgenommene Eintraege aus
    fremdem Nutzergedaechtnis zaehlt allein `hidden_count`.
    """

    count: int
    hidden_count: int
    results: list[MemoryBatchItemResult]


# ------------------------------------- Workspace-weite Liste und Zaehler (6.4.1)

# `GET /memories`: hoechstens so viele Eintraege je Seite (ADR-0053 6.4.1).
MEMORY_LIST_LIMIT_MAX = 50
MEMORY_LIST_LIMIT_DEFAULT = 20
# Freitextsuche `q` (Teilstring ueber `fact`).
MEMORY_LIST_QUERY_MAX_LENGTH = 200
# Grenzen der Gesundheits-Filter (ADR-0053 6.4.1, Design-Entscheidung W3 = a;
# gesetzte Annahmen).
MEMORY_HEALTH_EXPIRING_DAYS = 7
MEMORY_HEALTH_NEVER_DELIVERED_DAYS = 30
MEMORY_HEALTH_STALE_DELIVERY_DAYS = 90


class MemoryHealth(StrEnum):
    """Vom Server berechneter Gesundheitszustand (ADR-0053 6.4.1, Filter `health`).

    - ``unconfirmed``: `active`, `confirmed_at IS NULL`.
    - ``expiring_soon``: `pending` oder `active`, `expires_at` in den naechsten
      `MEMORY_HEALTH_EXPIRING_DAYS` Tagen.
    - ``never_delivered``: `active`, `retrieval_count = 0`, aelter als
      `MEMORY_HEALTH_NEVER_DELIVERED_DAYS` Tage.
    - ``stale_delivery``: `active`, `last_retrieved_at` aelter als
      `MEMORY_HEALTH_STALE_DELIVERY_DAYS` Tage.
    - ``external_or_inferred``: Herkunft `external_content` oder `inferred`.

    Die Zustaende schliessen sich nicht aus.
    """

    unconfirmed = "unconfirmed"
    expiring_soon = "expiring_soon"
    never_delivered = "never_delivered"
    stale_delivery = "stale_delivery"
    external_or_inferred = "external_or_inferred"


class MemoryListSort(StrEnum):
    """Sortierung von `GET /memories`; Keyset auf `(created_at, id)`."""

    newest = "newest"
    oldest = "oldest"


class MemoryCountGroup(StrEnum):
    """Gruppe eines Zaehlers in `GET /memories/counts` (ADR-0053 6.4.1).

    `subject_user_id` ist `admin` vorbehalten und zaehlt das
    Nutzergedaechtnis je Person — nur als Zahl (Owner-Entscheidung 3a).
    """

    agent = "agent"
    kind = "kind"
    status = "status"
    origin = "origin"
    source = "source"
    health = "health"
    subject_user_id = "subject_user_id"


class MemoryFilter(BaseModel):
    """Filter der workspace-weiten Liste, ihrer Zaehler und der Stapel-Auswahl.

    Alle Felder sind optional und wirken mit UND. `agent_id` trifft beim
    Agentengedaechtnis den Besitzer, beim Nutzergedaechtnis den einreichenden
    Agenten. `held` (zurueckgehalten) ist abgeleitet: `pending` und Herkunft
    `external_content`/`inferred` oder Kategorie `instruction`.
    `status=pending` ist die Warteschlange und schliesst Lernvorschlaege aus,
    ausser bei `kind=lesson` (6.4.1 „Zaehler“).
    """

    model_config = ConfigDict(extra="forbid")

    status: MemoryStatus | None = None
    kind: MemoryKind | None = None
    scope: MemoryScope | None = None
    agent_id: UUID | None = None
    origin: MemoryOrigin | None = None
    source: MemorySource | None = None
    health: MemoryHealth | None = None
    held: bool | None = None
    q: str | None = Field(default=None, min_length=1, max_length=MEMORY_LIST_QUERY_MAX_LENGTH)
    created_after: datetime | None = None

    @field_validator("created_after")
    @classmethod
    def _aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("Zeitpunkt braucht eine Zeitzone.")
        return value


class MemoryPage(BaseModel):
    """Eine Seite von `GET /memories`; `next_cursor` ist `None` am Ende."""

    items: list[MemoryRead]
    next_cursor: str | None = None


class MemoryCounts(BaseModel):
    """Antwort von `GET /memories/counts` (ADR-0053 6.4.1).

    `total` zaehlt die Eintraege, die die Liste mit denselben Filtern zeigt.
    `groups` nennt je angefragter Gruppe die Anzahl je Wert — jeweils ohne
    den eigenen Filter dieser Gruppe (Facetten). `health` meldet alle Werte,
    auch mit 0; die uebrigen Gruppen nur vorhandene Werte.
    """

    total: int
    groups: dict[MemoryCountGroup, dict[str, int]] = Field(default_factory=dict)


# ------------------------------------------------- Stapel und Purge (6.4.1)

# `POST /memories/batch`: hoechstens so viele IDs je Aufruf (ADR-0053 6.4.1).
MEMORY_BATCH_MAX_IDS = 100
# Inhaltsfreie Spur des Admin-Loeschens (6.4.1 W5 = a): `target=<user_id>`,
# `detail={count}`.
MEMORY_USER_PURGED_AUDIT_ACTION = "memory.user_purged"


class MemoryBatchAction(StrEnum):
    """Aktion eines Stapels — je Eintrag dieselbe wie die Einzelaktion.

    `approve`/`reject` entsprechen der Triage, `confirm` dem Bestaetigen
    (3.1.3), `delete` dem Loeschen. Aenderungs- und Loeschvorschlaege laufen
    nicht ueber den Stapel, sondern einzeln ueber `decide` (3.1.4).
    """

    approve = "approve"
    reject = "reject"
    confirm = "confirm"
    delete = "delete"


class MemoryBatchRequest(BaseModel):
    """Body von `POST /memories/batch` (ADR-0053 6.4.1).

    Genau eines von `ids` (1 bis `MEMORY_BATCH_MAX_IDS`, Dubletten werden
    reihenfolgetreu entfernt) oder `filter` (wie `GET /memories`). Im
    Filter-Modus ist `expected_count` Pflicht: die Zahl, die ein Mensch
    gesehen und bestaetigt hat. `note` wirkt nur bei `approve`/`reject` als
    Triage-Notiz.
    """

    model_config = ConfigDict(extra="forbid")

    action: MemoryBatchAction
    ids: list[UUID] | None = Field(default=None, min_length=1, max_length=MEMORY_BATCH_MAX_IDS)
    filter: MemoryFilter | None = None
    expected_count: int | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=MEMORY_TRIAGE_NOTE_MAX_LENGTH)

    @field_validator("ids")
    @classmethod
    def _unique(cls, value: list[UUID] | None) -> list[UUID] | None:
        return list(dict.fromkeys(value)) if value is not None else None

    @model_validator(mode="after")
    def _one_mode(self) -> MemoryBatchRequest:
        if (self.ids is None) == (self.filter is None):
            raise ValueError("Genau eines von `ids` oder `filter` angeben.")
        if self.filter is not None and self.expected_count is None:
            raise ValueError("`expected_count` ist im Filter-Modus Pflicht.")
        return self


class MemoryBatchResult(BaseModel):
    """Antwort eines Stapels: ein Ergebnis je Eintrag, Teilerfolg moeglich."""

    results: list[MemoryBatchItemResult]


class MemoryPurgeResult(BaseModel):
    """Antwort von `DELETE /members/{user_id}/memories` — nur die Anzahl (3a)."""

    deleted: int


class MemoryHit(BaseModel):
    """Ein Retrieval-Treffer fuer Agenten (bewusst schmal).

    Nur id (Kurzform fuer Referenzen), Fakt und Kategorie — kein `context`,
    keine Triage-Metadaten (Injection-/Leak-Minimierung).
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    fact: str
    category: MemoryCategory
