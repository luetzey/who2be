"""SQLite-Engine des Tabellen-Stores — eine Datei pro WorkArea (ADR-0049).

Die Datei IST die Isolationsgrenze (Entscheidung 1): eine Query kann
physisch nur die eigene Area sehen, Cross-Area-SQL ist konstruktionsbedingt
unmoeglich. Read-only ist eine ENGINE-Garantie, keine App-Konvention
(Entscheidung 2): der Query-Pfad laeuft auf einer eigenen Connection mit
URI ``mode=ro`` + ``PRAGMA query_only=ON`` + ``set_authorizer`` (Allowlist
SELECT/READ/RECURSIVE + eine NAMENS-Allowlist fuer SQL-Funktionen, alles
andere Deny — ATTACH und PRAGMA ausdruecklich). DROP/UPDATE/INSERT/ATTACH/
PRAGMA scheitern damit in der Engine selbst; der Store uebersetzt das in
`ReadOnlyViolation`, die der Service (WP13) auf 403 ``query_not_readonly``
mappt.

Ressourcen-Grenzen des Query-Pfads (Security-Review Phase 2 — freies
Agenten-SQL ist ein UNTRUSTED Input, auch wenn es nichts schreiben kann):

- **Zeit** (H1): ein `set_progress_handler`-Callback bricht jede Query nach
  `query_timeout_ms` ab (`sqlite3.OperationalError: interrupted` →
  `QueryTimeout`). Ohne ihn blockiert eine ``WITH RECURSIVE``-Endlosschleife
  einen `to_thread`-Worker dauerhaft — ein Query genuegt fuer eine
  Thread-Pool-Erschoepfung.
- **Zellgroesse** (H2a): `SQLITE_LIMIT_LENGTH` deckelt jeden einzelnen
  String/Blob auf `MAX_CELL_BYTES`; `randomblob(200000000)` endet damit als
  ``SQLITE_TOOBIG`` statt als 400-MB-Allokation.
- **Ergebnisgroesse** (H2b): beim Aufsammeln der Zeilen laeuft ein
  Byte-Budget (`MAX_RESULT_BYTES`) mit — viele mittelgrosse Zellen sind
  sonst derselbe Speicher-DoS wie eine grosse.

Beide Groessen-Grenzen enden als `ResultTooLarge` (Service → 413), der
Timeout als `QueryTimeout` (Router → 408).

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
import time
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
    validate_identifier,
)

# Deckel fuer den Distinct-Count von Textspalten in `describe` — der Zweck
# ist agentengerechte Orientierung ("wie viele Auspraegungen"), nicht ein
# vollstaendiges Kardinalitaets-Profil ueber beliebig grosse Tabellen.
DESCRIBE_DISTINCT_CAP: Final = 1000

# Zeitbudget einer einzelnen read-only Query (H1). Default hier, echter Wert
# aus `settings.tablestore_query_timeout_ms` ueber `services/tablestore_provider`
# — das Package bleibt damit konfig-unabhaengig (WP12).
DEFAULT_QUERY_TIMEOUT_MS: Final = 5000

# Aufrufabstand des Progress-Handlers in VM-Schritten. 10_000 ist der
# Kompromiss aus Reaktionszeit (Bruchteil einer Millisekunde pro Fenster) und
# Overhead (ein Python-Callback je 10_000 Opcodes ist im Messrauschen).
_PROGRESS_HANDLER_STEPS: Final = 10_000

# Obergrenze fuer JEDEN einzelnen String/Blob der ro-Connection (H2a,
# `SQLITE_LIMIT_LENGTH`). 1 MB liegt weit ueber jeder legitimen Tabellenzelle
# (Zellen entstehen aus validierten Skalar-Imports), macht aber
# `randomblob`/`printf`-Aufblaeher zu einem sofortigen ``SQLITE_TOOBIG``.
MAX_CELL_BYTES: Final = 1_000_000

# Byte-Budget des GESAMTEN Result-Sets beim Aufsammeln (H2b). Der Zeilen-Cap
# (`limit`) allein schuetzt nicht: 200 Zeilen a 900 KB waeren 180 MB. 2 MB ist
# grosszuegig gegenueber dem Artifact-Content-Cap und trotzdem beschraenkt.
MAX_RESULT_BYTES: Final = 2_000_000

# Authorizer-Allowlist (ADR-0049, Entscheidung 2): SELECT + Spalten-READ +
# RECURSIVE (WITH RECURSIVE-CTEs, konkret verifiziert: ohne SQLITE_RECURSIVE
# scheitern rekursive CTEs). SQLITE_FUNCTION steht bewusst NICHT hier —
# Funktionen laufen ueber die NAMENS-Allowlist `_ALLOWED_FUNCTIONS` (H3).
# JEDER andere Opcode — inklusive SQLITE_ATTACH und SQLITE_PRAGMA, die unten
# zur Dokumentation explizit stehen — wird verweigert.
_ALLOWED_ACTIONS: Final[frozenset[int]] = frozenset(
    {
        sqlite3.SQLITE_SELECT,
        sqlite3.SQLITE_READ,
        sqlite3.SQLITE_RECURSIVE,
    }
)

# Namens-Allowlist der SQL-Funktionen (H3, Security-Review Phase 2). Ein
# pauschales SQLITE_FUNCTION-OK erlaubt JEDE eingebaute Funktion — inklusive
# `fts3_tokenizer`, das rohe C-Pointer liest UND schreibt (verifizierter
# Pointer-Leak/-Write), sowie `randomblob`/`zeroblob` als Speicher-DoS.
# Deshalb: Deny by default, hier steht, was Analytik-SQL wirklich braucht.
#
# Die Namen sind empirisch gegen den Authorizer verifiziert (sqlite 3.45.1,
# `arg2` bei SQLITE_FUNCTION, lowercase). Zwei Beobachtungen daraus:
#   * `cast(x AS t)` ist ein OPCODE, keine Funktion — taucht nie als
#     SQLITE_FUNCTION auf und gehoert deshalb NICHT in diese Liste.
#   * Window-Funktionen (row_number/rank/dense_rank/lag/lead, `count(*) OVER
#     ()`) laufen sehr wohl als SQLITE_FUNCTION und muessen gelistet sein,
#     sonst bricht legitime Analytik.
#
# `printf`/`format` bleiben erlaubt: der einzige bekannte DoS-Vektor
# (`printf('%.900000000f', 1.0)`) ist durch `MAX_CELL_BYTES` entschaerft —
# SQLite liefert dann NULL statt eines 900-MB-Strings (verifiziert). JSON-
# Funktionen fehlen bewusst: Zellen tragen laut ADR-0049 kein JSON, also gibt
# es keinen Bedarf, der die zusaetzliche Parser-Angriffsflaeche rechtfertigt.
_ALLOWED_FUNCTIONS: Final[frozenset[str]] = frozenset(
    {
        # Aggregate
        "avg",
        "count",
        "group_concat",
        "max",
        "min",
        "sum",
        "total",
        # Numerik
        "abs",
        "round",
        # Text
        "instr",
        "length",
        "lower",
        "ltrim",
        "replace",
        "rtrim",
        "substr",
        "trim",
        "upper",
        "format",
        "printf",
        # NULL-/Fallunterscheidung
        "coalesce",
        "iif",
        "ifnull",
        "nullif",
        # Datum/Zeit
        "date",
        "datetime",
        "julianday",
        "strftime",
        "time",
        "unixepoch",
        # Praedikate + Typ-Introspektion
        "glob",
        "like",
        "typeof",
        # Window-Funktionen (s. o. — laufen als SQLITE_FUNCTION)
        "dense_rank",
        "lag",
        "lead",
        "rank",
        "row_number",
        # Diagnose
        "sqlite_version",
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


class QueryTimeout(Exception):
    """User-SQL hat das Zeitbudget des Query-Pfads gerissen (H1).

    Bewusst KEINE `ReadOnlyViolation` und kein Syntaxfehler: ein Timeout sagt
    nichts ueber die Zulaessigkeit der Query aus, nur ueber ihre Kosten. Der
    Router antwortet 408 (s. `routers/wa_tables`), damit der Agent die
    Anfrage verkleinern kann, statt sie fuer verboten oder kaputt zu halten.
    """


class ResultTooLarge(Exception):
    """Zelle oder Result-Set ueberschreiten die Speichergrenzen (H2).

    Zwei Quellen, eine Exception: ``SQLITE_TOOBIG`` aus `MAX_CELL_BYTES`
    (eine einzelne Zelle) und das App-seitige Budget `MAX_RESULT_BYTES`
    (Summe der aufgesammelten Zeilen). Der Service mappt auf 413
    ``ingest_too_large`` — dieselbe Schutzfamilie wie der Append-Cap.
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
    """SQLite-Authorizer des Query-Pfads: Allowlist, sonst Deny (ADR-0049).

    Bei ``SQLITE_FUNCTION`` traegt `arg2` den Funktionsnamen — er entscheidet
    (H3). Ihn zu ignorieren hiesse, JEDE eingebaute Funktion zu erlauben.
    """
    if action in _EXPLICIT_DENY_ACTIONS:
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_FUNCTION:
        name = (arg2 or "").lower()
        return sqlite3.SQLITE_OK if name in _ALLOWED_FUNCTIONS else sqlite3.SQLITE_DENY
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


def _is_interrupt(exc: sqlite3.DatabaseError) -> bool:
    """Abbruch durch den Progress-Handler (H1) — nicht mit Fehlern vermischen."""
    return str(getattr(exc, "sqlite_errorname", "")) == "SQLITE_INTERRUPT"


def _is_too_big(exc: sqlite3.DatabaseError) -> bool:
    """``SQLITE_TOOBIG`` aus `MAX_CELL_BYTES` (H2a) — kein Syntaxfehler."""
    return str(getattr(exc, "sqlite_errorname", "")) == "SQLITE_TOOBIG"


def _translate_query_error(exc: sqlite3.DatabaseError) -> Exception | None:
    """Uebersetzt Engine-Grenzen in Domain-Exceptions; sonst `None`.

    Reihenfolge ist Absicht: Timeout und Groessen-Grenze sind Aussagen ueber
    die KOSTEN der Query, `ReadOnlyViolation` ueber ihre ZULAESSIGKEIT — ein
    Syntaxfehler bleibt die rohe ``sqlite3``-Exception (Service → 400).
    """
    if _is_interrupt(exc):
        return QueryTimeout(
            "Die Query hat das Zeitbudget des Tabellen-Stores ueberschritten und wurde abgebrochen."
        )
    if _is_too_big(exc):
        return ResultTooLarge(f"Eine Zelle des Ergebnisses ueberschreitet {MAX_CELL_BYTES} Bytes.")
    if _is_readonly_rejection(exc):
        return ReadOnlyViolation(str(exc))
    return None


def _value_size(value: object) -> int:
    """Grober Speicherbedarf einer Zelle fuer das Result-Budget (H2b).

    Zeichen statt Bytes fuer `str` (der Unterschied liegt bei UTF-8 unter
    Faktor 4 und das Budget ist eine Schutz-, keine Abrechnungsgroesse);
    Zahlen/Bool/None pauschal, weil ihre Groesse konstant beschraenkt ist.
    """
    if isinstance(value, str):
        return len(value)
    if isinstance(value, bytes | bytearray | memoryview):
        return len(value)
    return 8


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


def _like_parameter(pattern: str) -> str:
    """LIKE-Parameter der Re-Kategorisierung — Substring, case-insensitive.

    Identische Semantik wie das In-Memory-Matching der Regel-Phase
    (`services/wa_rules._matches`): Wildcards werden escaped (``ESCAPE '\\'``
    im SQL), das Pattern laeuft lowercased gegen ``lower(match_column)``.
    """
    escaped = pattern.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


class TableStore:
    """SQLite-Store mit einer Datei pro WorkArea (ADR-0049, Entscheidung 1).

    Async-Fassade ueber sync ``sqlite3``: jeder oeffentliche Aufruf laeuft in
    ``asyncio.to_thread``; Writes serialisiert ein ``asyncio.Lock`` pro
    Area-Datei. Die Instanz gehoert zu GENAU EINER Event-Loop (die Locks
    binden sich an die Loop des ersten Awaits) — im API-Prozess ist das die
    Uvicorn-Loop.
    """

    def __init__(self, base_dir: Path, query_timeout_ms: int = DEFAULT_QUERY_TIMEOUT_MS) -> None:
        self._base_dir = base_dir
        # Zeitbudget je read-only Query (H1); der Provider reicht den
        # konfigurierten Wert (`settings.tablestore_query_timeout_ms`) durch.
        self._query_timeout_ms = query_timeout_ms
        self._area_locks: dict[Path, asyncio.Lock] = {}
        self._registry_lock = asyncio.Lock()

    # --- Pfade + Locks -------------------------------------------------------

    @property
    def base_dir(self) -> Path:
        """Wurzel des Store-Layouts (`WHO2BE_TABLESTORE_DIR`).

        Oeffentlich fuer den Purge-Sweep (`core/purge.py`, WP20): der muss das
        Verzeichnis ABLAUFEN koennen, um Dateien ohne `work_area`-Zeile zu
        finden — die IDs stehen nur im Dateisystem, nicht in Postgres.
        """
        return self._base_dir

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
        """Read-only-Connection des User-Query-Pfads: fuenffach gesichert.

        (a) URI ``mode=ro`` — die Datei ist schon auf OS-Ebene nicht
        beschreibbar geoeffnet; (b) ``PRAGMA query_only=ON`` — MUSS vor dem
        Authorizer gesetzt werden, danach waere das PRAGMA selbst verweigert;
        (c) `set_authorizer` mit Opcode- UND Funktions-Allowlist (H3);
        (d) `SQLITE_LIMIT_LENGTH` als Zell-Obergrenze (H2a);
        (e) `set_progress_handler` als Zeitbudget (H1).

        Die Deadline entsteht HIER, weil die Connection unmittelbar vor der
        Ausfuehrung geoeffnet und danach geschlossen wird — eine Connection
        bedient genau eine Query.
        """
        if not path.is_file():
            raise AreaStoreMissingError(path)
        uri = f"file:{quote(path.as_posix(), safe='/')}?mode=ro"
        connection = sqlite3.connect(uri, uri=True)
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("PRAGMA query_only=ON")
        connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_CELL_BYTES)
        connection.set_authorizer(_readonly_authorizer)
        deadline = time.monotonic() + self._query_timeout_ms / 1000.0

        def _abort_when_over_budget() -> int:
            # Rueckgabe != 0 ⇒ SQLite bricht mit ``SQLITE_INTERRUPT`` ab.
            return 1 if time.monotonic() > deadline else 0

        connection.set_progress_handler(_abort_when_over_budget, _PROGRESS_HANDLER_STEPS)
        return connection

    # --- Read-only-Query-Pfad (Agent-SQL) ------------------------------------

    async def run_readonly_query(
        self, workspace_id: UUID, area_id: UUID, sql: str, limit: int
    ) -> QueryResult:
        """Freies Agenten-SQL, read-only als Engine-Garantie (ADR-0049).

        Liefert hoechstens `limit` Zeilen (+ ``truncated``-Flag). Verweigerte
        Statements (DROP/UPDATE/ATTACH/PRAGMA/nicht gelistete Funktionen) →
        `ReadOnlyViolation`; Zeit- bzw. Groessen-Grenze → `QueryTimeout` bzw.
        `ResultTooLarge`; andere SQL-Fehler (z. B. Syntax) bleiben
        ``sqlite3``-Exceptions. Kein Lock: WAL erlaubt parallele Leser.
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
                fetched = self._fetch_within_budget(cursor, limit)
            except sqlite3.DatabaseError as exc:
                translated = _translate_query_error(exc)
                if translated is not None:
                    raise translated from exc
                raise
            description = cursor.description or []
            columns = [str(entry[0]) for entry in description]
            truncated = len(fetched) > limit
            rows = [list(row) for row in fetched[:limit]]
            return QueryResult(columns=columns, rows=rows, truncated=truncated)
        finally:
            connection.close()

    @staticmethod
    def _fetch_within_budget(cursor: sqlite3.Cursor, limit: int) -> list[tuple[object, ...]]:
        """Sammelt bis `limit`+1 Zeilen unter dem Byte-Budget ein (H2b).

        Zeilenweise statt `fetchmany`, damit das Budget greift, BEVOR der
        gesamte Speicher belegt ist — `fetchmany(limit + 1)` haette die
        Zeilen erst vollstaendig materialisiert und dann geprueft.
        """
        collected: list[tuple[object, ...]] = []
        budget = 0
        for row in cursor:
            budget += sum(_value_size(value) for value in row)
            if budget > MAX_RESULT_BYTES:
                raise ResultTooLarge(
                    f"Das Query-Ergebnis ueberschreitet das Speicher-Budget von "
                    f"{MAX_RESULT_BYTES} Bytes."
                )
            collected.append(row)
            if len(collected) > limit:
                break
        return collected

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

    async def drop_table(self, workspace_id: UUID, area_id: UUID, name: str) -> None:
        """Loescht eine Tabelle samt ihrer Indizes (`DROP TABLE`).

        Gegenstueck zu `create_table` und derselbe Weg: validierter
        Identifier, Lock der Area-Datei, DDL im Thread. SQLite raeumt die
        Indizes der Tabelle (u. a. den Dedupe-Index) mit ab — es bleibt nichts
        liegen, das eine gleichnamige Neuanlage blockieren wuerde.

        `IF EXISTS` bewusst: der Service loescht Katalog-Zeile UND Tabelle in
        einer Postgres-Transaktion. Fehlt die SQLite-Seite (Area-Datei nie
        angelegt, Volume-Verlust), soll der Katalog trotzdem aufgeraeumt
        werden koennen — sonst bliebe eine Karteileiche, die niemand mehr
        loeschen kann.
        """
        statement = f"DROP TABLE IF EXISTS {quote_identifier(validate_identifier(name))}"
        path = self.db_path(workspace_id, area_id)
        lock = await self._lock_for(path)
        async with lock:
            await asyncio.to_thread(self._execute_statements_sync, path, [statement])

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

    async def reapply_category(
        self,
        workspace_id: UUID,
        area_id: UUID,
        *,
        table: str,
        category_column: str,
        match_column: str,
        category: str,
        pattern: str,
        excluded_patterns: Sequence[str],
    ) -> int:
        """Rueckwirkende Re-Kategorisierung einer Regel (WP17, server-only).

        Setzt `category_column` auf `category` fuer alle Zeilen, deren
        `match_column` das `pattern` als Substring traegt (case-insensitive)
        UND kein `excluded_patterns`-Element matcht — die NOT-Klauseln lassen
        Konflikt-Zeilen unangetastet (Zeilen, die eine ANDERE aktive Regel mit
        anderer Kategorie matcht). Rueckgabe: Anzahl geaenderter Zeilen.

        Laeuft ueber `run_admin_sql` und ist damit derselbe SERVER-ONLY
        Schreibpfad (rw-Connection ohne Authorizer, ADR-0049, Entscheidung 2)
        — NIE mit Agenten-/User-Input als Identifier aufrufen.

        Der SQL-Bau lebt HIER und nicht im Service (ARC-3): Services kennen
        kein SQL, der Store ist die einzige Stelle, die Identifier gegen die
        Allowlist (`tablestore/schema.py`) validiert und quotet. Die
        Domaenen-Pruefung, OB eine Tabelle ueberhaupt category-/match-Spalten
        hat, bleibt beim Service (Katalog-Schema). Werte laufen
        parametrisiert.
        """
        quoted_table = quote_identifier(table)
        quoted_category = quote_identifier(validate_column_name(category_column))
        quoted_match = quote_identifier(validate_column_name(match_column))
        conditions = [f"lower({quoted_match}) LIKE ? ESCAPE '\\'"]
        parameters: list[object] = [category, _like_parameter(pattern)]
        for excluded in excluded_patterns:
            conditions.append(f"NOT (lower({quoted_match}) LIKE ? ESCAPE '\\')")
            parameters.append(_like_parameter(excluded))
        sql = f"UPDATE {quoted_table} SET {quoted_category} = ? WHERE " + " AND ".join(conditions)
        return await self.run_admin_sql(workspace_id, area_id, sql, parameters)

    # --- Discovery / Betrieb -------------------------------------------------

    async def describe(
        self, workspace_id: UUID, area_id: UUID, table: str, columns: Sequence[ColumnSpec]
    ) -> TableDescription:
        """Zeilenzahl + Wertebereiche pro Spalte — OHNE Rohzeilen (ADR-0049).

        Numerik/Datum/Boolean: min/max. Text: distinct-Count, gedeckelt auf
        `DESCRIBE_DISTINCT_CAP`. Laeuft auf der Read-only-Connection
        (Defense-in-Depth: describe KANN nicht schreiben) — und erbt damit
        auch deren Zeitbudget (H1): describe macht pro Spalte einen
        Full-Scan (count/min/max/distinct) und ist auf einer grossen Area
        genauso teuer wie eine Agenten-Query.
        """
        quoted_table = quote_identifier(table)
        path = self.db_path(workspace_id, area_id)
        return await asyncio.to_thread(self._describe_sync, path, quoted_table, list(columns))

    def _describe_sync(
        self, path: Path, quoted_table: str, columns: list[ColumnSpec]
    ) -> TableDescription:
        connection = self._connect_ro(path)
        try:
            return self._describe_on(connection, quoted_table, columns)
        except sqlite3.DatabaseError as exc:
            translated = _translate_query_error(exc)
            if translated is not None:
                raise translated from exc
            raise
        finally:
            connection.close()

    @staticmethod
    def _describe_on(
        connection: sqlite3.Connection, quoted_table: str, columns: list[ColumnSpec]
    ) -> TableDescription:
        """Die eigentlichen describe-Aggregate auf einer offenen ro-Connection."""
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
