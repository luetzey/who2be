"""Tabellen-Store-Endpunkte (ADR-0049, WP13 — Spec K).

Pfade unter `/v1/workspaces/{ws_id}` (Prefix aus `main.py`):

- ``POST /work-areas/{area_id}/tables`` — Tabelle anlegen (Katalog + DDL).
- ``GET /work-areas/{area_id}/tables`` — Katalog-Liste der Area.
- ``POST /wa-tables/{table_id}/rows`` — idempotenter Zeilen-Import
  (``{inserted, skipped}``, Spec K).
- ``POST /wa-tables/{table_id}/query`` — read-only SQL (Engine-Garantie;
  Formate json|markdown|csv, Zeilen-Cap + `truncated`).
- ``POST /wa-tables/{table_id}/save-result`` — Query + eingefrorenes Ergebnis
  als doc-Artifact in der Area der Tabelle (WP16, M-Ersatz — Entscheidung 7).
- ``GET /wa-tables/{table_id}`` — describe (Schema, Zeilenzahl,
  Wertebereiche, Area-Konventionen).

Rate-Limit-Paritaet (Muster `wa_artifacts`): Mutationen
`@limiter.limit(write_limit)` + `request` als erster Parameter; agent-lesbare
Pfade `enforce_mcp_read_limit` — auch der POST-Query-Pfad ist semantisch ein
Read. Autorisierung liegt im Service; der Router uebersetzt nur die
Domain-Exceptions (`TableRowsInvalid` → 422, `TableQueryInvalid` → 400) und
`None` → 404 (kein Existenz-Leak, Muster `routers/kb.py`).
"""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from who2be_api.core.db import get_pool
from who2be_api.core.rate_limit import limiter, write_limit
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.repositories.wa_table_repository import PgWaTableRepository
from who2be_api.routers.wa_artifacts import get_wa_artifact_service
from who2be_api.services.mcp_limit_service import enforce_mcp_read_limit
from who2be_api.services.tablestore_provider import get_table_store
from who2be_api.services.wa_artifacts import WaArtifactService
from who2be_api.services.wa_tables import TableQueryInvalid, TableRowsInvalid, WaTableService
from who2be_models import (
    ArtifactRead,
    QueryResult,
    RowsInsert,
    SaveQueryResult,
    TableDescription,
    TableQuery,
    WaTableCreate,
    WaTableRead,
)

router = APIRouter(tags=["wa-tables"])


class RowsInsertResult(BaseModel):
    """Bilanz eines Imports: wie viele Zeilen neu, wie viele Duplikate.

    Lokales Antwort-Modell (Router-Ebene, wie `Health` in `main.py`) — das
    MCP-Tool `insert_rows` (WP19) reicht es unveraendert durch.
    """

    inserted: int
    skipped: int


def get_wa_table_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
    artifact_service: Annotated[WaArtifactService, Depends(get_wa_artifact_service)],
) -> WaTableService:
    """Verdrahtet den Tabellen-Service mit dem BESTEHENDEN Artifact-Stack —
    `save_query_result` legt das Ergebnis-Artifact ueber dessen Anlage-Pfad an."""
    return WaTableService(
        pool, PgWaTableRepository(), get_table_store(), artifact_service=artifact_service
    )


Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]
Service = Annotated[WaTableService, Depends(get_wa_table_service)]


def _table_not_found() -> HTTPException:
    """404 fuer unbekannte ODER nicht lesbare Tabellen (kein Existenz-Leak)."""
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tabelle nicht gefunden.")


def _rows_invalid(exc: TableRowsInvalid) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))


def _query_invalid(exc: TableQueryInvalid) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"SQL-Fehler: {exc}")


@router.post("/work-areas/{area_id}/tables", status_code=status.HTTP_201_CREATED)
@limiter.limit(write_limit)
async def create_table(
    request: Request, area_id: UUID, data: WaTableCreate, ctx: Ctx, service: Service
) -> WaTableRead:
    """Legt eine Tabelle an (Katalog-Zeile + SQLite-DDL, atomar);
    Namens-Kollision in der Area → 409 `concurrent_conflict`."""
    return await service.create(ctx, area_id, data)


@router.get("/work-areas/{area_id}/tables", dependencies=[Depends(enforce_mcp_read_limit)])
async def list_tables(area_id: UUID, ctx: Ctx, service: Service) -> list[WaTableRead]:
    """Katalog-Liste der Area (ohne Zeilenzahlen — die liefert describe)."""
    return await service.list_for_area(ctx, area_id)


@router.post("/wa-tables/{table_id}/rows")
@limiter.limit(write_limit)
async def insert_rows(
    request: Request, table_id: UUID, data: RowsInsert, ctx: Ctx, service: Service
) -> RowsInsertResult:
    """Idempotenter Import (Spec K): Doppel-Importe zaehlen als `skipped`;
    Schema-Verstoesse (unbekannte Spalte, fehlendes `occurred_at`) → 422."""
    try:
        result = await service.insert_rows(ctx, table_id, data)
    except TableRowsInvalid as exc:
        raise _rows_invalid(exc) from exc
    if result is None:
        raise _table_not_found()
    return RowsInsertResult(inserted=result.inserted, skipped=result.skipped)


@router.post("/wa-tables/{table_id}/query", dependencies=[Depends(enforce_mcp_read_limit)])
async def query_table(table_id: UUID, data: TableQuery, ctx: Ctx, service: Service) -> QueryResult:
    """Read-only SQL gegen die Area-Datei (Engine-Garantie, ADR-0049);
    Schreibversuche → 403 `query_not_readonly`, Syntaxfehler → 400."""
    try:
        result = await service.query(ctx, table_id, data)
    except TableQueryInvalid as exc:
        raise _query_invalid(exc) from exc
    if result is None:
        raise _table_not_found()
    return result


@router.post("/wa-tables/{table_id}/save-result", status_code=status.HTTP_201_CREATED)
@limiter.limit(write_limit)
async def save_query_result(
    request: Request, table_id: UUID, data: SaveQueryResult, ctx: Ctx, service: Service
) -> ArtifactRead:
    """Fuehrt das SQL read-only aus und friert Query + Ergebnis als
    doc-Artifact in der Area der Tabelle ein (WP16, M-Ersatz): die Zahlen im
    Artifact rendert der SERVER aus dem Result-Set (Spec §10.6).
    Schreibversuche → 403 `query_not_readonly`, Syntaxfehler → 400 — dann
    entsteht KEIN Artifact. Die Antwort ist das ArtifactRead; nachgelagerte
    KB-Nodes referenzieren es als `source_ref` (Spec M)."""
    try:
        artifact = await service.save_query_result(ctx, table_id, data)
    except TableQueryInvalid as exc:
        raise _query_invalid(exc) from exc
    if artifact is None:
        raise _table_not_found()
    return artifact


@router.get("/wa-tables/{table_id}", dependencies=[Depends(enforce_mcp_read_limit)])
async def describe_table(table_id: UUID, ctx: Ctx, service: Service) -> TableDescription:
    """describe: Schema, Zeilenzahl, Wertebereiche, Area-Konventionen —
    Kontext fuer Queries OHNE Rohdaten-Dump (Spec K/M)."""
    description = await service.describe(ctx, table_id)
    if description is None:
        raise _table_not_found()
    return description
