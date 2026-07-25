"""Discovery-/Search-Endpunkte (ADR-0037, Passage-Suche ADR-0046).

- `GET /v1/workspaces/{ws_id}/search` — Entity-Ranking: welches ELEMENT passt
  zum Thema (Kuratieren).
- `GET /v1/workspaces/{ws_id}/search/content` — Passage-Retrieval: welche
  STELLE beantwortet die Frage (Agenten-Laufzeit).

Beide read-scope-gefiltert im Service, beide viewer-offen (reine Reads; kein
Mutations-Gate).
"""

from typing import Annotated, cast

import asyncpg
from fastapi import APIRouter, Depends, Query

from who2be_api.core.db import get_pool
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.embeddings import build_embedding_port
from who2be_api.repositories.content_chunk_repository import PgContentChunkRepository
from who2be_api.repositories.search_repository import PgSearchRepository
from who2be_api.services.content_chunk_service import ContentChunkService
from who2be_api.services.search_service import SearchService
from who2be_models import ChunkType, ContentChunkHit, SearchHit, SearchMode, SearchType

_VALID_TYPES: frozenset[str] = frozenset(("persona", "playbook", "resource", "external_tool"))
# Die Passage-Suche deckt zusaetzlich System-Prompt-Templates ab; ob der
# Aufrufer sie sehen darf, entscheidet `readable_content_scope`.
_VALID_CHUNK_TYPES: frozenset[str] = _VALID_TYPES | {"system_prompt_template"}


def _parse_types(types: str | None) -> list[SearchType] | None:
    """Kommaseparierte `types` in eine validierte Liste; unbekannte werden verworfen."""
    if not types:
        return None
    parsed = cast(
        "list[SearchType]",
        [t.strip() for t in types.split(",") if t.strip() in _VALID_TYPES],
    )
    return parsed or None


def _parse_chunk_types(types: str | None) -> list[ChunkType] | None:
    if not types:
        return None
    parsed = cast(
        "list[ChunkType]",
        [t.strip() for t in types.split(",") if t.strip() in _VALID_CHUNK_TYPES],
    )
    return parsed or None


router = APIRouter(tags=["search"])


def get_search_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> SearchService:
    return SearchService(PgSearchRepository(pool), pool)


def get_content_chunk_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> ContentChunkService:
    # `build_embedding_port()` liefert `None`, wenn keine Semantik verfuegbar
    # ist (Normalfall ohne die optionale Dependency-Gruppe) — der Service faellt
    # dann lautlos auf Volltext zurueck.
    return ContentChunkService(PgContentChunkRepository(pool), pool, build_embedding_port())


Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]
Service = Annotated[SearchService, Depends(get_search_service)]
ChunkService = Annotated[ContentChunkService, Depends(get_content_chunk_service)]


@router.get("/search")
async def search(
    ctx: Ctx,
    service: Service,
    q: Annotated[str, Query(min_length=1, max_length=200)],
    types: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[SearchHit]:
    return await service.search(ctx, q, _parse_types(types), limit)


@router.get("/search/content")
async def search_content(
    ctx: Ctx,
    service: ChunkService,
    q: Annotated[str, Query(min_length=1, max_length=200)],
    types: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
    mode: Annotated[SearchMode, Query()] = SearchMode.auto,
) -> list[ContentChunkHit]:
    """Passagen aus der aktiven Version, statt ganzer Aggregate.

    Kleineres `limit`-Fenster als die Entity-Suche: Passagen sind Nutztext und
    landen direkt im Kontext des Agenten.

    `mode` steuert Volltext/Semantik; ohne verfuegbaren Embedding-Port
    verhalten sich alle Stufen wie `text` (ADR-0046).
    """
    return await service.search(ctx, q, _parse_chunk_types(types), limit, mode)
