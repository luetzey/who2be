"""Tabellen-/Timeline-REST-Aufrufe des MCP-Servers (ADR-0049, WP19).

Freie Funktionen statt weiterer `ApiClient`-Methoden (Architektur-
Entscheidung 3.2, Muster `clients/workarea.py`): `client.py` bleibt
unangetastet, jede neue Domain liegt in `clients/<domain>.py`. Die Funktionen
nutzen bewusst die privaten Request-Helper des `ApiClient` (`_get`/`_write`
und `_workspace_prefix`) — dieses Modul ist ein paket-internes Friend-Modul
DESSELBEN Adapters (gleiche Fehler-Uebersetzung in `ToolError`, gleiche
Timeouts), keine externe API.

Pfade: Router `wa_tables.py` (Tabellen, Konventionen, Kategorie-Regeln) und
`wa_timeline.py` (Zeitachse) unter `/v1/workspaces/{ws_id}`.
"""

from __future__ import annotations

from datetime import datetime
from urllib.parse import quote
from uuid import UUID

from pydantic import BaseModel

from who2be_mcp.client import ApiClient
from who2be_models import (
    ArtifactRead,
    CategoryRuleRead,
    CategoryRuleUpsert,
    QueryResult,
    RowsInsert,
    SaveQueryResult,
    SourceConventionRead,
    SourceConventionSet,
    TableDescription,
    TableQuery,
    TimelineGranularity,
    TimelineResult,
    WaTableCreate,
    WaTableRead,
)


class RowsInsertResult(BaseModel):
    """Bilanz eines Zeilen-Imports (``{inserted, skipped}``, Spec K).

    Spiegelt das gleichnamige lokale Antwort-Modell des Routers
    (`routers/wa_tables.py`) — dort bewusst router-lokal, hier bewusst
    client-lokal: die Bilanz ist ein Endpunkt-Detail, kein geteiltes
    Domain-Model, und wandert deshalb nicht nach `who2be_models`.
    """

    inserted: int
    skipped: int


async def create_table(client: ApiClient, area_id: UUID, data: WaTableCreate) -> WaTableRead:
    """`POST .../work-areas/{area_id}/tables` — Katalog-Zeile + SQLite-DDL
    (atomar); Namens-Kollision in der Area → 409 als `ToolError`.

    Bewusst `_request` statt `_write`: der geteilte Write-Helper serialisiert
    mit `model_dump(mode="json")` OHNE `by_alias`, und `WaTableCreate` ist das
    einzige Write-Modell dieser Domain mit Alias (Feld `schema_`, Wire-Key
    `schema` — `BaseModel.schema` ist in Pydantic belegt). Ohne `by_alias`
    ginge `schema_` raus; das kaeme nur ueber `populate_by_name` durch und
    waere nicht das vom Router deklarierte Wire-Format.
    """
    response = await client._request(
        "POST",
        f"{client._workspace_prefix}/work-areas/{area_id}/tables",
        json=data.model_dump(mode="json", by_alias=True),
    )
    return WaTableRead.model_validate(response.json())


async def insert_rows(client: ApiClient, table_id: UUID, data: RowsInsert) -> RowsInsertResult:
    """`POST .../wa-tables/{id}/rows` — idempotenter Import; Doppel-Importe
    zaehlen als `skipped` (Dedupe-Hash), Schema-/Regel-/Konventions-Verstoesse
    kommen als 422-`ToolError` mit dem API-`detail` beim Agenten an."""
    payload = await client._write(
        "POST", f"{client._workspace_prefix}/wa-tables/{table_id}/rows", data
    )
    return RowsInsertResult.model_validate(payload)


async def query_table(client: ApiClient, table_id: UUID, data: TableQuery) -> QueryResult:
    """`POST .../wa-tables/{id}/query` — read-only SQL (Engine-Garantie,
    ADR-0049). Semantisch ein Read, technisch POST (SQL im Body);
    Schreibversuche antwortet die API mit 403 `query_not_readonly`."""
    payload = await client._write(
        "POST", f"{client._workspace_prefix}/wa-tables/{table_id}/query", data
    )
    return QueryResult.model_validate(payload)


async def save_query_result(
    client: ApiClient, table_id: UUID, data: SaveQueryResult
) -> ArtifactRead:
    """`POST .../wa-tables/{id}/save-result` — Query + Ergebnis serverseitig als
    doc-Artifact einfrieren (WP16, M-Ersatz). Fehlerhaftes SQL erzeugt KEIN
    Artifact (400/403 vor dem Schreiben)."""
    payload = await client._write(
        "POST", f"{client._workspace_prefix}/wa-tables/{table_id}/save-result", data
    )
    return ArtifactRead.model_validate(payload)


async def list_tables(client: ApiClient, area_id: UUID) -> list[WaTableRead]:
    """`GET .../work-areas/{area_id}/tables` — Katalog der Area (ohne Zeilen).

    Der Discovery-Einstieg: ohne ihn ist eine Tabelle nach dem Anlegen fuer
    einen Agenten strukturell nicht wiederauffindbar (Befund 2026-08-17) —
    die Suche indiziert Artifact-Passagen, die Timeline verlangt die ID
    bereits.
    """
    payload = await client._get(f"{client._workspace_prefix}/work-areas/{area_id}/tables")
    return [WaTableRead.model_validate(item) for item in payload]


async def delete_table(client: ApiClient, table_id: UUID) -> None:
    """`DELETE .../wa-tables/{id}` — Tabelle + Daten endgueltig."""
    await client._request("DELETE", f"{client._workspace_prefix}/wa-tables/{table_id}")


async def describe_table(client: ApiClient, table_id: UUID) -> TableDescription:
    """`GET .../wa-tables/{id}` — Schema, Zeilenzahl, Wertebereiche und die
    Quell-Konventionen der Area (Kontext ohne Rohdaten-Dump)."""
    payload = await client._get(f"{client._workspace_prefix}/wa-tables/{table_id}")
    return TableDescription.model_validate(payload)


async def timeline(
    client: ApiClient,
    window_start: datetime,
    window_end: datetime,
    granularity: TimelineGranularity,
    sources: list[str] | None = None,
) -> TimelineResult:
    """`GET .../timeline?from_=&to=&granularity=&sources=` — Zeitscheiben ueber
    Artifacts/Nodes/Tabellen + unknown-Bucket.

    Der Query-Key heisst serverseitig `from_` (Parametername des Routers, kein
    Alias). `sources` geht als EIN CSV-Wert raus — der Router akzeptiert CSV
    ODER Mehrfach-Parameter, CSV haelt die URL kurz.
    """
    params: dict[str, str] = {
        "from_": window_start.isoformat(),
        "to": window_end.isoformat(),
        "granularity": granularity.value,
    }
    if sources:
        params["sources"] = ",".join(sources)
    payload = await client._get(f"{client._workspace_prefix}/timeline", params=params)
    return TimelineResult.model_validate(payload)


async def set_convention(
    client: ApiClient, area_id: UUID, source_name: str, data: SourceConventionSet
) -> SourceConventionRead:
    """`PUT .../work-areas/{area_id}/conventions/{source_name}` — anlegen/ersetzen.

    `source_name` ist freier Text und wird als Pfadsegment prozentkodiert
    (`safe=""`, also auch `/`) — ein Name wie ``bank/giro`` darf den Pfad nicht
    umbiegen.
    """
    path = (
        f"{client._workspace_prefix}/work-areas/{area_id}/conventions/{quote(source_name, safe='')}"
    )
    payload = await client._write("PUT", path, data)
    return SourceConventionRead.model_validate(payload)


async def upsert_category_rule(
    client: ApiClient, area_id: UUID, data: CategoryRuleUpsert
) -> CategoryRuleRead:
    """`POST .../work-areas/{area_id}/category-rules` — Upsert auf (Area, Pattern);
    201 bei Anlage, 200 bei Ersetzung (beides Erfolg, kategorisiert rueckwirkend)."""
    payload = await client._write(
        "POST", f"{client._workspace_prefix}/work-areas/{area_id}/category-rules", data
    )
    return CategoryRuleRead.model_validate(payload)


async def list_category_rules(client: ApiClient, area_id: UUID) -> list[CategoryRuleRead]:
    """`GET .../work-areas/{area_id}/category-rules` — Regeln der Area (inkl. inaktiver)."""
    payload = await client._get(f"{client._workspace_prefix}/work-areas/{area_id}/category-rules")
    return [CategoryRuleRead.model_validate(item) for item in payload]
