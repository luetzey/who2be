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
Kategorisierung + Konventionen (WP17, Spec L/M2 — Logik in
`services/wa_rules.py`): ein `source_name` ohne hinterlegte
`wa_source_convention` der Area ist 422 `convention_missing`, VOR jedem
Write. Tragen Katalog-Schema `category_column` UND `match_column`, laeuft
vor dem SQLite-Import die Regel-Phase (`categorize_rows`, „Regel VOR
Modell") in EINER Postgres-Transaktion: `new_rules` persistieren, dann
matchen — 422 `rule_required` rollt auch die neuen Regeln zurueck, SQLite
sieht erst nach erfolgreicher Regel-Phase Writes (kein Teilzustand).
`source_artifact_id` landet als `_source_artifact` in jeder Row (Provenance).

Zugriffslog (Spec F, WP14): erfolgreiche Agent-Zugriffe werden NACH der
Operation best-effort geloggt (`services/access_log.log_access`, No-op fuer
Menschen): `query`/`describe` als ``(table, read)``, der Zeilen-Import als
``(table, write)`` — `ref_id` ist die Katalog-ID (`wa_table.id`).
`save_query_result` (WP16) loggt hier NUR ``(table, read)`` fuer die Query;
das ``(artifact, write)`` kommt aus dem Artifact-Anlage-Pfad
(`WaArtifactService.create`) — kein Doppel-Log. Die
Sensitivity ist fix ``general``: Tabellen tragen im MVP KEINE eigene
Sensitivity-Stufe (weder Katalog noch SQLite-Datei fuehren das Feld);
sobald sie eine bekommen, snapshottet der Log-Aufruf hier den Server-Wert.

ARC-3: kein SQL, keine HTTPException — nur `ApiGateError`, Domain-Exceptions
(`TableRowsInvalid`/`TableQueryInvalid`, uebersetzt der Router), Repos,
`core/workarea_scope` und der TableStore (SQLite NUR ueber ihn).
"""

from __future__ import annotations

import csv
import io
import logging
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from typing import Final
from uuid import UUID

import asyncpg
from fastapi import status

from who2be_api.core.errors import ApiGateError
from who2be_api.core.security import (
    WorkspaceContext,
    peek_write_rate,
    require_capability,
    require_role,
    require_write_rate,
)
from who2be_api.core.workarea_scope import ensure_area_access, readable_area_ids
from who2be_api.repositories.agent_access_log_repository import AccessOperation
from who2be_api.repositories.wa_rule_repository import WaRuleRepository
from who2be_api.repositories.wa_table_repository import WaTableRepository
from who2be_api.services.access_log import log_access
from who2be_api.services.wa_artifacts import WaArtifactService
from who2be_api.services.wa_rules import categorize_rows, convention_missing
from who2be_api.tablestore import (
    MAX_RESULT_BYTES,
    AreaStoreMissingError,
    ColumnSpec,
    InsertResult,
    ReadOnlyViolation,
    ResultTooLarge,
    TableStore,
    row_hash,
)
from who2be_models import (
    AgentCapability,
    ArtifactCreate,
    ArtifactRead,
    QueryFormat,
    QueryResult,
    RowsInsert,
    SaveQueryResult,
    Sensitivity,
    TableDescription,
    TableQuery,
    TableSchema,
    WaTableCreate,
    WaTableRead,
    WorkAreaGrantLevel,
    WorkspaceRole,
)
from who2be_models.tables import TableColumnType
from who2be_models.workarea import ARTIFACT_CONTENT_MAX_LENGTH

# JSON-Zeilenwerte, die SQLite parametrisiert tragen kann — Listen/Objekte in
# Zellen sind kein Tabellen-Datum (ADR-0049: kein json in Spalten).
logger = logging.getLogger(__name__)

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
    """403 fuer alles, was der Authorizer verweigert hat.

    Zwei Faelle unter einem Reason: Schreib-/Struktur-Statements (DDL/DML/
    ATTACH/PRAGMA) und seit dem Security-Review Phase 2 auch nicht gelistete
    SQL-FUNKTIONEN (H3). Beides ist dieselbe Aussage — „die Engine laesst das
    nicht zu" —, deshalb kein zweiter Reason; der `detail` nennt die
    Funktions-Allowlist, damit ein Agent weiss, wohin er ausweichen kann.
    """
    return ApiGateError(
        status=status.HTTP_403_FORBIDDEN,
        reason="query_not_readonly",
        actionable_by="agent",
        detail=(
            f"Die Query wurde von der Engine verweigert ({detail}). Erlaubt sind "
            "nur lesende Statements (SELECT) — DDL/DML/ATTACH/PRAGMA nie — und "
            "nur SQL-Funktionen aus der Allowlist (Aggregate, Text-/Datums-/"
            "Window-Funktionen); Datei-, Blob- und Erweiterungs-Funktionen "
            "(z. B. randomblob, load_extension, fts3_tokenizer) sind gesperrt."
        ),
    )


def _tablestore_unavailable() -> ApiGateError:
    """503, wenn der Store-Pfad nicht benutzbar ist (Deploy-/Rechte-Problem).

    Der Detail-Text nennt bewusst NUR die Stellschraube, nicht den
    OS-Fehler oder den Pfad — der Aufrufer ist im Zweifel ein Agent, und
    ein Serverpfad ist fuer ihn weder verwertbar noch seine Sache. Die
    echte Ursache steht im Log (`logger.error` an der Fangstelle).

    `actionable_by='human'`: kein Retry hilft. Analog
    `wa_ingest._blobstore_unconfigured` — dieselbe Familie „Infrastruktur
    fehlt", damit ein Betreiber beide Faelle gleich erkennt.
    """
    return ApiGateError(
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
        reason="tablestore_unavailable",
        actionable_by="human",
        detail=(
            "Der Tabellen-Store ist nicht beschreibbar — Tabellen sind auf "
            "dieser Installation derzeit nicht verfuegbar. Betreiber: "
            "`WHO2BE_TABLESTORE_DIR` pruefen (Existenz, Schreibrechte des "
            "Service-Nutzers, gemountetes Volume)."
        ),
    )


@contextmanager
def _store_failures() -> Iterator[None]:
    """Uebersetzt Datei-/Zugriffsfehler des Tabellen-Stores in ein 503.

    Hintergrund: die Store-Pfade legen Verzeichnis und SQLite-Datei bei
    Bedarf selbst an (`tablestore/engine.py::_connect_rw`). Ist das
    Basisverzeichnis nicht beschreibbar — der klassische Fall ist ein
    Named Volume, dessen Mount-Punkt root gehoert, waehrend der Container
    unprivilegiert laeuft —, schlaegt schon das `mkdir` mit
    `PermissionError` fehl. Ohne diese Uebersetzung liefe der nackte
    OSError bis zum 500 durch, und ein Betreiber haette nichts als einen
    Stacktrace.

    Gefangen werden zwei Formen desselben Problems: `OSError` (mkdir,
    Rechte, kein Platz) und die SQLite-Meldung „unable to open database
    file", mit der die Engine dasselbe meldet, wenn sie erst beim
    `connect` scheitert. Jede ANDERE `sqlite3.OperationalError` — allen
    voran „already exists" — laeuft bewusst weiter: das sind fachliche
    Faelle, keine Infrastruktur.
    """
    try:
        yield
    except OSError as exc:
        logger.error("Tabellen-Store nicht benutzbar: %s", exc, exc_info=True)
        raise _tablestore_unavailable() from exc
    except sqlite3.OperationalError as exc:
        if "unable to open database file" not in str(exc):
            raise
        logger.error("Tabellen-Store nicht oeffenbar: %s", exc, exc_info=True)
        raise _tablestore_unavailable() from exc


def _result_too_large() -> ApiGateError:
    """413 fuer ein gerendertes Query-Ergebnis ueber dem Artifact-Content-Cap.

    Reason ist bewusst das bestehende `ingest_too_large` (Muster
    `wa_artifacts._too_many_blocks`): dieselbe Schutzfamilie, geschlossene
    Taxonomie — ein neuer Reason fuer denselben Sachverhalt waere Vokabular
    ohne Not.
    """
    return ApiGateError(
        status=status.HTTP_413_CONTENT_TOO_LARGE,
        reason="ingest_too_large",
        actionable_by="agent",
        detail=(
            "Das gerenderte Query-Ergebnis ueberschreitet das Content-Limit "
            f"von {ARTIFACT_CONTENT_MAX_LENGTH} Zeichen pro Artifact — "
            "`limit` senken oder das Ergebnis per Aggregation verdichten."
        ),
    )


def _query_result_too_large(detail: str) -> ApiGateError:
    """413 fuer ein Query-Ergebnis ueber den Engine-Speichergrenzen (H2).

    Gleiche Reason-Wahl wie `_result_too_large` (`ingest_too_large`,
    geschlossene Taxonomie) — nur die Ursache liegt frueher: die Engine hat
    schon beim Aufsammeln abgebrochen, es wurde nie gerendert.
    """
    return ApiGateError(
        status=status.HTTP_413_CONTENT_TOO_LARGE,
        reason="ingest_too_large",
        actionable_by="agent",
        detail=(
            f"{detail} Die Query muss weniger Daten liefern — `limit` senken, "
            "Spalten einschraenken oder aggregieren (das Budget liegt bei "
            f"{MAX_RESULT_BYTES} Bytes pro Ergebnis)."
        ),
    )


def _single_line(text: str) -> str:
    """Presst Freitext auf EINE Zeile ohne Steuerzeichen (Security-Review M4).

    `title` kommt aus dem Request und landet als ``# {title}`` im
    server-komponierten Markdown. Ohne diese Normalisierung kann ein Titel
    mit ``\\n`` beliebige weitere Bloecke, Fences oder Anker-Marker in das
    Artifact schreiben — der Agent diktierte dann Struktur, die als
    Server-Ausgabe gelesen wird.
    """
    collapsed = "".join(
        " " if character < " " or character == "\x7f" else character for character in text
    )
    return " ".join(collapsed.split()) or "Ergebnis"


def _sql_fence(sql: str) -> str:
    """Waehlt einen Fence, der laenger ist als jede Backtick-Folge im SQL (M4).

    Ein fixes ```` ``` ```` liesse sich mit Backticks IM SQL schliessen — der
    Rest der Query stuende danach als freier Markdown-Text im Artifact.
    """
    longest = 0
    current = 0
    for character in sql:
        current = current + 1 if character == "`" else 0
        longest = max(longest, current)
    return "`" * max(3, longest + 1)


def _compose_result_doc(
    *,
    title: str,
    table_name: str,
    sql: str,
    columns: list[str],
    rows: list[list[object]],
    truncated: bool,
) -> str:
    """Komponiert das doc-Artifact eines eingefrorenen Query-Ergebnisses (WP16).

    Spec §10.6: die Zahlen im Artifact stammen aus dem Result-Set der Engine
    — der SERVER rendert (via `_render_markdown`), nie Modell-Text. Der
    Zeitstempel ist der Ausfuehrungszeitpunkt (UTC); `occurred_at` des
    Artifacts traegt davon getrennt den FACHLICHEN Zeitpunkt aus dem Request.

    Alles, was NICHT aus der Engine kommt (`title`, `sql`), wird vorher
    entschaerft (`_single_line`, `_sql_fence`, `_neutralize_anchor`) — sonst
    waere „der Server rendert" nur nominell wahr (Security-Review M4).
    """
    stamp = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M UTC")
    cut = ", gekuerzt" if truncated else ""
    safe_title = _neutralize_anchor(_single_line(title))
    fence = _sql_fence(sql)
    return (
        f"# {safe_title}\n\n"
        f"Eingefrorenes Query-Ergebnis vom {stamp} "
        f"(Tabelle '{table_name}', {len(rows)} Zeilen{cut}).\n\n"
        f"{fence}sql\n{sql}\n{fence}\n\n"
        f"{_render_markdown(columns, rows)}\n"
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


def _neutralize_anchor(text: str) -> str:
    """Entschaerft ``[#...]``-Anker-Marker in Freitext (Security-Review M4).

    ``[#xxxxxxxx]`` ist die ANKER-Sprache der Artifacts (ADR-0021): der
    Lesepfad rendert damit Block-Adressen. Steht die Sequenz in Zellinhalten
    oder im Titel, faelscht sie Anker, die es nicht gibt. Ein eingefuegtes
    Leerzeichen bricht das Muster, ohne den Text unlesbar zu machen (bewusst
    kein Zero-Width-Zeichen: unsichtbare Fixes sind nicht pruefbar).
    """
    return text.replace("[#", "[ #")


def _markdown_cell(value: object) -> str:
    """Eine Zelle als Markdown-Tabellenzelle — strukturneutral (M4).

    Drei Angriffe, drei Antworten: ``|`` bricht die Spaltenstruktur
    (escaped), ``\\r``/``\\n`` brechen die ZEILE (zu Leerzeichen — sonst
    schreibt eine Zelle beliebige neue Tabellenzeilen oder Bloecke), und
    ``[#`` faelscht Anker (`_neutralize_anchor`). Zellinhalte stammen aus
    importierten Fremddaten und sind damit ebenso untrusted wie Agenten-Text.
    """
    if value is None:
        return ""
    flattened = "".join(" " if character in "\r\n\t" else character for character in str(value))
    return _neutralize_anchor(flattened.replace("|", "\\|"))


def _render_markdown(columns: list[str], rows: list[list[object]]) -> str:
    """Ergebnis als Markdown-Tabelle (agentengerecht, Entscheidung 7)."""
    lines = [
        "| " + " | ".join(_markdown_cell(column) for column in columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    lines.extend("| " + " | ".join(_markdown_cell(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


# Zeichen, die Tabellenkalkulationen als Formel-Start lesen (OWASP CSV
# Injection). Ein importierter Zellwert `=cmd|'/c calc'!A1` wird in Excel/
# Sheets beim Oeffnen des Exports AUSGEFUEHRT — der Export ist damit ein
# Angriffspfad aus fremden Quelldaten in das Geraet des Menschen.
_CSV_FORMULA_PREFIXES: Final = ("=", "+", "-", "@", "\t", "\r")


def _csv_cell(value: object) -> object:
    """Entschaerft Formel-Zellen im CSV-Export (Security-Review L5).

    Nur `str`-Werte werden praefixiert: SQLite liefert Zahlen als int/float,
    und ein numerisches ``-3.2`` ist in jeder Tabellenkalkulation eine ZAHL,
    keine Formel. So bleibt der haeufigste legitime Fall (negative Betraege
    aus NUMERIC-Spalten) unveraendert, waehrend jeder Textwert mit
    Formel-Praefix ein fuehrendes ``'`` bekommt.
    """
    if value is None:
        return ""
    if isinstance(value, str) and value.startswith(_CSV_FORMULA_PREFIXES):
        return f"'{value}"
    return value


def _render_csv(columns: list[str], rows: list[list[object]]) -> str:
    """Ergebnis als CSV (stdlib `csv`, QUOTE_MINIMAL); None → leere Zelle."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    writer.writerow([_csv_cell(column) for column in columns])
    for row in rows:
        writer.writerow([_csv_cell(value) for value in row])
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
        self,
        pool: asyncpg.Pool,
        table_repo: WaTableRepository,
        store: TableStore,
        *,
        artifact_service: WaArtifactService,
        rule_repo: WaRuleRepository,
    ) -> None:
        self._pool = pool
        self._tables = table_repo
        self._store = store
        # Bestehender Artifact-Anlage-Pfad (WP4) fuer `save_query_result` —
        # Gates/Blocks/Chunk-Sync/Zugriffslog liegen dort, nie dupliziert hier.
        self._artifact_service = artifact_service
        # Regel-/Konventions-Zugriff fuer die Import-Gates (WP17, Spec L/M2)
        # UND fuer den Konventions-Teil von `describe` — die Fachlogik selbst
        # lebt in `services/wa_rules.py`. Konventions-Zeilen haben genau einen
        # Mapper (`wa_rule_repository`); die frueher parallele Kopie im
        # Tabellen-Repo hat describe mit 500 beendet (Befund 2026-08-16).
        self._rules = rule_repo

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
                with _store_failures():
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
        """Idempotenter Zeilen-Import (Spec K) mit L-/M2-Gates; `None` → Router 404.

        Spec M2: `source_name` ohne hinterlegte Quell-Konvention der Area →
        422 `convention_missing`, VOR jedem Write. Mit Konvention werden die
        Rows akzeptiert — die INHALTLICHE Anwendung der Konvention ist Sache
        der Agent-Runtime, der Server erzwingt nur ihre Existenz.

        Spec L („Regel VOR Modell", nur wenn das Schema `category_column`
        UND `match_column` traegt): die Regel-Phase (`categorize_rows`)
        laeuft in EINER Postgres-Transaktion VOR dem SQLite-Write — kein
        Lauf aendert eine Kategorie ohne Regeltabellen-Eintrag, und ein 422
        `rule_required` rollt auch frisch persistierte `new_rules` zurueck
        (kein Teilzustand). `source_artifact_id` wird als `_source_artifact`
        in jede Row durchgereicht (M2-Provenance).
        """
        table = await self._visible_table(ctx, table_id)
        if table is None:
            return None
        self._require_write(ctx)
        await ensure_area_access(self._pool, ctx, table.area_id, WorkAreaGrantLevel.write)

        schema = table.schema_
        _validate_rows(schema, data.rows)
        if data.source_name is not None:
            convention = await self._rules.get_convention(
                self._pool, ctx.workspace_id, table.area_id, data.source_name
            )
            if convention is None:
                raise convention_missing(data.source_name)
        if schema.category_column is not None and schema.match_column is not None:
            # Regel-Phase (Spec L) atomar VOR dem SQLite-Write: scheitert sie,
            # ist nichts persistiert — weder Regeln noch Zeilen.
            async with self._pool.acquire() as conn, conn.transaction():
                await categorize_rows(
                    conn,
                    ctx,
                    area_id=table.area_id,
                    schema=schema,
                    rows=data.rows,
                    new_rules=data.new_rules,
                    repo=self._rules,
                )
        column_names = [column.name for column in schema.columns]
        dedupe_columns = schema.dedupe_columns or column_names
        source_artifact = (
            str(data.source_artifact_id) if data.source_artifact_id is not None else None
        )
        try:
            with _store_failures():
                result = await self._store.insert_rows(
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
        await self._log(ctx, table.id, "write")
        return result

    async def save_query_result(
        self, ctx: WorkspaceContext, table_id: UUID, data: SaveQueryResult
    ) -> ArtifactRead | None:
        """Friert Query + Ergebnis als doc-Artifact ein (WP16, M-Ersatz); `None` → 404.

        Entscheidung 7 / Spec §10.6: der SERVER fuehrt das SQL read-only aus
        und rendert die Zahlen ins Artifact — nie Modell-Text. Das Artifact
        entsteht in DERSELBEN Area wie die Tabelle, ueber den BESTEHENDEN
        Anlage-Pfad `WaArtifactService.create` (Blocks/Chunk-Sync/Zugriffslog
        `(artifact, write)` inklusive — kein Doppel-Log hier).

        Gates: Rolle/Capability/Area-WRITE laufen als Fail-fast VOR der Query
        (ein nicht schreibberechtigter Aufrufer fuehrt kein SQL aus); dieselben
        Gates laufen in `WaArtifactService.create` erneut — idempotent und
        bewusst in Kauf genommen. Das Rate-Limit wird hier NICHT-KONSUMIEREND
        geprueft (`peek_write_rate`, Security-Review M3) und erst im
        Artifact-Create verbraucht: ohne den peek fuehrt ein am Limit
        stehender Agent erst das (teure) SQL aus und faellt danach ins 429 —
        Arbeit ohne Gegenwert und ein Umgehungspfad fuer die Drosselung.
        Doppelt gezaehlt wird nichts: peek liest das Fenster nur.

        Fehlerbild wie `query`: `ReadOnlyViolation` → 403 `query_not_readonly`,
        `ResultTooLarge` → 413 `ingest_too_large`, `QueryTimeout` → 408
        (Router), SQL-/Syntaxfehler → `TableQueryInvalid` (Router → 400) — in
        allen Faellen entsteht KEIN Artifact.
        """
        table = await self._visible_table(ctx, table_id)
        if table is None:
            return None
        require_role(ctx, WorkspaceRole.editor)
        require_capability(ctx, AgentCapability.workarea_write)
        peek_write_rate(ctx)
        await ensure_area_access(self._pool, ctx, table.area_id, WorkAreaGrantLevel.write)
        try:
            result = await self._store.run_readonly_query(
                ctx.workspace_id, table.area_id, data.sql, limit=data.limit
            )
        except ReadOnlyViolation as exc:
            raise _query_not_readonly(str(exc)) from exc
        except ResultTooLarge as exc:
            raise _query_result_too_large(str(exc)) from exc
        except AreaStoreMissingError:
            return None
        except sqlite3.DatabaseError as exc:
            raise TableQueryInvalid(str(exc)) from exc
        content = _compose_result_doc(
            title=data.title,
            table_name=table.name,
            sql=data.sql,
            columns=result.columns,
            rows=result.rows,
            truncated=result.truncated,
        )
        if len(content) > ARTIFACT_CONTENT_MAX_LENGTH:
            # Server-komponierter Content — der Cap aus `ArtifactCreate` wuerde
            # sonst als 500 (interne ValidationError) statt als 413 enden.
            raise _result_too_large()
        artifact = await self._artifact_service.create(
            ctx,
            table.area_id,
            ArtifactCreate(
                title=data.title,
                content_md=content,
                occurred_at=data.occurred_at,
                occurred_precision=data.occurred_precision,
            ),
        )
        await self._log(ctx, table.id, "read")
        return artifact

    # ------------------------------------------------------------------- Reads

    async def query(
        self, ctx: WorkspaceContext, table_id: UUID, data: TableQuery
    ) -> QueryResult | None:
        """Freies Agenten-SQL, read-only als Engine-Garantie; `None` → 404.

        Area-READ genuegt (der Authorizer erzwingt read-only, ADR-0049).
        Verweigerte Statements → 403 `query_not_readonly`; zu grosses
        Ergebnis → 413 `ingest_too_large` (H2); ueberschrittenes Zeitbudget →
        `QueryTimeout` (Router → 408, H1); SQL-Fehler (Syntax u. ae.) →
        `TableQueryInvalid` (Router → 400). Das Zeilen-Cap kommt aus
        `data.limit`; `truncated` zeigt den Schnitt an.
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
        except ResultTooLarge as exc:
            raise _query_result_too_large(str(exc)) from exc
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
        await self._log(ctx, table.id, "read")
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
        describe macht pro Spalte einen Full-Scan und unterliegt deshalb
        demselben Zeitbudget wie eine Agenten-Query (`QueryTimeout` → 408).
        """
        table = await self._visible_table(ctx, table_id)
        if table is None:
            return None
        try:
            described = await self._store.describe(
                ctx.workspace_id, table.area_id, table.name, _column_specs(table.schema_)
            )
        except ResultTooLarge as exc:
            raise _query_result_too_large(str(exc)) from exc
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
        conventions = await self._rules.list_conventions(
            self._pool, ctx.workspace_id, table.area_id
        )
        await self._log(ctx, table.id, "read")
        return TableDescription(
            schema=table.schema_,
            row_count=described.row_count,
            column_stats=column_stats,
            conventions=conventions,
        )

    async def list_for_area(self, ctx: WorkspaceContext, area_id: UUID) -> list[WaTableRead]:
        """Tabellen einer Area (Katalog); fehlender Read-Grant → 404.

        Zugriffslog: KEIN Eintrag pro Treffer (Metadaten-Liste, Muster
        `wa_artifacts.list_for_area`) — Daten fliessen erst bei
        `query`/`describe`, und DIE loggen.
        """
        await ensure_area_access(self._pool, ctx, area_id, WorkAreaGrantLevel.read)
        return await self._tables.list_for_area(self._pool, ctx.workspace_id, area_id)

    # ------------------------------------------------------------- Zugriffslog

    async def _log(self, ctx: WorkspaceContext, table_id: UUID, operation: AccessOperation) -> None:
        """Best-effort-Zugriffslog NACH erfolgreicher Operation (Spec F).

        Sensitivity fix ``general`` — Tabellen tragen im MVP keine eigene
        Sensitivity (s. Modul-Kopf); der Wert kommt trotzdem vom SERVER,
        nie vom Client.
        """
        await log_access(
            self._pool,
            ctx,
            ref_kind="table",
            ref_id=str(table_id),
            operation=operation,
            sensitivity=Sensitivity.general,
        )
