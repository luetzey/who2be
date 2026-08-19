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
- ``DELETE /wa-tables/{table_id}`` — Tabelle + Daten endgueltig loeschen.
- ``PUT /work-areas/{area_id}/conventions/{source_name}`` /
  ``GET /work-areas/{area_id}/conventions`` — Quell-Konventionen (WP17,
  Spec M2): anlegen/ersetzen bzw. Area-Liste.
- ``POST /work-areas/{area_id}/category-rules`` — Regel-Upsert (WP17,
  Spec L): 201 bei Anlage, 200 bei Ersetzung; kategorisiert rueckwirkend neu
  (auditiert). ``GET`` daneben listet die Regeln der Area.

Rate-Limit-Paritaet (Muster `wa_artifacts`): Mutationen
`@limiter.limit(write_limit)` + `request` als erster Parameter; agent-lesbare
Pfade `enforce_mcp_read_limit` — auch der POST-Query-Pfad ist semantisch ein
Read. Autorisierung liegt im Service; der Router uebersetzt nur die
Domain-Exceptions (`TableRowsInvalid` → 422, `TableQueryInvalid` → 400,
`QueryTimeout` → 408) und `None` → 404 (kein Existenz-Leak, Muster
`routers/kb.py`).

Warum `QueryTimeout` (Security-Review Phase 2, H1) OHNE `ApiGateError` laeuft:
die `ProblemReason`-Taxonomie ist geschlossen und beschreibt
Berechtigungs-/Zustands-Gruende. Ein ueberschrittenes ZEITBUDGET ist keiner
davon — `query_not_readonly` waere sachlich falsch (die Query war erlaubt),
`ingest_too_large` waere eine Groessen- statt Kostenaussage. Statt die
Taxonomie um Vokabular zu erweitern, das kein Agent verzweigen muss, geht der
Fall den generischen Domain-Exception-Weg des Repos (Muster
`TableQueryInvalid`): 408 + sprechendes `detail`, RFC-9110-konform
selbsterklaerend.
"""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response, status
from pydantic import BaseModel

from who2be_api.core.db import get_pool
from who2be_api.core.rate_limit import limiter, write_limit
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.repositories.audit_log_repository import PgAuditLogRepository
from who2be_api.repositories.wa_rule_repository import PgWaRuleRepository
from who2be_api.repositories.wa_table_repository import PgWaTableRepository
from who2be_api.routers.wa_artifacts import get_wa_artifact_service
from who2be_api.services.audit_service import AuditService
from who2be_api.services.mcp_limit_service import enforce_mcp_read_limit
from who2be_api.services.tablestore_provider import get_table_store
from who2be_api.services.wa_artifacts import WaArtifactService
from who2be_api.services.wa_rules import WaRuleService
from who2be_api.services.wa_tables import TableQueryInvalid, TableRowsInvalid, WaTableService
from who2be_api.tablestore import QueryTimeout
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
    `save_query_result` legt das Ergebnis-Artifact ueber dessen Anlage-Pfad an;
    das Regel-Repo bedient die Import-Gates (WP17, Spec L/M2)."""
    return WaTableService(
        pool,
        PgWaTableRepository(),
        get_table_store(),
        artifact_service=artifact_service,
        rule_repo=PgWaRuleRepository(),
    )


def get_wa_rule_service(pool: Annotated[asyncpg.Pool, Depends(get_pool)]) -> WaRuleService:
    """Regel-/Konventions-Service (WP17): Re-Kategorisierung schreibt SQLite
    ueber den TableStore (server-only) und protokolliert im `audit_log`."""
    return WaRuleService(
        pool,
        PgWaRuleRepository(),
        PgWaTableRepository(),
        get_table_store(),
        audit_service=AuditService(PgAuditLogRepository()),
    )


Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]
Service = Annotated[WaTableService, Depends(get_wa_table_service)]
RuleService = Annotated[WaRuleService, Depends(get_wa_rule_service)]
SourceName = Annotated[str, Path(min_length=1, max_length=100)]


def _table_not_found() -> HTTPException:
    """404 fuer unbekannte ODER nicht lesbare Tabellen (kein Existenz-Leak)."""
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tabelle nicht gefunden.")


def _rows_invalid(exc: TableRowsInvalid) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))


def _query_invalid(exc: TableQueryInvalid) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"SQL-Fehler: {exc}")


def _query_timeout(exc: QueryTimeout) -> HTTPException:
    """408 fuer eine abgebrochene Query (H1) — s. Modul-Kopf zur Reason-Wahl."""
    return HTTPException(
        status_code=status.HTTP_408_REQUEST_TIMEOUT,
        detail=(
            f"{exc} Die Anfrage muss guenstiger werden: Fenster einschraenken, "
            "aggregieren oder auf rekursive CTEs ohne Abbruchbedingung verzichten."
        ),
    )


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


@router.delete("/wa-tables/{table_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(write_limit)
async def delete_table(request: Request, table_id: UUID, ctx: Ctx, service: Service) -> None:
    """Loescht Tabelle + Daten endgueltig (Katalog-Zeile UND SQLite-Tabelle);
    unbekannt oder nicht sichtbar → 404 (kein Existenz-Leak)."""
    if not await service.delete(ctx, table_id):
        raise _table_not_found()


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
    Schreibversuche → 403 `query_not_readonly`, Syntaxfehler → 400,
    Zeitbudget gerissen → 408, Ergebnis zu gross → 413."""
    try:
        result = await service.query(ctx, table_id, data)
    except TableQueryInvalid as exc:
        raise _query_invalid(exc) from exc
    except QueryTimeout as exc:
        raise _query_timeout(exc) from exc
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
    except QueryTimeout as exc:
        raise _query_timeout(exc) from exc
    if artifact is None:
        raise _table_not_found()
    return artifact


@router.get("/wa-tables/{table_id}", dependencies=[Depends(enforce_mcp_read_limit)])
async def describe_table(table_id: UUID, ctx: Ctx, service: Service) -> TableDescription:
    """describe: Schema, Zeilenzahl, Wertebereiche, Area-Konventionen —
    Kontext fuer Queries OHNE Rohdaten-Dump (Spec K/M). Die Full-Scans
    unterliegen demselben Zeitbudget wie eine Query (→ 408)."""
    try:
        description = await service.describe(ctx, table_id)
    except QueryTimeout as exc:
        raise _query_timeout(exc) from exc
    if description is None:
        raise _table_not_found()
    return description


@router.put("/work-areas/{area_id}/conventions/{source_name}")
@limiter.limit(write_limit)
async def set_convention(
    request: Request,
    area_id: UUID,
    source_name: SourceName,
    data: SourceConventionSet,
    ctx: Ctx,
    service: RuleService,
) -> SourceConventionRead:
    """Quell-Konvention anlegen/ersetzen (WP17, Spec M2) — Pflicht, bevor ein
    Import mit diesem `source_name` akzeptiert wird (sonst 422
    `convention_missing`); die inhaltliche Anwendung ist Runtime-Sache."""
    return await service.set_convention(ctx, area_id, source_name, data)


@router.get("/work-areas/{area_id}/conventions", dependencies=[Depends(enforce_mcp_read_limit)])
async def list_conventions(
    area_id: UUID, ctx: Ctx, service: RuleService
) -> list[SourceConventionRead]:
    """Quell-Konventionen der Area (Spec M2); fehlender Read-Grant → 404."""
    return await service.list_conventions(ctx, area_id)


@router.post("/work-areas/{area_id}/category-rules")
@limiter.limit(write_limit)
async def upsert_category_rule(
    request: Request,
    response: Response,
    area_id: UUID,
    data: CategoryRuleUpsert,
    ctx: Ctx,
    service: RuleService,
) -> CategoryRuleRead:
    """Regel anlegen/ersetzen (WP17, Spec L — Upsert auf (area, pattern)):
    201 bei Anlage, 200 bei Ersetzung. Kategorisiert die SQLite-Rows der
    Area-Tabellen rueckwirkend NEU (nur nicht-konfligierende Rows) und
    protokolliert den Lauf im `audit_log` (`workarea.rules_reapplied`)."""
    rule, created = await service.upsert_rule(ctx, area_id, data)
    if created:
        response.status_code = status.HTTP_201_CREATED
    return rule


@router.get("/work-areas/{area_id}/category-rules", dependencies=[Depends(enforce_mcp_read_limit)])
async def list_category_rules(
    area_id: UUID, ctx: Ctx, service: RuleService
) -> list[CategoryRuleRead]:
    """Regeln der Area (Spec L, inkl. inaktiver); fehlender Read-Grant → 404."""
    return await service.list_rules(ctx, area_id)
