"""Discovery-/Search-Endpunkt (ADR-0037).

`GET /v1/workspaces/{ws_id}/search?q=&types=&limit=` — Volltext ueber die aktive
Version der Kern-Inhaltselemente, read-scope-gefiltert im Service. Viewer-offen
(reiner Read; kein Mutations-Gate).
"""

from typing import Annotated, cast

import asyncpg
from fastapi import APIRouter, Depends, Query

from who2be_api.core.db import get_pool
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.repositories.search_repository import PgSearchRepository
from who2be_api.services.search_service import SearchService
from who2be_models import SearchHit, SearchType

_VALID_TYPES: frozenset[str] = frozenset(("persona", "playbook", "resource"))


def _parse_types(types: str | None) -> list[SearchType] | None:
    """Kommaseparierte `types` in eine validierte Liste; unbekannte werden verworfen."""
    if not types:
        return None
    parsed = cast(
        "list[SearchType]",
        [t.strip() for t in types.split(",") if t.strip() in _VALID_TYPES],
    )
    return parsed or None


router = APIRouter(tags=["search"])


def get_search_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> SearchService:
    return SearchService(PgSearchRepository(pool), pool)


Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]
Service = Annotated[SearchService, Depends(get_search_service)]


@router.get("/search")
async def search(
    ctx: Ctx,
    service: Service,
    q: Annotated[str, Query(min_length=1, max_length=200)],
    types: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[SearchHit]:
    return await service.search(ctx, q, _parse_types(types), limit)
