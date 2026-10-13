"""Datenzugriff fuer das Dossier eines Agenten (ADR-0053 6.6, Paket E1).

Nur Lesen. Jede Query filtert auf `workspace_id` — per Signatur erzwungen
(Defense-in-Depth zusaetzlich zur RLS, Muster `case_repository`). Status-
Ableitung der Faelle, Versions-Tabellen und Betroffenen-Abfragen kommen aus
ihren Repositories (eine Quelle, kein zweiter Ableitungsweg).

Mengen-Regel: keine Abfrage je Zeile. Die Blocks lesen in festen
Sammelabfragen (`ANY`/`unnest`); nur `shared_agent_count` fragt je Baustein
einer Generationen-Seite (hoechstens `DOSSIER_GENERATIONS_LIMIT`).

Was das Repository bewusst NICHT tut: Rechte pruefen, kuerzen, deckeln
(ausser per `limit`) und Schwellen anwenden — das ist Sache des Service.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol
from uuid import UUID

import asyncpg

from who2be_api.repositories.case_repository import _CASES_WITH_STATUS, _VERSION_TABLES
from who2be_api.repositories.test_case_repository import _AFFECTED_SQL

# Fall-Status, die im Dossier als offen gelten (Karte E1).
_OPEN_STATUSES = ("open", "triaged", "in_progress", "reopened")

# Bausteine des Agenten HEUTE (W3 O1: Zuordnungen sind nicht historisiert):
# Persona, Template, Playbooks der Persona samt Composite-Kindern, Resources
# dieser Playbooks samt Composite-Kindern. Rekursion mit UNION terminiert auch
# bei einem Zyklus (endliche Menge). `ord` legt die Reihenfolge fest.
_ELEMENTS_SQL = (
    "WITH RECURSIVE a AS ("
    "  SELECT persona_id, system_prompt_template_id FROM agent "
    "  WHERE workspace_id = $1 AND id = $2"
    "), pb(id) AS ("
    "  SELECT pp.playbook_id FROM persona_playbook pp JOIN a ON pp.persona_id = a.persona_id "
    "  WHERE pp.workspace_id = $1 "
    "  UNION "
    "  SELECT pc.child_id FROM playbook_composition pc JOIN pb ON pc.parent_id = pb.id "
    "  WHERE pc.workspace_id = $1"
    "), rs(id) AS ("
    "  SELECT prl.resource_id FROM playbook_resource_link prl JOIN pb ON prl.playbook_id = pb.id "
    "  WHERE prl.workspace_id = $1 "
    "  UNION "
    "  SELECT rc.child_id FROM resource_composition rc JOIN rs ON rc.parent_id = rs.id "
    "  WHERE rc.workspace_id = $1"
    ") "
    "SELECT 'persona' AS entity_type, p.id AS entity_id, p.name, 0 AS ord "
    "  FROM persona p JOIN a ON p.id = a.persona_id WHERE p.workspace_id = $1 "
    "UNION ALL "
    "SELECT 'system_prompt_template', t.id, t.name, 1 "
    "  FROM system_prompt_template t JOIN a ON t.id = a.system_prompt_template_id "
    "  WHERE t.workspace_id = $1 "
    "UNION ALL "
    "SELECT 'playbook', p.id, p.name, 2 FROM playbook p "
    "  WHERE p.workspace_id = $1 AND p.id IN (SELECT id FROM pb) "
    "UNION ALL "
    "SELECT 'resource', r.id, r.name, 3 FROM resource r "
    "  WHERE r.workspace_id = $1 AND r.id IN (SELECT id FROM rs) "
    "ORDER BY ord, name, entity_id"
)

# Namen der Elemente aus Massnahmen-Zielen, je Art eine feste Tabelle.
_NAME_CASE_SQL = (
    "CASE m.target "
    + " ".join(
        f"WHEN '{kind}' THEN (SELECT x.name FROM {table} x "
        f"WHERE x.workspace_id = m.workspace_id AND x.id = m.entity_id)"
        for kind, (table, _, _) in _VERSION_TABLES.items()
    )
    + " END"
)

# Versionsnummer eines `activated`-Events, je Art eine feste Tabelle.
_EVENT_VERSION_CASE_SQL = (
    "CASE e.version_entity_type "
    + " ".join(
        f"WHEN '{kind}' THEN (SELECT v.version FROM {version_table} v WHERE v.id = e.version_id)"
        for kind, (_, version_table, _) in _VERSION_TABLES.items()
    )
    + " END"
)

_ELEMENT_PAIRS = "(SELECT * FROM unnest($2::text[], $3::uuid[]))"

_ACTIVE_STATUS = "to_status = 'active' AND version IS NOT NULL"


@dataclass(frozen=True)
class ElementRef:
    """Ein Baustein: Art, ID, Name (Name None = Element geloescht)."""

    entity_type: str
    entity_id: UUID
    name: str | None


@dataclass(frozen=True)
class CaseRow:
    id: UUID
    status: str
    severity: str
    situation: str
    expected_behavior: str
    created_at: datetime


@dataclass(frozen=True)
class VersionRow:
    entity_type: str
    entity_id: UUID
    version: int
    active: bool


@dataclass(frozen=True)
class ActivationRow:
    """Eine Aktivierung aus `status_history`."""

    id: UUID
    entity_type: str
    entity_id: UUID
    version: int
    changed_at: datetime


@dataclass(frozen=True)
class CaseWindow:
    """Zeitfenster `[since, until)` eines Bausteins fuer die Fallzaehlung."""

    entity_type: str
    entity_id: UUID
    since: datetime
    until: datetime | None


@dataclass(frozen=True)
class UsageRow:
    entity_type: str
    entity_id: UUID
    version: int
    source: str
    outcome: str | None
    count: int


@dataclass(frozen=True)
class SignalRow:
    entity_type: str
    entity_id: UUID
    version: int
    signal: str
    count: int


@dataclass(frozen=True)
class AccessRow:
    ref_kind: str
    operation: str
    sensitivity: str
    entries: int
    refs: int
    last_on: date


@dataclass(frozen=True)
class MeasureRow:
    id: UUID
    session_id: UUID
    target: str
    entity_id: UUID | None
    change_summary: str
    last_event: str | None
    last_verdict: str | None
    reviewed_verdict: str | None
    reviewed_at: datetime | None
    follow_up_at: date
    case_count: int
    created_at: datetime


@dataclass(frozen=True)
class GenerationRow:
    id: UUID
    entity_type: str
    entity_id: UUID
    name: str | None
    from_version: int | None
    to_version: int
    activated_at: datetime


@dataclass(frozen=True)
class GenerationMeasure:
    """Eine Massnahme, die mit der Aktivierung `activation_id` aktiviert wurde."""

    activation_id: UUID
    measure_id: UUID
    verdict: str | None
    reviewed_at: datetime | None


def _pairs(elements: Sequence[tuple[str, UUID]]) -> tuple[list[str], list[UUID]]:
    return [t for t, _ in elements], [i for _, i in elements]


class DossierRepository(Protocol):
    """Vertrag des Dossier-Datenzugriffs (Service-Sicht)."""

    async def agent_name(self, workspace_id: UUID, agent_id: UUID) -> str | None: ...

    async def open_case_counts(self, workspace_id: UUID, agent_id: UUID) -> dict[str, int]: ...

    async def open_cases(self, workspace_id: UUID, agent_id: UUID, limit: int) -> list[CaseRow]: ...

    async def elements(self, workspace_id: UUID, agent_id: UUID) -> list[ElementRef]: ...

    async def versions(
        self, workspace_id: UUID, elements: Sequence[tuple[str, UUID]]
    ) -> list[VersionRow]: ...

    async def activations(
        self, workspace_id: UUID, elements: Sequence[tuple[str, UUID]]
    ) -> list[ActivationRow]: ...

    async def case_counts(self, workspace_id: UUID, windows: Sequence[CaseWindow]) -> list[int]: ...

    async def usage(
        self, workspace_id: UUID, elements: Sequence[tuple[str, UUID]]
    ) -> list[UsageRow]: ...

    async def signals(
        self, workspace_id: UUID, elements: Sequence[tuple[str, UUID]]
    ) -> list[SignalRow]: ...

    async def access_summary(
        self, workspace_id: UUID, agent_id: UUID, since: date
    ) -> list[AccessRow]: ...

    async def measures(
        self, workspace_id: UUID, agent_id: UUID, limit: int
    ) -> tuple[list[MeasureRow], int]: ...

    async def generations(
        self,
        workspace_id: UUID,
        elements: Sequence[tuple[str, UUID]],
        *,
        limit: int,
        cursor: tuple[datetime, UUID] | None,
    ) -> list[GenerationRow]: ...

    async def generation_measures(
        self, workspace_id: UUID, elements: Sequence[tuple[str, UUID]]
    ) -> list[GenerationMeasure]: ...

    async def shared_agent_count(
        self, workspace_id: UUID, entity_type: str, entity_id: UUID, agent_id: UUID
    ) -> int | None: ...


class PgDossierRepository:
    """asyncpg-Implementierung von `DossierRepository`."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def agent_name(self, workspace_id: UUID, agent_id: UUID) -> str | None:
        name: str | None = await self._pool.fetchval(
            "SELECT name FROM agent WHERE workspace_id = $1 AND id = $2", workspace_id, agent_id
        )
        return name

    async def open_case_counts(self, workspace_id: UUID, agent_id: UUID) -> dict[str, int]:
        """Zaehler je offenem Status (Muster `count_by_status`)."""
        rows = await self._pool.fetch(
            f"SELECT x.status, COUNT(*)::int AS n FROM {_CASES_WITH_STATUS} "
            "WHERE x.workspace_id = $1 AND x.agent_id = $2 AND x.status = ANY($3::text[]) "
            "GROUP BY x.status",
            workspace_id,
            agent_id,
            list(_OPEN_STATUSES),
        )
        return {row["status"]: row["n"] for row in rows}

    async def open_cases(self, workspace_id: UUID, agent_id: UUID, limit: int) -> list[CaseRow]:
        """Offene Faelle, schwerste zuerst, dann neueste."""
        rows = await self._pool.fetch(
            "SELECT x.id, x.status, x.severity, x.situation, x.expected_behavior, x.created_at "
            f"FROM {_CASES_WITH_STATUS} "
            "WHERE x.workspace_id = $1 AND x.agent_id = $2 AND x.status = ANY($3::text[]) "
            "ORDER BY CASE x.severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, "
            "         x.created_at DESC, x.id DESC "
            "LIMIT $4",
            workspace_id,
            agent_id,
            list(_OPEN_STATUSES),
            limit,
        )
        return [CaseRow(**dict(row)) for row in rows]

    async def elements(self, workspace_id: UUID, agent_id: UUID) -> list[ElementRef]:
        """Heutige Bausteine plus versionierte Ziele der Massnahmen des Agenten."""
        rows = await self._pool.fetch(_ELEMENTS_SQL, workspace_id, agent_id)
        extra = await self._pool.fetch(
            f"SELECT DISTINCT m.target AS entity_type, m.entity_id, {_NAME_CASE_SQL} AS name "
            "FROM measure m WHERE m.workspace_id = $1 AND m.agent_id = $2 "
            "  AND m.entity_id IS NOT NULL AND m.target = ANY($3::text[]) "
            "ORDER BY m.target, name, m.entity_id",
            workspace_id,
            agent_id,
            list(_VERSION_TABLES),
        )
        seen: set[tuple[str, UUID]] = set()
        result: list[ElementRef] = []
        for row in [*rows, *extra]:
            key = (row["entity_type"], row["entity_id"])
            if key in seen:
                continue
            seen.add(key)
            result.append(ElementRef(row["entity_type"], row["entity_id"], row["name"]))
        return result

    async def versions(
        self, workspace_id: UUID, elements: Sequence[tuple[str, UUID]]
    ) -> list[VersionRow]:
        """Alle Versionsnummern je Baustein (eine Abfrage je Art, Locales zusammengefasst)."""
        result: list[VersionRow] = []
        for kind, (table, version_table, fk) in _VERSION_TABLES.items():
            ids = [i for t, i in elements if t == kind]
            if not ids:
                continue
            rows = await self._pool.fetch(
                f"SELECT v.{fk} AS entity_id, v.version, bool_or(v.status = 'active') AS active "
                f"FROM {version_table} v JOIN {table} e ON e.id = v.{fk} "
                f"WHERE e.workspace_id = $1 AND v.{fk} = ANY($2::uuid[]) "
                f"GROUP BY v.{fk}, v.version",
                workspace_id,
                ids,
            )
            result.extend(
                VersionRow(kind, row["entity_id"], row["version"], row["active"]) for row in rows
            )
        return result

    async def activations(
        self, workspace_id: UUID, elements: Sequence[tuple[str, UUID]]
    ) -> list[ActivationRow]:
        """Aktivierungen der Bausteine, aelteste zuerst."""
        if not elements:
            return []
        rows = await self._pool.fetch(
            "SELECT id, entity_type, entity_id, version, changed_at FROM status_history "
            f"WHERE workspace_id = $1 AND {_ACTIVE_STATUS} "
            f"  AND (entity_type, entity_id) IN {_ELEMENT_PAIRS} "
            "ORDER BY changed_at, id",
            workspace_id,
            *_pairs(elements),
        )
        return [ActivationRow(**dict(row)) for row in rows]

    async def case_counts(self, workspace_id: UUID, windows: Sequence[CaseWindow]) -> list[int]:
        """Faelle aller Agenten je Fenster (Zuordnung zum Baustein), in Eingabe-Reihenfolge."""
        if not windows:
            return []
        rows = await self._pool.fetch(
            "SELECT w.i, (SELECT COUNT(DISTINCT c.id) FROM agent_case c "
            "  JOIN agent_case_element el "
            "    ON el.workspace_id = c.workspace_id AND el.case_id = c.id "
            "  WHERE c.workspace_id = $1 AND el.target = w.t AND el.entity_id = w.e "
            "    AND c.created_at >= w.s AND (w.u IS NULL OR c.created_at < w.u))::int AS n "
            "FROM unnest($2::int[], $3::text[], $4::uuid[], $5::timestamptz[], "
            "            $6::timestamptz[]) AS w(i, t, e, s, u)",
            workspace_id,
            list(range(len(windows))),
            [w.entity_type for w in windows],
            [w.entity_id for w in windows],
            [w.since for w in windows],
            [w.until for w in windows],
        )
        counts = [0] * len(windows)
        for row in rows:
            counts[row["i"]] = row["n"]
        return counts

    async def usage(
        self, workspace_id: UUID, elements: Sequence[tuple[str, UUID]]
    ) -> list[UsageRow]:
        """`usage_event` aller Agenten je Version, getrennt nach `source` (3.4, D3)."""
        if not elements:
            return []
        rows = await self._pool.fetch(
            "SELECT entity_type, entity_id, version, source, outcome, COUNT(*)::int AS count "
            "FROM usage_event "
            "WHERE workspace_id = $1 AND version IS NOT NULL "
            f"  AND (entity_type, entity_id) IN {_ELEMENT_PAIRS} "
            "GROUP BY entity_type, entity_id, version, source, outcome",
            workspace_id,
            *_pairs(elements),
        )
        return [UsageRow(**dict(row)) for row in rows]

    async def signals(
        self, workspace_id: UUID, elements: Sequence[tuple[str, UUID]]
    ) -> list[SignalRow]:
        """Alt-Feedback (`agent_feedback`) aller Agenten je Version und Signal."""
        if not elements:
            return []
        rows = await self._pool.fetch(
            "SELECT entity_type, entity_id, version, signal, COUNT(*)::int AS count "
            "FROM agent_feedback "
            "WHERE workspace_id = $1 AND version IS NOT NULL "
            f"  AND (entity_type, entity_id) IN {_ELEMENT_PAIRS} "
            "GROUP BY entity_type, entity_id, version, signal",
            workspace_id,
            *_pairs(elements),
        )
        return [SignalRow(**dict(row)) for row in rows]

    async def access_summary(
        self, workspace_id: UUID, agent_id: UUID, since: date
    ) -> list[AccessRow]:
        """Summen des Zugriffslogs ab `since`; keine `ref_id`, keine Personen."""
        rows = await self._pool.fetch(
            "SELECT ref_kind, operation, sensitivity_at_access AS sensitivity, "
            "       COUNT(*)::int AS entries, COUNT(DISTINCT ref_id)::int AS refs, "
            "       MAX(access_date) AS last_on "
            "FROM agent_access_log "
            "WHERE workspace_id = $1 AND agent_id = $2 AND access_date >= $3 "
            "GROUP BY ref_kind, operation, sensitivity_at_access "
            "ORDER BY ref_kind, operation, sensitivity_at_access",
            workspace_id,
            agent_id,
            since,
        )
        return [AccessRow(**dict(row)) for row in rows]

    async def measures(
        self, workspace_id: UUID, agent_id: UUID, limit: int
    ) -> tuple[list[MeasureRow], int]:
        """Juengste Massnahmen mit letztem Event und letzter Einstufung; plus Gesamtzahl."""
        rows = await self._pool.fetch(
            "SELECT m.id, m.session_id, m.target, m.entity_id, m.change_summary, m.created_at, "
            "       COALESCE(m.follow_up_at, s.follow_up_at) AS follow_up_at, "
            "       last.event AS last_event, last.verdict AS last_verdict, "
            "       rv.verdict AS reviewed_verdict, rv.created_at AS reviewed_at, "
            "       (SELECT COUNT(*) FROM measure_case mc "
            "         WHERE mc.workspace_id = m.workspace_id AND mc.measure_id = m.id)::int "
            "         AS case_count, "
            "       COUNT(*) OVER ()::int AS total "
            "FROM measure m "
            "JOIN feedback_session s ON s.workspace_id = m.workspace_id AND s.id = m.session_id "
            "LEFT JOIN LATERAL (SELECT e.event, e.verdict FROM measure_event e "
            "    WHERE e.workspace_id = m.workspace_id AND e.measure_id = m.id "
            "    ORDER BY e.created_at DESC, e.id DESC LIMIT 1) last ON TRUE "
            "LEFT JOIN LATERAL (SELECT e.verdict, e.created_at FROM measure_event e "
            "    WHERE e.workspace_id = m.workspace_id AND e.measure_id = m.id "
            "      AND e.event = 'reviewed' "
            "    ORDER BY e.created_at DESC, e.id DESC LIMIT 1) rv ON TRUE "
            "WHERE m.workspace_id = $1 AND m.agent_id = $2 "
            "ORDER BY m.created_at DESC, m.id DESC LIMIT $3",
            workspace_id,
            agent_id,
            limit,
        )
        total = rows[0]["total"] if rows else 0
        items = [MeasureRow(**{k: v for k, v in dict(row).items() if k != "total"}) for row in rows]
        return items, total

    async def generations(
        self,
        workspace_id: UUID,
        elements: Sequence[tuple[str, UUID]],
        *,
        limit: int,
        cursor: tuple[datetime, UUID] | None,
    ) -> list[GenerationRow]:
        """Aktivierungen der Bausteine, neueste zuerst, Keyset `(changed_at, id)`.

        `from_version` ist die unmittelbar vorher aktivierte Version desselben
        Bausteins (auch dieselbe Nummer bei einer Re-Aktivierung).
        """
        if not elements:
            return []
        rows = await self._pool.fetch(
            "SELECT h.id, h.entity_type, h.entity_id, h.version AS to_version, "
            "       h.changed_at AS activated_at, "
            "       (SELECT p.version FROM status_history p "
            "         WHERE p.workspace_id = h.workspace_id AND p.entity_type = h.entity_type "
            "           AND p.entity_id = h.entity_id AND p.to_status = 'active' "
            "           AND p.version IS NOT NULL AND (p.changed_at, p.id) < (h.changed_at, h.id) "
            "         ORDER BY p.changed_at DESC, p.id DESC LIMIT 1) AS from_version "
            "FROM status_history h "
            f"WHERE h.workspace_id = $1 AND h.{_ACTIVE_STATUS} "
            f"  AND (h.entity_type, h.entity_id) IN {_ELEMENT_PAIRS} "
            "  AND ($4::timestamptz IS NULL OR (h.changed_at, h.id) < ($4, $5::uuid)) "
            "ORDER BY h.changed_at DESC, h.id DESC LIMIT $6",
            workspace_id,
            *_pairs(elements),
            cursor[0] if cursor is not None else None,
            cursor[1] if cursor is not None else None,
            limit,
        )
        return [GenerationRow(name=None, **dict(row)) for row in rows]

    async def generation_measures(
        self, workspace_id: UUID, elements: Sequence[tuple[str, UUID]]
    ) -> list[GenerationMeasure]:
        """Massnahmen (aller Agenten) an den Bausteinen, je `activated` die Aktivierung.

        `activated` entsteht in der Transaktion der Aktivierung (E3,
        `version_status._activate_measures`); `status_history.changed_at` ist
        dort `now()` (Transaktionsbeginn), das Event `clock_timestamp()`. Die
        Aktivierung ist deshalb die juengste derselben Version mit
        `changed_at <= created_at`.
        """
        if not elements:
            return []
        rows = await self._pool.fetch(
            "SELECT h.id AS activation_id, m.id AS measure_id, "
            "       rv.verdict, rv.created_at AS reviewed_at "
            "FROM measure m "
            "JOIN measure_event e ON e.workspace_id = m.workspace_id AND e.measure_id = m.id "
            "  AND e.event = 'activated' "
            "JOIN LATERAL (SELECT sh.id FROM status_history sh "
            "    WHERE sh.workspace_id = m.workspace_id AND sh.entity_type = m.target "
            "      AND sh.entity_id = m.entity_id AND sh.to_status = 'active' "
            f"      AND sh.version = {_EVENT_VERSION_CASE_SQL} "
            "      AND sh.changed_at <= e.created_at "
            "    ORDER BY sh.changed_at DESC, sh.id DESC LIMIT 1) h ON TRUE "
            "LEFT JOIN LATERAL (SELECT r.verdict, r.created_at FROM measure_event r "
            "    WHERE r.workspace_id = m.workspace_id AND r.measure_id = m.id "
            "      AND r.event = 'reviewed' "
            "    ORDER BY r.created_at DESC, r.id DESC LIMIT 1) rv ON TRUE "
            f"WHERE m.workspace_id = $1 AND (m.target, m.entity_id) IN {_ELEMENT_PAIRS} "
            "ORDER BY m.created_at, m.id",
            workspace_id,
            *_pairs(elements),
        )
        return [GenerationMeasure(**dict(row)) for row in rows]

    async def shared_agent_count(
        self, workspace_id: UUID, entity_type: str, entity_id: UUID, agent_id: UUID
    ) -> int | None:
        """Andere Agenten, die den Baustein heute erreichen (ADR 3.2.1); None ohne Index."""
        sql = _AFFECTED_SQL.get(entity_type)
        if sql is None:
            return None
        rows = await self._pool.fetch(sql, workspace_id, entity_id)
        return sum(1 for row in rows if row["agent_id"] != agent_id)
