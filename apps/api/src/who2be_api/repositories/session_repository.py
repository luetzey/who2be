"""Datenzugriff fuer Gespraechsprotokolle und Massnahmen (ADR-0053 3.5/3.6, Migration 0103).

Jede Query filtert auf `workspace_id` — per Signatur erzwungen
(Defense-in-Depth zusaetzlich zur RLS, Muster `case_repository`).

Schreibwege:

- `insert_session`: Protokoll samt Faellen und Massnahmen (mit deren Faellen)
  in der Transaktion des UEBERGEBENEN `conn`. Der Service (E2b-1) oeffnet die
  Transaktion, weil in derselben Transaktion die Faelle auf `in_progress`
  gehen (W-E2 = a) — das schreibt das Fall-Repository, nicht dieses hier.
- `append_measure_event`: ein Event an einer Massnahme; optional in einer
  uebergebenen Transaktion (E3: `activated` zusammen mit dem Versionswechsel).

Lesewege: Protokoll je ID (mit eingebetteten Massnahmen, QE1 = a), Liste je
Workspace/Agent/Fall mit Keyset-Cursor, Massnahme je ID, Massnahmen je Fall
und je verknuepfter Version (E3).

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
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

import asyncpg

from who2be_models import (
    EntityType,
    MeasureActorKind,
    MeasureEventCreate,
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


class PgSessionRepository:
    """asyncpg-Implementierung von `SessionRepository`."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

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
