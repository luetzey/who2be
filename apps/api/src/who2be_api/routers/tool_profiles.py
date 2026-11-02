"""REST-Endpunkte der Werkzeug-Profile pro Agent (ADR-0059 §7.1, Paket Q2b).

Pfade unter ``/v1/workspaces/{workspace_id}`` (Prefix aus ``main.py``):

* ``GET    /tool-profiles``               Profile mit Agenten-Zahl (viewer)
* ``GET    /tool-profiles/catalog``       Gruppen und Kern aus dem Code (viewer)
* ``POST   /tool-profiles``               eigenes Profil anlegen (admin)
* ``PUT    /tool-profiles/{id}``          Profil ersetzen (admin)
* ``POST   /tool-profiles/{id}/reset``    mitgeliefertes Profil zuruecksetzen (admin)
* ``DELETE /tool-profiles/{id}``          eigenes Profil loeschen (admin)
* ``PUT    /agents/{agent_id}/tool-profile``  Zuordnung (editor, nur Menschen)

Rollen, Fehlercodes und Audit setzt ``ToolProfileService``; der Router
deklariert die Fehler nur im Schema (ADR-0051). Keine neuen MCP-Werkzeuge
(§7.5): Profile pflegt ein Mensch im Web.
"""

from typing import Annotated, Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Request, Response, status

from who2be_api.core.db import get_pool
from who2be_api.core.rate_limit import limiter, write_limit
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.repositories.agent_repository import PgAgentRepository
from who2be_api.repositories.audit_log_repository import PgAuditLogRepository
from who2be_api.repositories.tool_profile_repository import PgToolProfileRepository
from who2be_api.repositories.workspace_repository import PgWorkspaceRepository
from who2be_api.services.audit_service import AuditService
from who2be_api.services.tool_profile_service import ToolProfileService
from who2be_models import AgentRead, ApiErrorBody
from who2be_models.tool_profiles import (
    AgentToolProfileUpdate,
    ToolCatalogRead,
    ToolProfileCreate,
    ToolProfileRead,
    ToolProfileUpdate,
)

router = APIRouter(tags=["tool-profiles"])


def get_tool_profile_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> ToolProfileService:
    return ToolProfileService(
        PgToolProfileRepository(pool),
        PgAgentRepository(pool),
        PgWorkspaceRepository(pool),
        audit_service=AuditService(PgAuditLogRepository()),
        pool=pool,
    )


Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]
Service = Annotated[ToolProfileService, Depends(get_tool_profile_service)]


_Responses = dict[int | str, dict[str, Any]]


def _err(description: str) -> dict[str, Any]:
    return {"model": ApiErrorBody, "description": description}


_NOT_FOUND: _Responses = {404: _err("reason: tool_profile_not_found")}
_NAMES_422: _Responses = {422: _err("reason: unknown_tool | unknown_tool_group")}
_NAME_409: _Responses = {409: _err("reason: tool_profile_name_conflict")}


@router.get("/tool-profiles")
async def list_tool_profiles(ctx: Ctx, service: Service) -> list[ToolProfileRead]:
    return await service.list_all(ctx)


@router.get("/tool-profiles/catalog")
async def get_tool_catalog(ctx: Ctx, service: Service) -> ToolCatalogRead:
    return await service.catalog(ctx)


@router.post(
    "/tool-profiles",
    status_code=status.HTTP_201_CREATED,
    responses={**_NAME_409, **_NAMES_422},
)
@limiter.limit(write_limit)
async def create_tool_profile(
    request: Request, data: ToolProfileCreate, ctx: Ctx, service: Service
) -> ToolProfileRead:
    return await service.create(ctx, data)


@router.put(
    "/tool-profiles/{profile_id}",
    responses={**_NOT_FOUND, **_NAME_409, **_NAMES_422},
)
@limiter.limit(write_limit)
async def update_tool_profile(
    request: Request, profile_id: UUID, data: ToolProfileUpdate, ctx: Ctx, service: Service
) -> ToolProfileRead:
    return await service.update(ctx, profile_id, data)


@router.post(
    "/tool-profiles/{profile_id}/reset",
    responses={
        **_NOT_FOUND,
        409: _err("reason: tool_profile_not_builtin | tool_profile_name_conflict"),
    },
)
@limiter.limit(write_limit)
async def reset_tool_profile(
    request: Request, profile_id: UUID, ctx: Ctx, service: Service
) -> ToolProfileRead:
    return await service.reset(ctx, profile_id)


@router.delete(
    "/tool-profiles/{profile_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**_NOT_FOUND, 409: _err("reason: tool_profile_builtin | tool_profile_in_use")},
)
@limiter.limit(write_limit)
async def delete_tool_profile(
    request: Request, profile_id: UUID, ctx: Ctx, service: Service
) -> Response:
    await service.delete(ctx, profile_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/agents/{agent_id}/tool-profile",
    responses={
        403: {"description": "reason: human_only (application/problem+json)"},
        404: _err("reason: agent_not_found | tool_profile_not_found"),
        422: _err("reason: unknown_tool | core_tool_not_removable"),
    },
)
@limiter.limit(write_limit)
async def set_agent_tool_profile(
    request: Request, agent_id: UUID, data: AgentToolProfileUpdate, ctx: Ctx, service: Service
) -> AgentRead:
    return await service.assign(ctx, agent_id, data)
