"""Knowledge-Base-Endpunkte (ADR-0047, WP7 — Spec D + E-Sichtbarkeit).

Pfade unter `/v1/workspaces/{ws_id}` (Prefix aus `main.py`):

- ``POST /kb/nodes`` — belegte Aussage anlegen (Belegpflicht, Spec D).
- ``PATCH /kb/nodes/{id}`` — Teilupdate mit Tier-Regeln (Serverlogik O).
- ``GET /kb/nodes/{id}`` — Einzel-Read; nicht sichtbar → 404 (kein
  Existenz-Leak).
- ``POST /kb/edges`` — getypte, belegpflichtige Kante (EINE Transaktion).
- ``GET /kb/neighbors?anchor=&type=&depth=`` — Nachbar-Nodes (Tiefe 1..3).
- ``GET /kb-search?q=&limit=`` — FTS ueber `kb_node` (nie WorkArea-Inhalte).

Rate-Limit-Paritaet (Muster `wa_artifacts.py`): Mutationen
`@limiter.limit(write_limit)` + `request` als erster Parameter; agent-Reads
`enforce_mcp_read_limit`. Autorisierung + Sichtbarkeit liegen im Service;
dieser Router uebersetzt nur `None`-Ergebnisse in 404.
"""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from who2be_api.core.db import get_pool
from who2be_api.core.rate_limit import limiter, write_limit
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.repositories.kb_repository import PgKbRepository
from who2be_api.repositories.work_area_repository import PgWorkAreaRepository
from who2be_api.repositories.workspace_repository import PgWorkspaceRepository
from who2be_api.services.kb import KbService
from who2be_api.services.mcp_limit_service import enforce_mcp_read_limit
from who2be_models import (
    EdgeType,
    KbEdgeCreate,
    KbEdgeRead,
    KbNeighbor,
    KbNodeCreate,
    KbNodeRead,
    KbNodeUpdate,
    KbSearchHit,
)

router = APIRouter(tags=["kb"])


def get_kb_service(pool: Annotated[asyncpg.Pool, Depends(get_pool)]) -> KbService:
    return KbService(
        pool,
        PgKbRepository(),
        PgWorkAreaRepository(pool),
        workspace_repo=PgWorkspaceRepository(pool),
    )


Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]
Service = Annotated[KbService, Depends(get_kb_service)]


def _node_not_found() -> HTTPException:
    """404 fuer unbekannte ODER nicht sichtbare Nodes (kein Existenz-Leak)."""
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="KB-Node nicht gefunden.")


@router.post("/kb/nodes", status_code=status.HTTP_201_CREATED)
@limiter.limit(write_limit)
async def create_node(
    request: Request, data: KbNodeCreate, ctx: Ctx, service: Service
) -> KbNodeRead:
    """Legt eine belegte Aussage an; `source_ref_kind` und die Quell-Areas
    (`kb_node_source_area`) leitet der Server aus den Referenzen ab."""
    return await service.create_node(ctx, data)


@router.patch("/kb/nodes/{node_id}")
@limiter.limit(write_limit)
async def update_node(
    request: Request, node_id: UUID, data: KbNodeUpdate, ctx: Ctx, service: Service
) -> KbNodeRead:
    """Teilupdate mit Tier-Regeln: Hochstufen auf `verified` immer 422;
    `hypothesis → derived` nur mit Beleg anderer Art (Serverlogik O)."""
    updated = await service.update_node(ctx, node_id, data)
    if updated is None:
        raise _node_not_found()
    return updated


@router.get("/kb/nodes/{node_id}", dependencies=[Depends(enforce_mcp_read_limit)])
async def read_node(node_id: UUID, ctx: Ctx, service: Service) -> KbNodeRead:
    """Einzel-Read im Sichtbarkeits-Scope des Aufrufers — sonst 404."""
    node = await service.get_node(ctx, node_id)
    if node is None:
        raise _node_not_found()
    return node


@router.post("/kb/edges", status_code=status.HTTP_201_CREATED)
@limiter.limit(write_limit)
async def create_edge(
    request: Request, data: KbEdgeCreate, ctx: Ctx, service: Service
) -> KbEdgeRead:
    """Legt eine getypte, belegpflichtige Kante an — Anker-Aufloesung,
    Evidence und Source-Area-Propagation in EINER Transaktion."""
    return await service.create_edge(ctx, data)


@router.get("/kb/neighbors", dependencies=[Depends(enforce_mcp_read_limit)])
async def neighbors(
    ctx: Ctx,
    service: Service,
    anchor: Annotated[str, Query(min_length=1, max_length=200)],
    edge_type: Annotated[EdgeType | None, Query(alias="type")] = None,
    depth: Annotated[int, Query(ge=1, le=3)] = 1,
) -> list[KbNeighbor]:
    """Nachbar-Nodes eines Ankers (``node:<uuid>`` oder Artifact-Anker);
    `co_n` traegt bei `co_occurs_with` immer die Fallzahl (Spec O)."""
    return await service.neighbors(ctx, anchor, edge_type, depth)


@router.get("/kb-search", dependencies=[Depends(enforce_mcp_read_limit)])
async def search_kb(
    ctx: Ctx,
    service: Service,
    q: Annotated[str, Query(min_length=1, max_length=200)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[KbSearchHit]:
    """Rangsortierte KB-Treffer (Anker ``node:<id>`` + Snippet) im
    Sichtbarkeits-Scope — per Konstruktion nie WorkArea-Inhalte."""
    return await service.search(ctx, q, limit)
