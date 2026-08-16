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

    `schema` ist ein Objekt: `columns` (Liste aus {name, type, nullable};
    type = text|integer|numeric|date|timestamp|boolean), dazu optional
    `dedupe_columns` (Spalten des Idempotenz-Hashes), `match_column`
    (Eingang der Kategorisierung) und `category_column` (Ziel der Kategorie).

    Eine Spalte `occurred_at` (type `timestamp` oder `date`) ist PFLICHT —
    sie traegt den fachlichen Zeitpunkt jeder Zeile und haengt die Tabelle an
    die Zeitachse (`timeline`). Tabellen- und Spaltennamen muessen
    `^[a-z][a-z0-9_]*$` erfuellen (klein, keine Leerzeichen/Umlaute);
    `_dedupe_hash`/`_source_artifact` vergibt der Server und sind als
    Eingabe verboten.

    Danach fuellt `insert_rows` die Tabelle und `query_table` wertet sie aus:
    Zahlen gehoeren in eine Tabelle und in SQL, nicht in Prosa.
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
    """Importiert Zeilen in eine Tabelle — idempotent ueber den Dedupe-Hash.

    Antwort ist die Bilanz {inserted, skipped}: derselbe Datensatz zweimal
    importiert zaehlt als `skipped`, nicht als Fehler — ein Import darf also
    gefahrlos wiederholt werden. Jede Zeile ist ein Objekt Spaltenname →
    Wert und braucht `occurred_at` (fachlicher Zeitpunkt, nie now()).

    Kategorien entstehen NUR aus Regeln (Regel vor Modell): traegt eine Zeile
    einen Kategorie-Wert ohne passende Regel, antwortet der Server 422 —
    dann die Regel als `new_rules` [{pattern, category, confidence?}]
    mitschicken; sie wird VOR dem Import persistiert und angewandt. Eine
    Kategorie im Kopf zu vergeben ist nie richtig.

    `source_artifact_id` verankert die Herkunft der Zeilen (Roheingabe-
    Artifact). `source_name` verlangt eine hinterlegte Quell-Konvention —
    ohne sie 422 `convention_missing`, dann zuerst `set_convention` rufen.
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
    """Rechnet auf einer Tabelle — read-only SQL; das Ergebnis ist der Beleg.

    Rechne Zahlen NIE selbst aus und tippe sie nie ab: Summen, Mittelwerte,
    Gruppierungen und Vergleiche gehoeren in die Query. Nur Lesen ist
    erlaubt (Engine-Garantie) — INSERT/UPDATE/DELETE/DROP beantwortet der
    Server mit 403, ungueltiges SQL mit 400.

    `format`: `json` (Spalten + Zeilen), `markdown` (fertige Tabelle zum
    Zitieren), `csv`. `limit` deckelt die Zeilen (Default 200, max. 1000);
    `truncated=true` heisst: es gab mehr — dann in SQL aggregieren, statt das
    Cap hochzudrehen.

    Kennst du Schema und Wertebereiche noch nicht, rufe zuerst
    `describe_table`. Soll die Auswertung belegbar bleiben (Zitat, KB-Node),
    nimm `save_query_result` statt Zahlen im Fliesstext.
    """
    client = await _client()
    try:
        data = TableQuery(sql=sql, format=format, limit=limit)
    except ValidationError as exc:
        raise ToolError(f"Ungueltige Eingabe: {_first_error(exc)}") from exc
    return await tables_api.query_table(client, _parse_uuid(table_id, "Tabellen"), data)


@with_tool_log("describe_table")
async def describe_table(table_id: str) -> TableDescription:
    """DER Einstieg vor jeder Query: Schema, Umfang, Wertebereiche, Konventionen.

    Liefert die Spalten mit Typ und Nullable, die Zeilenzahl, je Spalte
    Wertebereiche (z. B. min/max/distinct) und die Quell-Konventionen der
    Area (Einheiten, Notation, Datumsformat). Damit formulierst du eine
    Query, ohne Rohdaten zu laden.

    Lade NIE Rohzeilen (`SELECT *`), nur um dich zu orientieren — das kostet
    Kontext und verleitet dazu, Zahlen abzutippen. Danach `query_table`
    (rechnen) bzw. `save_query_result` (Ergebnis belegen).
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
    """Friert Query + Ergebnis als doc-Artifact ein — die belegbare Auswertung.

    Der Server fuehrt das SQL read-only aus und schreibt Abfrage UND
    Ergebnistabelle in ein doc-Artifact in der Area der Tabelle: die Zahlen
    darin stammen aus der Engine, nicht aus deinem Text. Genau das nimmst du,
    wenn ein Ergebnis zitiert, geteilt oder spaeter geprueft werden soll —
    `query_table` allein hinterlaesst keinen Beleg.

    Die Antwort traegt die Artifact-ID; ein KB-Node zu dieser Auswertung
    referenziert sie als `source_ref=<artifact_id>` (`create_node`).
    `occurred_at` ist der fachliche Zeitpunkt des ERGEBNISSES (z. B. der
    ausgewertete Monat), nie der Aufruf-Zeitpunkt; `occurred_precision`
    steht default auf `day`. Fehlerhaftes oder schreibendes SQL erzeugt KEIN
    Artifact (400/403 vor dem Schreiben).
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
    """Zeitscheiben ueber Artifacts, KB-Nodes und Tabellen-Zeilen.

    Fenster `[from_, to)` — `to` exklusiv, max. 366 Tage —, gebuckelt nach
    `granularity` (day|week|month). Jede Scheibe traegt Anker + Zaehlungen je
    Quellenart; `sources` waehlt die Quellen: `artifacts`, `nodes`,
    `table:<table_id>` (Default: artifacts + nodes).

    Gebuckelt wird IMMER ueber `occurred_at` — den fachlichen Zeitpunkt, nie
    das Erfassungsdatum. Eintraege mit unbekannter Zeit landen im separaten
    `unknown`-Bucket und nie in einer Scheibe: nenne sie getrennt, statt sie
    irgendwo einzusortieren.

    Gleichzeitigkeit ist KEIN Zusammenhang. Aus einer gemeinsamen Zeitscheibe
    folgt hoechstens eine `co_occurs_with`-Kante (`create_edge`) mit Fallzahl
    n >= 20 — nie `supports`, `derived_from` oder eine Kausalaussage im Text.
    """
    client = await _client()
    return await tables_api.timeline(client, from_, to, granularity, sources)


@with_tool_log("set_convention")
async def set_convention(
    area_id: str, source_name: str, convention: dict[str, object]
) -> SourceConventionRead:
    """Legt Einheiten und Notation einer Datenquelle EINMAL fest, statt zu raten.

    `convention` ist ein flaches Objekt, z. B. {"currency": "EUR",
    "decimal_separator": ",", "date_format": "DD.MM.YYYY", "amount_sign":
    "Ausgaben negativ"} — alles, was du sonst pro Zeile erraten muesstest.
    Rate solche Dinge nie im Einzelfall; frag im Zweifel nach und hinterlege
    die Antwort hier.

    `source_name` benennt die Quelle (z. B. `giro_export`). Ein Import mit
    diesem `source_name` wird erst akzeptiert, wenn dazu eine Konvention
    hinterlegt ist (sonst 422 `convention_missing`). Der Aufruf ersetzt eine
    bestehende Konvention vollstaendig; `describe_table` zeigt die
    Konventionen der Area mit an.
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
    """Setzt eine Kategorisierungs-Regel — Regeln sind die SSoT der Kategorien.

    Regel vor Modell: Kategorien entstehen NUR hieraus, nie aus deinem
    Urteil pro Zeile. `pattern` matcht die `match_column` der Tabellen,
    `category` ist das Ergebnis, `confidence` (0-1) optional deine
    Modell-Konfidenz. Upsert-Schluessel ist (Area, Pattern) — dasselbe
    `pattern` erneut gesetzt ERSETZT die bestehende Regel.

    Ein Upsert kategorisiert die bestehenden Zeilen der Area rueckwirkend neu
    (nur nicht-konfligierende) und wird protokolliert. Faellt eine unbekannte
    Kategorie erst beim Import auf, kannst du die Regel auch direkt als
    `new_rules` an `insert_rows` mitgeben. Vorher `list_category_rules`
    lesen, damit du keine bestehende Zuordnung ueberschreibst.
    """
    client = await _client()
    try:
        data = CategoryRuleUpsert(pattern=pattern, category=category, confidence=confidence)
    except ValidationError as exc:
        raise ToolError(f"Ungueltige Eingabe: {_first_error(exc)}") from exc
    return await tables_api.upsert_category_rule(client, _parse_uuid(area_id, "Area"), data)


@with_tool_log("list_category_rules")
async def list_category_rules(area_id: str) -> list[CategoryRuleRead]:
    """Listet die Kategorisierungs-Regeln einer Area (inkl. inaktiver).

    Der Blick in die geltende Kategorien-SSoT: Pattern, Kategorie,
    `confidence`, `active` und wer die Regel gesetzt hat. Lies das, bevor du
    per `upsert_category_rule` eine Regel setzt — der Upsert laeuft auf
    (Area, Pattern) und wuerde eine bestehende Zuordnung ersetzen.
    """
    client = await _client()
    return await tables_api.list_category_rules(client, _parse_uuid(area_id, "Area"))


def register(mcp: FastMCP) -> None:
    """Registriert die 9 Tabellen-/Timeline-Tools an der FastMCP-Instanz.

    Die Tool-Funktionen bleiben modulweite, direkt importier- und aufrufbare
    async-Funktionen (Test-Muster A); hier werden sie lediglich mit
    `output_schema=None` (Payload-Budget, siehe server.py) angehaengt.
    `promote_artifact` gehoert fachlich dazu, wird aber in `tools/kb.py`
    registriert (dort implementiert, WP9).
    """
    for fn in (
        create_table,
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
