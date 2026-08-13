"""WorkArea-Such-Endpunkt (ADR-0047, WP6 — Spec C).

``GET /v1/workspaces/{ws_id}/workarea-search`` — DER Einstieg in die WorkArea:
Anker + Snippet statt ganzer Dokumente. Die Artifact-Liste
(``GET /work-areas/{area_id}/artifacts``) ist bewusst NICHT der Einstieg.

Read-Route mit Agenten-Publikum → `enforce_mcp_read_limit` (Muster
`wa_artifacts.read_artifact`); das Area-Scoping liegt im Service bzw. in der
Such-SQL selbst.
"""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query

from who2be_api.core.db import get_pool
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.repositories.wa_search_repository import PgWaSearchRepository
from who2be_api.services.mcp_limit_service import enforce_mcp_read_limit
from who2be_api.services.wa_search import WaSearchService
from who2be_models import WorkAreaSearchHit

router = APIRouter(tags=["wa-search"])


def get_wa_search_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> WaSearchService:
    return WaSearchService(pool, PgWaSearchRepository(pool))


Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]
Service = Annotated[WaSearchService, Depends(get_wa_search_service)]


@router.get("/workarea-search", dependencies=[Depends(enforce_mcp_read_limit)])
async def search_workarea(
    ctx: Ctx,
    service: Service,
    q: Annotated[str, Query(min_length=1, max_length=200)],
    area_id: Annotated[UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[WorkAreaSearchHit]:
    """Rangsortierte Passagen-Treffer ueber die lesbaren Areas.

    DER Einstieg in die WorkArea: jeder Treffer traegt einen `anchor`
    (``<artifact_id>#<block_id>``), mit dem
    ``GET /wa-artifacts/{id}?anchor=`` direkt den einen Block liefert —
    NICHT die Artifact-Liste durchgehen und Dokumente komplett lesen.
    `area_id` schraenkt optional auf eine Area ein; ausserhalb des
    Lese-Scopes ist das Ergebnis leer (kein Existenz-Orakel).
    """
    return await service.search(ctx, q, area_id, limit)
