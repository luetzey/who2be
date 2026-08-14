"""SQLite-Engine des Tabellen-Stores — eine Datei pro WorkArea (ADR-0049).

Die Datei IST die Isolationsgrenze (Entscheidung 1): eine Query kann
physisch nur die eigene Area sehen, Cross-Area-SQL ist konstruktionsbedingt
unmoeglich. Read-only ist eine ENGINE-Garantie, keine App-Konvention
(Entscheidung 2): der Query-Pfad laeuft auf einer eigenen Connection mit
URI ``mode=ro`` + ``PRAGMA query_only=ON`` + ``set_authorizer`` (Allowlist
SELECT/READ/FUNCTION/RECURSIVE, alles andere Deny — ATTACH und PRAGMA
ausdruecklich). DROP/UPDATE/INSERT/ATTACH/PRAGMA scheitern damit in der
Engine selbst; der Store uebersetzt das in `ReadOnlyViolation`, die der
Service (WP13) auf 403 ``query_not_readonly`` mappt.

Nebenlaeufigkeit: alle SQLite-Aufrufe sind sync (stdlib ``sqlite3``) und
werden via ``asyncio.to_thread`` von der Event-Loop ferngehalten. Pro
Area-Datei serialisiert ein ``asyncio.Lock`` (Registry-Dict hinter einem
globalen Lock) die WRITE-Pfade; Reads brauchen kein Lock — WAL erlaubt
parallele Leser neben genau einem Writer.

Pfad-Layout ``{base_dir}/{workspace_id}/{area_id}.sqlite``: beide IDs sind
als `UUID` typisiert und werden per ``str(uuid)`` in den Pfad gebaut —
Pfad-Injection ist damit strukturell ausgeschlossen (eine UUID enthaelt
weder ``/`` noch ``..``).

Dieses Package ist in Welle 4 bewusst modell-unabhaengig (WP12): Schemata
kommen als `ColumnSpec` (schema.py); WP13 verdrahtet
``who2be_models.tables.TableSchema`` darauf.
"""

from __future__ import annotations

import asyncio
import contextlib
import sqlite3
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Final
from urllib.parse import quote
from uuid import UUID

from who2be_api.tablestore.schema import (
    ColumnSpec,
    ColumnType,
    build_create_table_sql,
    quote_identifier,
    validate_column_name,
)

# Deckel fuer den Distinct-Count von Textspalten in `describe` — der Zweck
# ist agentengerechte Orientierung ("wie viele Auspraegungen"), nicht ein
# vollstaendiges Kardinalitaets-Profil ueber beliebig grosse Tabellen.
DESCRIBE_DISTINCT_CAP: Final = 1000

# Authorizer-Allowlist (ADR-0049, Entscheidung 2): SELECT + Spalten-READ +
# SQL-Funktionen (sum/count/...) + RECURSIVE (WITH RECURSIVE-CTEs, konkret
# verifiziert: ohne SQLITE_RECURSIVE scheitern rekursive CTEs). JEDER andere
# Opcode — inklusive SQLITE_ATTACH und SQLITE_PRAGMA, die unten zur
# Dokumentation explizit stehen — wird verweigert.
_ALLOWED_ACTIONS: Final[frozenset[int]] = frozenset(
    {
        sqlite3.SQLITE_SELECT,
        sqlite3.SQLITE_READ,
        sqlite3.SQLITE_FUNCTION,
        sqlite3.SQLITE_RECURSIVE,
    }
)

_EXPLICIT_DENY_ACTIONS: Final[frozenset[int]] = frozenset(
    {
        # ATTACH wuerde eine ZWEITE Datei in die Query holen — das waere der
        # eine Weg, die Datei-als-Isolationsgrenze zu unterlaufen.
        sqlite3.SQLITE_ATTACH,
        # PRAGMA im User-SQL: teils schreibend (journal_mode), teils
        # Metadaten-Leak (database_list) — pauschal verweigert.
        sqlite3.SQLITE_PRAGMA,
    }
)


class ReadOnlyViolation(Exception):
    """User-SQL hat versucht, die Read-only-Garantie zu verletzen (ADR-0049).

    Geworfen, wenn SQLite ein Statement wegen Authorizer-Deny
    (``SQLITE_AUTH``) oder ``query_only``/``mode=ro`` (``SQLITE_READONLY``)
    ablehnt. Der Service (WP13) mappt auf 403 ``query_not_readonly``.
    """


class AreaStoreMissingError(LookupError):
    """Lese-Zugriff auf eine Area ohne SQLite-Datei.

    Domain-Exception statt roher ``sqlite3.OperationalError`` ("unable to
    open database file"), damit der Service sie sauber auf 404 mappen kann.
    Schreibpfade legen die Datei dagegen bei Bedarf an (``mkdir`` + connect).
    """

    def __init__(self, path: Path) -> None:
        super().__init__(f"Kein Tabellen-Store unter {path}")
        self.path = path


@dataclass(frozen=True, slots=True)
class QueryResult:
    """Ergebnis von `run_readonly_query`: Spalten + Zeilen (Python-Primitive)."""

    columns: list[str]
    rows: list[list[object]]
    truncated: bool


@dataclass(frozen=True, slots=True)
class InsertResult:
    """Bilanz eines idempotenten Imports (``INSERT OR IGNORE``, ADR-0049)."""

    inserted: int
    skipped: int


@dataclass(frozen=True, slots=True)
class ColumnStats:
    """Spalten-Statistik aus `describe` — Wertebereiche, NIE Rohzeilen.

    Numerik/Datum: ``min_value``/``max_value``. Text: gedeckelter
    ``distinct_count`` (+ ``distinct_capped``, wenn der Deckel griff).
    """

    name: str
    type: ColumnType | str
    min_value: object = None
    max_value: object = None
    distinct_count: int | None = None
    distinct_capped: bool = False


@dataclass(frozen=True, slots=True)
class TableDescription:
    """`describe`-Ergebnis: Zeilenzahl + Spalten-Statistiken, keine Zeilen."""

    row_count: int
    columns: list[ColumnStats] = field(default_factory=list)


def _readonly_authorizer(
    action: int,
    arg1: str | None,
    arg2: str | None,
    db_name: str | None,
    source: str | None,
) -> int:
    """SQLite-Authorizer des Query-Pfads: Allowlist, sonst Deny (ADR-0049)."""
    if action in _EXPLICIT_DENY_ACTIONS:
        return sqlite3.SQLITE_DENY
    if action in _ALLOWED_ACTIONS:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def _is_readonly_rejection(exc: sqlite3.DatabaseError) -> bool:
    """Authorizer-Deny/Write-Versuch — im Gegensatz zu z. B. Syntaxfehlern."""
    errorname = str(getattr(exc, "sqlite_errorname", ""))
    return (
        errorname.startswith("SQLITE_AUTH")
        or errorname.startswith("SQLITE_READONLY")
        or "not authorized" in str(exc)
    )


def _require_uuid(name: str, value: UUID) -> UUID:
    """Pfad-Injection-Schranke: nur echte UUID-Objekte duerfen in den Pfad."""
    if not isinstance(value, UUID):
        raise TypeError(f"{name} muss eine uuid.UUID sein, nicht {type(value).__name__}.")
    return value


def _to_sql_value(value: object) -> object:
    """Kanonisiert Python-Werte auf SQLite-Primitive (Typ-Mapping schema.py).

    bool → INTEGER 0/1, date/datetime → ISO-8601-TEXT, Decimal → str (die
    NUMERIC-Affinitaet wandelt verlustfrei zurueck). Bewusst OHNE die
    deprecateten sqlite3-Default-Adapter (ab Python 3.12 entfernt).
    """
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


class TableStore:
    """SQLite-Store mit einer Datei pro WorkArea (ADR-0049, Entscheidung 1).

    Async-Fassade ueber sync ``sqlite3``: jeder oeffentliche Aufruf laeuft in
    ``asyncio.to_thread``; Writes serialisiert ein ``asyncio.Lock`` pro
    Area-Datei. Die Instanz gehoert zu GENAU EINER Event-Loop (die Locks
    binden sich an die Loop des ersten Awaits) — im API-Prozess ist das die
    Uvicorn-Loop.
    """

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir
        self._area_locks: dict[Path, asyncio.Lock] = {}
        self._registry_lock = asyncio.Lock()

    # --- Pfade + Locks -------------------------------------------------------

    def db_path(self, workspace_id: UUID, area_id: UUID) -> Path:
        """`{base_dir}/{workspace_id}/{area_id}.sqlite` — nur aus UUIDs gebaut."""
        _require_uuid("workspace_id", workspace_id)
        _require_uuid("area_id", area_id)
        return self._base_dir / str(workspace_id) / f"{area_id}.sqlite"

    async def _lock_for(self, path: Path) -> asyncio.Lock:
        """Write-Lock der Area-Datei; Registry-Zugriff selbst ist gelockt.

        Eintraege werden bewusst nie entfernt (auch nicht bei
        `delete_area_store`): die Anzahl Areas ist klein, und ein
        Registry-Aufraeumen unter laufenden Wartenden koennte kurzzeitig
        ZWEI Locks fuer dieselbe Datei erzeugen.
        """
        async with self._registry_lock:
            lock = self._area_locks.get(path)
            if lock is None:
                lock = asyncio.Lock()
                self._area_locks[path] = lock
            return lock

    # --- Connections ---------------------------------------------------------

    def _connect_rw(self, path: Path) -> sqlite3.Connection:
        """Write-Connection: WAL + foreign_keys + busy_timeout (ADR-0049)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(path))
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    def _connect_ro(self, path: Path) -> sqlite3.Connection:
        """Read-only-Connection des User-Query-Pfads: dreifach gesichert.

        (a) URI ``mode=ro`` — die Datei ist schon auf OS-Ebene nicht
        beschreibbar geoeffnet; (b) ``PRAGMA query_only=ON`` — MUSS vor dem
        Authorizer gesetzt werden, danach waere das PRAGMA selbst verweigert;
        (c) `set_authorizer` mit der Opcode-Allowlist.
        """
        if not path.is_file():
            raise AreaStoreMissingError(path)
        uri = f"file:{quote(path.as_posix(), safe='/')}?mode=ro"
        connection = sqlite3.connect(uri, uri=True)
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("PRAGMA query_only=ON")
        connection.set_authorizer(_readonly_authorizer)
        return connection

    # --- Read-only-Query-Pfad (Agent-SQL) ------------------------------------

    async def run_readonly_query(
        self, workspace_id: UUID, area_id: UUID, sql: str, limit: int
    ) -> QueryResult:
        """Freies Agenten-SQL, read-only als Engine-Garantie (ADR-0049).

        Liefert hoechstens `limit` Zeilen (+ ``truncated``-Flag). Verweigerte
        Statements (DROP/UPDATE/ATTACH/PRAGMA/...) → `ReadOnlyViolation`;
        andere SQL-Fehler (z. B. Syntax) bleiben ``sqlite3``-Exceptions.
        Kein Lock: WAL erlaubt parallele Leser.
        """
        if limit < 1:
            raise ValueError("limit muss >= 1 sein.")
        path = self.db_path(workspace_id, area_id)
        return await asyncio.to_thread(self._run_readonly_query_sync, path, sql, limit)

    def _run_readonly_query_sync(self, path: Path, sql: str, limit: int) -> QueryResult:
        connection = self._connect_ro(path)
        try:
            try:
                cursor = connection.execute(sql)
                fetched = cursor.fetchmany(limit + 1)
            except sqlite3.DatabaseError as exc:
                if _is_readonly_rejection(exc):
                    raise ReadOnlyViolation(str(exc)) from exc
                raise
            description = cursor.description or []
            columns = [str(entry[0]) for entry in description]
            truncated = len(fetched) > limit
            rows = [list(row) for row in fetched[:limit]]
            return QueryResult(columns=columns, rows=rows, truncated=truncated)
        finally:
            connection.close()

    # --- Serverseitige Schreibpfade ------------------------------------------

    async def create_table(
        self, workspace_id: UUID, area_id: UUID, name: str, columns: list[ColumnSpec]
    ) -> None:
        """Legt eine Tabelle aus validierten Spalten an (Allowlist, schema.py).

        Haengt immer `_dedupe_hash` (UNIQUE) + `_source_artifact` an; DDL und
        Index laufen in EINER Transaktion. Existiert die Tabelle bereits,
        propagiert der ``sqlite3.OperationalError`` (Konflikt-Mapping ist
        Sache des Service-Katalogs `wa_table`, WP13).
        """
        statements = build_create_table_sql(name, columns)
        path = self.db_path(workspace_id, area_id)
        lock = await self._lock_for(path)
        async with lock:
            await asyncio.to_thread(self._execute_statements_sync, path, statements)

    def _execute_statements_sync(self, path: Path, statements: Sequence[str]) -> None:
        connection = self._connect_rw(path)
        try:
            with connection:
                for statement in statements:
                    connection.execute(statement)
        finally:
            connection.close()

    async def insert_rows(
        self,
        workspace_id: UUID,
        area_id: UUID,
        table: str,
        columns: Sequence[str],
        rows: Sequence[Mapping[str, object]],
        dedupe_hash_fn: Callable[[Mapping[str, object]], str],
        source_artifact: str | None = None,
    ) -> InsertResult:
        """Idempotenter Import via ``INSERT OR IGNORE`` (ADR-0049, Spec K).

        Werte laufen ausschliesslich parametrisiert (NIE interpoliert);
        Identifier durch die Allowlist. Jede Zeile bekommt
        ``_dedupe_hash = dedupe_hash_fn(row)`` (UNIQUE → Doppel-Import wird
        uebersprungen) und ``_source_artifact`` (Provenance zur Roheingabe).
        Rueckgabe: wie viele Zeilen eingefuegt bzw. uebersprungen wurden.
        """
        quoted_table = quote_identifier(table)
        quoted_columns = [quote_identifier(validate_column_name(column)) for column in columns]
        all_columns = ", ".join([*quoted_columns, '"_dedupe_hash"', '"_source_artifact"'])
        placeholders = ", ".join("?" for _ in range(len(quoted_columns) + 2))
        sql = f"INSERT OR IGNORE INTO {quoted_table} ({all_columns}) VALUES ({placeholders})"
        parameters = [
            [
                *(_to_sql_value(row.get(column)) for column in columns),
                dedupe_hash_fn(row),
                source_artifact,
            ]
            for row in rows
        ]
        path = self.db_path(workspace_id, area_id)
        lock = await self._lock_for(path)
        async with lock:
            return await asyncio.to_thread(self._insert_rows_sync, path, sql, parameters, len(rows))

    def _insert_rows_sync(
        self, path: Path, sql: str, parameters: list[list[object]], total: int
    ) -> InsertResult:
        connection = self._connect_rw(path)
        try:
            changes_before = connection.total_changes
            with connection:
                connection.executemany(sql, parameters)
            inserted = connection.total_changes - changes_before
            return InsertResult(inserted=inserted, skipped=total - inserted)
        finally:
            connection.close()

    async def run_admin_sql(
        self,
        workspace_id: UUID,
        area_id: UUID,
        sql: str,
        parameters: Sequence[object] = (),
    ) -> int:
        """SERVER-ONLY Schreibpfad — NIE mit Agenten-/User-SQL aufrufen.

        Normale rw-Connection OHNE Authorizer (ADR-0049, Entscheidung 2: der
        Server selbst unterliegt dem Authorizer nicht), fuer serverseitige
        Operationen wie die Re-Kategorisierung nach Regel-Update (WP17,
        protokolliert ueber den aufrufenden Service). Werte parametrisiert;
        Rueckgabe: betroffene Zeilen (``rowcount``).
        """
        path = self.db_path(workspace_id, area_id)
        lock = await self._lock_for(path)
        async with lock:
            return await asyncio.to_thread(self._run_admin_sql_sync, path, sql, list(parameters))

    def _run_admin_sql_sync(self, path: Path, sql: str, parameters: list[object]) -> int:
        connection = self._connect_rw(path)
        try:
            with connection:
                cursor = connection.execute(sql, parameters)
            return cursor.rowcount
        finally:
            connection.close()

    # --- Discovery / Betrieb -------------------------------------------------

    async def describe(
        self, workspace_id: UUID, area_id: UUID, table: str, columns: Sequence[ColumnSpec]
    ) -> TableDescription:
        """Zeilenzahl + Wertebereiche pro Spalte — OHNE Rohzeilen (ADR-0049).

        Numerik/Datum/Boolean: min/max. Text: distinct-Count, gedeckelt auf
        `DESCRIBE_DISTINCT_CAP`. Laeuft auf der Read-only-Connection
        (Defense-in-Depth: describe KANN nicht schreiben).
        """
        quoted_table = quote_identifier(table)
        path = self.db_path(workspace_id, area_id)
        return await asyncio.to_thread(self._describe_sync, path, quoted_table, list(columns))

    def _describe_sync(
        self, path: Path, quoted_table: str, columns: list[ColumnSpec]
    ) -> TableDescription:
        connection = self._connect_ro(path)
        try:
            count_row = connection.execute(f"SELECT count(*) FROM {quoted_table}").fetchone()
            row_count = int(count_row[0])
            stats: list[ColumnStats] = []
            for spec in columns:
                quoted_column = quote_identifier(validate_column_name(spec.name))
                if ColumnType(spec.type) is ColumnType.TEXT:
                    inner = (
                        f"SELECT DISTINCT {quoted_column} FROM {quoted_table} "
                        f"LIMIT {DESCRIBE_DISTINCT_CAP + 1}"
                    )
                    distinct_row = connection.execute(f"SELECT count(*) FROM ({inner})").fetchone()
                    distinct = int(distinct_row[0])
                    stats.append(
                        ColumnStats(
                            name=spec.name,
                            type=spec.type,
                            distinct_count=min(distinct, DESCRIBE_DISTINCT_CAP),
                            distinct_capped=distinct > DESCRIBE_DISTINCT_CAP,
                        )
                    )
                else:
                    minmax = connection.execute(
                        f"SELECT min({quoted_column}), max({quoted_column}) FROM {quoted_table}"
                    ).fetchone()
                    stats.append(
                        ColumnStats(
                            name=spec.name,
                            type=spec.type,
                            min_value=minmax[0],
                            max_value=minmax[1],
                        )
                    )
            return TableDescription(row_count=row_count, columns=stats)
        finally:
            connection.close()

    async def delete_area_store(self, workspace_id: UUID, area_id: UUID) -> None:
        """Entfernt die Area-Datei samt WAL/SHM — fuer Purge/GDPR (WP20).

        Idempotent (fehlende Dateien sind ein No-op); das Workspace-
        Verzeichnis wird best-effort mit entfernt, wenn es leer ist.
        """
        path = self.db_path(workspace_id, area_id)
        lock = await self._lock_for(path)
        async with lock:
            await asyncio.to_thread(self._delete_files_sync, path)

    def _delete_files_sync(self, path: Path) -> None:
        for suffix in ("", "-wal", "-shm"):
            Path(f"{path}{suffix}").unlink(missing_ok=True)
        with contextlib.suppress(OSError):
            path.parent.rmdir()

    async def snapshot_to(self, workspace_id: UUID, area_id: UUID, target_path: Path) -> None:
        """Konsistenter Snapshot via ``VACUUM INTO`` (Backup, RUNBOOK, ADR-0049).

        Erzeugt eine kompaktierte, eigenstaendig lesbare Kopie unter
        `target_path` (Elternverzeichnis wird angelegt; SQLite lehnt ein
        bereits existierendes Ziel ab). Laeuft unter dem Area-Write-Lock,
        damit kein Import in den Snapshot hineinschreibt.
        """
        path = self.db_path(workspace_id, area_id)
        lock = await self._lock_for(path)
        async with lock:
            await asyncio.to_thread(self._snapshot_sync, path, target_path)

    def _snapshot_sync(self, path: Path, target_path: Path) -> None:
        if not path.is_file():
            raise AreaStoreMissingError(path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        connection = self._connect_rw(path)
        try:
            connection.execute("VACUUM INTO ?", (str(target_path),))
        finally:
            connection.close()
