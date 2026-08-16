"""WorkArea-Ingest-Endpunkte (ADR-0048, WP5 — Spec B).

Pfade unter `/v1/workspaces/{ws_id}` (Prefix aus `main.py`):

- ``POST /work-areas/{area_id}/ingest`` — Datei (`file_b64`) ODER `url` in
  eine Area ingestieren (Base64-JSON, bewusst kein multipart — ein Body-Format
  fuer Agenten UND Web-UI).
- ``POST /ingest`` — ohne Area = private Area des gebundenen Agenten
  (Auto-Anlage); Menschen-Tokens haben KEINE private Area → 422.

Antwort: 201 mit `IngestResult`; war derselbe Inhalt (sha256) in der Ziel-Area
bereits ingestiert, 200 mit den bestehenden IDs (`deduplicated=True`) — der
Ingest ist idempotent.

Rate-Limit-Paritaet (Muster `wa_artifacts`): Mutationen
`@limiter.limit(write_limit)` + `request` als erster Parameter; zusaetzlich
drosselt `require_write_rate` im Service pro Agent. Autorisierung (Capability/
Rolle/Area-Grant), SSRF-Guard und Groessenlimit liegen im Service.
"""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from who2be_api.core.db import get_pool
from who2be_api.core.rate_limit import limiter, write_limit
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.repositories.wa_blob_repository import PgWaBlobRepository
from who2be_api.repositories.work_area_repository import PgWorkAreaRepository
from who2be_api.repositories.workspace_repository import PgWorkspaceRepository
from who2be_api.services.wa_ingest import WaIngestService
from who2be_models import IngestRequest, IngestResult

router = APIRouter(tags=["wa-ingest"])


def get_wa_ingest_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> WaIngestService:
    return WaIngestService(
        pool,
        PgWaBlobRepository(),
        PgWorkAreaRepository(pool),
        workspace_repo=PgWorkspaceRepository(pool),
    )


Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]
Service = Annotated[WaIngestService, Depends(get_wa_ingest_service)]


def _with_dedup_status(result: IngestResult, response: Response) -> IngestResult:
    """Dedup-Treffer antworten 200 (idempotent, nichts angelegt) statt 201."""
    if result.deduplicated:
        response.status_code = status.HTTP_200_OK
    return result


@router.post("/work-areas/{area_id}/ingest", status_code=status.HTTP_201_CREATED)
@limiter.limit(write_limit)
async def ingest_into_area(
    request: Request,
    response: Response,
    area_id: UUID,
    data: IngestRequest,
    ctx: Ctx,
    service: Service,
) -> IngestResult:
    """Ingestiert Datei oder URL in die Area: Blob- + doc-Artifact in EINER
    Transaktion; bereits bekannter Inhalt (sha256) → 200 `deduplicated`."""
    return _with_dedup_status(await service.ingest(ctx, area_id, data), response)


@router.post("/ingest", status_code=status.HTTP_201_CREATED)
@limiter.limit(write_limit)
async def ingest_into_private_area(
    request: Request,
    response: Response,
    data: IngestRequest,
    ctx: Ctx,
    service: Service,
) -> IngestResult:
    """Wie `ingest_into_area`, aber ohne Area: Ziel ist die private Area des
    gebundenen Agenten (Auto-Anlage beim ersten Zugriff)."""
    if ctx.tool_policy is None and ctx.agent_id is None:
        # Menschen (JWT/ungebundener Token) haben KEINE private Area — der
        # Aufruf ist semantisch unvollstaendig, kein Autorisierungsproblem
        # (Muster `wa_artifacts.create_artifact_in_private_area`).
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Ohne area_id ingestiert nur ein agent-gebundener Token (private "
                "Area). Menschen nutzen POST /work-areas/{area_id}/ingest."
            ),
        )
    return _with_dedup_status(await service.ingest(ctx, None, data), response)
