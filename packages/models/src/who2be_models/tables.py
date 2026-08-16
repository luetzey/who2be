"""Tabellen-Store-Models (ADR-0049) — Katalog, Zeilen-Import, Read-only-Query.

Der Tabellen-Store haelt strukturierte Agent-Daten in SQLite (eine Datei pro
Area); Postgres traegt nur den Katalog (`wa_table.schema_json` = das hier
validierte `TableSchema`). Weil Spaltennamen VERBATIM in SQLite-DDL eingehen,
sind sie hart auf SQL-sichere Identifier (`^[a-z][a-z0-9_]*$`) beschraenkt —
das Modell ist die erste Verteidigungslinie, der Engine-Authorizer (ADR-0049)
die zweite. `occurred_at` ist Pflichtspalte jeder Tabelle (Timeline N);
`_dedupe_hash`/`_source_artifact` vergibt der SERVER (idempotenter Import K,
Row-Provenance M2) — als Eingabe-Spalten sind sie reserviert und verboten.

Abfragen (`TableQuery`) sind read-only als ENGINE-Garantie (`PRAGMA
query_only` + Authorizer, 403 `query_not_readonly`) — das Modell begrenzt nur
Laenge und Zeilen-Cap. Kategorisierung folgt „Regel VOR Modell" (Anforderung
L): `RowsInsert.new_rules` persistiert neue Regeln, DANN werden sie
angewandt; ein Kategorie-Wert ohne matchende Regel ist 422 `rule_required`.
Quell-Konventionen (M2) sind Pflicht, sobald `source_name` gesetzt ist
(422 `convention_missing`) — geraten wird nie.

`AccessLogEntry` ist das Read-Modell des Auto-Zugriffslogs
(`agent_access_log`, 0079, User-Entscheidung 6) fuer die Betreiber-/
Compliance-Sicht ab WP14.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from who2be_models.workarea import OccurredPrecision, Sensitivity

# SQL-Identifier-Sicherheit: Spalten- und Tabellennamen gehen verbatim in
# SQLite-DDL ein — nur Kleinbuchstaben, Ziffern, Unterstrich, kein
# fuehrender Unterstrich/keine fuehrende Ziffer (kein Quoting noetig).
TABLE_IDENTIFIER_PATTERN = r"^[a-z][a-z0-9_]*$"
# Vom Server vergebene bzw. SQLite-eigene Spalten — als Eingabe verboten.
# `_dedupe_hash`/`_source_artifact` scheitern zusaetzlich schon am
# Identifier-Pattern (fuehrender Unterstrich); `rowid` faengt NUR diese Liste.
RESERVED_COLUMN_NAMES = frozenset({"_dedupe_hash", "_source_artifact", "rowid"})
# Obergrenzen (DoS-Schutz, F-01-Linie): Spaltenzahl pro Tabelle, Zeilen pro
# Import, SQL-Laenge und Zeilen-Cap pro Query, Keys pro Konvention.
TABLE_MAX_COLUMNS = 40
ROWS_INSERT_MAX_ROWS = 1_000
TABLE_QUERY_SQL_MAX_LENGTH = 4_000
TABLE_QUERY_MAX_LIMIT = 1_000
CONVENTION_MAX_KEYS = 50


class TableColumnType(StrEnum):
    """Typen-Allowlist der Tabellen-Spalten (ADR-0049).

    Bewusst klein gehalten: alles, was SQLite verlustfrei traegt und die
    Timeline/Aggregation braucht — kein blob, kein json in Spalten.
    """

    text = "text"
    integer = "integer"
    numeric = "numeric"
    date = "date"
    timestamp = "timestamp"
    boolean = "boolean"


class TableColumn(BaseModel):
    """Eine Spalte eines Tabellen-Schemas (`wa_table.schema_json`).

    `name` ist auf SQL-sichere Identifier beschraenkt (s. Modul-Docstring) —
    er wird ohne Quoting in die SQLite-DDL uebernommen.
    """

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    name: str = Field(min_length=1, max_length=64, pattern=TABLE_IDENTIFIER_PATTERN)
    type: TableColumnType
    nullable: bool = True


class TableSchema(BaseModel):
    """Das Schema einer Tabelle — der Postgres-Katalogteil (ADR-0049).

    Invarianten (Validator):

    - Spaltennamen sind eindeutig und nie reserviert (`RESERVED_COLUMN_NAMES`).
    - Eine ``occurred_at``-Spalte (type ``timestamp`` | ``date``) ist PFLICHT —
      jede Zeile traegt ihren fachlichen Zeitpunkt (Timeline-Anforderung N).
    - `dedupe_columns` (idempotenter Import K), `match_column`
      (Kategorisierungs-Eingang L) und `category_column` (Kategorie-Ziel L)
      muessen existierende Spalten benennen.
    """

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    columns: list[TableColumn] = Field(min_length=1, max_length=TABLE_MAX_COLUMNS)
    dedupe_columns: list[str] = Field(default_factory=list)
    match_column: str | None = None
    category_column: str | None = None

    @model_validator(mode="after")
    def _check_schema_invariants(self) -> Self:
        names = [column.name for column in self.columns]
        if len(names) != len(set(names)):
            raise ValueError("Spaltennamen muessen eindeutig sein.")
        reserved = sorted(set(names) & RESERVED_COLUMN_NAMES)
        if reserved:
            raise ValueError(f"Reservierte Spaltennamen sind verboten: {', '.join(reserved)}.")
        occurred = next((column for column in self.columns if column.name == "occurred_at"), None)
        if occurred is None:
            raise ValueError("Eine `occurred_at`-Spalte ist Pflicht (Timeline-Anforderung N).")
        if occurred.type not in (TableColumnType.timestamp, TableColumnType.date):
            raise ValueError("`occurred_at` muss type 'timestamp' oder 'date' haben.")
        known = set(names)
        unknown_dedupe = sorted(set(self.dedupe_columns) - known)
        if unknown_dedupe:
            raise ValueError(f"Unbekannte dedupe_columns: {', '.join(unknown_dedupe)}.")
        if self.match_column is not None and self.match_column not in known:
            raise ValueError(f"Unbekannte match_column: {self.match_column}.")
        if self.category_column is not None and self.category_column not in known:
            raise ValueError(f"Unbekannte category_column: {self.category_column}.")
        return self


class WaTableCreate(BaseModel):
    """Eingabe fuer `POST .../work-areas/{area_id}/tables` — legt eine Tabelle an.

    `name` unterliegt derselben Identifier-Regel wie Spaltennamen (er wird
    der SQLite-Tabellenname). Das Feld heisst im Wire-Format ``schema``
    (Alias) — `schema_` nur, weil `BaseModel.schema` in Pydantic belegt ist.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str = Field(min_length=1, max_length=100, pattern=TABLE_IDENTIFIER_PATTERN)
    schema_: TableSchema = Field(alias="schema")


class WaTableRead(BaseModel):
    """Eine Tabelle im aktuellen Stand (`wa_table` + optionale Zeilenzahl).

    `row_count` ist None, wenn der Endpunkt die SQLite-Datei nicht
    mitzaehlt (List-Pfad); der describe-Pfad befuellt es.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    workspace_id: UUID
    area_id: UUID
    name: str
    schema_: TableSchema = Field(alias="schema")
    row_count: int | None = None
    created_at: datetime
    updated_at: datetime


class NewRule(BaseModel):
    """Eine mit dem Import mitgelieferte Kategorisierungs-Regel (L).

    Wird VOR der Anwendung persistiert (`wa_category_rule`, created_by =
    Akteur-Kennung serverseitig); `confidence` traegt die Modell-Konfidenz.
    """

    model_config = ConfigDict(extra="forbid")

    pattern: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=100)
    confidence: float | None = Field(default=None, ge=0, le=1)


class RowsInsert(BaseModel):
    """Eingabe fuer `POST .../wa-tables/{id}/rows` — idempotenter Zeilen-Import.

    Zeilen werden gegen das `TableSchema` geprueft (Server); der Dedupe-Hash
    ueber `dedupe_columns` macht Doppel-Importe zu No-ops (K).
    `source_artifact_id` verweist auf das Roheingabe-Artifact (M2,
    Row-Provenance `_source_artifact`); `source_name` verlangt eine
    hinterlegte Quell-Konvention (422 `convention_missing`).
    """

    model_config = ConfigDict(extra="forbid")

    rows: list[dict[str, object]] = Field(min_length=1, max_length=ROWS_INSERT_MAX_ROWS)
    source_artifact_id: UUID | None = None
    source_name: str | None = Field(default=None, max_length=100)
    new_rules: list[NewRule] = Field(default_factory=list)


class QueryFormat(StrEnum):
    """Ausgabeformat einer Tabellen-Query (agentengerecht, Entscheidung 7)."""

    json = "json"
    markdown = "markdown"
    csv = "csv"


class TableQuery(BaseModel):
    """Eingabe fuer `POST .../wa-tables/{id}/query` — read-only SQL.

    Read-only ist ENGINE-Garantie (Authorizer + `PRAGMA query_only`,
    403 `query_not_readonly`) — das Modell begrenzt nur SQL-Laenge und
    Zeilen-Cap (`limit`, Default 200).
    """

    model_config = ConfigDict(extra="forbid")

    sql: str = Field(min_length=1, max_length=TABLE_QUERY_SQL_MAX_LENGTH)
    format: QueryFormat = QueryFormat.json
    limit: int = Field(default=200, ge=1, le=TABLE_QUERY_MAX_LIMIT)


class SaveQueryResult(BaseModel):
    """Eingabe fuer `POST .../wa-tables/{id}/save-result` — Query einfrieren (M-Ersatz).

    Entscheidung 7 (kein Chart-Rendering): der SERVER fuehrt das SQL read-only
    aus und persistiert Query + eingefrorenes Ergebnis als doc-Artifact in der
    Area der Tabelle — die Zahlen im Artifact stammen aus der Engine, nie aus
    Modell-Text (Spec §10.6). `occurred_at` ist der fachliche Zeitpunkt des
    Ergebnisses (Pflicht, kein now()-Fallback — Muster `ArtifactCreate`);
    Default-Praezision `day`, weil Auswertungen typisch tagesgenau sind.
    `sql`/`limit` unterliegen denselben Grenzen wie `TableQuery`.
    """

    model_config = ConfigDict(extra="forbid")

    sql: str = Field(min_length=1, max_length=TABLE_QUERY_SQL_MAX_LENGTH)
    title: str = Field(min_length=1, max_length=300)
    occurred_at: datetime
    occurred_precision: OccurredPrecision = OccurredPrecision.day
    limit: int = Field(default=200, ge=1, le=TABLE_QUERY_MAX_LIMIT)


class QueryResult(BaseModel):
    """Ergebnis einer Tabellen-Query.

    `rows` ist bei format='json' gefuellt, `rendered` bei
    markdown/csv (genau eine der beiden Darstellungen). `truncated` zeigt
    an, dass das Zeilen-Cap (`limit`) das Ergebnis beschnitten hat.
    """

    model_config = ConfigDict(from_attributes=True)

    columns: list[str]
    rows: list[list[object]] | None = None
    rendered: str | None = None
    row_count: int
    truncated: bool


class SourceConventionSet(BaseModel):
    """Eingabe fuer `PUT .../conventions/{source}` — Quell-Konvention (M2).

    `convention` traegt Einheiten, Notation, Dezimal-/Datumsformat der
    Quelle als flaches JSON-Objekt (max. `CONVENTION_MAX_KEYS` Keys —
    DoS-Schutz, kein fachliches Limit).
    """

    model_config = ConfigDict(extra="forbid")

    convention: dict[str, object]

    @model_validator(mode="after")
    def _check_convention_size(self) -> Self:
        if len(self.convention) > CONVENTION_MAX_KEYS:
            raise ValueError(f"Konvention hat zu viele Keys (max. {CONVENTION_MAX_KEYS}).")
        return self


class SourceConventionRead(BaseModel):
    """Eine Quell-Konvention im aktuellen Stand (`wa_source_convention`)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    area_id: UUID
    source_name: str
    convention: dict[str, object]
    # Mensch, der die Konvention gesetzt hat (None = System-Seed).
    created_by: UUID | None = None
    created_at: datetime
    updated_at: datetime


class TableDescription(BaseModel):
    """Antwort von `GET .../wa-tables/{id}` (describe) — Kontext fuer Agenten.

    `column_stats` liefert pro Spalte Wertebereiche/Verteilung (z. B. min,
    max, distinct) aus der SQLite-Datei; `conventions` die hinterlegten
    Quell-Konventionen der Area — genug Kontext, um Queries ohne
    Rohdaten-Dump zu formulieren (Anforderung K/M).
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    schema_: TableSchema = Field(alias="schema")
    row_count: int
    column_stats: dict[str, dict[str, object]] = Field(default_factory=dict)
    conventions: list[SourceConventionRead] = Field(default_factory=list)


class CategoryRuleRead(BaseModel):
    """Eine Kategorisierungs-Regel im aktuellen Stand (`wa_category_rule`).

    `created_by` ist die Akteur-Kennung als Text
    (``agent:<id>`` | ``user:<id>`` | ``model:<id>``), analog
    `wa_artifact.updated_by`.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    area_id: UUID
    pattern: str
    category: str
    created_by: str
    confidence: float | None = None
    active: bool
    created_at: datetime
    updated_at: datetime


class CategoryRuleUpsert(BaseModel):
    """Eingabe fuer `POST .../category-rules` — Regel anlegen/ersetzen (L).

    Upsert-Schluessel ist (area, pattern) — `UNIQUE (area_id, pattern)` in
    0078 macht ihn deterministisch. Die Akteur-Kennung (`created_by`) setzt
    der Server aus dem Token, nie der Client.
    """

    model_config = ConfigDict(extra="forbid")

    pattern: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=100)
    confidence: float | None = Field(default=None, ge=0, le=1)


class AccessRefKind(StrEnum):
    """Art des Elements im Zugriffslog (`agent_access_log.ref_kind`)."""

    artifact = "artifact"
    node = "node"
    table = "table"
    blob = "blob"


class AccessOperation(StrEnum):
    """Zugriffsart im Zugriffslog (`agent_access_log.operation`)."""

    read = "read"
    write = "write"


class AccessLogEntry(BaseModel):
    """Ein Eintrag des Auto-Zugriffslogs (`agent_access_log`, 0079) — read-only.

    Vom Server geschrieben (User-Entscheidung 6), dedupliziert pro
    (Agent, Element, Operation, Kalendertag); `first_at` ist der erste
    Zugriff des Tages, `sensitivity_at_access` der Server-Snapshot zum
    Zugriffszeitpunkt. Konsumiert ab WP14 (Betreiber-/Compliance-Query).
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_id: UUID
    ref_kind: AccessRefKind
    ref_id: str
    operation: AccessOperation
    sensitivity_at_access: Sensitivity
    access_date: date
    first_at: datetime
