"""Datenzugriff fuer die Timeline (Spec N, ADR-0047/0049 — WP15).

Die Timeline hat ZWEI Datenseiten, beide leben in DIESEM Repo (ARC-3: SQL nur
im Repo; SQLite ausschliesslich ueber den `TableStore`):

- **Postgres:** `wa_artifact` und `kb_node` werden per
  ``date_trunc(granularity, occurred_at)`` gebuckelt — nur Eintraege mit
  ``occurred_precision <> 'unknown'`` (ein unbekannter Zeitpunkt gehoert in
  KEINE Datums-Scheibe, Spec-Akzeptanz N). Der Area-Scope der Artifacts und
  die KB-Sichtbarkeit sitzen IN der WHERE-Klausel: Artifacts filtern auf
  ``area_id = ANY($scope)``, Nodes nutzen dieselbe NOT-EXISTS-Bedingung wie
  `kb_repository._visible_sql` (bewusst hier dupliziert statt importiert —
  die Datei bleibt unangetastet, WP-Disziplin) — kein Nachfiltern, kein
  Existenz-Leak.
- **SQLite (TableStore):** je Tabellen-Quelle ein Tages-Aggregat
  ``SELECT date(<occurred_col>), count(*) ... GROUP BY``, ausgefuehrt ueber
  `run_readonly_query` (Engine-Garantie read-only, ADR-0049). Zurueck kommen
  NUR Tageszaehler, NIE Rohzeilen — SQLite-Zeilen haben keine adressierbaren
  Anker (kein stabiles ``rowid``-Adressschema in der Anker-Sprache ADR-0021),
  darum repraesentiert `TimelineItem(anchor='table:<id>', kind='table_rows')`
  die Tabelle pro Bucket genau einmal.

Pro Bucket werden die Items SQL-seitig gekappt (`item_cap` via
``row_number()``); die Bucket-Gesamtzahl (`total`) zaehlt IMMER vollstaendig
(``count(*) OVER (PARTITION BY bucket)``) — auch wenn Items abgeschnitten
sind, stimmen die counts (Spec N).

Anker-Sprache (ADR-0021, konsistent zu Suche/KB): Artifacts ``<artifact_id>``,
Nodes ``node:<id>``, Tabellen ``table:<id>``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Final, Protocol, TypeAlias
from uuid import UUID

import asyncpg

from who2be_api.tablestore import (
    AreaStoreMissingError,
    TableStore,
    quote_identifier,
    validate_column_name,
)
from who2be_models import TableSchema
from who2be_models.tables import TableColumnType

_Fetcher: TypeAlias = asyncpg.Pool | asyncpg.Connection

# Zeilen-Cap fuer das SQLite-Tages-Aggregat: das Fenster ist auf 366 Tage
# begrenzt (Router), mehr als ~367 Tages-Buckets kann es nicht geben — der
# Deckel ist reine Defensive gegen kaputte Daten.
_TABLE_DAY_LIMIT: Final = 400

# Dieselbe Sichtbarkeits-Bedingung wie `kb_repository._visible_sql` (Spec E):
# NULL = unbeschraenkt; sonst ist ein Node lesbar, wenn KEINE seiner
# Source-Areas ausserhalb der Scope-Liste liegt (quellenlose Nodes sind fuer
# alle lesbar — NOT EXISTS ueber null Zeilen ist wahr).
_NODE_VISIBLE_SQL: Final = (
    "($4::uuid[] IS NULL OR NOT EXISTS ("
    "SELECT 1 FROM kb_node_source_area s "
    "WHERE s.node_id = n.id AND NOT (s.area_id = ANY($4::uuid[]))))"
)

_ARTIFACT_BUCKETS_SQL: Final = (
    "SELECT bucket, anchor, total FROM ("
    "  SELECT date_trunc($5, a.occurred_at) AS bucket,"
    "         a.id::text AS anchor,"
    "         count(*) OVER (PARTITION BY date_trunc($5, a.occurred_at)) AS total,"
    "         row_number() OVER (PARTITION BY date_trunc($5, a.occurred_at)"
    "                            ORDER BY a.occurred_at, a.id) AS rn"
    "  FROM wa_artifact a"
    "  WHERE a.workspace_id = $1"
    "    AND a.occurred_at >= $2 AND a.occurred_at < $3"
    "    AND a.occurred_precision <> 'unknown'"
    "    AND ($4::uuid[] IS NULL OR a.area_id = ANY($4::uuid[]))"
    ") t WHERE rn <= $6 ORDER BY bucket, rn"
)

_NODE_BUCKETS_SQL: Final = (
    "SELECT bucket, anchor, total FROM ("
    "  SELECT date_trunc($5, n.occurred_at) AS bucket,"
    "         'node:' || n.id::text AS anchor,"
    "         count(*) OVER (PARTITION BY date_trunc($5, n.occurred_at)) AS total,"
    "         row_number() OVER (PARTITION BY date_trunc($5, n.occurred_at)"
    "                            ORDER BY n.occurred_at, n.id) AS rn"
    "  FROM kb_node n"
    "  WHERE n.workspace_id = $1"
    "    AND n.occurred_at >= $2 AND n.occurred_at < $3"
    "    AND n.occurred_precision <> 'unknown'"
    f"    AND {_NODE_VISIBLE_SQL}"
    ") t WHERE rn <= $6 ORDER BY bucket, rn"
)

# unknown-Eintraege BEWUSST ohne Zeitfenster: `occurred_precision='unknown'`
# heisst "Zeitpunkt nicht verlaesslich" — ein Fenster-Filter auf einem
# unzuverlaessigen Datum wuerde Eintraege willkuerlich verstecken (Spec N).
_UNKNOWN_ARTIFACTS_SQL: Final = (
    "SELECT a.id::text AS anchor FROM wa_artifact a "
    "WHERE a.workspace_id = $1 AND a.occurred_precision = 'unknown' "
    "AND ($2::uuid[] IS NULL OR a.area_id = ANY($2::uuid[])) "
    "ORDER BY a.created_at, a.id LIMIT $3"
)

_UNKNOWN_NODES_SQL: Final = (
    "SELECT 'node:' || n.id::text AS anchor FROM kb_node n "
    "WHERE n.workspace_id = $1 AND n.occurred_precision = 'unknown' "
    "AND ($2::uuid[] IS NULL OR NOT EXISTS ("
    "SELECT 1 FROM kb_node_source_area s "
    "WHERE s.node_id = n.id AND NOT (s.area_id = ANY($2::uuid[])))) "
    "ORDER BY n.created_at, n.id LIMIT $3"
)

_TABLE_SOURCE_SQL: Final = (
    "SELECT id, area_id, name, schema_json FROM wa_table WHERE workspace_id = $1 AND id = $2"
)


@dataclass(frozen=True, slots=True)
class TimelineBucketRow:
    """Ein (gekapptes) Item einer Datums-Scheibe + die VOLLE Bucket-Zaehlung."""

    bucket: date
    anchor: str
    total: int


@dataclass(frozen=True, slots=True)
class TableTimelineSource:
    """Katalog-Sicht einer Tabellen-Quelle (`table:<id>`) fuer die Timeline."""

    table_id: UUID
    area_id: UUID
    name: str
    occurred_column: str


def _to_bucket_row(row: asyncpg.Record) -> TimelineBucketRow:
    """Row → `TimelineBucketRow`; `date_trunc` liefert UTC-Mitternacht →
    ``.date()`` ist das ISO-Bucket-Label (Tag/Wochen-/Monatsanfang)."""
    bucket: datetime = row["bucket"]
    return TimelineBucketRow(bucket=bucket.date(), anchor=row["anchor"], total=row["total"])


class TimelineRepository(Protocol):
    """Vertrag des Timeline-Datenzugriffs (Service-Sicht)."""

    async def artifact_buckets(
        self,
        fetcher: _Fetcher,
        workspace_id: UUID,
        *,
        window_start: datetime,
        window_end: datetime,
        granularity: str,
        restrict_area_ids: list[UUID] | None,
        item_cap: int,
    ) -> list[TimelineBucketRow]: ...

    async def node_buckets(
        self,
        fetcher: _Fetcher,
        workspace_id: UUID,
        *,
        window_start: datetime,
        window_end: datetime,
        granularity: str,
        restrict_area_ids: list[UUID] | None,
        item_cap: int,
    ) -> list[TimelineBucketRow]: ...

    async def unknown_artifact_anchors(
        self,
        fetcher: _Fetcher,
        workspace_id: UUID,
        *,
        restrict_area_ids: list[UUID] | None,
        cap: int,
    ) -> list[str]: ...

    async def unknown_node_anchors(
        self,
        fetcher: _Fetcher,
        workspace_id: UUID,
        *,
        restrict_area_ids: list[UUID] | None,
        cap: int,
    ) -> list[str]: ...

    async def table_source(
        self, fetcher: _Fetcher, workspace_id: UUID, table_id: UUID
    ) -> TableTimelineSource | None: ...

    async def table_day_counts(
        self,
        store: TableStore,
        workspace_id: UUID,
        area_id: UUID,
        table_name: str,
        occurred_column: str,
        *,
        window_start: datetime,
        window_end: datetime,
    ) -> list[tuple[date, int]]: ...


class PgTimelineRepository:
    """asyncpg- + TableStore-Implementierung von `TimelineRepository`.

    Bewusst ohne Pool/Store im Konstruktor (Muster `PgKbRepository`): Reads
    laufen ueber Pool ODER Connection, der Store kommt vom Service.
    """

    async def artifact_buckets(
        self,
        fetcher: _Fetcher,
        workspace_id: UUID,
        *,
        window_start: datetime,
        window_end: datetime,
        granularity: str,
        restrict_area_ids: list[UUID] | None,
        item_cap: int,
    ) -> list[TimelineBucketRow]:
        """Artifact-Buckets im halboffenen Fenster ``[start, end)`` (Spec N).

        Bucket-Basis ist IMMER `occurred_at` (der fachliche Zeitpunkt), nie
        `created_at` — ein am Dienstag Geschehenes, heute Erfasstes gehoert
        unter Dienstag (Spec-Akzeptanz). Area-Scope IN der WHERE-Klausel.
        """
        rows = await fetcher.fetch(
            _ARTIFACT_BUCKETS_SQL,
            workspace_id,
            window_start,
            window_end,
            restrict_area_ids,
            granularity,
            item_cap,
        )
        return [_to_bucket_row(row) for row in rows]

    async def node_buckets(
        self,
        fetcher: _Fetcher,
        workspace_id: UUID,
        *,
        window_start: datetime,
        window_end: datetime,
        granularity: str,
        restrict_area_ids: list[UUID] | None,
        item_cap: int,
    ) -> list[TimelineBucketRow]:
        """Node-Buckets — Sichtbarkeit wie `kb_repository._visible_sql`."""
        rows = await fetcher.fetch(
            _NODE_BUCKETS_SQL,
            workspace_id,
            window_start,
            window_end,
            restrict_area_ids,
            granularity,
            item_cap,
        )
        return [_to_bucket_row(row) for row in rows]

    async def unknown_artifact_anchors(
        self,
        fetcher: _Fetcher,
        workspace_id: UUID,
        *,
        restrict_area_ids: list[UUID] | None,
        cap: int,
    ) -> list[str]:
        """Anker ALLER unknown-Artifacts im Scope — fensterlos (s. Modul-Kopf)."""
        rows = await fetcher.fetch(_UNKNOWN_ARTIFACTS_SQL, workspace_id, restrict_area_ids, cap)
        return [row["anchor"] for row in rows]

    async def unknown_node_anchors(
        self,
        fetcher: _Fetcher,
        workspace_id: UUID,
        *,
        restrict_area_ids: list[UUID] | None,
        cap: int,
    ) -> list[str]:
        """Anker ALLER unknown-Nodes im Sichtbarkeits-Scope — fensterlos."""
        rows = await fetcher.fetch(_UNKNOWN_NODES_SQL, workspace_id, restrict_area_ids, cap)
        return [row["anchor"] for row in rows]

    async def table_source(
        self, fetcher: _Fetcher, workspace_id: UUID, table_id: UUID
    ) -> TableTimelineSource | None:
        """Katalog-Lookup einer `table:<id>`-Quelle; `None` = unbekannt.

        Die occurred-Spalte ist die ERSTE timestamp|date-Spalte des Schemas
        (Plan WP15); `TableSchema` garantiert eine `occurred_at`-Spalte
        dieser Typen (0078) — der Fallback ist reine Defensive.
        """
        row = await fetcher.fetchrow(_TABLE_SOURCE_SQL, workspace_id, table_id)
        if row is None:
            return None
        schema = TableSchema.model_validate(row["schema_json"])
        occurred_column = next(
            (
                column.name
                for column in schema.columns
                if column.type in (TableColumnType.timestamp, TableColumnType.date)
            ),
            "occurred_at",
        )
        return TableTimelineSource(
            table_id=row["id"],
            area_id=row["area_id"],
            name=row["name"],
            occurred_column=occurred_column,
        )

    async def table_day_counts(
        self,
        store: TableStore,
        workspace_id: UUID,
        area_id: UUID,
        table_name: str,
        occurred_column: str,
        *,
        window_start: datetime,
        window_end: datetime,
    ) -> list[tuple[date, int]]:
        """Tages-Aggregat einer Tabellen-Quelle via `run_readonly_query`.

        NUR ``date(col), count(*)`` — nie Rohzeilen (Spec K/N). Identifier
        laufen durch die Allowlist (`validate_column_name`) + Quoting; die
        Datums-Literale sind serverseitig aus validierten datetimes gebaut
        (``date().isoformat()``), nie User-Input — `run_readonly_query` kennt
        keine Bind-Parameter. Fenster-Raender sind TAG-granular (SQLite
        aggregiert auf Tage; Woche/Monat bucketet der Service app-seitig).
        Fehlende Area-Datei (z. B. Volume-Verlust) → leeres Ergebnis.
        """
        quoted_table = quote_identifier(table_name)
        quoted_column = quote_identifier(validate_column_name(occurred_column))
        start = window_start.date().isoformat()
        end = window_end.date().isoformat()
        sql = (
            f"SELECT date({quoted_column}) AS d, count(*) AS n FROM {quoted_table} "
            f"WHERE {quoted_column} IS NOT NULL "
            f"AND date({quoted_column}) >= '{start}' AND date({quoted_column}) <= '{end}' "
            "GROUP BY d ORDER BY d"
        )
        try:
            result = await store.run_readonly_query(
                workspace_id, area_id, sql, limit=_TABLE_DAY_LIMIT
            )
        except AreaStoreMissingError:
            return []
        counts: list[tuple[date, int]] = []
        for row in result.rows:
            raw_day, raw_count = row[0], row[1]
            if not isinstance(raw_day, str) or not isinstance(raw_count, int):
                continue  # defensiv: unparsebare Zelle zaehlt nicht
            try:
                day = date.fromisoformat(raw_day)
            except ValueError:
                continue
            counts.append((day, raw_count))
        return counts
