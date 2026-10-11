"""Tabellen-/Timeline-MCP-Tools (ADR-0049, WP19) — Tools 15-23 des Plans.

Drittes Submodul nach Architektur-Entscheidung 3.2 (Muster aus WP8/WP9,
`tools/workarea.py` und `tools/kb.py`): modulweite
`@with_tool_log`-async-Funktionen (fuer Tests direkt aufrufbar),
`register(mcp)` haengt sie an die FastMCP-Instanz. `build_client` wird zur
LAUFZEIT ueber das `server`-Modul aufgeloest (`_client()` importiert es erst
im Tool-Aufruf) — das haelt den Import zyklisch-sicher in BEIDE Richtungen
und laesst den bestehenden Test-monkeypatch-Pfad
(`monkeypatch.setattr(server, "build_client", ...)`) unveraendert greifen.

Die zehnte Tool-Zeile des Plans (`promote_artifact`) lebt weiterhin in
`tools/kb.py` und wird dort mit WP19 registriert — die REST-Route existiert
jetzt.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import ValidationError

from who2be_mcp.client import ApiClient
from who2be_mcp.clients import tables as tables_api
from who2be_mcp.clients.tables import RowsInsertResult
from who2be_mcp.core_logging import with_tool_log
from who2be_mcp.tools.area_ref import parse_area_id, resolve_private_area_id
from who2be_models import (
    ArtifactRead,
    CategoryRuleRead,
    CategoryRuleUpsert,
    NewRule,
    OccurredPrecision,
    QueryFormat,
    QueryResult,
    RowsInsert,
    SaveQueryResult,
    SourceConventionRead,
    SourceConventionSet,
    TableDescription,
    TableQuery,
    TableSchema,
    TimelineGranularity,
    TimelineResult,
    WaTableCreate,
    WaTableRead,
)


async def _client() -> ApiClient:
    """Baut den API-Client fuer den aktuellen Aufruf ueber `server.build_client`.

    Der `server`-Import liegt bewusst IM Aufruf (nicht auf Modul-Ebene):
    `server.py` importiert dieses Modul fuer `register(mcp)` — ein
    Modul-Level-Rueck-Import braeche, sobald `tools.tables` zuerst geladen
    wird. Der Laufzeit-Zugriff ueber das Modul-Attribut haelt zugleich den
    Test-Pfad intakt (monkeypatch von `server.build_client`).
    """
    from who2be_mcp import server

    return await server.build_client()


def _parse_uuid(value: str, label: str) -> UUID:
    """Parst eine UUID oder wirft einen fuer Agenten lesbaren `ToolError`."""
    try:
        return UUID(value)
    except ValueError as exc:
        raise ToolError(f"Ungueltige {label}-UUID: '{value}'.") from exc


def _first_error(exc: ValidationError) -> str:
    errors = exc.errors()
    return str(errors[0]["msg"]) if errors else "Ungueltige Eingabe."


@with_tool_log("create_table")
async def create_table(area_id: str, name: str, schema: dict[str, object]) -> WaTableRead:
    """Legt eine Tabelle fuer strukturierte Daten in einer Area an.

    `schema.columns`: {name, type, nullable}, type text, integer, numeric, date, timestamp oder
    boolean; optional `dedupe_columns`, `match_column`, `category_column`. Pflicht ist eine
    Spalte `occurred_at` (date oder timestamp). Namen: `^[a-z][a-z0-9_]*$`. Danach `insert_rows`
    und `query_table`.
    """
    client = await _client()
    try:
        # Konstruktion ueber den Wire-Alias `schema` (Feldname ist `schema_`,
        # weil `BaseModel.schema` in Pydantic belegt ist).
        data = WaTableCreate(name=name, schema=TableSchema.model_validate(schema))
    except ValidationError as exc:
        raise ToolError(f"Ungueltige Eingabe: {_first_error(exc)}") from exc
    return await tables_api.create_table(client, _parse_uuid(area_id, "Area"), data)


@with_tool_log("insert_rows")
async def insert_rows(
    table_id: str,
    rows: list[dict[str, object]],
    source_artifact_id: str | None = None,
    source_name: str | None = None,
    new_rules: list[NewRule] | None = None,
) -> RowsInsertResult:
    """Importiert Zeilen in eine Tabelle, idempotent ueber den Dedupe-Hash.

    Antwort {inserted, skipped}; Wiederholen ist gefahrlos. Jede Zeile braucht `occurred_at`.
    Kategorien nur ueber Regeln: fehlt eine, antwortet der Server 422, dann `new_rules`
    [{pattern, category}] mitschicken. `source_name` verlangt eine Konvention
    (`set_convention`).
    """
    client = await _client()
    try:
        data = RowsInsert(
            rows=rows,
            source_artifact_id=(
                None if source_artifact_id is None else _parse_uuid(source_artifact_id, "Artifact")
            ),
            source_name=source_name,
            new_rules=new_rules or [],
        )
    except ValidationError as exc:
        raise ToolError(f"Ungueltige Eingabe: {_first_error(exc)}") from exc
    return await tables_api.insert_rows(client, _parse_uuid(table_id, "Tabellen"), data)


@with_tool_log("query_table")
async def query_table(
    table_id: str,
    sql: str,
    format: QueryFormat = QueryFormat.json,
    limit: int = 200,
) -> QueryResult:
    """Rechnet auf einer Tabelle mit read-only SQL; das Ergebnis ist der Beleg.

    Zahlen nie selbst ausrechnen oder abtippen: Summen und Gruppierungen gehoeren in die Query.
    Schreibendes SQL: 403. `format`: json, markdown oder csv; `limit` Default 200, max. 1000;
    `truncated=true` heisst: in SQL aggregieren. Fuer zitierbare Ergebnisse `save_query_result`.
    """
    client = await _client()
    try:
        data = TableQuery(sql=sql, format=format, limit=limit)
    except ValidationError as exc:
        raise ToolError(f"Ungueltige Eingabe: {_first_error(exc)}") from exc
    return await tables_api.query_table(client, _parse_uuid(table_id, "Tabellen"), data)


@with_tool_log("list_tables")
async def list_tables(area_id: str | None = None) -> list[WaTableRead]:
    """Tabellen einer Area mit ID und Schema, ohne Zeilen.

    Am Anfang aufrufen, statt eine Tabelle neu anzulegen: Tabellen erscheinen weder in
    `search_workarea` noch in `timeline`. Danach `describe_table`, dann `query_table`.
    `area_id=None` ist die private Area.
    """
    client = await _client()
    parsed_area = parse_area_id(area_id)
    if parsed_area is None:
        parsed_area = await resolve_private_area_id(client)
    return await tables_api.list_tables(client, parsed_area)


@with_tool_log("delete_table")
async def delete_table(table_id: str) -> str:
    """Loescht eine Tabelle samt Zeilen endgueltig.

    Gespeicherte Auswertungen (`save_query_result`), Regeln und Konventionen bleiben.
    """
    client = await _client()
    parsed = _parse_uuid(table_id, "Tabellen")
    await tables_api.delete_table(client, parsed)
    return f"Tabelle {parsed} geloescht."


@with_tool_log("describe_table")
async def describe_table(table_id: str) -> TableDescription:
    """Schema, Zeilenzahl, Wertebereiche und Quell-Konventionen einer Tabelle.

    Vor jeder Query aufrufen, statt zur Orientierung Rohzeilen zu laden. Danach `query_table`.
    """
    client = await _client()
    return await tables_api.describe_table(client, _parse_uuid(table_id, "Tabellen"))


@with_tool_log("save_query_result")
async def save_query_result(
    table_id: str,
    sql: str,
    title: str,
    occurred_at: datetime,
    occurred_precision: OccurredPrecision = OccurredPrecision.day,
    limit: int = 200,
) -> ArtifactRead:
    """Friert Query und Ergebnis als WorkArea-Dokument ein, als zitierbaren Beleg.

    Fuer Ergebnisse, die zitiert oder geprueft werden; `query_table` hinterlaesst keinen Beleg.
    Ein KB-Node verweist mit `source_ref=<artifact_id>` darauf. `occurred_at` ist der Zeitpunkt
    des Ergebnisses.
    """
    client = await _client()
    try:
        data = SaveQueryResult(
            sql=sql,
            title=title,
            occurred_at=occurred_at,
            occurred_precision=occurred_precision,
            limit=limit,
        )
    except ValidationError as exc:
        raise ToolError(f"Ungueltige Eingabe: {_first_error(exc)}") from exc
    return await tables_api.save_query_result(client, _parse_uuid(table_id, "Tabellen"), data)


@with_tool_log("timeline")
async def timeline(
    from_: datetime,
    to: datetime,
    sources: list[str] | None = None,
    granularity: TimelineGranularity = TimelineGranularity.day,
) -> TimelineResult:
    """Zeitscheiben ueber Artifacts, KB-Nodes und Tabellenzeilen nach `occurred_at`.

    Fenster `[from_, to)`, max. 366 Tage, `granularity` day, week oder month; `sources`:
    `artifacts`, `nodes`, `table:<id>`. Unbekannte Zeiten stehen im eigenen `unknown`-Bucket;
    nenne sie getrennt. Gleichzeitigkeit ist kein Zusammenhang: hoechstens `co_occurs_with` mit
    n >= 20.
    """
    client = await _client()
    return await tables_api.timeline(client, from_, to, granularity, sources)


@with_tool_log("set_convention")
async def set_convention(
    area_id: str, source_name: str, convention: dict[str, object]
) -> SourceConventionRead:
    """Legt Einheiten und Notation einer Datenquelle einmal fest, statt zu raten.

    `convention` ist ein flaches Objekt (Waehrung, Dezimaltrenner, Datumsformat, Vorzeichen),
    `source_name` benennt die Quelle. Ersetzt eine bestehende Konvention; Importe mit
    `source_name` brauchen sie.
    """
    client = await _client()
    try:
        data = SourceConventionSet(convention=convention)
    except ValidationError as exc:
        raise ToolError(f"Ungueltige Eingabe: {_first_error(exc)}") from exc
    return await tables_api.set_convention(client, _parse_uuid(area_id, "Area"), source_name, data)


@with_tool_log("upsert_category_rule")
async def upsert_category_rule(
    area_id: str, pattern: str, category: str, confidence: float | None = None
) -> CategoryRuleRead:
    """Setzt eine Kategorisierungs-Regel; Kategorien entstehen nur aus Regeln.

    `pattern` trifft die `match_column`, `category` ist das Ergebnis, `confidence` optional.
    Dasselbe Pattern in derselben Area ersetzt die Regel und kategorisiert bestehende Zeilen
    neu. Vorher `list_category_rules` lesen.
    """
    client = await _client()
    try:
        data = CategoryRuleUpsert(pattern=pattern, category=category, confidence=confidence)
    except ValidationError as exc:
        raise ToolError(f"Ungueltige Eingabe: {_first_error(exc)}") from exc
    return await tables_api.upsert_category_rule(client, _parse_uuid(area_id, "Area"), data)


@with_tool_log("list_category_rules")
async def list_category_rules(area_id: str) -> list[CategoryRuleRead]:
    """Listet die Kategorisierungs-Regeln einer Area, auch inaktive.

    Pattern, Kategorie, `confidence`, `active` und Urheber. Vor `upsert_category_rule` lesen:
    dasselbe Pattern ersetzt die Regel.
    """
    client = await _client()
    return await tables_api.list_category_rules(client, _parse_uuid(area_id, "Area"))


def register(mcp: FastMCP) -> None:
    """Registriert die 11 Tabellen-/Timeline-Tools an der FastMCP-Instanz.

    Die Tool-Funktionen bleiben modulweite, direkt importier- und aufrufbare
    async-Funktionen (Test-Muster A); hier werden sie lediglich mit
    `output_schema=None` (Payload-Budget, siehe server.py) angehaengt.
    `promote_artifact` gehoert fachlich dazu, wird aber in `tools/kb.py`
    registriert (dort implementiert, WP9).
    """
    for fn in (
        create_table,
        list_tables,
        delete_table,
        insert_rows,
        query_table,
        describe_table,
        save_query_result,
        timeline,
        set_convention,
        upsert_category_rule,
        list_category_rules,
    ):
        mcp.tool(output_schema=None)(fn)
