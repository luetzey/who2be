"""WorkArea-Endpunkte: Areas + Grants (ADR-0047, WP4).

Pfade unter `/v1/workspaces/{ws_id}` (Prefix aus `main.py`):

- ``POST /work-areas`` — legt eine SHARED Area an (private Areas entstehen
  ausschliesslich per Auto-Anlage beim ersten Agent-Zugriff).
- ``GET /work-areas`` — sichtbare Areas des Aufrufers (Scope im Service).
- ``PUT/DELETE /work-areas/{area_id}/grants/{agent_id}`` — Grant-Verwaltung,
  Menschen vorbehalten (Gate im Service).

Rate-Limit-Paritaet (Muster `memory.py`/`resources.py`): jede Mutation traegt
`@limiter.limit(write_limit)` (+ `request` als erster Parameter), der
agent-gerichtete Read `enforce_mcp_read_limit`. Autorisierung liegt im Service.
"""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Request, status

from who2be_api.core.db import get_pool
from who2be_api.core.rate_limit import limiter, write_limit
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.repositories.work_area_repository import PgWorkAreaRepository
from who2be_api.services.mcp_limit_service import enforce_mcp_read_limit
from who2be_api.services.work_areas import WorkAreaService
from who2be_models import WorkAreaCreate, WorkAreaGrantRead, WorkAreaGrantSet, WorkAreaRead

router = APIRouter(tags=["work-areas"])


def get_work_area_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> WorkAreaService:
    return WorkAreaService(PgWorkAreaRepository(pool), pool)


Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]
Service = Annotated[WorkAreaService, Depends(get_work_area_service)]


@router.post("/work-areas", status_code=status.HTTP_201_CREATED)
@limiter.limit(write_limit)
async def create_work_area(
    request: Request, data: WorkAreaCreate, ctx: Ctx, service: Service
) -> WorkAreaRead:
    return await service.create_shared(ctx, data)


@router.get("/work-areas", dependencies=[Depends(enforce_mcp_read_limit)])
async def list_work_areas(ctx: Ctx, service: Service) -> list[WorkAreaRead]:
    """Sichtbare Areas; loest fuer agent-gebundene Tokens die private
    Auto-Anlage aus (erster Zugriff, Plan-Entscheidung 5)."""
    return await service.list_visible(ctx)


@router.put("/work-areas/{area_id}/grants/{agent_id}")
@limiter.limit(write_limit)
async def set_work_area_grant(
    request: Request,
    area_id: UUID,
    agent_id: UUID,
    data: WorkAreaGrantSet,
    ctx: Ctx,
    service: Service,
) -> WorkAreaGrantRead:
    """Setzt/aktualisiert den Grant eines Agenten auf eine shared Area (Mensch, editor+)."""
    return await service.set_grant(ctx, area_id, agent_id, data)


@router.delete("/work-areas/{area_id}/grants/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(write_limit)
async def delete_work_area_grant(
    request: Request, area_id: UUID, agent_id: UUID, ctx: Ctx, service: Service
) -> None:
    await service.delete_grant(ctx, area_id, agent_id)
