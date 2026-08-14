"""Tabellen-Store (ADR-0049, WP12) — Engine-Garantien, komplett DB-los.

Die Kernfaelle sind SICHERHEITSGARANTIEN, keine Features: freies Agenten-SQL
darf die Area-Datei unter keinen Umstaenden veraendern (query_only +
Authorizer → `ReadOnlyViolation`), Identifier laufen nur durch die
Allowlist, Werte nur parametrisiert. Alles gegen `tmp_path`, ohne Postgres.

Hinweis zur Test-Struktur: eine `TableStore`-Instanz gehoert zu genau einer
Event-Loop (die per-Area-Locks binden sich an die Loop des ersten Awaits) —
Szenarien mit Schreibpfaden laufen deshalb in EINEM `asyncio.run`; die
lock-freien Lesepfade (`run_readonly_query`, `describe`) duerfen danach in
einem weiteren laufen.
"""

import asyncio
import sqlite3
from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from who2be_api.tablestore import (
    DESCRIBE_DISTINCT_CAP,
    AreaStoreMissingError,
    ColumnSpec,
    ColumnType,
    InsertResult,
    ReadOnlyViolation,
    SchemaError,
    TableStore,
    build_create_table_sql,
    quote_identifier,
    row_hash,
    sql_type_for,
)

_WS = UUID("00000000-0000-0000-0000-00000000000a")
_AREA = UUID("00000000-0000-0000-0000-00000000000b")
_AREA_2 = UUID("00000000-0000-0000-0000-00000000000c")

# Spec-K-Beispiel: Transaktionen mit Dedupe ueber Datum/Betrag/Zweck/Konto —
# die SPALTEN kommen im Echtbetrieb aus dem Katalog (`wa_table`), hier fix.
_COLUMNS = [
    ColumnSpec(name="booked_on", type=ColumnType.DATE, nullable=False),
    ColumnSpec(name="amount", type=ColumnType.NUMERIC, nullable=False),
    ColumnSpec(name="purpose", type=ColumnType.TEXT),
    ColumnSpec(name="account", type=ColumnType.TEXT),
]
_COLUMN_NAMES = ["booked_on", "amount", "purpose", "account"]
_DEDUPE_COLUMNS = ("booked_on", "amount", "purpose", "account")

_ROWS = [
    {"booked_on": "2026-08-01", "amount": 12.5, "purpose": "Miete", "account": "giro"},
    {"booked_on": "2026-08-02", "amount": -3.2, "purpose": "Kaffee", "account": "giro"},
    {"booked_on": "2026-08-02", "amount": 100, "purpose": "Gehalt", "account": "spar"},
]


def _hash_fn(row: Mapping[str, object]) -> str:
    return row_hash(row, _DEDUPE_COLUMNS)


def _seeded_store(tmp_path: Path, rows: Sequence[Mapping[str, object]]) -> TableStore:
    """Store mit angelegter Tabelle + Zeilen; Schreibpfade in einem Loop-Lauf."""
    store = TableStore(base_dir=tmp_path)

    async def _seed() -> None:
        await store.create_table(_WS, _AREA, "transactions", _COLUMNS)
        if rows:
            await store.insert_rows(_WS, _AREA, "transactions", _COLUMN_NAMES, rows, _hash_fn)

    asyncio.run(_seed())
    return store


# --- Read-only als Engine-Garantie (ADR-0049, Entscheidung 2) ----------------


@pytest.mark.parametrize(
    "sql",
    [
        'DROP TABLE "transactions"',
        "UPDATE \"transactions\" SET purpose = 'x'",
        'DELETE FROM "transactions"',
        "INSERT INTO \"transactions\" (booked_on, amount) VALUES ('2026-01-01', 1)",
        "ATTACH DATABASE ':memory:' AS fremde_datei",
        "PRAGMA journal_mode=DELETE",
        "PRAGMA table_info('transactions')",
        "CREATE TABLE hijack (x TEXT)",
    ],
    ids=["drop", "update", "delete", "insert", "attach", "pragma-write", "pragma-read", "create"],
)
def test_readonly_query_denies_mutations(tmp_path: Path, sql: str) -> None:
    store = _seeded_store(tmp_path, _ROWS)

    async def _attempt() -> None:
        with pytest.raises(ReadOnlyViolation):
            await store.run_readonly_query(_WS, _AREA, sql, limit=10)

    asyncio.run(_attempt())
    # Und: der Datenbestand ist unveraendert (nichts hat geschrieben).
    result = asyncio.run(
        store.run_readonly_query(_WS, _AREA, 'SELECT count(*) FROM "transactions"', limit=1)
    )
    assert result.rows == [[len(_ROWS)]]


def test_readonly_query_syntax_error_is_not_masked(tmp_path: Path) -> None:
    # Ein Syntaxfehler ist KEINE Read-only-Verletzung — der Service muss
    # beide unterscheiden koennen (403 query_not_readonly vs. 400).
    store = _seeded_store(tmp_path, _ROWS)

    async def _attempt() -> None:
        with pytest.raises(sqlite3.OperationalError):
            await store.run_readonly_query(_WS, _AREA, "SELEC kaputt", limit=1)

    asyncio.run(_attempt())


def test_readonly_query_missing_area_raises_domain_error(tmp_path: Path) -> None:
    store = TableStore(base_dir=tmp_path)

    async def _attempt() -> None:
        with pytest.raises(AreaStoreMissingError):
            await store.run_readonly_query(_WS, _AREA_2, "SELECT 1", limit=1)

    asyncio.run(_attempt())


def test_select_with_join_aggregate_and_recursive_cte(tmp_path: Path) -> None:
    # Die Allowlist (SELECT/READ/FUNCTION/RECURSIVE) muss legitimes Lese-SQL
    # vollstaendig tragen: CTE + JOIN + Aggregat in einer Query.
    store = _seeded_store(tmp_path, _ROWS)
    sql = """
        WITH sums AS (
            SELECT account, sum(amount) AS total
            FROM "transactions"
            GROUP BY account
        )
        SELECT t.account, count(*) AS n, s.total
        FROM "transactions" AS t
        JOIN sums AS s ON s.account = t.account
        GROUP BY t.account
        ORDER BY t.account
    """
    result = asyncio.run(store.run_readonly_query(_WS, _AREA, sql, limit=10))
    assert result.columns == ["account", "n", "total"]
    assert result.rows == [["giro", 2, pytest.approx(9.3)], ["spar", 1, 100]]
    assert result.truncated is False

    recursive = asyncio.run(
        store.run_readonly_query(
            _WS,
            _AREA,
            "WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n WHERE i < 5) "
            "SELECT sum(i) FROM n",
            limit=1,
        )
    )
    assert recursive.rows == [[15]]


def test_readonly_query_truncates_at_limit(tmp_path: Path) -> None:
    store = _seeded_store(tmp_path, _ROWS)
    sql = 'SELECT purpose FROM "transactions" ORDER BY booked_on'
    capped = asyncio.run(store.run_readonly_query(_WS, _AREA, sql, limit=2))
    assert len(capped.rows) == 2
    assert capped.truncated is True
    complete = asyncio.run(store.run_readonly_query(_WS, _AREA, sql, limit=3))
    assert len(complete.rows) == 3
    assert complete.truncated is False


# --- Idempotenter Import + 10k-Aggregat (Spec K) -----------------------------


def test_double_import_is_idempotent(tmp_path: Path) -> None:
    store = TableStore(base_dir=tmp_path)

    async def _scenario() -> tuple[InsertResult, InsertResult]:
        await store.create_table(_WS, _AREA, "transactions", _COLUMNS)
        first = await store.insert_rows(_WS, _AREA, "transactions", _COLUMN_NAMES, _ROWS, _hash_fn)
        second = await store.insert_rows(_WS, _AREA, "transactions", _COLUMN_NAMES, _ROWS, _hash_fn)
        return first, second

    first, second = asyncio.run(_scenario())
    assert first == InsertResult(inserted=len(_ROWS), skipped=0)
    assert second == InsertResult(inserted=0, skipped=len(_ROWS))


def test_10k_rows_aggregate_and_describe_without_rows(tmp_path: Path) -> None:
    store = TableStore(base_dir=tmp_path)
    rows: list[Mapping[str, object]] = [
        {
            "booked_on": f"2026-{1 + i % 12:02d}-{1 + i % 28:02d}",
            "amount": i,
            "purpose": f"zweck-{i}",
            "account": "giro" if i % 2 == 0 else "spar",
        }
        for i in range(10_000)
    ]

    async def _scenario() -> InsertResult:
        await store.create_table(_WS, _AREA, "transactions", _COLUMNS)
        return await store.insert_rows(_WS, _AREA, "transactions", _COLUMN_NAMES, rows, _hash_fn)

    result = asyncio.run(_scenario())
    assert result == InsertResult(inserted=10_000, skipped=0)

    aggregate = asyncio.run(
        store.run_readonly_query(
            _WS, _AREA, 'SELECT count(*), sum(amount) FROM "transactions"', limit=10
        )
    )
    assert aggregate.rows == [[10_000, sum(range(10_000))]]
    assert aggregate.truncated is False

    description = asyncio.run(store.describe(_WS, _AREA, "transactions", _COLUMNS))
    assert description.row_count == 10_000
    by_name = {stats.name: stats for stats in description.columns}
    # Numerik/Datum: Wertebereiche, keine Zeilen.
    assert by_name["amount"].min_value == 0
    assert by_name["amount"].max_value == 9_999
    assert by_name["booked_on"].min_value == "2026-01-01"
    # Text: distinct-Count, hart gedeckelt — describe gibt NIE Rohzeilen zurueck.
    assert by_name["purpose"].distinct_count == DESCRIBE_DISTINCT_CAP
    assert by_name["purpose"].distinct_capped is True
    assert by_name["account"].distinct_count == 2
    assert by_name["account"].distinct_capped is False
    assert not hasattr(description, "rows")


def test_parallel_inserts_are_serialized_by_area_lock(tmp_path: Path) -> None:
    store = TableStore(base_dir=tmp_path)
    batches: list[list[Mapping[str, object]]] = [
        [
            {
                "booked_on": "2026-08-01",
                "amount": batch * 1_000 + i,
                "purpose": f"batch-{batch}-{i}",
                "account": "giro",
            }
            for i in range(50)
        ]
        for batch in range(8)
    ]

    async def _scenario() -> list[InsertResult]:
        await store.create_table(_WS, _AREA, "transactions", _COLUMNS)
        return list(
            await asyncio.gather(
                *(
                    store.insert_rows(_WS, _AREA, "transactions", _COLUMN_NAMES, batch, _hash_fn)
                    for batch in batches
                )
            )
        )

    results = asyncio.run(_scenario())
    assert sum(result.inserted for result in results) == 400
    assert all(result.skipped == 0 for result in results)
    count = asyncio.run(
        store.run_readonly_query(_WS, _AREA, 'SELECT count(*) FROM "transactions"', limit=1)
    )
    assert count.rows == [[400]]


def test_insert_rows_records_source_artifact(tmp_path: Path) -> None:
    # Provenance (ADR-0049, Entscheidung 5): jede Row traegt _source_artifact.
    store = TableStore(base_dir=tmp_path)

    async def _scenario() -> None:
        await store.create_table(_WS, _AREA, "transactions", _COLUMNS)
        await store.insert_rows(
            _WS,
            _AREA,
            "transactions",
            _COLUMN_NAMES,
            _ROWS[:1],
            _hash_fn,
            source_artifact="artifact-123",
        )

    asyncio.run(_scenario())
    result = asyncio.run(
        store.run_readonly_query(_WS, _AREA, 'SELECT _source_artifact FROM "transactions"', limit=1)
    )
    assert result.rows == [["artifact-123"]]


def test_insert_rows_rejects_invalid_column_names(tmp_path: Path) -> None:
    store = _seeded_store(tmp_path, [])

    async def _attempt(column: str) -> None:
        await store.insert_rows(_WS, _AREA, "transactions", [column], _ROWS[:1], _hash_fn)

    for bad in ('amount"; DROP TABLE x --', "_dedupe_hash", "rowid"):
        with pytest.raises(SchemaError):
            asyncio.run(_attempt(bad))


# --- Server-only-Schreibpfad + Betrieb ---------------------------------------


def test_run_admin_sql_writes_where_agents_cannot(tmp_path: Path) -> None:
    # Der Server unterliegt dem Authorizer NICHT (ADR-0049, Entscheidung 2) —
    # Re-Kategorisierung (WP17) laeuft ueber diesen dokumentierten rw-Pfad.
    store = TableStore(base_dir=tmp_path)

    async def _scenario() -> int:
        await store.create_table(_WS, _AREA, "transactions", _COLUMNS)
        await store.insert_rows(_WS, _AREA, "transactions", _COLUMN_NAMES, _ROWS, _hash_fn)
        return await store.run_admin_sql(
            _WS,
            _AREA,
            'UPDATE "transactions" SET purpose = ? WHERE account = ?',
            ["neu-kategorisiert", "giro"],
        )

    affected = asyncio.run(_scenario())
    assert affected == 2
    result = asyncio.run(
        store.run_readonly_query(
            _WS,
            _AREA,
            "SELECT count(*) FROM \"transactions\" WHERE purpose = 'neu-kategorisiert'",
            limit=1,
        )
    )
    assert result.rows == [[2]]


def test_delete_area_store_removes_all_files(tmp_path: Path) -> None:
    store = TableStore(base_dir=tmp_path)
    path = store.db_path(_WS, _AREA)

    async def _scenario() -> None:
        await store.create_table(_WS, _AREA, "transactions", _COLUMNS)
        await store.insert_rows(_WS, _AREA, "transactions", _COLUMN_NAMES, _ROWS, _hash_fn)
        assert path.is_file()
        await store.delete_area_store(_WS, _AREA)
        # Idempotent: nochmal loeschen ist ein No-op, kein Fehler.
        await store.delete_area_store(_WS, _AREA)

    asyncio.run(_scenario())
    assert not path.exists()
    assert not Path(f"{path}-wal").exists()
    assert not Path(f"{path}-shm").exists()


def test_snapshot_to_creates_readable_copy(tmp_path: Path) -> None:
    store = TableStore(base_dir=tmp_path / "store")
    target = tmp_path / "backup" / "area.sqlite"

    async def _scenario() -> None:
        await store.create_table(_WS, _AREA, "transactions", _COLUMNS)
        await store.insert_rows(_WS, _AREA, "transactions", _COLUMN_NAMES, _ROWS, _hash_fn)
        await store.snapshot_to(_WS, _AREA, target)

    asyncio.run(_scenario())
    assert target.is_file()
    # Der Snapshot ist eine eigenstaendig lesbare SQLite-Datei (VACUUM INTO).
    connection = sqlite3.connect(str(target))
    try:
        count = connection.execute('SELECT count(*) FROM "transactions"').fetchone()
        assert count[0] == len(_ROWS)
    finally:
        connection.close()


# --- Pfad-Layout (Isolationsgrenze) ------------------------------------------


def test_db_path_layout_is_uuid_per_area(tmp_path: Path) -> None:
    store = TableStore(base_dir=tmp_path)
    assert store.db_path(_WS, _AREA) == tmp_path / str(_WS) / f"{_AREA}.sqlite"
    assert store.db_path(_WS, _AREA_2) != store.db_path(_WS, _AREA)


def test_db_path_rejects_non_uuid_inputs(tmp_path: Path) -> None:
    # Pfad-Injection-Schranke: Strings (auch "harmlose") sind keine Area-IDs.
    store = TableStore(base_dir=tmp_path)
    with pytest.raises(TypeError):
        store.db_path("../../etc", _AREA)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        store.db_path(_WS, f"{_AREA}")  # type: ignore[arg-type]


# --- Schema-Allowlist (schema.py) --------------------------------------------


@pytest.mark.parametrize(
    "bad",
    ["", "1abc", "Amount", "a-b", "a b", "ä", 'x";drop', "rowid", "oid", "_dedupe_hash", "a" * 64],
)
def test_create_table_sql_rejects_bad_column_names(bad: str) -> None:
    with pytest.raises(SchemaError):
        build_create_table_sql("t", [ColumnSpec(name=bad, type=ColumnType.TEXT)])


def test_create_table_sql_rejects_bad_table_and_duplicates() -> None:
    with pytest.raises(SchemaError):
        build_create_table_sql('t"; DROP', [ColumnSpec(name="a", type=ColumnType.TEXT)])
    with pytest.raises(SchemaError):
        build_create_table_sql("t", [])
    with pytest.raises(SchemaError):
        build_create_table_sql(
            "t",
            [
                ColumnSpec(name="a", type=ColumnType.TEXT),
                ColumnSpec(name="a", type=ColumnType.INTEGER),
            ],
        )


def test_create_table_sql_maps_types_and_adds_store_columns() -> None:
    create_sql, index_sql = build_create_table_sql(
        "t",
        [
            ColumnSpec(name="a", type=ColumnType.TEXT),
            ColumnSpec(name="b", type=ColumnType.INTEGER, nullable=False),
            ColumnSpec(name="c", type=ColumnType.NUMERIC),
            ColumnSpec(name="d", type=ColumnType.DATE),
            ColumnSpec(name="e", type=ColumnType.TIMESTAMP),
            ColumnSpec(name="f", type=ColumnType.BOOLEAN),
        ],
    )
    assert '"a" TEXT' in create_sql
    assert '"b" INTEGER NOT NULL' in create_sql
    assert '"c" NUMERIC' in create_sql
    assert '"d" TEXT' in create_sql  # date als ISO-8601-TEXT (sortiert korrekt)
    assert '"e" TEXT' in create_sql
    assert '"f" INTEGER' in create_sql  # boolean als 0/1
    assert '"_dedupe_hash" TEXT NOT NULL' in create_sql
    assert '"_source_artifact" TEXT' in create_sql
    assert index_sql == 'CREATE UNIQUE INDEX "idx_t_dedupe_hash" ON "t" ("_dedupe_hash")'


def test_sql_type_for_accepts_strings_and_rejects_unknown() -> None:
    # WP13 reicht Katalog-JSON als Strings durch — beide Schreibweisen gleich.
    assert sql_type_for("numeric") == sql_type_for(ColumnType.NUMERIC)
    with pytest.raises(SchemaError):
        sql_type_for("json")


def test_quote_identifier_validates_first() -> None:
    assert quote_identifier("betrag_eur") == '"betrag_eur"'
    with pytest.raises(SchemaError):
        quote_identifier('x" OR 1=1')


# --- Dedupe-Hash (dedupe.py) -------------------------------------------------


def test_row_hash_ignores_dict_key_order() -> None:
    row_a = {"booked_on": "2026-08-01", "amount": 10, "purpose": "Miete", "account": "giro"}
    row_b = {"account": "giro", "purpose": "Miete", "amount": 10, "booked_on": "2026-08-01"}
    assert row_hash(row_a, _DEDUPE_COLUMNS) == row_hash(row_b, _DEDUPE_COLUMNS)


def test_row_hash_normalizes_strings() -> None:
    # Whitespace-Trim + Unicode-NFC: dieselbe Buchung, zweimal exportiert.
    composed = {"purpose": "Café"}
    decomposed = {"purpose": "Café"}
    assert row_hash(composed, ["purpose"]) == row_hash(decomposed, ["purpose"])
    assert row_hash({"purpose": "  Miete "}, ["purpose"]) == row_hash(
        {"purpose": "Miete"}, ["purpose"]
    )


def test_row_hash_distinguishes_none_from_empty_string() -> None:
    assert row_hash({"purpose": None}, ["purpose"]) != row_hash({"purpose": ""}, ["purpose"])
    # Fehlende Spalte zaehlt als None — nicht als leerer String.
    assert row_hash({}, ["purpose"]) == row_hash({"purpose": None}, ["purpose"])


def test_row_hash_normalizes_numbers_and_temporal_values() -> None:
    assert (
        row_hash({"amount": 10}, ["amount"])
        == row_hash({"amount": 10.0}, ["amount"])
        == row_hash({"amount": Decimal("10.00")}, ["amount"])
    )
    assert row_hash({"amount": 10}, ["amount"]) != row_hash({"amount": 10.5}, ["amount"])
    # Typ-Tags trennen Typen: bool kollidiert nicht mit 1, date nicht mit
    # seinem ISO-String (beide waeren sonst byte-identisch).
    assert row_hash({"x": True}, ["x"]) != row_hash({"x": 1}, ["x"])
    assert row_hash({"d": date(2026, 8, 1)}, ["d"]) != row_hash({"d": "2026-08-01"}, ["d"])
    # -0.0 und 0 sind derselbe Betrag.
    assert row_hash({"amount": -0.0}, ["amount"]) == row_hash({"amount": 0}, ["amount"])


def test_row_hash_requires_dedupe_columns() -> None:
    with pytest.raises(ValueError):
        row_hash({"a": 1}, [])


def test_row_hash_field_boundaries_are_unambiguous() -> None:
    # Laengenpraefix-Codierung: ("ab", "c") darf nie wie ("a", "bc") hashen.
    assert row_hash({"a": "ab", "b": "c"}, ["a", "b"]) != row_hash(
        {"a": "a", "b": "bc"}, ["a", "b"]
    )
