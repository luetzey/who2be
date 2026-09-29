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
- **Die Pruefall-Menge nach 3.2.1 zusammensetzen.** Hier liegen nur die
  Bausteine: `affected_agents` (welche Agenten ein Element heute erreichen,
  mit Weg `via`, eine Abfrage je Zeile der Tabelle in 3.2.1) und
  `list_active_for_element` (Vereinigung aus direkt gebundenen und
  agent-gebundenen aktiven Pruefaellen). Die Zusammensetzung zum Bericht
  macht `test_case_service.build_test_report` — dieselbe Funktion fuer
  Bericht (6.2) und Aktivierung (6.3).
- **Laufzahlen/Urteil validieren.** Der Service prueft vorab mit
  `who2be_models.verdict_consistent` und antwortet mit
  `test_run_verdict_inconsistent`; die CHECKs der Migration sind die letzte
  Linie.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
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


# Identitaets- und Versionstabelle je Elementart. Feste Zuordnung, kein
# Nutzereingabe-Text im SQL: der Schluessel ist ein `EntityType`-Literal.
_ENTITY_TABLES: dict[str, tuple[str, str, str]] = {
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

# Betroffene Agenten nach ADR 3.2.1, eine Abfrage je Elementart. Jede liefert
# `(agent_id, agent_name, via text[])`; `via` nennt die Wege, ueber die der
# Agent das Element HEUTE erreicht (Verknuepfungen sind unversioniert).
# Die rekursiven CTEs nutzen UNION (nicht UNION ALL): die Menge der Paare
# (Knoten, Weg) ist endlich, damit terminieren sie auch, falls die
# Zyklus-Sperre der Composites je umgangen wuerde.
_AFFECTED_PERSONA_SQL = (
    "SELECT a.id AS agent_id, a.name AS agent_name, ARRAY['persona']::text[] AS via "
    "FROM agent a WHERE a.workspace_id = $1 AND a.persona_id = $2 "
    "ORDER BY a.name ASC, a.id ASC"
)

_AFFECTED_TEMPLATE_SQL = (
    "SELECT a.id AS agent_id, a.name AS agent_name, "
    "       ARRAY['system_prompt_template']::text[] AS via "
    "FROM agent a WHERE a.workspace_id = $1 AND a.system_prompt_template_id = $2 "
    "ORDER BY a.name ASC, a.id ASC"
)

_AFFECTED_PLAYBOOK_SQL = (
    "WITH RECURSIVE pb(id, via) AS ("
    "  SELECT $2::uuid, 'persona_playbook'::text "
    "  UNION "
    "  SELECT pc.parent_id, 'playbook_composite'::text "
    "  FROM playbook_composition pc JOIN pb ON pc.child_id = pb.id "
    "  WHERE pc.workspace_id = $1"
    ") "
    "SELECT a.id AS agent_id, a.name AS agent_name, "
    "       array_agg(DISTINCT pb.via ORDER BY pb.via) AS via "
    "FROM pb "
    "JOIN persona_playbook pp ON pp.playbook_id = pb.id AND pp.workspace_id = $1 "
    "JOIN agent a ON a.persona_id = pp.persona_id AND a.workspace_id = $1 "
    "GROUP BY a.id, a.name "
    "ORDER BY a.name ASC, a.id ASC"
)

_AFFECTED_RESOURCE_SQL = (
    "WITH RECURSIVE rs(id, via) AS ("
    "  SELECT $2::uuid, 'resource_link'::text "
    "  UNION "
    "  SELECT rc.parent_id, 'resource_composite'::text "
    "  FROM resource_composition rc JOIN rs ON rc.child_id = rs.id "
    "  WHERE rc.workspace_id = $1"
    "), pb(id, rvia, pvia) AS ("
    "  SELECT prl.playbook_id, rs.via, 'persona_playbook'::text "
    "  FROM playbook_resource_link prl JOIN rs ON prl.resource_id = rs.id "
    "  WHERE prl.workspace_id = $1 "
    "  UNION "
    "  SELECT pc.parent_id, pb.rvia, 'playbook_composite'::text "
    "  FROM playbook_composition pc JOIN pb ON pc.child_id = pb.id "
    "  WHERE pc.workspace_id = $1"
    ") "
    "SELECT a.id AS agent_id, a.name AS agent_name, "
    "       array_agg(DISTINCT v.via ORDER BY v.via) AS via "
    "FROM pb "
    "CROSS JOIN LATERAL unnest(ARRAY[pb.rvia, pb.pvia]) AS v(via) "
    "JOIN persona_playbook pp ON pp.playbook_id = pb.id AND pp.workspace_id = $1 "
    "JOIN agent a ON a.persona_id = pp.persona_id AND a.workspace_id = $1 "
    "GROUP BY a.id, a.name "
    "ORDER BY a.name ASC, a.id ASC"
)

_AFFECTED_SQL: dict[str, str] = {
    "persona": _AFFECTED_PERSONA_SQL,
    "system_prompt_template": _AFFECTED_TEMPLATE_SQL,
    "playbook": _AFFECTED_PLAYBOOK_SQL,
    "resource": _AFFECTED_RESOURCE_SQL,
}


@dataclass(frozen=True)
class AffectedAgent:
    """Ein Agent, der ein Element heute erreicht, mit den Wegen dorthin."""

    agent_id: UUID
    agent_name: str
    via: tuple[str, ...]


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

    async def get_cases(
        self, workspace_id: UUID, case_ids: Sequence[UUID]
    ) -> list[TestCaseRead]: ...

    async def agent_exists(self, workspace_id: UUID, agent_id: UUID) -> bool: ...

    async def entity_exists(
        self, workspace_id: UUID, entity_type: EntityType, entity_id: UUID
    ) -> bool: ...

    async def version_entity_id(
        self, workspace_id: UUID, entity_type: EntityType, version_id: UUID
    ) -> UUID | None: ...

    async def affected_agents(
        self, workspace_id: UUID, entity_type: EntityType, entity_id: UUID
    ) -> list[AffectedAgent]: ...

    async def agent_names(
        self, workspace_id: UUID, agent_ids: Sequence[UUID]
    ) -> dict[UUID, str]: ...


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

    async def get_cases(self, workspace_id: UUID, case_ids: Sequence[UUID]) -> list[TestCaseRead]:
        """Mehrere Pruefaelle auf einmal (unbekannte IDs fehlen im Ergebnis)."""
        rows = await self._pool.fetch(
            f"SELECT {_CASE_COLUMNS} FROM test_case "
            "WHERE workspace_id = $1 AND id = ANY($2::uuid[])",
            workspace_id,
            list(case_ids),
        )
        return [_case(row) for row in rows]

    async def agent_exists(self, workspace_id: UUID, agent_id: UUID) -> bool:
        found = await self._pool.fetchval(
            "SELECT 1 FROM agent WHERE workspace_id = $1 AND id = $2", workspace_id, agent_id
        )
        return found is not None

    async def entity_exists(
        self, workspace_id: UUID, entity_type: EntityType, entity_id: UUID
    ) -> bool:
        table = _ENTITY_TABLES[entity_type][0]
        found = await self._pool.fetchval(
            f"SELECT 1 FROM {table} WHERE workspace_id = $1 AND id = $2",
            workspace_id,
            entity_id,
        )
        return found is not None

    async def version_entity_id(
        self, workspace_id: UUID, entity_type: EntityType, version_id: UUID
    ) -> UUID | None:
        """Element-ID einer Version, None wenn sie nicht zum Workspace gehoert.

        Geprueft ueber die Identitaetstabelle (nicht nur die denormalisierte
        `workspace_id` der Versionstabelle), damit die Zugehoerigkeit an
        derselben Stelle haengt wie bei allen anderen Element-Zugriffen.
        """
        table, version_table, fk = _ENTITY_TABLES[entity_type]
        entity_id: UUID | None = await self._pool.fetchval(
            f"SELECT e.id FROM {version_table} v JOIN {table} e ON e.id = v.{fk} "
            "WHERE v.id = $2 AND e.workspace_id = $1",
            workspace_id,
            version_id,
        )
        return entity_id

    async def affected_agents(
        self, workspace_id: UUID, entity_type: EntityType, entity_id: UUID
    ) -> list[AffectedAgent]:
        """Agenten, die das Element heute erreichen (ADR 3.2.1, Tabelle).

        `external_tool` hat keinen Verweisindex und liefert immer eine leere
        Liste; der Service weist das als `scope_note` aus.
        """
        sql = _AFFECTED_SQL.get(entity_type)
        if sql is None:
            return []
        rows = await self._pool.fetch(sql, workspace_id, entity_id)
        return [
            AffectedAgent(
                agent_id=row["agent_id"], agent_name=row["agent_name"], via=tuple(row["via"])
            )
            for row in rows
        ]

    async def agent_names(self, workspace_id: UUID, agent_ids: Sequence[UUID]) -> dict[UUID, str]:
        rows = await self._pool.fetch(
            "SELECT id, name FROM agent WHERE workspace_id = $1 AND id = ANY($2::uuid[])",
            workspace_id,
            list(agent_ids),
        )
        return {row["id"]: row["name"] for row in rows}


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
