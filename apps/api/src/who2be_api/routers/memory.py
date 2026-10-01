"""Agent-Memory-Endpunkte (ADR-0044).

Agent-Pfad (`/agent-memories*`, agent-gebundener Token, operiert IMMER auf
`ctx.agent_id` — nie auf einem Pfad-Parameter): save/search/list. Management-
Pfad (`/agents/{agent_id}/memories*`, human-only editor+): Liste, Triage,
Bearbeiten, Loeschen. Autorisierung liegt im Service. Mount unter
`/v1/workspaces/{ws_id}`.

Rate-Limit-Paritaet (Review 2026-07-20 SEC-2/SEC-3): die agent-gerichteten
Reads tragen `enforce_mcp_read_limit` wie alle anderen agent-facing Read-Routen;
`save_memory` und der Guard-PUT tragen `@limiter.limit(write_limit)` wie jeder
andere mutierende Endpunkt (F-Phase2-01-Muster).
"""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query, Request, Response

from who2be_api.core.db import get_pool
from who2be_api.core.rate_limit import limiter, write_limit
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.repositories.memory_repository import PgMemoryRepository
from who2be_api.services.mcp_limit_service import enforce_mcp_read_limit
from who2be_api.services.memory_service import MemoryService
from who2be_models import (
    MemoryCreate,
    MemoryGuardConfig,
    MemoryHit,
    MemoryRead,
    MemoryStatus,
    MemoryTriage,
    MemoryUpdate,
)
from who2be_models.memory import MemoryAutoPolicy, MemoryAutoPolicyRead, MemorySaveResult

router = APIRouter(tags=["memory"])


def get_memory_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> MemoryService:
    return MemoryService(PgMemoryRepository(pool))


Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]
Service = Annotated[MemoryService, Depends(get_memory_service)]


# ------------------------------------------------------------------ Agent-Pfad


@router.post("/agent-memories", status_code=201)
@limiter.limit(write_limit)
async def save_memory(
    request: Request, response: Response, data: MemoryCreate, ctx: Ctx, service: Service
) -> MemorySaveResult:
    # `status` in der Antwort sagt dem Agenten, ob der Fakt live ist (`active`,
    # per Freigabematrix, dann `auto_activated=true`) oder auf menschliche
    # Freigabe wartet (`pending`). Eine lesson-Wiederholung ist kein neuer
    # Eintrag: 200 mit `merged_into` (ADR-0053 3.1.6).
    result = await service.save(ctx, data)
    if result.merged_into is not None:
        response.status_code = 200
    return result


@router.get("/agent-memories/search", dependencies=[Depends(enforce_mcp_read_limit)])
async def search_memory(
    ctx: Ctx,
    service: Service,
    query: Annotated[str, Query(min_length=1, max_length=500)],
    k: Annotated[int, Query(ge=1, le=20)] = 5,
) -> list[MemoryHit]:
    return await service.search(ctx, query, k)


@router.get("/agent-memories", dependencies=[Depends(enforce_mcp_read_limit)])
async def list_memories_for_agent(
    ctx: Ctx,
    service: Service,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[MemoryHit]:
    return await service.list_active(ctx, limit)


# ---------------------------------------------------- Waechter-Konfiguration


@router.get("/memory-guard")
async def get_memory_guard(ctx: Ctx, service: Service) -> MemoryGuardConfig:
    # Workspace-weite Injection-Waechter-Konfiguration (admin + human-only).
    return await service.get_guard(ctx)


@router.put("/memory-guard")
@limiter.limit(write_limit)
async def update_memory_guard(
    request: Request, data: MemoryGuardConfig, ctx: Ctx, service: Service
) -> MemoryGuardConfig:
    return await service.set_guard(ctx, data)


# ------------------------------------------------------------ Freigabematrix


@router.get("/memory-auto-policy")
async def get_memory_auto_policy(ctx: Ctx, service: Service) -> MemoryAutoPolicyRead:
    # Freigabematrix Art x Herkunft (ADR-0053 4, admin + human-only).
    return await service.get_auto_policy(ctx)


@router.put("/memory-auto-policy")
@limiter.limit(write_limit)
async def update_memory_auto_policy(
    request: Request, data: MemoryAutoPolicy, ctx: Ctx, service: Service
) -> MemoryAutoPolicyRead:
    # Nie-Zellen werden ignoriert (nicht 422); die Antwort zeigt die wirksame
    # Einstellung. Jede geaenderte Zelle landet im audit_log (4.3).
    return await service.set_auto_policy(ctx, data)


# ------------------------------------------------------------- Management-Pfad


@router.get("/agents/{agent_id}/memories")
async def list_agent_memories(
    agent_id: UUID,
    ctx: Ctx,
    service: Service,
    status: Annotated[MemoryStatus | None, Query()] = None,
) -> list[MemoryRead]:
    return await service.list_memories(ctx, agent_id, status)


@router.post("/agents/{agent_id}/memories/{memory_id}/triage")
async def triage_memory(
    agent_id: UUID, memory_id: UUID, data: MemoryTriage, ctx: Ctx, service: Service
) -> MemoryRead:
    return await service.triage(ctx, agent_id, memory_id, data)


@router.put("/agents/{agent_id}/memories/{memory_id}")
async def update_memory(
    agent_id: UUID, memory_id: UUID, data: MemoryUpdate, ctx: Ctx, service: Service
) -> MemoryRead:
    return await service.update_memory(ctx, agent_id, memory_id, data)


@router.delete("/agents/{agent_id}/memories/{memory_id}", status_code=204)
async def delete_memory(agent_id: UUID, memory_id: UUID, ctx: Ctx, service: Service) -> None:
    await service.delete_memory(ctx, agent_id, memory_id)


@router.delete("/agents/{agent_id}/memories", status_code=204)
async def delete_all_memories(agent_id: UUID, ctx: Ctx, service: Service) -> None:
    await service.delete_all(ctx, agent_id)
