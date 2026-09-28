"""Datenzugriff fuer Pruefall + Prueflauf (ADR-0053 Abschnitt 3.2, Migration 0089).

Jede Query filtert auf `workspace_id` — per Signatur erzwungen
(Defense-in-Depth zusaetzlich zur RLS, Muster `memory_repository`).

Was das Repository bewusst NICHT tut:

- **Inhalt aendern.** Es gibt nur `retire` (Status) und `supersede` (neuer
  Pruefall + `retired` am alten in EINER Transaktion). Die DB sichert das
  zusaetzlich ab: `who2be_app` hat auf `test_case` nur einen UPDATE-Grant fuer
  die Spalte `status`, auf `test_run` gar keinen.
- **Rechte oder Sichtbarkeit pruefen.** Wer welche Pruefaelle lesen, anlegen
  oder melden darf (ADR 3.2, Tabelle „Rechte"), entscheidet der Service (B2).
- **Die Pruefall-Menge nach 3.2.1 aufloesen.** Welche Agenten ein Element
  heute erreichen, berechnet der Service; hier liegt nur der Baustein
  `list_active_for_element`, der die Vereinigung aus direkt gebundenen und
  agent-gebundenen aktiven Pruefaellen liefert.
- **Laufzahlen/Urteil validieren.** Der Service prueft vorab mit
  `who2be_models.verdict_consistent` und antwortet mit
  `test_run_verdict_inconsistent`; die CHECKs der Migration sind die letzte
  Linie.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

import asyncpg

from who2be_models import (
    EntityType,
    TestAttestation,
    TestCaseCreate,
    TestCaseCreatedByKind,
    TestCaseRead,
    TestCaseStatus,
    TestRunCreate,
    TestRunRead,
)

_CASE_COLUMNS = (
    "id, workspace_id, agent_id, entity_type, entity_id, title, input, "
    "expected_behavior, check_kind, check_pattern, origin_case_id, "
    "origin_measure_id, status, supersedes_id, created_by_kind, created_by, created_at"
)

_RUN_COLUMNS = (
    "id, workspace_id, test_case_id, subject_entity_type, subject_version_id, "
    "runs_total, runs_passed, verdict, output_excerpt, attestation, model_provider, "
    "model_name, reported_by_agent_id, reported_by_user_id, created_at"
)

_INSERT_CASE_SQL = (
    "INSERT INTO test_case "
    "(workspace_id, agent_id, entity_type, entity_id, title, input, expected_behavior, "
    " check_kind, check_pattern, origin_case_id, origin_measure_id, supersedes_id, "
    " created_by_kind, created_by) "
    "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14) "
    f"RETURNING {_CASE_COLUMNS}"
)


def _case(row: asyncpg.Record) -> TestCaseRead:
    return TestCaseRead.model_validate(dict(row))


def _run(row: asyncpg.Record) -> TestRunRead:
    return TestRunRead.model_validate(dict(row))


class TestCaseRepository(Protocol):
    """Vertrag des Pruefall-Datenzugriffs (Service-Sicht)."""

    async def create_case(
        self,
        workspace_id: UUID,
        data: TestCaseCreate,
        *,
        created_by_kind: TestCaseCreatedByKind,
        created_by: UUID,
    ) -> TestCaseRead: ...

    async def get_case(self, workspace_id: UUID, case_id: UUID) -> TestCaseRead | None: ...

    async def list_cases(
        self,
        workspace_id: UUID,
        *,
        agent_id: UUID | None = None,
        entity_type: EntityType | None = None,
        entity_id: UUID | None = None,
        status: TestCaseStatus | None = None,
    ) -> list[TestCaseRead]: ...

    async def list_active_for_element(
        self,
        workspace_id: UUID,
        entity_type: EntityType,
        entity_id: UUID,
        agent_ids: Sequence[UUID],
    ) -> list[TestCaseRead]: ...

    async def retire_case(self, workspace_id: UUID, case_id: UUID) -> TestCaseRead | None: ...

    async def supersede_case(
        self,
        workspace_id: UUID,
        old_case_id: UUID,
        data: TestCaseCreate,
        *,
        created_by_kind: TestCaseCreatedByKind,
        created_by: UUID,
    ) -> TestCaseRead | None: ...

    async def insert_runs(
        self,
        workspace_id: UUID,
        subject_entity_type: EntityType,
        subject_version_id: UUID,
        results: Sequence[TestRunCreate],
        *,
        attestation: TestAttestation,
        reported_by_agent_id: UUID | None,
        reported_by_user_id: UUID | None,
        model_provider: str | None,
        model_name: str | None,
    ) -> list[TestRunRead]: ...

    async def latest_runs_for_version(
        self,
        workspace_id: UUID,
        subject_version_id: UUID,
        case_ids: Sequence[UUID],
    ) -> dict[UUID, TestRunRead]: ...


class PgTestCaseRepository:
    """asyncpg-Implementierung von `TestCaseRepository`."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create_case(
        self,
        workspace_id: UUID,
        data: TestCaseCreate,
        *,
        created_by_kind: TestCaseCreatedByKind,
        created_by: UUID,
    ) -> TestCaseRead:
        row = await self._pool.fetchrow(
            _INSERT_CASE_SQL,
            *_case_args(workspace_id, data, None, created_by_kind, created_by),
        )
        assert row is not None  # INSERT ... RETURNING liefert immer eine Zeile.
        return _case(row)

    async def get_case(self, workspace_id: UUID, case_id: UUID) -> TestCaseRead | None:
        row = await self._pool.fetchrow(
            f"SELECT {_CASE_COLUMNS} FROM test_case WHERE workspace_id = $1 AND id = $2",
            workspace_id,
            case_id,
        )
        return _case(row) if row is not None else None

    async def list_cases(
        self,
        workspace_id: UUID,
        *,
        agent_id: UUID | None = None,
        entity_type: EntityType | None = None,
        entity_id: UUID | None = None,
        status: TestCaseStatus | None = None,
    ) -> list[TestCaseRead]:
        # Feste Parameter-Positionen, NULL = Filter aus — kein dynamisches SQL.
        rows = await self._pool.fetch(
            f"SELECT {_CASE_COLUMNS} FROM test_case "
            "WHERE workspace_id = $1 "
            "  AND ($2::uuid IS NULL OR agent_id = $2) "
            "  AND ($3::text IS NULL OR entity_type = $3) "
            "  AND ($4::uuid IS NULL OR entity_id = $4) "
            "  AND ($5::text IS NULL OR status = $5) "
            "ORDER BY created_at ASC, id ASC",
            workspace_id,
            agent_id,
            entity_type,
            entity_id,
            status.value if status is not None else None,
        )
        return [_case(row) for row in rows]

    async def list_active_for_element(
        self,
        workspace_id: UUID,
        entity_type: EntityType,
        entity_id: UUID,
        agent_ids: Sequence[UUID],
    ) -> list[TestCaseRead]:
        """Vereinigung nach ADR 3.2.1: direkt gebunden ODER Agent in `agent_ids`.

        `agent_ids` (die Agenten, die das Element heute erreichen) berechnet
        der Service. Jeder Pruefall erscheint hoechstens einmal.
        """
        rows = await self._pool.fetch(
            f"SELECT {_CASE_COLUMNS} FROM test_case "
            "WHERE workspace_id = $1 AND status = 'active' "
            "  AND ((entity_type = $2 AND entity_id = $3) OR agent_id = ANY($4::uuid[])) "
            "ORDER BY created_at ASC, id ASC",
            workspace_id,
            entity_type,
            entity_id,
            list(agent_ids),
        )
        return [_case(row) for row in rows]

    async def retire_case(self, workspace_id: UUID, case_id: UUID) -> TestCaseRead | None:
        """Setzt `retired` (idempotent). None, wenn der Pruefall nicht existiert."""
        row = await self._pool.fetchrow(
            "UPDATE test_case SET status = 'retired' "
            f"WHERE workspace_id = $1 AND id = $2 RETURNING {_CASE_COLUMNS}",
            workspace_id,
            case_id,
        )
        return _case(row) if row is not None else None

    async def supersede_case(
        self,
        workspace_id: UUID,
        old_case_id: UUID,
        data: TestCaseCreate,
        *,
        created_by_kind: TestCaseCreatedByKind,
        created_by: UUID,
    ) -> TestCaseRead | None:
        """Korrektur (ADR 3.2): neuer Pruefall mit `supersedes_id`, alter `retired`.

        Beides in EINER Transaktion; der alte Pruefall wird per `FOR UPDATE`
        gesperrt, damit zwei parallele Korrekturen nicht beide gegen einen
        noch aktiven Vorgaenger laufen. None, wenn der alte Pruefall nicht
        existiert oder schon `retired` ist.
        """
        async with self._pool.acquire() as conn, conn.transaction():
            status = await conn.fetchval(
                "SELECT status FROM test_case WHERE workspace_id = $1 AND id = $2 FOR UPDATE",
                workspace_id,
                old_case_id,
            )
            if status != TestCaseStatus.active.value:
                return None
            row = await conn.fetchrow(
                _INSERT_CASE_SQL,
                *_case_args(workspace_id, data, old_case_id, created_by_kind, created_by),
            )
            await conn.execute(
                "UPDATE test_case SET status = 'retired' WHERE workspace_id = $1 AND id = $2",
                workspace_id,
                old_case_id,
            )
        assert row is not None
        return _case(row)

    async def insert_runs(
        self,
        workspace_id: UUID,
        subject_entity_type: EntityType,
        subject_version_id: UUID,
        results: Sequence[TestRunCreate],
        *,
        attestation: TestAttestation,
        reported_by_agent_id: UUID | None,
        reported_by_user_id: UUID | None,
        model_provider: str | None,
        model_name: str | None,
    ) -> list[TestRunRead]:
        """Schreibt eine Ergebnis-Charge atomar (alles oder nichts)."""
        created: list[TestRunRead] = []
        async with self._pool.acquire() as conn, conn.transaction():
            for result in results:
                row = await conn.fetchrow(
                    "INSERT INTO test_run "
                    "(workspace_id, test_case_id, subject_entity_type, subject_version_id, "
                    " runs_total, runs_passed, verdict, output_excerpt, attestation, "
                    " model_provider, model_name, reported_by_agent_id, reported_by_user_id) "
                    "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13) "
                    f"RETURNING {_RUN_COLUMNS}",
                    workspace_id,
                    result.test_case_id,
                    subject_entity_type,
                    subject_version_id,
                    result.runs_total,
                    result.runs_passed,
                    result.verdict.value,
                    result.output_excerpt,
                    attestation.value,
                    model_provider,
                    model_name,
                    reported_by_agent_id,
                    reported_by_user_id,
                )
                assert row is not None
                created.append(_run(row))
        return created

    async def latest_runs_for_version(
        self,
        workspace_id: UUID,
        subject_version_id: UUID,
        case_ids: Sequence[UUID],
    ) -> dict[UUID, TestRunRead]:
        """Letztes Ergebnis je Pruefall fuer eine Version („es zaehlt das letzte").

        Pruefaelle ohne Ergebnis fehlen im Mapping — der Bericht (B2) fuehrt
        sie als `missing`.
        """
        rows = await self._pool.fetch(
            f"SELECT DISTINCT ON (test_case_id) {_RUN_COLUMNS} FROM test_run "
            "WHERE workspace_id = $1 AND subject_version_id = $2 "
            "  AND test_case_id = ANY($3::uuid[]) "
            "ORDER BY test_case_id, created_at DESC, id DESC",
            workspace_id,
            subject_version_id,
            list(case_ids),
        )
        return {row["test_case_id"]: _run(row) for row in rows}


def _case_args(
    workspace_id: UUID,
    data: TestCaseCreate,
    supersedes_id: UUID | None,
    created_by_kind: TestCaseCreatedByKind,
    created_by: UUID,
) -> tuple[object, ...]:
    return (
        workspace_id,
        data.agent_id,
        data.entity_type,
        data.entity_id,
        data.title,
        data.input,
        data.expected_behavior,
        data.check_kind.value,
        data.check_pattern,
        data.origin_case_id,
        data.origin_measure_id,
        supersedes_id,
        created_by_kind.value,
        created_by,
    )
