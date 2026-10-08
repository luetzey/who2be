"""Datenzugriff fuer Faelle (ADR-0053 Abschnitt 3.3, Migration 0100).

Jede Query filtert auf `workspace_id` — per Signatur erzwungen
(Defense-in-Depth zusaetzlich zur RLS, Muster `test_case_repository`).

Der Status eines Falls ist keine Spalte: er ist das juengste Status-Event
(`_STATUS_SQL`; `reported` heisst `open`). Jeder Schreibweg, der den Fall
beruehrt, schreibt sein Event in DERSELBEN Transaktion:

- `create_case`: Fall + `reported`.
- `convert_lesson`: Lernvorschlag -> Fall (6.4): Fall + `reported`,
  Eintrag `converted` mit `converted_case_id`, Gedaechtnis-Event `converted`.
- `promote_feedback`: Alt-Feedback -> Fall (6.5, 5.2): Fall + `reported`,
  Triage-Ereignis `addressed` mit Verweis `case:<id>` am Alt-Feedback.
- `append_event`: ein Status-Event.
- `append_transition`: ein Status-Event unter der Fall-Sperre, nur wenn der
  vom Service gepruefte Ausgangsstatus (und bei `triaged` die Zuordnung)
  noch gilt (D2, gegen Check-then-act).
- `set_elements`: Replace-Semantik; je hinzugekommenem Element
  `element_assigned`, je entferntem `element_unassigned`.
- `add_statement`: Schilderung + `statement`.
- `delete_case`: Hard-Delete samt Verlauf (CASCADE) und eine inhaltsfreie
  `audit_log`-Zeile `case.deleted` in EINER Anweisung (PM-Entscheidung Q6,
  Muster `memory.deleted`, Weiche G3/M5); ein in den Fall umgewandelter
  Lernvorschlag faellt mit (Begruendung an der Methode).

Was das Repository bewusst NICHT tut:

- **Rechte pruefen.** Wer melden, lesen, triagieren, schildern oder loeschen
  darf (3.3, Tabelle „Rechte“), entscheidet der Service (D2).
- **Uebergaenge pruefen.** Ob `triaged -> addressed` erlaubt ist, steht in
  der Uebergangstabelle 3.3 und gehoert in den Service. Die DB haelt nur die
  Form-Invarianten (Version bei `addressed`, Massnahme bei `in_progress`/
  `verified`, Begruendung bei `reopened`/`dismissed`, kein Agent als Richter).
- **Inhalt aendern.** Es gibt keinen Update-Weg; `who2be_app` hat auf
  `agent_case` auch keinen UPDATE-Grant.

Nebenlaeufigkeit: `who2be_app` darf auf `agent_case` nicht `FOR UPDATE`
sperren (das verlangt ein UPDATE-Recht). Schreibwege, die vom aktuellen
Stand abhaengen (`set_elements`), serialisieren sich deshalb ueber eine
transaktionsgebundene Advisory-Sperre je Fall.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

import asyncpg

# `_READ_COLUMNS` und `_insert_human_event` bewusst aus dem Gedaechtnis-
# Repository: EINE Quelle fuer Spaltenliste und Event-Form (3.1.2), damit
# `converted` nicht anders aussieht als `approved`/`rejected`.
from who2be_api.repositories.memory_repository import (
    _READ_COLUMNS as _MEMORY_COLUMNS,
)
from who2be_api.repositories.memory_repository import (
    MEMORY_DELETED_AUDIT_ACTION,
    _insert_human_event,
)
from who2be_models import (
    CASE_STATUS_EVENTS,
    CaseActorKind,
    CaseAssignedByKind,
    CaseCreate,
    CaseDetail,
    CaseElementInput,
    CaseElementRead,
    CaseEventCreate,
    CaseEventKind,
    CaseEventRead,
    CaseRead,
    CaseReporterKind,
    CaseStatementCreate,
    CaseStatementRead,
    CaseStatus,
    CaseTarget,
    EntityType,
    FeedbackResolution,
    MemoryEventKind,
    MemoryKind,
    MemoryRead,
    MemoryStatus,
)
from who2be_models.case import CaseConvertRequest

CASE_DELETED_AUDIT_ACTION = "case.deleted"

# Verweis im `note` des Triage-Ereignisses, wenn ein Alt-Feedback in einen
# Fall uebernommen wurde (ADR-0053 5.2): `case:<uuid>`, sprachneutral und
# maschinenlesbar.
PROMOTED_NOTE_PREFIX = "case:"


@dataclass(frozen=True)
class NotConvertible:
    """Eintrag existiert, ist aber kein offener Lernvorschlag (convert -> 409)."""

    kind: MemoryKind
    status: MemoryStatus


@dataclass(frozen=True)
class NotPromotable:
    """Alt-Feedback existiert, ist aber schon triagiert (promote -> 409)."""

    resolution: str


# Zuordnungsziel -> Tabelle (fest, nie aus Eingaben). `tool_policy` und
# `model_limit` haben keine `entity_id` und fehlen deshalb.
_TARGET_TABLES: dict[CaseTarget, str] = {
    CaseTarget.persona: "persona",
    CaseTarget.playbook: "playbook",
    CaseTarget.resource: "resource",
    CaseTarget.external_tool: "external_tool",
    CaseTarget.system_prompt_template: "system_prompt_template",
    CaseTarget.memory: "agent_memory",
}

# Versionsart -> (Identitaetstabelle, Versionstabelle, FK-Spalte), Muster
# `test_case_repository._ENTITY_TABLES`.
_VERSION_TABLES: dict[str, tuple[str, str, str]] = {
    "persona": ("persona", "persona_version", "persona_id"),
    "playbook": ("playbook", "playbook_version", "playbook_id"),
    "resource": ("resource", "resource_version", "resource_id"),
    "system_prompt_template": (
        "system_prompt_template",
        "system_prompt_template_version",
        "template_id",
    ),
    "external_tool": ("external_tool", "external_tool_version", "external_tool_id"),
}

_STATUS_EVENT_VALUES = ", ".join(f"'{event.value}'" for event in CASE_STATUS_EVENTS)

# Juengstes Status-Event eines Falls `c`. Gleichstand bricht `id` (die
# Event-Zeit kommt aus `clock_timestamp()`, Gleichstand ist also selten).
_STATUS_SQL = (
    "COALESCE(("
    "  SELECT CASE e.event WHEN 'reported' THEN 'open' ELSE e.event END "
    "  FROM agent_case_event e "
    "  WHERE e.workspace_id = c.workspace_id AND e.case_id = c.id "
    f"   AND e.event IN ({_STATUS_EVENT_VALUES}) "
    "  ORDER BY e.created_at DESC, e.id DESC LIMIT 1"
    "), 'open')"
)

_CASE_COLUMNS = (
    "c.id, c.workspace_id, c.agent_id, c.reporter_kind, c.reporter_user_id, "
    "c.reporter_agent_id, c.situation, c.behavior, c.impact, c.expected_behavior, "
    "c.severity, c.signal, c.source_ref, c.source_feedback_id, c.source_memory_id, "
    "c.created_at"
)

# Fall plus abgeleiteter Status, als Unterabfrage filterbar.
_CASES_WITH_STATUS = f"(SELECT {_CASE_COLUMNS}, {_STATUS_SQL} AS status FROM agent_case c) AS x"

_EVENT_COLUMNS = (
    "id, case_id, event, actor_kind, actor_id, note, version_entity_type, version_id, "
    "measure_id, element_target, element_entity_id, created_at"
)

_ELEMENT_COLUMNS = "id, case_id, target, entity_id, assigned_by_kind, assigned_by, created_at"

_STATEMENT_COLUMNS = (
    "id, case_id, agent_id, followed_instruction, missing_information, conflict, created_at"
)

_INSERT_EVENT_SQL = (
    "INSERT INTO agent_case_event "
    "(workspace_id, case_id, event, actor_kind, actor_id, note, version_entity_type, "
    " version_id, measure_id, element_target, element_entity_id) "
    "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11) "
    f"RETURNING {_EVENT_COLUMNS}"
)


def _case(row: asyncpg.Record) -> CaseRead:
    return CaseRead.model_validate(dict(row))


def _event(row: asyncpg.Record) -> CaseEventRead:
    return CaseEventRead.model_validate(dict(row))


def _element(row: asyncpg.Record) -> CaseElementRead:
    return CaseElementRead.model_validate(dict(row))


def _statement(row: asyncpg.Record) -> CaseStatementRead:
    return CaseStatementRead.model_validate(dict(row))


def _reporter_actor(
    reporter_kind: CaseReporterKind,
    reporter_user_id: UUID | None,
    reporter_agent_id: UUID | None,
) -> tuple[CaseActorKind, UUID | None]:
    """Akteur des `reported`-Events aus dem Melder.

    Mensch -> Nutzer-ID; Agent und Builder -> Agent-ID; Muster -> System.
    """
    if reporter_kind is CaseReporterKind.human:
        return CaseActorKind.human, reporter_user_id
    if reporter_kind is CaseReporterKind.pattern:
        return CaseActorKind.system, None
    return CaseActorKind.agent, reporter_agent_id


class CaseRepository(Protocol):
    """Vertrag des Fall-Datenzugriffs (Service-Sicht, D2)."""

    async def create_case(
        self,
        workspace_id: UUID,
        data: CaseCreate,
        *,
        reporter_kind: CaseReporterKind,
        reporter_user_id: UUID | None,
        reporter_agent_id: UUID | None,
        source_feedback_id: UUID | None = None,
        source_memory_id: UUID | None = None,
    ) -> CaseRead: ...

    async def get_case(self, workspace_id: UUID, case_id: UUID) -> CaseRead | None: ...

    async def convert_lesson(
        self,
        workspace_id: UUID,
        agent_id: UUID,
        memory_id: UUID,
        data: CaseConvertRequest,
        *,
        actor_id: UUID,
    ) -> CaseRead | NotConvertible | None: ...

    async def promote_feedback(
        self,
        workspace_id: UUID,
        feedback_id: UUID,
        data: CaseCreate,
        *,
        actor_id: UUID,
    ) -> CaseRead | NotPromotable | None: ...

    async def get_detail(self, workspace_id: UUID, case_id: UUID) -> CaseDetail | None: ...

    async def list_cases(
        self,
        workspace_id: UUID,
        *,
        agent_id: UUID | None = None,
        status: CaseStatus | None = None,
        target: CaseTarget | None = None,
        reporter_user_id: UUID | None = None,
        limit: int = 50,
        cursor: tuple[datetime, UUID] | None = None,
    ) -> list[CaseRead]: ...

    async def count_by_status(
        self,
        workspace_id: UUID,
        *,
        agent_id: UUID | None = None,
        reporter_user_id: UUID | None = None,
    ) -> dict[CaseStatus, int]: ...

    async def append_event(
        self,
        workspace_id: UUID,
        case_id: UUID,
        data: CaseEventCreate,
        *,
        actor_kind: CaseActorKind,
        actor_id: UUID | None,
    ) -> CaseEventRead | None: ...

    async def append_transition(
        self,
        workspace_id: UUID,
        case_id: UUID,
        data: CaseEventCreate,
        *,
        expected_status: CaseStatus,
        require_element: bool,
        actor_kind: CaseActorKind,
        actor_id: UUID | None,
    ) -> CaseEventRead | None: ...

    async def set_elements(
        self,
        workspace_id: UUID,
        case_id: UUID,
        elements: Sequence[CaseElementInput],
        *,
        assigned_by_kind: CaseAssignedByKind,
        assigned_by: UUID,
    ) -> list[CaseElementRead] | None: ...

    async def agent_exists(self, workspace_id: UUID, agent_id: UUID) -> bool: ...

    async def element_exists(
        self, workspace_id: UUID, target: CaseTarget, entity_id: UUID
    ) -> bool: ...

    async def version_exists(
        self, workspace_id: UUID, entity_type: EntityType, version_id: UUID
    ) -> bool: ...

    async def add_statement(
        self,
        workspace_id: UUID,
        case_id: UUID,
        agent_id: UUID,
        data: CaseStatementCreate,
    ) -> CaseStatementRead | None: ...

    async def delete_case(
        self, workspace_id: UUID, case_id: UUID, actor_id: UUID | None
    ) -> bool: ...


class PgCaseRepository:
    """asyncpg-Implementierung von `CaseRepository`."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create_case(
        self,
        workspace_id: UUID,
        data: CaseCreate,
        *,
        reporter_kind: CaseReporterKind,
        reporter_user_id: UUID | None,
        reporter_agent_id: UUID | None,
        source_feedback_id: UUID | None = None,
        source_memory_id: UUID | None = None,
    ) -> CaseRead:
        """Legt Fall und `reported`-Event atomar an (Status `open`)."""
        async with self._pool.acquire() as conn, conn.transaction():
            return await _create_case_in(
                conn,
                workspace_id,
                data,
                reporter_kind=reporter_kind,
                reporter_user_id=reporter_user_id,
                reporter_agent_id=reporter_agent_id,
                source_feedback_id=source_feedback_id,
                source_memory_id=source_memory_id,
            )

    async def convert_lesson(
        self,
        workspace_id: UUID,
        agent_id: UUID,
        memory_id: UUID,
        data: CaseConvertRequest,
        *,
        actor_id: UUID,
    ) -> CaseRead | NotConvertible | None:
        """Lernvorschlag -> Fall (ADR-0053 6.4), alles in EINER Transaktion.

        Liest den Eintrag besitzer-gebunden `FOR UPDATE`; nur `lesson` mit
        `status='pending'` wird umgewandelt. Dann: Fall mit
        `source_memory_id` + `reported` (Melder = der umwandelnde Mensch),
        Eintrag auf `converted` mit `converted_case_id` (CHECK aus 0091), und
        das Gedaechtnis-Event `converted` (3.1.2, Mensch, `before`/`after`).
        Bricht ein Schritt ab, bleibt nichts davon stehen.

        None: kein Eintrag dieses Agenten. `NotConvertible`: Eintrag da, aber
        kein offener Lernvorschlag (der Service antwortet 409).
        """
        async with self._pool.acquire() as conn, conn.transaction():
            before_row = await conn.fetchrow(
                f"SELECT {_MEMORY_COLUMNS} FROM agent_memory "
                "WHERE workspace_id = $1 AND agent_id = $2 AND id = $3 FOR UPDATE",
                workspace_id,
                agent_id,
                memory_id,
            )
            if before_row is None:
                return None
            before = MemoryRead.model_validate(dict(before_row))
            if before.kind is not MemoryKind.lesson or before.status is not MemoryStatus.pending:
                return NotConvertible(kind=before.kind, status=before.status)
            case = await _create_case_in(
                conn,
                workspace_id,
                data.for_agent(agent_id),
                reporter_kind=CaseReporterKind.human,
                reporter_user_id=actor_id,
                reporter_agent_id=None,
                source_memory_id=memory_id,
            )
            after_row = await conn.fetchrow(
                "UPDATE agent_memory SET status = 'converted', converted_case_id = $3, "
                "updated_at = now() "
                f"WHERE workspace_id = $1 AND id = $2 RETURNING {_MEMORY_COLUMNS}",
                workspace_id,
                memory_id,
                case.id,
            )
            assert after_row is not None  # Zeile ist gesperrt
            after = MemoryRead.model_validate(dict(after_row))
            await _insert_human_event(
                conn, workspace_id, before, MemoryEventKind.converted, actor_id, None, after
            )
        return case

    async def promote_feedback(
        self,
        workspace_id: UUID,
        feedback_id: UUID,
        data: CaseCreate,
        *,
        actor_id: UUID,
    ) -> CaseRead | NotPromotable | None:
        """Alt-Feedback -> Fall (ADR-0053 6.5, 5.2), alles in EINER Transaktion.

        Nur ein offenes Feedback (kein Triage-Ereignis) wird uebernommen. Dann:
        Fall mit `source_feedback_id` + `reported` (Melder = der Mensch, der
        uebernimmt) und ein Triage-Ereignis `addressed` am Alt-Feedback mit dem
        Verweis `case:<id>` im `note`. Das Alt-Feedback selbst bleibt
        unveraendert (append-only, 0053/0054).

        Serialisiert ueber eine Advisory-Sperre je Feedback: `who2be_app` hat
        auf `agent_feedback` kein UPDATE und damit kein `FOR UPDATE`. So kann
        dasselbe Feedback nicht zweimal uebernommen werden.

        None: kein Feedback in diesem Workspace. `NotPromotable`: schon
        triagiert (der Service antwortet 409).
        """
        async with self._pool.acquire() as conn, conn.transaction():
            await conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended($1::text, 0))",
                f"feedback:{feedback_id}",
            )
            found = await conn.fetchrow(
                "SELECT (SELECT r.resolution FROM feedback_resolution r "
                "   WHERE r.workspace_id = f.workspace_id AND r.feedback_id = f.id "
                "   ORDER BY r.created_at DESC, r.id DESC LIMIT 1) AS resolution "
                "FROM agent_feedback f WHERE f.workspace_id = $1 AND f.id = $2",
                workspace_id,
                feedback_id,
            )
            if found is None:
                return None
            if found["resolution"] is not None:
                return NotPromotable(resolution=found["resolution"])
            case = await _create_case_in(
                conn,
                workspace_id,
                data,
                reporter_kind=CaseReporterKind.human,
                reporter_user_id=actor_id,
                reporter_agent_id=None,
                source_feedback_id=feedback_id,
            )
            await _insert_resolution(
                conn,
                workspace_id,
                feedback_id,
                actor_id,
                FeedbackResolution.addressed,
                f"{PROMOTED_NOTE_PREFIX}{case.id}",
            )
        return case

    async def get_case(self, workspace_id: UUID, case_id: UUID) -> CaseRead | None:
        row = await self._pool.fetchrow(
            f"SELECT * FROM {_CASES_WITH_STATUS} WHERE workspace_id = $1 AND id = $2",
            workspace_id,
            case_id,
        )
        return _case(row) if row is not None else None

    async def get_detail(self, workspace_id: UUID, case_id: UUID) -> CaseDetail | None:
        """Fall mit Verlauf (aelteste zuerst), Zuordnungen und Schilderungen (neueste zuerst)."""
        async with self._pool.acquire() as conn, conn.transaction(isolation="repeatable_read"):
            row = await conn.fetchrow(
                f"SELECT * FROM {_CASES_WITH_STATUS} WHERE workspace_id = $1 AND id = $2",
                workspace_id,
                case_id,
            )
            if row is None:
                return None
            events = await conn.fetch(
                f"SELECT {_EVENT_COLUMNS} FROM agent_case_event "
                "WHERE workspace_id = $1 AND case_id = $2 ORDER BY created_at ASC, id ASC",
                workspace_id,
                case_id,
            )
            elements = await conn.fetch(
                f"SELECT {_ELEMENT_COLUMNS} FROM agent_case_element "
                "WHERE workspace_id = $1 AND case_id = $2 ORDER BY created_at ASC, id ASC",
                workspace_id,
                case_id,
            )
            statements = await conn.fetch(
                f"SELECT {_STATEMENT_COLUMNS} FROM agent_case_statement "
                "WHERE workspace_id = $1 AND case_id = $2 ORDER BY created_at DESC, id DESC",
                workspace_id,
                case_id,
            )
        return CaseDetail(
            case=_case(row),
            events=[_event(r) for r in events],
            elements=[_element(r) for r in elements],
            statements=[_statement(r) for r in statements],
        )

    async def list_cases(
        self,
        workspace_id: UUID,
        *,
        agent_id: UUID | None = None,
        status: CaseStatus | None = None,
        target: CaseTarget | None = None,
        reporter_user_id: UUID | None = None,
        limit: int = 50,
        cursor: tuple[datetime, UUID] | None = None,
    ) -> list[CaseRead]:
        """Eine Seite, neueste zuerst, Keyset auf `(created_at, id)` (Q1).

        `target`: Faelle mit mindestens einer Zuordnung dieses Ziels.
        `reporter_user_id`: „eigene gemeldete Faelle“ (viewer, 3.3).
        Feste Parameter-Positionen, NULL = Filter aus — kein dynamisches SQL.
        """
        rows = await self._pool.fetch(
            f"SELECT * FROM {_CASES_WITH_STATUS} "
            "WHERE x.workspace_id = $1 "
            "  AND ($2::uuid IS NULL OR x.agent_id = $2) "
            "  AND ($3::text IS NULL OR x.status = $3) "
            "  AND ($4::text IS NULL OR EXISTS ("
            "        SELECT 1 FROM agent_case_element el "
            "        WHERE el.workspace_id = x.workspace_id AND el.case_id = x.id "
            "          AND el.target = $4)) "
            "  AND ($5::uuid IS NULL OR x.reporter_user_id = $5) "
            "  AND ($6::timestamptz IS NULL OR (x.created_at, x.id) < ($6, $7::uuid)) "
            "ORDER BY x.created_at DESC, x.id DESC LIMIT $8",
            workspace_id,
            agent_id,
            status.value if status is not None else None,
            target.value if target is not None else None,
            reporter_user_id,
            cursor[0] if cursor is not None else None,
            cursor[1] if cursor is not None else None,
            limit,
        )
        return [_case(row) for row in rows]

    async def count_by_status(
        self,
        workspace_id: UUID,
        *,
        agent_id: UUID | None = None,
        reporter_user_id: UUID | None = None,
    ) -> dict[CaseStatus, int]:
        """Zaehler je Status fuer die Chips (Q1); jeder Status ist enthalten, auch mit 0."""
        rows = await self._pool.fetch(
            f"SELECT x.status, COUNT(*)::int AS n FROM {_CASES_WITH_STATUS} "
            "WHERE x.workspace_id = $1 "
            "  AND ($2::uuid IS NULL OR x.agent_id = $2) "
            "  AND ($3::uuid IS NULL OR x.reporter_user_id = $3) "
            "GROUP BY x.status",
            workspace_id,
            agent_id,
            reporter_user_id,
        )
        counts = dict.fromkeys(CaseStatus, 0)
        for row in rows:
            counts[CaseStatus(row["status"])] = row["n"]
        return counts

    async def append_event(
        self,
        workspace_id: UUID,
        case_id: UUID,
        data: CaseEventCreate,
        *,
        actor_kind: CaseActorKind,
        actor_id: UUID | None,
    ) -> CaseEventRead | None:
        """Haengt ein Status-Event an. None, wenn der Fall nicht existiert."""
        async with self._pool.acquire() as conn, conn.transaction():
            if not await _case_exists(conn, workspace_id, case_id):
                return None
            return await _insert_event(
                conn,
                workspace_id,
                case_id,
                data.event,
                actor_kind,
                actor_id,
                note=data.note,
                version_entity_type=data.version_entity_type,
                version_id=data.version_id,
                measure_id=data.measure_id,
            )

    async def append_transition(
        self,
        workspace_id: UUID,
        case_id: UUID,
        data: CaseEventCreate,
        *,
        expected_status: CaseStatus,
        require_element: bool,
        actor_kind: CaseActorKind,
        actor_id: UUID | None,
    ) -> CaseEventRead | None:
        """Status-Event nur, wenn der Fall noch im erwarteten Zustand ist (D2).

        Der Service prueft Kante und Pflichtfelder vorab; hier wird dieselbe
        Bedingung unter der Fall-Sperre (wie `set_elements`) noch einmal
        geprueft und erst dann geschrieben. So koennen zwei gleichzeitige
        Uebergaenge nicht beide von demselben Ausgangsstatus ausgehen, und ein
        paralleles Leeren der Zuordnung kann ein `triaged` ohne Element nicht
        mehr unterlaufen. `require_element`: mindestens eine Zuordnung.

        None, wenn der Fall fehlt oder der Stand abweicht; der Aufrufer liest
        dann neu und meldet den passenden Fehler.
        """
        async with self._pool.acquire() as conn, conn.transaction():
            if not await _case_exists(conn, workspace_id, case_id):
                return None
            await _lock_case(conn, case_id)
            current = await conn.fetchval(
                f"SELECT {_STATUS_SQL} FROM agent_case c WHERE c.workspace_id = $1 AND c.id = $2",
                workspace_id,
                case_id,
            )
            if current != expected_status.value:
                return None
            if require_element:
                has_element = await conn.fetchval(
                    "SELECT 1 FROM agent_case_element WHERE workspace_id = $1 AND case_id = $2 "
                    "LIMIT 1",
                    workspace_id,
                    case_id,
                )
                if has_element is None:
                    return None
            return await _insert_event(
                conn,
                workspace_id,
                case_id,
                data.event,
                actor_kind,
                actor_id,
                note=data.note,
                version_entity_type=data.version_entity_type,
                version_id=data.version_id,
                measure_id=data.measure_id,
            )

    async def agent_exists(self, workspace_id: UUID, agent_id: UUID) -> bool:
        found = await self._pool.fetchval(
            "SELECT 1 FROM agent WHERE workspace_id = $1 AND id = $2", workspace_id, agent_id
        )
        return found is not None

    async def element_exists(self, workspace_id: UUID, target: CaseTarget, entity_id: UUID) -> bool:
        """Gehoert das Zuordnungsziel zu diesem Workspace?

        Nur fuer Ziele mit `entity_id` (nicht `tool_policy`/`model_limit`).
        Tabellenname aus einer festen Abbildung, nie aus Eingaben.
        """
        table = _TARGET_TABLES[target]
        found = await self._pool.fetchval(
            f"SELECT 1 FROM {table} WHERE workspace_id = $1 AND id = $2",
            workspace_id,
            entity_id,
        )
        return found is not None

    async def version_exists(
        self, workspace_id: UUID, entity_type: EntityType, version_id: UUID
    ) -> bool:
        """Gehoert die Version zu einem Element dieses Workspace (`addressed`, F-W6)?

        Ueber die Identitaetstabelle geprueft, Muster
        `PgTestCaseRepository.version_entity_id`.
        """
        table, version_table, fk = _VERSION_TABLES[entity_type]
        found = await self._pool.fetchval(
            f"SELECT 1 FROM {version_table} v JOIN {table} e ON e.id = v.{fk} "
            "WHERE v.id = $2 AND e.workspace_id = $1",
            workspace_id,
            version_id,
        )
        return found is not None

    async def set_elements(
        self,
        workspace_id: UUID,
        case_id: UUID,
        elements: Sequence[CaseElementInput],
        *,
        assigned_by_kind: CaseAssignedByKind,
        assigned_by: UUID,
    ) -> list[CaseElementRead] | None:
        """Ersetzt die Zuordnung (Replace-Semantik, `PUT /cases/{id}/elements`).

        Unveraenderte Zuordnungen bleiben mit ihrem Urheber stehen. Je neuem
        Element ein `element_assigned`, je entferntem ein `element_unassigned`
        (3.3: „das Event `element_unassigned` haelt es fest“). Eine leere Liste
        loescht alle Zuordnungen. None, wenn der Fall nicht existiert.
        """
        wanted = list(dict.fromkeys(elements))  # Dubletten im Request einmal
        actor_kind = CaseActorKind(assigned_by_kind.value)
        async with self._pool.acquire() as conn, conn.transaction():
            if not await _case_exists(conn, workspace_id, case_id):
                return None
            await _lock_case(conn, case_id)
            current = await conn.fetch(
                f"SELECT {_ELEMENT_COLUMNS} FROM agent_case_element "
                "WHERE workspace_id = $1 AND case_id = $2 ORDER BY created_at ASC, id ASC",
                workspace_id,
                case_id,
            )
            current_keys = {(CaseTarget(r["target"]), r["entity_id"]): r["id"] for r in current}
            wanted_keys = {(e.target, e.entity_id) for e in wanted}
            for (target, entity_id), element_id in current_keys.items():
                if (target, entity_id) in wanted_keys:
                    continue
                await conn.execute(
                    "DELETE FROM agent_case_element WHERE workspace_id = $1 AND id = $2",
                    workspace_id,
                    element_id,
                )
                await _insert_event(
                    conn,
                    workspace_id,
                    case_id,
                    CaseEventKind.element_unassigned,
                    actor_kind,
                    assigned_by,
                    element_target=target,
                    element_entity_id=entity_id,
                )
            for element in wanted:
                if (element.target, element.entity_id) in current_keys:
                    continue
                await conn.execute(
                    "INSERT INTO agent_case_element "
                    "(workspace_id, case_id, target, entity_id, assigned_by_kind, assigned_by) "
                    "VALUES ($1, $2, $3, $4, $5, $6)",
                    workspace_id,
                    case_id,
                    element.target.value,
                    element.entity_id,
                    assigned_by_kind.value,
                    assigned_by,
                )
                await _insert_event(
                    conn,
                    workspace_id,
                    case_id,
                    CaseEventKind.element_assigned,
                    actor_kind,
                    assigned_by,
                    element_target=element.target,
                    element_entity_id=element.entity_id,
                )
            rows = await conn.fetch(
                f"SELECT {_ELEMENT_COLUMNS} FROM agent_case_element "
                "WHERE workspace_id = $1 AND case_id = $2 ORDER BY created_at ASC, id ASC",
                workspace_id,
                case_id,
            )
        return [_element(r) for r in rows]

    async def add_statement(
        self,
        workspace_id: UUID,
        case_id: UUID,
        agent_id: UUID,
        data: CaseStatementCreate,
    ) -> CaseStatementRead | None:
        """Haengt die Schilderung des betroffenen Agenten an, plus Event `statement`.

        None, wenn der Fall nicht existiert. Ist `agent_id` nicht der Agent
        des Falls, weist der Composite-FK die Zeile ab
        (`asyncpg.ForeignKeyViolationError`); der Service (D2) prueft das
        vorher und antwortet mit `case_statement_not_subject`.
        """
        async with self._pool.acquire() as conn, conn.transaction():
            if not await _case_exists(conn, workspace_id, case_id):
                return None
            row = await conn.fetchrow(
                "INSERT INTO agent_case_statement "
                "(workspace_id, case_id, agent_id, followed_instruction, missing_information, "
                " conflict) VALUES ($1, $2, $3, $4, $5, $6) "
                f"RETURNING {_STATEMENT_COLUMNS}",
                workspace_id,
                case_id,
                agent_id,
                data.followed_instruction,
                data.missing_information,
                data.conflict,
            )
            await _insert_event(
                conn, workspace_id, case_id, CaseEventKind.statement, CaseActorKind.agent, agent_id
            )
        assert row is not None
        return _statement(row)

    async def delete_case(self, workspace_id: UUID, case_id: UUID, actor_id: UUID | None) -> bool:
        """Hard-Delete samt Verlauf, Zuordnung und Schilderungen (Q6).

        Loeschen und inhaltsfreie `audit_log`-Zeile in EINER Anweisung.

        Ist aus einem Lernvorschlag dieser Fall geworden
        (`agent_memory.converted_case_id`, FK ON DELETE NO ACTION, Migration
        0100), faellt der Lernvorschlag in derselben Anweisung mit, samt
        Historie per Cascade und je Zeile einer inhaltsfreien Spur
        `memory.deleted` (Weiche M5). Warum mitloeschen statt
        `converted_case_id` auf NULL: der CHECK `converted <=>
        converted_case_id` (0091) verlangte dann einen neuen Status, und
        weder `rejected` (eine Ablehnung, die es nie gab) noch `pending`
        (zurueck in die Triage) stimmt. Ausserdem ist der Lernvorschlag die
        Quelle des Fall-Inhalts; bliebe er stehen, bliebe genau der Inhalt,
        den „Loeschen samt Verlauf“ entfernen soll. Der NO-ACTION-FK wird erst
        am Ende der Anweisung geprueft, beide Loeschungen sind dann durch.
        """
        result: str = await self._pool.execute(
            "WITH lessons AS ("
            "  DELETE FROM agent_memory WHERE workspace_id = $1 AND converted_case_id = $2 "
            "  RETURNING id, workspace_id"
            "), deleted AS ("
            "  DELETE FROM agent_case WHERE workspace_id = $1 AND id = $2 "
            "  RETURNING id, workspace_id"
            "), lesson_audit AS ("
            "  INSERT INTO audit_log (workspace_id, actor_id, action, target) "
            f"  SELECT workspace_id, $3::uuid, '{MEMORY_DELETED_AUDIT_ACTION}', id::text "
            "  FROM lessons"
            ") "
            "INSERT INTO audit_log (workspace_id, actor_id, action, target) "
            f"SELECT workspace_id, $3::uuid, '{CASE_DELETED_AUDIT_ACTION}', id::text FROM deleted",
            workspace_id,
            case_id,
            actor_id,
        )
        return result.endswith(" 1")


async def _lock_case(conn: asyncpg.Connection, case_id: UUID) -> None:
    """Transaktionsgebundene Sperre je Fall (Zuordnung und Uebergaenge)."""
    await conn.execute("SELECT pg_advisory_xact_lock(hashtextextended($1::uuid::text, 0))", case_id)


async def _create_case_in(
    conn: asyncpg.Connection,
    workspace_id: UUID,
    data: CaseCreate,
    *,
    reporter_kind: CaseReporterKind,
    reporter_user_id: UUID | None,
    reporter_agent_id: UUID | None,
    source_feedback_id: UUID | None = None,
    source_memory_id: UUID | None = None,
) -> CaseRead:
    """Fall + `reported`-Event in der Transaktion von `conn` (Melden, convert, promote)."""
    actor_kind, actor_id = _reporter_actor(reporter_kind, reporter_user_id, reporter_agent_id)
    case_id: UUID = await conn.fetchval(
        "INSERT INTO agent_case "
        "(workspace_id, agent_id, reporter_kind, reporter_user_id, reporter_agent_id, "
        " situation, behavior, impact, expected_behavior, severity, signal, source_ref, "
        " source_feedback_id, source_memory_id) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14) "
        "RETURNING id",
        workspace_id,
        data.agent_id,
        reporter_kind.value,
        reporter_user_id,
        reporter_agent_id,
        data.situation,
        data.behavior,
        data.impact,
        data.expected_behavior,
        data.severity.value,
        data.signal.value if data.signal is not None else None,
        data.source_ref,
        source_feedback_id,
        source_memory_id,
    )
    await _insert_event(conn, workspace_id, case_id, CaseEventKind.reported, actor_kind, actor_id)
    row = await conn.fetchrow(
        f"SELECT * FROM {_CASES_WITH_STATUS} WHERE workspace_id = $1 AND id = $2",
        workspace_id,
        case_id,
    )
    assert row is not None  # in derselben Transaktion angelegt
    return _case(row)


async def _insert_resolution(
    conn: asyncpg.Connection,
    workspace_id: UUID,
    feedback_id: UUID,
    actor_id: UUID,
    resolution: FeedbackResolution,
    note: str,
) -> None:
    """Triage-Ereignis am Alt-Feedback (append-only, Migration 0054)."""
    await conn.execute(
        "INSERT INTO feedback_resolution (workspace_id, feedback_id, actor_id, resolution, note) "
        "VALUES ($1, $2, $3, $4, $5)",
        workspace_id,
        feedback_id,
        actor_id,
        resolution.value,
        note,
    )


async def _case_exists(conn: asyncpg.Connection, workspace_id: UUID, case_id: UUID) -> bool:
    found = await conn.fetchval(
        "SELECT 1 FROM agent_case WHERE workspace_id = $1 AND id = $2", workspace_id, case_id
    )
    return found is not None


async def _insert_event(
    conn: asyncpg.Connection,
    workspace_id: UUID,
    case_id: UUID,
    event: CaseEventKind,
    actor_kind: CaseActorKind,
    actor_id: UUID | None,
    *,
    note: str | None = None,
    version_entity_type: str | None = None,
    version_id: UUID | None = None,
    measure_id: UUID | None = None,
    element_target: CaseTarget | None = None,
    element_entity_id: UUID | None = None,
) -> CaseEventRead:
    row = await conn.fetchrow(
        _INSERT_EVENT_SQL,
        workspace_id,
        case_id,
        event.value,
        actor_kind.value,
        actor_id,
        note,
        version_entity_type,
        version_id,
        measure_id,
        element_target.value if element_target is not None else None,
        element_entity_id,
    )
    assert row is not None
    return _event(row)
