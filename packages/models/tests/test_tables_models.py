"""Unit-Tests fuer die Tabellen-Store-Models (WP11, ADR-0049).

DB-frei: die Schema-Invarianten (occurred_at-Pflicht, unbekannte
dedupe-/match-/category-Spalten, reservierte Namen, Identifier-Regex,
eindeutige Spaltennamen), der `schema`-Alias, die Feld-Bounds und die
Roundtrips der Query-/Regel-/Konventions-/Zugriffslog-Modelle. Die
serverseitige Durchsetzung (Engine-Authorizer, rule_required,
convention_missing) lebt in den API-WPs (Wellen 5-6).
"""

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from who2be_models import (
    AccessLogEntry,
    AccessOperation,
    AccessRefKind,
    CategoryRuleRead,
    CategoryRuleUpsert,
    NewRule,
    QueryFormat,
    QueryResult,
    RowsInsert,
    Sensitivity,
    SourceConventionRead,
    SourceConventionSet,
    TableColumn,
    TableColumnType,
    TableDescription,
    TableQuery,
    TableSchema,
    WaTableCreate,
    WaTableRead,
)

_NOW = datetime(2026, 8, 14, 12, 0, tzinfo=UTC)


def _columns(*extra: TableColumn) -> list[TableColumn]:
    """Minimal gueltige Spaltenliste: occurred_at (timestamp) + Extras."""
    return [TableColumn(name="occurred_at", type=TableColumnType.timestamp), *extra]


def _schema(**overrides: object) -> TableSchema:
    base: dict[str, object] = {
        "columns": _columns(
            TableColumn(name="amount", type=TableColumnType.numeric),
            TableColumn(name="merchant", type=TableColumnType.text),
        )
    }
    base.update(overrides)
    return TableSchema.model_validate(base)


class TestTableColumn:
    def test_defaults_and_roundtrip(self) -> None:
        column = TableColumn(name="amount", type=TableColumnType.numeric)
        assert column.nullable is True
        assert TableColumn.model_validate(column.model_dump()) == column

    @pytest.mark.parametrize("name", ["Amount", "1amount", "a-b", "a b", "_dedupe_hash", ""])
    def test_identifier_regex_rejects_unsafe_names(self, name: str) -> None:
        # SQL-Identifier-Sicherheit: Spaltennamen gehen verbatim in
        # SQLite-DDL ein — alles ausserhalb ^[a-z][a-z0-9_]*$ ist abgelehnt
        # (damit scheitern auch die server-vergebenen _-Spalten frueh).
        with pytest.raises(ValidationError):
            TableColumn(name=name, type=TableColumnType.text)

    def test_forbids_extra_fields(self) -> None:
        with pytest.raises(ValidationError):
            TableColumn.model_validate({"name": "a", "type": "text", "default": 1})


class TestTableSchema:
    def test_minimal_valid_and_roundtrip(self) -> None:
        schema = _schema()
        assert schema.dedupe_columns == []
        assert schema.match_column is None
        assert TableSchema.model_validate(schema.model_dump()) == schema

    def test_occurred_at_column_required(self) -> None:
        with pytest.raises(ValidationError, match="occurred_at"):
            TableSchema(columns=[TableColumn(name="amount", type=TableColumnType.numeric)])

    def test_occurred_at_must_be_temporal(self) -> None:
        with pytest.raises(ValidationError, match="timestamp"):
            TableSchema(columns=[TableColumn(name="occurred_at", type=TableColumnType.text)])

    def test_occurred_at_as_date_ok(self) -> None:
        schema = TableSchema(columns=[TableColumn(name="occurred_at", type=TableColumnType.date)])
        assert schema.columns[0].type == TableColumnType.date

    def test_duplicate_column_names_rejected(self) -> None:
        with pytest.raises(ValidationError, match="eindeutig"):
            TableSchema(
                columns=_columns(
                    TableColumn(name="amount", type=TableColumnType.numeric),
                    TableColumn(name="amount", type=TableColumnType.text),
                )
            )

    def test_reserved_column_name_rejected(self) -> None:
        # `rowid` passiert die Identifier-Regex und MUSS an der
        # Reserviert-Liste scheitern (SQLite-eigene Spalte).
        with pytest.raises(ValidationError, match="rowid"):
            TableSchema(columns=_columns(TableColumn(name="rowid", type=TableColumnType.integer)))

    def test_unknown_dedupe_column_rejected(self) -> None:
        with pytest.raises(ValidationError, match="dedupe_columns"):
            _schema(dedupe_columns=["nope"])

    def test_unknown_match_column_rejected(self) -> None:
        with pytest.raises(ValidationError, match="match_column"):
            _schema(match_column="nope")

    def test_unknown_category_column_rejected(self) -> None:
        with pytest.raises(ValidationError, match="category_column"):
            _schema(category_column="nope")

    def test_known_special_columns_ok(self) -> None:
        schema = _schema(
            dedupe_columns=["occurred_at", "amount"],
            match_column="merchant",
            category_column="merchant",
        )
        assert schema.dedupe_columns == ["occurred_at", "amount"]

    def test_column_count_capped(self) -> None:
        too_many = _columns(
            *[TableColumn(name=f"c{i}", type=TableColumnType.text) for i in range(40)]
        )
        with pytest.raises(ValidationError):
            TableSchema(columns=too_many)


class TestWaTable:
    def test_create_accepts_wire_alias_schema(self) -> None:
        created = WaTableCreate.model_validate(
            {"name": "expenses", "schema": _schema().model_dump()}
        )
        assert created.schema_.match_column is None
        # Roundtrip ueber das Wire-Format: dump(by_alias) -> validate.
        assert WaTableCreate.model_validate(created.model_dump(by_alias=True)) == created

    def test_create_name_follows_identifier_regex(self) -> None:
        # Der Name wird SQLite-Tabellenname — gleiche Regel wie Spalten.
        with pytest.raises(ValidationError):
            WaTableCreate.model_validate(
                {"name": "Ausgaben 2026", "schema": _schema().model_dump()}
            )

    def test_read_roundtrip(self) -> None:
        read = WaTableRead.model_validate(
            {
                "id": uuid4(),
                "workspace_id": uuid4(),
                "area_id": uuid4(),
                "name": "expenses",
                "schema": _schema().model_dump(),
                "created_at": _NOW,
                "updated_at": _NOW,
            }
        )
        assert read.row_count is None
        assert read.schema_.columns[0].name == "occurred_at"


class TestRowsInsert:
    def test_minimal_and_defaults(self) -> None:
        insert = RowsInsert(rows=[{"occurred_at": "2026-08-14", "amount": 12.5}])
        assert insert.source_artifact_id is None
        assert insert.new_rules == []

    def test_empty_rows_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RowsInsert(rows=[])

    def test_with_new_rules_roundtrip(self) -> None:
        insert = RowsInsert(
            rows=[{"occurred_at": "2026-08-14"}],
            source_artifact_id=uuid4(),
            source_name="bank-csv",
            new_rules=[NewRule(pattern="REWE*", category="groceries", confidence=0.9)],
        )
        assert RowsInsert.model_validate(insert.model_dump()) == insert

    def test_new_rule_confidence_bounds(self) -> None:
        with pytest.raises(ValidationError):
            NewRule(pattern="x", category="y", confidence=1.5)


class TestTableQuery:
    def test_defaults(self) -> None:
        query = TableQuery(sql="SELECT count(*) FROM expenses")
        assert query.format == QueryFormat.json
        assert query.limit == 200

    def test_limit_bounds(self) -> None:
        with pytest.raises(ValidationError):
            TableQuery(sql="SELECT 1", limit=0)
        with pytest.raises(ValidationError):
            TableQuery(sql="SELECT 1", limit=1001)

    def test_result_roundtrip(self) -> None:
        result = QueryResult(
            columns=["month", "total"],
            rows=[["2026-08", 42.0]],
            row_count=1,
            truncated=False,
        )
        assert result.rendered is None
        assert QueryResult.model_validate(result.model_dump()) == result


class TestRulesAndConventions:
    def test_category_rule_upsert_and_read(self) -> None:
        upsert = CategoryRuleUpsert(pattern="REWE*", category="groceries")
        assert upsert.confidence is None
        rule = CategoryRuleRead.model_validate(
            {
                "id": uuid4(),
                "area_id": uuid4(),
                "pattern": "REWE*",
                "category": "groceries",
                "created_by": "model:gpt-x",
                "confidence": 0.8,
                "active": True,
                "created_at": _NOW,
                "updated_at": _NOW,
            }
        )
        assert rule.active is True

    def test_convention_set_caps_keys(self) -> None:
        SourceConventionSet(convention={f"k{i}": "v" for i in range(50)})
        with pytest.raises(ValidationError, match="Keys"):
            SourceConventionSet(convention={f"k{i}": "v" for i in range(51)})

    def test_convention_read_roundtrip(self) -> None:
        read = SourceConventionRead.model_validate(
            {
                "id": uuid4(),
                "area_id": uuid4(),
                "source_name": "bank-csv",
                "convention": {"decimal": ",", "date_format": "DD.MM.YYYY"},
                "created_by": None,
                "created_at": _NOW,
                "updated_at": _NOW,
            }
        )
        assert read.created_by is None

    def test_description_roundtrip_with_alias(self) -> None:
        description = TableDescription.model_validate(
            {
                "schema": _schema().model_dump(),
                "row_count": 3,
                "column_stats": {"amount": {"min": 1, "max": 99}},
                "conventions": [],
            }
        )
        assert description.schema_.columns[0].name == "occurred_at"
        dumped = description.model_dump(by_alias=True)
        assert "schema" in dumped and "schema_" not in dumped


class TestAccessLogEntry:
    def test_roundtrip(self) -> None:
        entry = AccessLogEntry.model_validate(
            {
                "id": uuid4(),
                "agent_id": uuid4(),
                "ref_kind": "artifact",
                "ref_id": str(uuid4()),
                "operation": "read",
                "sensitivity_at_access": "sensitive",
                "access_date": date(2026, 8, 14),
                "first_at": _NOW,
            }
        )
        assert entry.ref_kind == AccessRefKind.artifact
        assert entry.operation == AccessOperation.read
        assert entry.sensitivity_at_access == Sensitivity.sensitive
        assert AccessLogEntry.model_validate(entry.model_dump()) == entry
