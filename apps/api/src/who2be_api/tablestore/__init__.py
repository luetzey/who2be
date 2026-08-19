"""Tabellen-Store: SQLite pro WorkArea (ADR-0049).

Die Datei ist die Isolationsgrenze, read-only ist Engine-Garantie
(query_only + Authorizer) — siehe `engine.py`. Schema-Allowlist in
`schema.py`, deterministischer Import-Hash in `dedupe.py`. Modell-
unabhaengig (WP12); WP13 verdrahtet `who2be_models.tables` darauf.
"""

from who2be_api.tablestore.dedupe import row_hash
from who2be_api.tablestore.engine import (
    DEFAULT_QUERY_TIMEOUT_MS,
    DESCRIBE_DISTINCT_CAP,
    EXPORT_ROW_LIMIT,
    MAX_CELL_BYTES,
    MAX_RESULT_BYTES,
    AreaStoreMissingError,
    ColumnStats,
    InsertResult,
    QueryResult,
    QueryTimeout,
    ReadOnlyViolation,
    ResultTooLarge,
    TableDescription,
    TableStore,
)
from who2be_api.tablestore.schema import (
    COLUMN_NAME_RE,
    RESERVED_COLUMN_NAMES,
    ColumnSpec,
    ColumnType,
    SchemaError,
    build_create_table_sql,
    quote_identifier,
    sql_type_for,
    validate_column_name,
)

__all__ = [
    "COLUMN_NAME_RE",
    "DEFAULT_QUERY_TIMEOUT_MS",
    "DESCRIBE_DISTINCT_CAP",
    "EXPORT_ROW_LIMIT",
    "MAX_CELL_BYTES",
    "MAX_RESULT_BYTES",
    "RESERVED_COLUMN_NAMES",
    "AreaStoreMissingError",
    "ColumnSpec",
    "ColumnStats",
    "ColumnType",
    "InsertResult",
    "QueryResult",
    "QueryTimeout",
    "ReadOnlyViolation",
    "ResultTooLarge",
    "SchemaError",
    "TableDescription",
    "TableStore",
    "build_create_table_sql",
    "quote_identifier",
    "row_hash",
    "sql_type_for",
    "validate_column_name",
]
