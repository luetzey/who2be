"""Schema-Allowlist des Tabellen-Stores (ADR-0049).

Identifier und Spaltentypen sind die EINZIGEN Stellen, an denen
Aufrufer-Input in DDL landet — deshalb Allowlist statt Escaping: ein
Identifier, der nicht auf `COLUMN_NAME_RE` matcht, wird abgelehnt, nie
"repariert". Werte laufen davon getrennt IMMER ueber parametrisierte
Statements (engine.py); diese Datei erzeugt ausschliesslich DDL aus
validierten Bausteinen.

Das Package ist in Welle 4 bewusst modell-unabhaengig (WP12): `ColumnSpec`
ist eine leichte eigene Dataclass; WP13 verdrahtet spaeter
`who2be_models.tables.TableSchema` darauf. Die Typ-Allowlist
`text|integer|numeric|date|timestamp|boolean` entspricht dem Katalog-Schema
`wa_table.schema_json` (ADR-0049, Entscheidung 3).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

# Nur Kleinbuchstaben/Ziffern/Underscore, fuehrender Buchstabe — damit ist
# jeder validierte Identifier auch double-quoted ein harmloser SQL-Baustein
# (kein Quote-Zeichen, kein Whitespace, kein Unicode-Trick moeglich).
COLUMN_NAME_RE: Final = re.compile(r"^[a-z][a-z0-9_]*$")

# Obergrenze wie Postgres-Identifier (63) — der Katalog (`wa_table`, Postgres)
# muss jeden Namen ebenfalls tragen koennen, und Riesen-Namen sind nie legitim.
MAX_IDENTIFIER_LENGTH: Final = 63

# Vom Store selbst belegte bzw. von SQLite implizit vergebene Namen. Die
# Underscore-Namen scheitern bereits an COLUMN_NAME_RE; sie stehen hier
# trotzdem, damit die Verbotsliste vollstaendig DOKUMENTIERT ist (ADR-0049,
# Entscheidung 5: `_dedupe_hash` + `_source_artifact` haengt der Store an).
RESERVED_COLUMN_NAMES: Final[frozenset[str]] = frozenset(
    {"_dedupe_hash", "_source_artifact", "rowid", "oid"}
)

# Spalten, die create_table IMMER anlegt (Idempotenz + Provenance, ADR-0049).
DEDUPE_HASH_COLUMN: Final = "_dedupe_hash"
SOURCE_ARTIFACT_COLUMN: Final = "_source_artifact"


class SchemaError(ValueError):
    """Ungueltiger Identifier oder Spaltentyp — Aufruferfehler, kein Engine-Zustand.

    Domain-Exception statt roher ValueError-Streuung, damit der Service
    (WP13) sie einheitlich auf 422 mappen kann.
    """


class ColumnType(StrEnum):
    """Typ-Allowlist aus ADR-0049 (Katalog `wa_table.schema_json`)."""

    TEXT = "text"
    INTEGER = "integer"
    NUMERIC = "numeric"
    DATE = "date"
    TIMESTAMP = "timestamp"
    BOOLEAN = "boolean"


# SQLite-Affinitaeten: NUMERIC (statt REAL) haelt ganzzahlige Betraege
# verlustfrei als INTEGER; date/timestamp werden als ISO-8601-TEXT abgelegt
# (SQLite hat keinen Datumstyp, ISO-Strings sortieren korrekt und min/max in
# `describe` funktionieren lexikographisch); boolean als INTEGER 0/1.
_SQL_TYPES: Final[dict[ColumnType, str]] = {
    ColumnType.TEXT: "TEXT",
    ColumnType.INTEGER: "INTEGER",
    ColumnType.NUMERIC: "NUMERIC",
    ColumnType.DATE: "TEXT",
    ColumnType.TIMESTAMP: "TEXT",
    ColumnType.BOOLEAN: "INTEGER",
}


@dataclass(frozen=True, slots=True)
class ColumnSpec:
    """Leichte, modell-unabhaengige Spaltendefinition (WP12).

    `type` akzeptiert bewusst auch den String-Wert (`"text"`, ...), damit
    WP13 Katalog-JSON ohne Import-Kopplung durchreichen kann — aufgeloest
    wird er in `sql_type_for` gegen die Allowlist.
    """

    name: str
    type: ColumnType | str
    nullable: bool = True


def validate_identifier(name: str) -> str:
    """Validiert einen Identifier gegen die Allowlist-Regex (ADR-0049).

    Gibt den Namen unveraendert zurueck oder wirft `SchemaError` — es gibt
    bewusst KEINE Normalisierung: was nicht exakt passt, ist abgelehnt.
    """
    if not COLUMN_NAME_RE.fullmatch(name):
        raise SchemaError(
            f"Ungueltiger Identifier {name!r} — erlaubt ist ^[a-z][a-z0-9_]*$ (ADR-0049)."
        )
    if len(name) > MAX_IDENTIFIER_LENGTH:
        raise SchemaError(f"Identifier {name!r} ueberschreitet {MAX_IDENTIFIER_LENGTH} Zeichen.")
    return name


def validate_column_name(name: str) -> str:
    """Wie `validate_identifier`, zusaetzlich gegen `RESERVED_COLUMN_NAMES`."""
    validate_identifier(name)
    if name in RESERVED_COLUMN_NAMES:
        raise SchemaError(f"Spaltenname {name!r} ist reserviert (ADR-0049).")
    return name


def quote_identifier(name: str) -> str:
    """Double-quoted Identifier — NACH Regex-Validierung, nie als Escaping.

    Das Quoting schuetzt nicht vor Injection (das tut die Allowlist), es
    verhindert nur Kollisionen mit SQL-Schluesselwoertern.
    """
    return f'"{validate_identifier(name)}"'


def sql_type_for(column_type: ColumnType | str) -> str:
    """SQLite-Typ zur Allowlist-Angabe; unbekannte Typen sind `SchemaError`."""
    try:
        resolved = ColumnType(column_type)
    except ValueError as exc:
        allowed = ", ".join(member.value for member in ColumnType)
        raise SchemaError(f"Unbekannter Spaltentyp {column_type!r} — erlaubt: {allowed}.") from exc
    return _SQL_TYPES[resolved]


def build_create_table_sql(table_name: str, columns: list[ColumnSpec]) -> list[str]:
    """DDL-Statements fuer eine neue Area-Tabelle (ADR-0049, Entscheidung 5).

    Liefert `[CREATE TABLE ..., CREATE UNIQUE INDEX ...]` — die Engine fuehrt
    beide in EINER Transaktion aus. Zusaetzlich zu den validierten
    Aufrufer-Spalten haengt der Store immer an:

    - `_dedupe_hash TEXT NOT NULL` + UNIQUE-Index → idempotenter Import
      via `INSERT OR IGNORE` (dedupe.py liefert den Hash),
    - `_source_artifact TEXT NULL` → Provenance zur Roheingabe (`wa_artifact`).
    """
    quoted_table = quote_identifier(table_name)
    if not columns:
        raise SchemaError("Eine Tabelle braucht mindestens eine Spalte.")

    seen: set[str] = set()
    column_sql: list[str] = []
    for spec in columns:
        name = validate_column_name(spec.name)
        if name in seen:
            raise SchemaError(f"Doppelte Spalte {name!r}.")
        seen.add(name)
        nullable_sql = "" if spec.nullable else " NOT NULL"
        column_sql.append(f"{quote_identifier(name)} {sql_type_for(spec.type)}{nullable_sql}")

    # Store-Spalten woertlich (sie scheitern absichtlich an COLUMN_NAME_RE,
    # deshalb NICHT ueber quote_identifier):
    column_sql.append(f'"{DEDUPE_HASH_COLUMN}" TEXT NOT NULL')
    column_sql.append(f'"{SOURCE_ARTIFACT_COLUMN}" TEXT')

    create_sql = f"CREATE TABLE {quoted_table} ({', '.join(column_sql)})"
    index_sql = (
        f'CREATE UNIQUE INDEX "idx_{table_name}_dedupe_hash" '
        f'ON {quoted_table} ("{DEDUPE_HASH_COLUMN}")'
    )
    return [create_sql, index_sql]
