"""Geschaeftslogik fuer den Tabellen-Store (ADR-0049, WP13 — Spec K).

Aufteilung der Wahrheit (Entscheidung 3): der KATALOG (`wa_table`, Postgres)
traegt Schema + Namen, die DATEN liegen in der Area-SQLite (`tablestore`).
`create` haelt beide Seiten konsistent: Katalog-Insert und SQLite-DDL laufen
in EINER Postgres-Transaktion — die DDL wird VOR dem Commit ausgefuehrt,
scheitert sie, rollt die Katalog-Zeile mit zurueck (kein Katalog-Eintrag ohne
Tabelle). Namens-Kollision → 409 `concurrent_conflict` — derselbe Reason, den
`work_areas.create_shared` fuer die Area-Namens-Kollision nutzt (geschlossene
Taxonomie; die aeltere Slug-Kollision in `resource_service` wirft noch rohe
HTTPException, fuer neuen Code gilt `ApiGateError`).

Gates (H1-Muster `wa_artifacts`): Schreibpfade IMMER zuerst
`require_role(editor)` — die Rolle ist auch bei agent-gebundenen Tokens am
Token gepinnt —, dann `require_capability(workarea_write)` +
`require_write_rate`; dazu `ensure_area_access(write)` auf der Area der
Tabelle. Reads (query/describe/list) brauchen nur Area-READ; eine nicht
lesbare Tabelle ist von einer nicht existierenden nicht unterscheidbar —
der Service liefert `None`, der Router antwortet 404 (kein Existenz-Leak,
Muster `services/kb.py`).

Read-only ist ENGINE-Garantie (Authorizer + `PRAGMA query_only`, ADR-0049):
`ReadOnlyViolation` wird hier auf 403 `query_not_readonly` gemappt; ein
SQL-SYNTAXfehler ist dagegen `TableQueryInvalid` (Router → 400) — die beiden
Faelle werden nie vermischt. Der Import ist idempotent (Spec K):
`row_hash` ueber `dedupe_columns` (Fallback: alle Spalten) + `INSERT OR
IGNORE` macht den Doppel-Import zum No-op (`{inserted, skipped}`).
`source_name`/`new_rules` aus `RowsInsert` werden hier bewusst NUR
durchgereicht/ignoriert — Konventions- und Regel-Logik (M2/L) ist WP17;
`source_artifact_id` landet als `_source_artifact` in jeder Row (Provenance).

ARC-3: kein SQL, keine HTTPException — nur `ApiGateError`, Domain-Exceptions
(`TableRowsInvalid`/`TableQueryInvalid`, uebersetzt der Router), Repos,
`core/workarea_scope` und der TableStore (SQLite NUR ueber ihn).
"""

from __future__ import annotations

import csv
import io
import sqlite3
from datetime import date, datetime
from uuid import UUID

import asyncpg
from fastapi import status

from who2be_api.core.errors import ApiGateError
from who2be_api.core.security import (
    WorkspaceContext,
    require_capability,
    require_role,
    require_write_rate,
)
from who2be_api.core.workarea_scope import ensure_area_access, readable_area_ids
from who2be_api.repositories.wa_table_repository import WaTableRepository
from who2be_api.tablestore import (
    AreaStoreMissingError,
    ColumnSpec,
    InsertResult,
    ReadOnlyViolation,
    TableStore,
    row_hash,
)
from who2be_models import (
    AgentCapability,
    QueryFormat,
    QueryResult,
    RowsInsert,
    TableDescription,
    TableQuery,
    TableSchema,
    WaTableCreate,
    WaTableRead,
    WorkAreaGrantLevel,
    WorkspaceRole,
)
from who2be_models.tables import TableColumnType

# JSON-Zeilenwerte, die SQLite parametrisiert tragen kann — Listen/Objekte in
# Zellen sind kein Tabellen-Datum (ADR-0049: kein json in Spalten).
_SCALAR_TYPES = (str, int, float, bool)


class TableRowsInvalid(ValueError):
    """Zeilen-Import passt nicht zum Katalog-Schema — Router antwortet 422.

    Domain-Exception statt HTTPException (ARC-3/DECISIONS 2026-07-20):
    unbekannte Spalten, fehlendes/unparsebares `occurred_at`, NOT-NULL-Luecke
    oder Nicht-Skalar-Werte.
    """


class TableQueryInvalid(ValueError):
    """SQL-Fehler im Agenten-SQL (Syntax u. ae.) — Router antwortet 400.

    Bewusst getrennt von `ReadOnlyViolation` (→ 403 `query_not_readonly`):
    ein Tippfehler ist kein Schreibversuch.
    """


def _name_conflict(name: str) -> ApiGateError:
    """409 fuer eine Namens-Kollision in der Area (UNIQUE (area_id, name)).

    Reason `concurrent_conflict` uebernimmt die bestehende Taxonomie-Wahl von
    `work_areas.create_shared` (Area-Name bereits vergeben) — ein neuer Reason
    fuer denselben Sachverhalt waere Vokabular ohne Not.
    """
    return ApiGateError(
        status=status.HTTP_409_CONFLICT,
        reason="concurrent_conflict",
        actionable_by="agent",
        detail=(
            f"Eine Tabelle mit dem Namen '{name}' existiert bereits in dieser "
            "Area. Anderen Namen waehlen oder die bestehende Tabelle nutzen "
            "(GET /work-areas/{area_id}/tables)."
        ),
    )


def _query_not_readonly(detail: str) -> ApiGateError:
    return ApiGateError(
        status=status.HTTP_403_FORBIDDEN,
        reason="query_not_readonly",
        actionable_by="agent",
        detail=(
            f"Die Query wurde von der Engine verweigert ({detail}). Nur lesende "
            "Statements (SELECT) sind erlaubt — DDL/DML/ATTACH/PRAGMA nie."
        ),
    )


def _validate_rows(schema: TableSchema, rows: list[dict[str, object]]) -> None:
    """Prueft jede Zeile gegen das Katalog-Schema (VOR jedem SQLite-Write).

    Unbekannte Spalten, Nicht-Skalare, NOT-NULL-Luecken und fehlendes oder
    unparsebares `occurred_at` (Pflicht je Row, Anforderung N) →
    `TableRowsInvalid`. Die Vorab-Pruefung ist noetig, weil `INSERT OR
    IGNORE` Constraint-Verletzungen sonst still als "skipped" zaehlen wuerde
    — ein kaputter Import saehe wie ein Doppel-Import aus.
    """
    known = {column.name: column for column in schema.columns}
    occurred_type = known["occurred_at"].type
    for index, row in enumerate(rows):
        unknown = sorted(set(row) - set(known))
        if unknown:
            raise TableRowsInvalid(
                f"Zeile {index}: unbekannte Spalten {', '.join(unknown)} — das Schema "
                f"kennt nur: {', '.join(known)}."
            )
        for name, value in row.items():
            if value is not None and not isinstance(value, _SCALAR_TYPES):
                raise TableRowsInvalid(
                    f"Zeile {index}: Spalte '{name}' traegt {type(value).__name__} — "
                    "erlaubt sind nur Skalare (string/number/boolean/null)."
                )
        for column in schema.columns:
            if not column.nullable and row.get(column.name) is None:
                raise TableRowsInvalid(
                    f"Zeile {index}: Spalte '{column.name}' ist NOT NULL und fehlt."
                )
        _validate_occurred_at(index, row.get("occurred_at"), occurred_type)


def _validate_occurred_at(index: int, value: object, column_type: TableColumnType) -> None:
    """`occurred_at` je Row: vorhanden und ISO-8601-parsebar (Spec K/N)."""
    if value is None:
        raise TableRowsInvalid(
            f"Zeile {index}: 'occurred_at' fehlt — jede Zeile traegt ihren "
            "fachlichen Zeitpunkt (Pflichtspalte, Anforderung N)."
        )
    if not isinstance(value, str):
        raise TableRowsInvalid(
            f"Zeile {index}: 'occurred_at' muss ein ISO-8601-String sein, "
            f"nicht {type(value).__name__}."
        )
    try:
        if column_type is TableColumnType.date:
            date.fromisoformat(value)
        else:
            datetime.fromisoformat(value)
    except ValueError as exc:
        raise TableRowsInvalid(
            f"Zeile {index}: 'occurred_at' ist nicht parsebar ({value!r}) — "
            f"erwartet ISO-8601 als {column_type.value}."
        ) from exc


def _render_markdown(columns: list[str], rows: list[list[object]]) -> str:
    """Ergebnis als Markdown-Tabelle (agentengerecht, Entscheidung 7)."""

    def cell(value: object) -> str:
        return "" if value is None else str(value).replace("|", "\\|")

    lines = [
        "| " + " | ".join(cell(column) for column in columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    lines.extend("| " + " | ".join(cell(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


def _render_csv(columns: list[str], rows: list[list[object]]) -> str:
    """Ergebnis als CSV (stdlib `csv`, QUOTE_MINIMAL); None → leere Zelle."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow(["" if value is None else value for value in row])
    return buffer.getvalue()


def _column_specs(schema: TableSchema) -> list[ColumnSpec]:
    """Katalog-Schema → Engine-Spalten (WP12 ist bewusst modell-unabhaengig)."""
    return [
        ColumnSpec(name=column.name, type=column.type.value, nullable=column.nullable)
        for column in schema.columns
    ]


class WaTableService:
    """Tabellen-Katalog + SQLite-Store hinter den Workspace-Gates."""

    def __init__(
        self, pool: asyncpg.Pool, table_repo: WaTableRepository, store: TableStore
    ) -> None:
        self._pool = pool
        self._tables = table_repo
        self._store = store

    # ------------------------------------------------------------------ Gates

    def _require_write(self, ctx: WorkspaceContext) -> None:
        """Schreib-Gate (H1, Muster `wa_artifacts`): IMMER zuerst
        `require_role(editor)`, dann Capability + Rate (fuer Menschen No-Ops)."""
        require_role(ctx, WorkspaceRole.editor)
        require_capability(ctx, AgentCapability.workarea_write)
        require_write_rate(ctx)

    async def _visible_table(self, ctx: WorkspaceContext, table_id: UUID) -> WaTableRead | None:
        """Katalog-Zeile im Lese-Scope des Aufrufers; `None` → Router 404.

        Unbekannte Tabelle und Tabelle in nicht lesbarer Area sind bewusst
        ununterscheidbar (kein Existenz-Leak, Muster `services/kb.py`).
        """
        table = await self._tables.get(self._pool, ctx.workspace_id, table_id)
        if table is None:
            return None
        restrict = await readable_area_ids(self._pool, ctx)
        if restrict is not None and table.area_id not in restrict:
            return None
        return table

    # ------------------------------------------------------------------ Writes

    async def create(
        self, ctx: WorkspaceContext, area_id: UUID, data: WaTableCreate
    ) -> WaTableRead:
        """Legt Katalog-Zeile UND SQLite-Tabelle an — atomar (s. Modul-Kopf).

        Reihenfolge: erst der Katalog-Insert (offene Transaktion), dann die
        DDL; jede Exception vor dem Commit — DDL-Fehler ODER Namens-409 —
        rollt die Katalog-Zeile zurueck.
        """
        self._require_write(ctx)
        await ensure_area_access(self._pool, ctx, area_id, WorkAreaGrantLevel.write)
        async with self._pool.acquire() as conn, conn.transaction():
            created = await self._tables.insert(
                conn, ctx.workspace_id, area_id, name=data.name, schema=data.schema_
            )
            if created is None:
                raise _name_conflict(data.name)
            try:
                await self._store.create_table(
                    ctx.workspace_id, area_id, data.name, _column_specs(data.schema_)
                )
            except sqlite3.OperationalError as exc:
                if "already exists" in str(exc):
                    # SQLite-Tabelle ohne Katalog-Zeile (WP12-Hinweis) — als
                    # Konflikt behandeln, die Katalog-Zeile rollt zurueck.
                    raise _name_conflict(data.name) from exc
                raise
        return created

    async def insert_rows(
        self, ctx: WorkspaceContext, table_id: UUID, data: RowsInsert
    ) -> InsertResult | None:
        """Idempotenter Zeilen-Import (Spec K); `None` → Router 404.

        `source_name`/`new_rules` werden ignoriert (WP17, s. Modul-Kopf);
        `source_artifact_id` wird als `_source_artifact` in jede Row
        durchgereicht (M2-Provenance).
        """
        table = await self._visible_table(ctx, table_id)
        if table is None:
            return None
        self._require_write(ctx)
        await ensure_area_access(self._pool, ctx, table.area_id, WorkAreaGrantLevel.write)

        schema = table.schema_
        _validate_rows(schema, data.rows)
        column_names = [column.name for column in schema.columns]
        dedupe_columns = schema.dedupe_columns or column_names
        source_artifact = (
            str(data.source_artifact_id) if data.source_artifact_id is not None else None
        )
        try:
            return await self._store.insert_rows(
                ctx.workspace_id,
                table.area_id,
                table.name,
                column_names,
                data.rows,
                lambda row: row_hash(row, dedupe_columns),
                source_artifact=source_artifact,
            )
        except sqlite3.IntegrityError as exc:
            # Backstop hinter der Vorab-Validierung (z. B. Typ-Kollision) —
            # Aufruferfehler, kein Serverzustand.
            raise TableRowsInvalid(f"Import verletzt das Tabellen-Schema: {exc}") from exc

    # ------------------------------------------------------------------- Reads

    async def query(
        self, ctx: WorkspaceContext, table_id: UUID, data: TableQuery
    ) -> QueryResult | None:
        """Freies Agenten-SQL, read-only als Engine-Garantie; `None` → 404.

        Area-READ genuegt (der Authorizer erzwingt read-only, ADR-0049).
        Verweigerte Statements → 403 `query_not_readonly`; SQL-Fehler
        (Syntax u. ae.) → `TableQueryInvalid` (Router → 400). Das Zeilen-Cap
        kommt aus `data.limit`; `truncated` zeigt den Schnitt an.
        """
        table = await self._visible_table(ctx, table_id)
        if table is None:
            return None
        try:
            result = await self._store.run_readonly_query(
                ctx.workspace_id, table.area_id, data.sql, limit=data.limit
            )
        except ReadOnlyViolation as exc:
            raise _query_not_readonly(str(exc)) from exc
        except AreaStoreMissingError:
            # Katalog-Zeile ohne Area-Datei (z. B. Volume-Verlust) — nach
            # aussen nicht von einer unbekannten Tabelle unterscheidbar.
            return None
        except sqlite3.DatabaseError as exc:
            raise TableQueryInvalid(str(exc)) from exc
        if data.format is QueryFormat.markdown:
            rendered: str | None = _render_markdown(result.columns, result.rows)
        elif data.format is QueryFormat.csv:
            rendered = _render_csv(result.columns, result.rows)
        else:
            rendered = None
        return QueryResult(
            columns=result.columns,
            rows=result.rows if data.format is QueryFormat.json else None,
            rendered=rendered,
            row_count=len(result.rows),
            truncated=result.truncated,
        )

    async def describe(self, ctx: WorkspaceContext, table_id: UUID) -> TableDescription | None:
        """Schema + Zeilenzahl + Wertebereiche + Area-Konventionen; `None` → 404.

        Genug Kontext, um Queries ohne Rohdaten-Dump zu formulieren (K/M);
        die Spalten-Statistik kommt aus `TableStore.describe` (nie Rohzeilen).
        """
        table = await self._visible_table(ctx, table_id)
        if table is None:
            return None
        try:
            described = await self._store.describe(
                ctx.workspace_id, table.area_id, table.name, _column_specs(table.schema_)
            )
        except AreaStoreMissingError:
            return None
        column_stats: dict[str, dict[str, object]] = {}
        for stats in described.columns:
            if stats.distinct_count is not None:
                column_stats[stats.name] = {
                    "type": str(stats.type),
                    "distinct_count": stats.distinct_count,
                    "distinct_capped": stats.distinct_capped,
                }
            else:
                column_stats[stats.name] = {
                    "type": str(stats.type),
                    "min": stats.min_value,
                    "max": stats.max_value,
                }
        conventions = await self._tables.list_conventions(
            self._pool, ctx.workspace_id, table.area_id
        )
        return TableDescription(
            schema=table.schema_,
            row_count=described.row_count,
            column_stats=column_stats,
            conventions=conventions,
        )

    async def list_for_area(self, ctx: WorkspaceContext, area_id: UUID) -> list[WaTableRead]:
        """Tabellen einer Area (Katalog); fehlender Read-Grant → 404."""
        await ensure_area_access(self._pool, ctx, area_id, WorkAreaGrantLevel.read)
        return await self._tables.list_for_area(self._pool, ctx.workspace_id, area_id)
