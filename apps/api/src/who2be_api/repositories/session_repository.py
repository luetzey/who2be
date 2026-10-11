"""Datenzugriff fuer Gespraechsprotokolle und Massnahmen (ADR-0053 3.5/3.6, Migration 0103).

Jede Query filtert auf `workspace_id` — per Signatur erzwungen
(Defense-in-Depth zusaetzlich zur RLS, Muster `case_repository`).

Schreibwege:

- `insert_session`: Protokoll samt Faellen und Massnahmen (mit deren Faellen)
  in der Transaktion des UEBERGEBENEN `conn`. Der Service (E2b-1) oeffnet die
  Transaktion, weil in derselben Transaktion die Faelle auf `in_progress`
  gehen (W-E2 = a, `start_cases`).
- `append_measure_event`: ein Event an einer Massnahme; optional in einer
  uebergebenen Transaktion (E3: `activated` zusammen mit dem Versionswechsel).
- `start_cases`: die Faelle der Massnahmen gehen auf `in_progress` (W-E2 = a,
  E2b-1), in derselben uebergebenen Transaktion und unter der Fall-Sperre
  aus `case_repository` — dieselbe Event-Form wie jeder andere Fall-Uebergang.

Lesewege: Protokoll je ID (mit eingebetteten Massnahmen, QE1 = a), Liste je
Workspace/Agent/Fall mit Keyset-Cursor, Massnahme je ID, Massnahmen je Fall
und je verknuepfter Version (E3), Zahl der faelligen Massnahmen
(`count_due_measures`, Aufgaben-Zaehler Navigation W1). Fuer die Pruefungen
vor dem Einreichen (`submit_refs`) liest es in der Transaktion des Aufrufers,
welche der genannten Faelle, Pruefaelle und welches Vorgaenger-Protokoll dem
besprochenen Agenten gehoeren.

Was das Repository bewusst NICHT tut:

- **Rechte pruefen** und **Event-Folgen pruefen** (z. B. `reviewed` erst nach
  `activated`, QE4) — das ist Sache des Service (E2b). Die DB haelt nur die
  Form-Invarianten der Events (Migration 0103).
- **Pruefen, ob die Faelle einer Massnahme zum Protokoll gehoeren** und ob
  eine Massnahme mindestens einen Fall hat (3.6 „>= 1“): Service E2b-1; das
  Modell `MeasureCreate` verlangt bereits einen Eintrag.
- **Aendern oder loeschen.** `who2be_app` hat auf allen fuenf Tabellen nur
  SELECT und INSERT (3.5: unveraenderlich ueber die Grants).
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Protocol
from uuid import UUID

import asyncpg

# Status-Ableitung, Fall-Sperre und Event-Form aus EINER Quelle: ein
# automatischer Uebergang (W-E2 = a) sieht genauso aus wie ein manueller.
from who2be_api.repositories.case_repository import (
    _STATUS_SQL,
    _VERSION_TABLES,
    _insert_event,
    _lock_case,
)
from who2be_models import (
    MEASURE_TARGETS_WITHOUT_ENTITY,
    CaseActorKind,
    CaseEventKind,
    CaseStatus,
    EntityType,
    MeasureActorKind,
    MeasureEventCreate,
    MeasureEventKind,
    MeasureEventRead,
    MeasureRead,
    SessionCreate,
    SessionDetail,
    SessionRead,
    SessionSubmitterKind,
    measure_state_for,
)

_SESSION_COLUMNS = (
    "s.id, s.workspace_id, s.agent_id, s.trigger, s.participants, s.summary, s.decisions, "
    "s.dissent, s.follow_up_at, s.supersedes_id, s.submitted_by_kind, s.submitted_by, "
    "s.created_at"
)

# Fall-IDs eines Protokolls in Einfuege-Reihenfolge.
_SESSION_CASES_SQL = (
    "ARRAY(SELECT fc.case_id FROM feedback_session_case fc "
    "      WHERE fc.workspace_id = s.workspace_id AND fc.session_id = s.id "
    "      ORDER BY fc.created_at, fc.case_id) AS case_ids"
)

_MEASURE_COLUMNS = (
    "m.id, m.workspace_id, m.agent_id, m.session_id, m.target, m.entity_id, "
    "m.change_summary, m.test_case_id, m.success_criterion, m.counterposition, "
    "m.follow_up_at, m.created_at"
)

_EVENT_COLUMNS = (
    "id, measure_id, event, actor_kind, actor_id, version_entity_type, version_id, "
    "verdict, metrics, note, created_at"
)


@dataclass(frozen=True)
class SubmitRefs:
    """Was von den Verweisen eines Protokolls dem besprochenen Agenten gehoert."""

    agent_exists: bool
    case_ids: frozenset[UUID]
    test_case_ids: frozenset[UUID]
    supersedes_ok: bool


@dataclass(frozen=True)
class CaseStart:
    """Ergebnis von `start_cases` je Fall: Status vorher, und ob er jetzt `in_progress` ist."""

    case_id: UUID
    status_before: CaseStatus
    started: bool


@dataclass(frozen=True)
class RunFigure:
    """Juengster Prueflauf des Pruefalls einer Massnahme fuer eine Version (3.2)."""

    runs_total: int
    runs_passed: int
    verdict: str
    attestation: str
    created_at: datetime


@dataclass(frozen=True)
class VersionFigures:
    """Rohzahlen einer Version fuer die Nachschau (6.6, QE8 a).

    `cases` ist None, solange es fuer diese Seite kein Zeitfenster gibt
    (nachher: vor `activated`).
    """

    version_id: UUID | None
    version: int
    run: RunFigure | None
    uses: int
    cases: int | None


@dataclass(frozen=True)
class FollowUpFigures:
    """Kennzahlen einer Massnahme: vorher, nachher, Wiederauftreten."""

    before: VersionFigures | None
    after: VersionFigures | None
    recurrence: int | None


def _json_list(value: object) -> list[Any]:
    """jsonb-Liste, egal ob die Verbindung den jsonb-Codec hat oder nicht."""
    raw = json.loads(value) if isinstance(value, str) else value
    if not isinstance(raw, list):
        raise TypeError(f"jsonb-Liste erwartet, nicht {type(raw).__name__}")
    return raw


def _json_object(value: object) -> dict[str, Any] | None:
    if value is None:
        return None
    raw = json.loads(value) if isinstance(value, str) else value
    if not isinstance(raw, dict):
        raise TypeError(f"jsonb-Objekt erwartet, nicht {type(raw).__name__}")
    return raw


def _session(row: asyncpg.Record) -> SessionRead:
    data = dict(row)
    for key in ("participants", "decisions", "dissent"):
        data[key] = _json_list(data[key])
    data["case_ids"] = list(data["case_ids"])
    return SessionRead.model_validate(data)


def _event(row: asyncpg.Record) -> MeasureEventRead:
    data = dict(row)
    data["metrics"] = _json_object(data["metrics"])
    return MeasureEventRead.model_validate(data)


class SessionRepository(Protocol):
    """Vertrag des Protokoll-/Massnahmen-Datenzugriffs (Service-Sicht, E2b)."""

    async def insert_session(
        self,
        conn: asyncpg.Connection,
        workspace_id: UUID,
        data: SessionCreate,
        *,
        submitted_by_kind: SessionSubmitterKind,
        submitted_by: UUID,
    ) -> SessionDetail: ...

    async def get_session(self, workspace_id: UUID, session_id: UUID) -> SessionDetail | None: ...

    async def list_sessions(
        self,
        workspace_id: UUID,
        *,
        agent_id: UUID | None = None,
        case_id: UUID | None = None,
        limit: int = 50,
        cursor: tuple[datetime, UUID] | None = None,
    ) -> list[SessionRead]: ...

    async def count_due_measures(
        self, workspace_id: UUID, *, today: date, agent_id: UUID | None = None
    ) -> int: ...

    async def get_measure(self, workspace_id: UUID, measure_id: UUID) -> MeasureRead | None: ...

    async def append_measure_event(
        self,
        workspace_id: UUID,
        measure_id: UUID,
        data: MeasureEventCreate,
        *,
        actor_kind: MeasureActorKind,
        actor_id: UUID | None,
        conn: asyncpg.Connection | None = None,
    ) -> MeasureEventRead | None: ...

    async def measures_for_case(self, workspace_id: UUID, case_id: UUID) -> list[MeasureRead]: ...

    async def measures_for_version(
        self,
        workspace_id: UUID,
        entity_type: EntityType,
        version_id: UUID,
        *,
        conn: asyncpg.Connection | None = None,
    ) -> list[MeasureRead]: ...

    def begin(self) -> AbstractAsyncContextManager[asyncpg.Connection]: ...

    async def submit_refs(
        self,
        conn: asyncpg.Connection,
        workspace_id: UUID,
        agent_id: UUID,
        *,
        case_ids: Sequence[UUID],
        test_case_ids: Sequence[UUID],
        supersedes_id: UUID | None,
    ) -> SubmitRefs: ...

    async def start_cases(
        self,
        conn: asyncpg.Connection,
        workspace_id: UUID,
        starts: Sequence[tuple[UUID, UUID]],
        *,
        actor_kind: CaseActorKind,
        actor_id: UUID,
    ) -> list[CaseStart]: ...

    async def lock_measure(
        self, conn: asyncpg.Connection, workspace_id: UUID, measure_id: UUID
    ) -> tuple[MeasureRead, date] | None: ...

    async def version_ref(
        self, workspace_id: UUID, entity_type: EntityType, version_id: UUID
    ) -> tuple[UUID, int] | None: ...

    async def reset_cases_after_withdraw(
        self,
        conn: asyncpg.Connection,
        workspace_id: UUID,
        measure_id: UUID,
        case_ids: Sequence[UUID],
        *,
        note: str,
    ) -> list[UUID]: ...

    async def follow_up_figures(
        self, workspace_id: UUID, measure: MeasureRead
    ) -> FollowUpFigures: ...


class PgSessionRepository:
    """asyncpg-Implementierung von `SessionRepository`."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    @asynccontextmanager
    async def begin(self) -> AsyncIterator[asyncpg.Connection]:
        """Eine Verbindung in einer offenen Transaktion (Einreichen, E2b-1).

        Der Service haelt damit Pruefungen, Protokoll und Fall-Uebergaenge in
        EINER Transaktion, ohne den Pool zu kennen.
        """
        async with self._pool.acquire() as conn, conn.transaction():
            yield conn

    async def submit_refs(
        self,
        conn: asyncpg.Connection,
        workspace_id: UUID,
        agent_id: UUID,
        *,
        case_ids: Sequence[UUID],
        test_case_ids: Sequence[UUID],
        supersedes_id: UUID | None,
    ) -> SubmitRefs:
        """Welche Verweise gehoeren dem besprochenen Agenten in diesem Workspace?

        In der Transaktion des Aufrufers; unbekannte, fremde und Verweise
        eines anderen Agenten fehlen im Ergebnis. Der Service macht daraus
        die Fehler, die Composite-FKs der Migration 0103 halten es zusaetzlich.
        """
        agent = await conn.fetchval(
            "SELECT 1 FROM agent WHERE workspace_id = $1 AND id = $2", workspace_id, agent_id
        )
        cases = await conn.fetch(
            "SELECT id FROM agent_case "
            "WHERE workspace_id = $1 AND agent_id = $2 AND id = ANY($3::uuid[])",
            workspace_id,
            agent_id,
            list(case_ids),
        )
        tests = await conn.fetch(
            "SELECT id FROM test_case "
            "WHERE workspace_id = $1 AND agent_id = $2 AND id = ANY($3::uuid[])",
            workspace_id,
            agent_id,
            list(test_case_ids),
        )
        supersedes_ok = True
        if supersedes_id is not None:
            found = await conn.fetchval(
                "SELECT 1 FROM feedback_session WHERE workspace_id = $1 AND agent_id = $2 "
                "AND id = $3",
                workspace_id,
                agent_id,
                supersedes_id,
            )
            supersedes_ok = found is not None
        return SubmitRefs(
            agent_exists=agent is not None,
            case_ids=frozenset(r["id"] for r in cases),
            test_case_ids=frozenset(r["id"] for r in tests),
            supersedes_ok=supersedes_ok,
        )

    async def start_cases(
        self,
        conn: asyncpg.Connection,
        workspace_id: UUID,
        starts: Sequence[tuple[UUID, UUID]],
        *,
        actor_kind: CaseActorKind,
        actor_id: UUID,
    ) -> list[CaseStart]:
        """Faelle mit Massnahme auf `in_progress` (W-E2 = a), Paare `(case_id, measure_id)`.

        Kanten nach ADR-0053 3.3: `triaged -> in_progress` direkt. `open` und
        `reopened` fuehren nur ueber `triaged`, und `-> triaged` verlangt eine
        Zuordnung (>= 1 Element oder `model_limit`); mit Zuordnung entstehen
        beide Events (`triaged`, dann `in_progress`), ohne bleibt der Fall.
        Jeder andere Status bleibt unveraendert. Das `in_progress`-Event traegt
        die `measure_id`.

        Unter der Fall-Sperre aus `case_repository` (wie `append_transition`),
        in fester Reihenfolge nach `case_id`, damit zwei Einreichungen sich
        nicht gegenseitig sperren. Ergebnis in der Reihenfolge von `starts`.
        """
        results: dict[UUID, CaseStart] = {}
        for case_id, measure_id in sorted(starts, key=lambda pair: pair[0].int):
            await _lock_case(conn, case_id)
            raw = await conn.fetchval(
                f"SELECT {_STATUS_SQL} FROM agent_case c WHERE c.workspace_id = $1 AND c.id = $2",
                workspace_id,
                case_id,
            )
            before = CaseStatus(raw)
            path: list[CaseEventKind] = []
            if before is CaseStatus.triaged:
                path = [CaseEventKind.in_progress]
            elif before in (CaseStatus.open, CaseStatus.reopened):
                has_element = await conn.fetchval(
                    "SELECT 1 FROM agent_case_element WHERE workspace_id = $1 AND case_id = $2 "
                    "LIMIT 1",
                    workspace_id,
                    case_id,
                )
                if has_element is not None:
                    path = [CaseEventKind.triaged, CaseEventKind.in_progress]
            for event in path:
                await _insert_event(
                    conn,
                    workspace_id,
                    case_id,
                    event,
                    actor_kind,
                    actor_id,
                    measure_id=measure_id if event is CaseEventKind.in_progress else None,
                )
            results[case_id] = CaseStart(case_id=case_id, status_before=before, started=bool(path))
        return [results[case_id] for case_id, _ in starts]

    @asynccontextmanager
    async def _tx(self, conn: asyncpg.Connection | None) -> AsyncIterator[asyncpg.Connection]:
        """Die uebergebene Verbindung (Transaktion des Aufrufers) oder eine eigene."""
        if conn is not None:
            yield conn
            return
        async with self._pool.acquire() as own, own.transaction():
            yield own

    async def insert_session(
        self,
        conn: asyncpg.Connection,
        workspace_id: UUID,
        data: SessionCreate,
        *,
        submitted_by_kind: SessionSubmitterKind,
        submitted_by: UUID,
    ) -> SessionDetail:
        """Protokoll + Faelle + Massnahmen (+ deren Faelle) in der Transaktion von `conn`.

        Der Aufrufer haelt die Transaktion offen; scheitert ein Schritt (z. B.
        ein Fall eines anderen Agenten -> Composite-FK), rollt er alles
        zurueck. Fehler der Datenbank gehen unveraendert nach oben; der
        Service prueft vorher und antwortet mit `session_cases_invalid` bzw.
        `measure_test_case_required`.
        """
        session_id: UUID = await conn.fetchval(
            "INSERT INTO feedback_session "
            "(workspace_id, agent_id, trigger, participants, summary, decisions, dissent, "
            " follow_up_at, supersedes_id, submitted_by_kind, submitted_by) "
            "VALUES ($1, $2, $3, $4::text::jsonb, $5, $6::text::jsonb, $7::text::jsonb, "
            " $8, $9, $10, $11) RETURNING id",
            workspace_id,
            data.agent_id,
            data.trigger.value,
            json.dumps([p.model_dump(mode="json") for p in data.participants]),
            data.summary,
            json.dumps([d.model_dump(mode="json", exclude_none=True) for d in data.decisions]),
            json.dumps([d.model_dump(mode="json") for d in data.dissent]),
            data.follow_up_at,
            data.supersedes_id,
            submitted_by_kind.value,
            submitted_by,
        )
        # Reihenfolge per clock_timestamp() (Migration 0103) wie eingereicht.
        for case_id in data.case_ids:
            await conn.execute(
                "INSERT INTO feedback_session_case (workspace_id, session_id, agent_id, case_id) "
                "VALUES ($1, $2, $3, $4)",
                workspace_id,
                session_id,
                data.agent_id,
                case_id,
            )
        for measure in data.measures:
            measure_id: UUID = await conn.fetchval(
                "INSERT INTO measure "
                "(workspace_id, agent_id, session_id, target, entity_id, change_summary, "
                " test_case_id, success_criterion, counterposition, follow_up_at) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) RETURNING id",
                workspace_id,
                data.agent_id,
                session_id,
                measure.target.value,
                measure.entity_id,
                measure.change_summary,
                measure.test_case_id,
                measure.success_criterion,
                measure.counterposition,
                measure.follow_up_at,
            )
            for case_id in measure.case_ids:
                await conn.execute(
                    "INSERT INTO measure_case (workspace_id, measure_id, agent_id, case_id) "
                    "VALUES ($1, $2, $3, $4)",
                    workspace_id,
                    measure_id,
                    data.agent_id,
                    case_id,
                )
        detail = await _load_session(conn, workspace_id, session_id)
        assert detail is not None  # in derselben Transaktion angelegt
        return detail

    async def get_session(self, workspace_id: UUID, session_id: UUID) -> SessionDetail | None:
        """Protokoll mit Massnahmen (je mit Faellen, Zustand und Verlauf)."""
        async with self._pool.acquire() as conn, conn.transaction(isolation="repeatable_read"):
            return await _load_session(conn, workspace_id, session_id)

    async def list_sessions(
        self,
        workspace_id: UUID,
        *,
        agent_id: UUID | None = None,
        case_id: UUID | None = None,
        limit: int = 50,
        cursor: tuple[datetime, UUID] | None = None,
    ) -> list[SessionRead]:
        """Eine Seite, neueste zuerst, Keyset auf `(created_at, id)`.

        `agent_id`: Protokolle zu diesem Agenten. `case_id`: Protokolle, die
        diesen Fall besprechen (QE1 = a). Feste Parameter-Positionen, NULL =
        Filter aus — kein dynamisches SQL.
        """
        rows = await self._pool.fetch(
            f"SELECT {_SESSION_COLUMNS}, {_SESSION_CASES_SQL} FROM feedback_session s "
            "WHERE s.workspace_id = $1 "
            "  AND ($2::uuid IS NULL OR s.agent_id = $2) "
            "  AND ($3::uuid IS NULL OR EXISTS (SELECT 1 FROM feedback_session_case fc "
            "        WHERE fc.workspace_id = s.workspace_id AND fc.session_id = s.id "
            "          AND fc.case_id = $3)) "
            "  AND ($4::timestamptz IS NULL OR (s.created_at, s.id) < ($4, $5::uuid)) "
            "ORDER BY s.created_at DESC, s.id DESC LIMIT $6",
            workspace_id,
            agent_id,
            case_id,
            cursor[0] if cursor is not None else None,
            cursor[1] if cursor is not None else None,
            limit,
        )
        return [_session(r) for r in rows]

    async def count_due_measures(
        self, workspace_id: UUID, *, today: date, agent_id: UUID | None = None
    ) -> int:
        """Faellige Massnahmen (Phase-E-Delta §0.4, Navigation §2.2 Art 1).

        Faellig = Nachschau-Datum (`measure.follow_up_at`, sonst das des
        Protokolls) `<= today` UND das juengste Event ist weder `reviewed`
        noch `withdrawn`. Massnahmen eines ersetzten Protokolls zaehlen mit
        (QE11 a: sie gelten weiter, bis ein Mensch sie zurueckzieht).
        """
        count = await self._pool.fetchval(
            "SELECT COUNT(*)::int FROM measure m "
            "JOIN feedback_session s ON s.workspace_id = m.workspace_id AND s.id = m.session_id "
            "LEFT JOIN LATERAL (SELECT e.event FROM measure_event e "
            "    WHERE e.workspace_id = m.workspace_id AND e.measure_id = m.id "
            "    ORDER BY e.created_at DESC, e.id DESC LIMIT 1) last ON TRUE "
            "WHERE m.workspace_id = $1 "
            "  AND ($2::uuid IS NULL OR m.agent_id = $2) "
            "  AND COALESCE(m.follow_up_at, s.follow_up_at) <= $3 "
            "  AND (last.event IS NULL OR last.event NOT IN ('reviewed', 'withdrawn'))",
            workspace_id,
            agent_id,
            today,
        )
        return int(count or 0)

    async def get_measure(self, workspace_id: UUID, measure_id: UUID) -> MeasureRead | None:
        async with self._pool.acquire() as conn, conn.transaction(isolation="repeatable_read"):
            measures = await _load_measures(conn, workspace_id, "m.id = $2", measure_id)
        return measures[0] if measures else None

    async def append_measure_event(
        self,
        workspace_id: UUID,
        measure_id: UUID,
        data: MeasureEventCreate,
        *,
        actor_kind: MeasureActorKind,
        actor_id: UUID | None,
        conn: asyncpg.Connection | None = None,
    ) -> MeasureEventRead | None:
        """Haengt ein Event an. None, wenn die Massnahme nicht existiert.

        Die Folge der Events (QE4) prueft der Service; die Form (Version,
        `metrics`, `verdict`, Begruendung, Akteur) haelt die DB per CHECK.
        """
        async with self._tx(conn) as tx:
            found = await tx.fetchval(
                "SELECT 1 FROM measure WHERE workspace_id = $1 AND id = $2",
                workspace_id,
                measure_id,
            )
            if found is None:
                return None
            row = await tx.fetchrow(
                "INSERT INTO measure_event "
                "(workspace_id, measure_id, event, actor_kind, actor_id, version_entity_type, "
                " version_id, verdict, metrics, note) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::text::jsonb, $10) "
                f"RETURNING {_EVENT_COLUMNS}",
                workspace_id,
                measure_id,
                data.event.value,
                actor_kind.value,
                actor_id,
                data.version_entity_type,
                data.version_id,
                data.verdict.value if data.verdict is not None else None,
                json.dumps(data.metrics) if data.metrics is not None else None,
                data.note,
            )
        assert row is not None
        return _event(row)

    async def measures_for_case(self, workspace_id: UUID, case_id: UUID) -> list[MeasureRead]:
        """Alle Massnahmen, die diesen Fall abdecken (aelteste zuerst)."""
        async with self._pool.acquire() as conn, conn.transaction(isolation="repeatable_read"):
            return await _load_measures(
                conn,
                workspace_id,
                "EXISTS (SELECT 1 FROM measure_case mc WHERE mc.workspace_id = m.workspace_id "
                "        AND mc.measure_id = m.id AND mc.case_id = $2)",
                case_id,
            )

    async def measures_for_version(
        self,
        workspace_id: UUID,
        entity_type: EntityType,
        version_id: UUID,
        *,
        conn: asyncpg.Connection | None = None,
    ) -> list[MeasureRead]:
        """Massnahmen, deren JUENGSTES `draft_linked` auf diese Version zeigt (E3).

        Wird ein anderer Entwurf verknuepft, gilt der juengste (QE4 = a); eine
        zuvor verknuepfte Version loest dann nichts mehr aus. Optional in der
        Transaktion des Aufrufers (Versionswechsel + `activated`).
        """
        async with self._tx(conn) as tx:
            return await _load_measures(
                tx,
                workspace_id,
                "(SELECT (e.version_entity_type, e.version_id) FROM measure_event e "
                " WHERE e.workspace_id = m.workspace_id AND e.measure_id = m.id "
                "   AND e.event = 'draft_linked' "
                " ORDER BY e.created_at DESC, e.id DESC LIMIT 1) "
                "= ($2::text, $3::uuid)",
                entity_type,
                version_id,
            )

    # --- Lebenszyklus der Massnahme (E2b-2) -----------------------------------

    async def lock_measure(
        self, conn: asyncpg.Connection, workspace_id: UUID, measure_id: UUID
    ) -> tuple[MeasureRead, date] | None:
        """Sperrt die Massnahme (Transaktion von `conn`) und liest sie samt Nachschau-Datum.

        Die Sperre haelt die Event-Folge (QE4: `reviewed` genau einmal, nichts
        nach `withdrawn`) gegen zwei gleichzeitige Aufrufe. Nachschau-Datum =
        `measure.follow_up_at`, sonst das des Protokolls (wie
        `count_due_measures`). None, wenn es die Massnahme nicht gibt.
        """
        await conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended('measure:' || $1::uuid::text, 0))",
            measure_id,
        )
        measures = await _load_measures(conn, workspace_id, "m.id = $2", measure_id)
        if not measures:
            return None
        due: date = await conn.fetchval(
            "SELECT COALESCE(m.follow_up_at, s.follow_up_at) FROM measure m "
            "JOIN feedback_session s ON s.workspace_id = m.workspace_id AND s.id = m.session_id "
            "WHERE m.workspace_id = $1 AND m.id = $2",
            workspace_id,
            measure_id,
        )
        return measures[0], due

    async def version_ref(
        self, workspace_id: UUID, entity_type: EntityType, version_id: UUID
    ) -> tuple[UUID, int] | None:
        """`(entity_id, version)` einer Version dieses Workspace, sonst None.

        Ueber die Identitaetstabelle geprueft (Muster
        `PgCaseRepository.version_exists`). Liest nur — die Versions-Tabellen
        bleiben unberuehrt (Weiche E2 = a).
        """
        table, version_table, fk = _VERSION_TABLES[entity_type]
        row = await self._pool.fetchrow(
            f"SELECT e.id, v.version FROM {version_table} v JOIN {table} e ON e.id = v.{fk} "
            "WHERE v.id = $2 AND e.workspace_id = $1",
            workspace_id,
            version_id,
        )
        return (row["id"], row["version"]) if row is not None else None

    async def reset_cases_after_withdraw(
        self,
        conn: asyncpg.Connection,
        workspace_id: UUID,
        measure_id: UUID,
        case_ids: Sequence[UUID],
        *,
        note: str,
    ) -> list[UUID]:
        """QE5 a: Faelle `in_progress` -> `triaged`, wenn keine andere offene Massnahme sie traegt.

        Owner 2026-10-09: „Zurueckziehen einer Massnahme setzt ihre Faelle von
        in_progress automatisch auf triaged zurueck, sofern keine andere offene
        Massnahme sie enthaelt.“ Offen = juengstes Event weder `reviewed` noch
        `withdrawn`. Akteur ist das System; das Event traegt die
        `measure_id` und die Begruendung des Zurueckziehens. Unter der
        Fall-Sperre, in fester Reihenfolge nach `case_id` (wie `start_cases`).
        Ergebnis: die zurueckgesetzten Faelle.
        """
        reset: list[UUID] = []
        for case_id in sorted(case_ids, key=lambda c: c.int):
            await _lock_case(conn, case_id)
            current = await conn.fetchval(
                f"SELECT {_STATUS_SQL} FROM agent_case c WHERE c.workspace_id = $1 AND c.id = $2",
                workspace_id,
                case_id,
            )
            if current != CaseStatus.in_progress.value:
                continue
            other_open = await conn.fetchval(
                "SELECT 1 FROM measure_case mc "
                "LEFT JOIN LATERAL (SELECT e.event FROM measure_event e "
                "    WHERE e.workspace_id = mc.workspace_id AND e.measure_id = mc.measure_id "
                "    ORDER BY e.created_at DESC, e.id DESC LIMIT 1) last ON TRUE "
                "WHERE mc.workspace_id = $1 AND mc.case_id = $2 AND mc.measure_id <> $3 "
                "  AND (last.event IS NULL OR last.event NOT IN ('reviewed', 'withdrawn')) "
                "LIMIT 1",
                workspace_id,
                case_id,
                measure_id,
            )
            if other_open is not None:
                continue
            await _insert_event(
                conn,
                workspace_id,
                case_id,
                CaseEventKind.triaged,
                CaseActorKind.system,
                None,
                note=note,
                measure_id=measure_id,
            )
            reset.append(case_id)
        return reset

    async def follow_up_figures(self, workspace_id: UUID, measure: MeasureRead) -> FollowUpFigures:
        """Rohzahlen der Nachschau (6.6: Pruefall-Quote vorher/nachher, Fallrate je
        Nutzung alte gegen neue Version, Wiederauftreten; QE8 a: keine Raten).

        - **nachher** = die juengst verknuepfte Version (`draft_linked`, QE4).
        - **vorher** = die Version, die vor der Aktivierung (bzw. jetzt) zuletzt
          aktiv war, laut `status_history`.
        - **Quote**: juengster `test_run` des Pruefalls der Massnahme fuer die
          Version (3.2: „Es zaehlt das letzte Ergebnis“).
        - **Nutzungen**: `usage_event` mit `source='server'` und der
          Versionsnummer (3.4: Nutzungen zaehlen nur `source='server'`).
        - **Faelle**: Faelle aller Agenten mit Zuordnung zu diesem Element im
          Zeitfenster der Version (vorher: ab ihrer Aktivierung bis zur
          Aktivierung der neuen; nachher: ab `activated`). `agent_case` kennt
          keine Version; das Zeitfenster ist die Naeherung.
        - **Wiederauftreten**: neue Faelle des besprochenen Agenten am selben
          Element nach `activated` — bei Zielen ohne Versionen (QE6 a) nach
          Anlage der Massnahme. Ohne Aktivierung eines versionierten Ziels None.
        """
        async with self._pool.acquire() as conn, conn.transaction(isolation="repeatable_read"):
            activated_at = _last_event_at(measure, MeasureEventKind.activated)
            linked = _last_event(measure, MeasureEventKind.draft_linked)
            before: VersionFigures | None = None
            after: VersionFigures | None = None
            since: datetime | None
            if not measure_target_versioned(measure.target):
                since = measure.created_at
            else:
                since = activated_at
                if linked is not None and linked.version_id is not None:
                    entity_type = linked.version_entity_type
                    assert entity_type is not None
                    after, before = await _version_pair(
                        conn, workspace_id, measure, entity_type, linked.version_id, activated_at
                    )
            recurrence: int | None = None
            if since is not None:
                recurrence = await _count_cases(
                    conn, workspace_id, measure, since, None, agent_id=measure.agent_id
                )
        return FollowUpFigures(before=before, after=after, recurrence=recurrence)


def measure_target_versioned(target: str) -> bool:
    """Hat das Ziel Versionen? (QE6: `tool_policy`, `memory` haben keine.)

    Eine Quelle mit der Versionspruefung: die Ziele aus `_VERSION_TABLES`.
    """
    return target in _VERSION_TABLES


def _last_event(measure: MeasureRead, kind: MeasureEventKind) -> MeasureEventRead | None:
    hits = [e for e in measure.events if e.event is kind]
    return hits[-1] if hits else None


def _last_event_at(measure: MeasureRead, kind: MeasureEventKind) -> datetime | None:
    event = _last_event(measure, kind)
    return event.created_at if event is not None else None


async def _version_pair(
    conn: asyncpg.Connection,
    workspace_id: UUID,
    measure: MeasureRead,
    entity_type: str,
    version_id: UUID,
    activated_at: datetime | None,
) -> tuple[VersionFigures | None, VersionFigures | None]:
    """(nachher, vorher) fuer die verknuepfte Version; None, wenn es sie nicht mehr gibt."""
    table, version_table, fk = _VERSION_TABLES[entity_type]
    new = await conn.fetchrow(
        f"SELECT e.id AS entity_id, v.version FROM {version_table} v "
        f"JOIN {table} e ON e.id = v.{fk} WHERE v.id = $2 AND e.workspace_id = $1",
        workspace_id,
        version_id,
    )
    if new is None:
        return None, None
    entity_id: UUID = new["entity_id"]
    after = VersionFigures(
        version_id=version_id,
        version=new["version"],
        run=await _latest_run(conn, workspace_id, measure.test_case_id, version_id),
        uses=await _count_uses(conn, workspace_id, entity_type, entity_id, new["version"]),
        cases=(
            await _count_cases(conn, workspace_id, measure, activated_at, None)
            if activated_at is not None
            else None
        ),
    )
    # Juengste Aktivierung einer ANDEREN Versionsnummer vor dem Stichtag.
    old = await conn.fetchrow(
        "SELECT version, changed_at FROM status_history "
        "WHERE workspace_id = $1 AND entity_type = $2 AND entity_id = $3 "
        "  AND to_status = 'active' AND version IS NOT NULL AND version <> $4 "
        "  AND changed_at <= COALESCE($5::timestamptz, now()) "
        "ORDER BY changed_at DESC LIMIT 1",
        workspace_id,
        entity_type,
        entity_id,
        new["version"],
        activated_at,
    )
    if old is None:
        return after, None
    old_version_id: UUID | None = await conn.fetchval(
        f"SELECT v.id FROM {version_table} v JOIN {table} e ON e.id = v.{fk} "
        f"WHERE v.{fk} = $1 AND v.version = $2 ORDER BY (v.locale = e.locale) DESC LIMIT 1",
        entity_id,
        old["version"],
    )
    before = VersionFigures(
        version_id=old_version_id,
        version=old["version"],
        run=(
            await _latest_run(conn, workspace_id, measure.test_case_id, old_version_id)
            if old_version_id is not None
            else None
        ),
        uses=await _count_uses(conn, workspace_id, entity_type, entity_id, old["version"]),
        cases=await _count_cases(conn, workspace_id, measure, old["changed_at"], activated_at),
    )
    return after, before


async def _latest_run(
    conn: asyncpg.Connection, workspace_id: UUID, test_case_id: UUID, version_id: UUID
) -> RunFigure | None:
    row = await conn.fetchrow(
        "SELECT runs_total, runs_passed, verdict, attestation, created_at FROM test_run "
        "WHERE workspace_id = $1 AND test_case_id = $2 AND subject_version_id = $3 "
        "ORDER BY created_at DESC, id DESC LIMIT 1",
        workspace_id,
        test_case_id,
        version_id,
    )
    return RunFigure(**dict(row)) if row is not None else None


async def _count_uses(
    conn: asyncpg.Connection, workspace_id: UUID, entity_type: str, entity_id: UUID, version: int
) -> int:
    count = await conn.fetchval(
        "SELECT COUNT(*)::int FROM usage_event "
        "WHERE workspace_id = $1 AND entity_type = $2 AND entity_id = $3 AND version = $4 "
        "  AND source = 'server'",
        workspace_id,
        entity_type,
        entity_id,
        version,
    )
    return int(count or 0)


async def _count_cases(
    conn: asyncpg.Connection,
    workspace_id: UUID,
    measure: MeasureRead,
    since: datetime | None,
    until: datetime | None,
    *,
    agent_id: UUID | None = None,
) -> int:
    """Faelle mit Zuordnung zum Ziel der Massnahme, angelegt in `[since, until)`.

    Ohne die Faelle der Massnahme selbst. `tool_policy` haengt am Agenten
    (keine `entity_id`): dort zaehlt nur der Agent der Massnahme.
    """
    if measure.target in MEASURE_TARGETS_WITHOUT_ENTITY:
        agent_id = measure.agent_id
    count = await conn.fetchval(
        "SELECT COUNT(DISTINCT c.id)::int FROM agent_case c "
        "JOIN agent_case_element el ON el.workspace_id = c.workspace_id AND el.case_id = c.id "
        "WHERE c.workspace_id = $1 AND el.target = $2 "
        "  AND el.entity_id IS NOT DISTINCT FROM $3::uuid "
        "  AND ($4::timestamptz IS NULL OR c.created_at >= $4) "
        "  AND ($5::timestamptz IS NULL OR c.created_at < $5) "
        "  AND ($6::uuid IS NULL OR c.agent_id = $6) "
        "  AND NOT (c.id = ANY($7::uuid[]))",
        workspace_id,
        measure.target.value,
        measure.entity_id,
        since,
        until,
        agent_id,
        list(measure.case_ids),
    )
    return int(count or 0)


async def _load_session(
    conn: asyncpg.Connection, workspace_id: UUID, session_id: UUID
) -> SessionDetail | None:
    row = await conn.fetchrow(
        f"SELECT {_SESSION_COLUMNS}, {_SESSION_CASES_SQL} FROM feedback_session s "
        "WHERE s.workspace_id = $1 AND s.id = $2",
        workspace_id,
        session_id,
    )
    if row is None:
        return None
    measures = await _load_measures(conn, workspace_id, "m.session_id = $2", session_id)
    return SessionDetail(session=_session(row), measures=measures)


async def _load_measures(
    conn: asyncpg.Connection, workspace_id: UUID, where: str, *args: object
) -> list[MeasureRead]:
    """Massnahmen samt Faellen und Verlauf; `where` ist ein festes SQL-Fragment.

    `where` kommt nur aus diesem Modul (nie aus Eingaben) und nutzt `$2`
    folgende; `$1` ist der Workspace. Drei Abfragen statt N+1.
    """
    rows = await conn.fetch(
        f"SELECT {_MEASURE_COLUMNS} FROM measure m "
        f"WHERE m.workspace_id = $1 AND {where} ORDER BY m.created_at, m.id",
        workspace_id,
        *args,
    )
    if not rows:
        return []
    ids = [r["id"] for r in rows]
    case_rows = await conn.fetch(
        "SELECT measure_id, case_id FROM measure_case "
        "WHERE workspace_id = $1 AND measure_id = ANY($2::uuid[]) "
        "ORDER BY created_at, case_id",
        workspace_id,
        ids,
    )
    event_rows = await conn.fetch(
        f"SELECT {_EVENT_COLUMNS} FROM measure_event "
        "WHERE workspace_id = $1 AND measure_id = ANY($2::uuid[]) "
        "ORDER BY created_at, id",
        workspace_id,
        ids,
    )
    cases: dict[UUID, list[UUID]] = {i: [] for i in ids}
    for r in case_rows:
        cases[r["measure_id"]].append(r["case_id"])
    events: dict[UUID, list[MeasureEventRead]] = {i: [] for i in ids}
    for r in event_rows:
        events[r["measure_id"]].append(_event(r))
    result: list[MeasureRead] = []
    for r in rows:
        trail = events[r["id"]]
        last = trail[-1] if trail else None
        state = measure_state_for(
            last.event if last is not None else None,
            last.verdict if last is not None else None,
        )
        result.append(
            MeasureRead.model_validate(
                {**dict(r), "case_ids": cases[r["id"]], "state": state, "events": trail}
            )
        )
    return result
