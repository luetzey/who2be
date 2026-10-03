"""REST-Endpunkte fuer Workspace-Mitglieder (`/v1/workspaces/{ws}/members`).

Lesen ist jedem Mitglied erlaubt; Rollen-Aenderung und Entfernen sind
admin-only (`require_role`-Gate, Plan §2.3.B — durch Prompt A zur vollen
Permission-Matrix ausgebaut). Ebenfalls admin-only: das Loeschen des
Nutzergedaechtnisses einer Person (`DELETE /{user_id}/memories`, ADR-0053
6.4.1 W5 = a) ueber den Memory-Service.
"""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Request, status

from who2be_api.core.db import get_pool
from who2be_api.core.rate_limit import limiter, write_limit
from who2be_api.core.security import (
    WorkspaceContext,
    deny_agent_bound_workspace_admin,
    get_current_workspace,
    require_role,
)
from who2be_api.repositories.audit_log_repository import PgAuditLogRepository
from who2be_api.repositories.token_repository import PgTokenRepository
from who2be_api.repositories.workspace_member_repository import (
    PgWorkspaceMemberRepository,
)
from who2be_api.routers.memory import get_memory_service
from who2be_api.services.memory_service import MemoryService
from who2be_api.services.workspace_member_service import WorkspaceMemberService
from who2be_models import WorkspaceMemberRead, WorkspaceMemberUpdate, WorkspaceRole
from who2be_models.memory import MemoryPurgeResult

router = APIRouter(prefix="/members", tags=["members"])


def get_member_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> WorkspaceMemberService:
    return WorkspaceMemberService(
        PgWorkspaceMemberRepository(pool, audit_repo=PgAuditLogRepository()),
        PgTokenRepository(pool),
    )


Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]
Service = Annotated[WorkspaceMemberService, Depends(get_member_service)]


@router.get("")
async def list_members(ctx: Ctx, service: Service) -> list[WorkspaceMemberRead]:
    return await service.list_members(ctx.workspace_id)


@router.patch("/{user_id}")
@limiter.limit(write_limit)
async def update_member_role(
    request: Request, user_id: UUID, data: WorkspaceMemberUpdate, ctx: Ctx, service: Service
) -> WorkspaceMemberRead:
    require_role(ctx, WorkspaceRole.admin)
    # Rollenvergabe ist der direkteste Weg zur Rechte-Eskalation — ein
    # agent-gebundener Token bleibt davon ausgeschlossen (siehe Gate-Docstring).
    deny_agent_bound_workspace_admin(ctx)
    return await service.update_role(ctx.workspace_id, user_id, data.role, actor_id=ctx.user_id)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(write_limit)
async def remove_member(request: Request, user_id: UUID, ctx: Ctx, service: Service) -> None:
    require_role(ctx, WorkspaceRole.admin)
    deny_agent_bound_workspace_admin(ctx)
    await service.remove(ctx.workspace_id, user_id, actor_id=ctx.user_id)


@router.delete("/{user_id}/memories")
@limiter.limit(write_limit)
async def purge_member_memories(
    request: Request,
    user_id: UUID,
    ctx: Ctx,
    memory: Annotated[MemoryService, Depends(get_memory_service)],
) -> MemoryPurgeResult:
    # Loescht das gesamte Nutzergedaechtnis dieser Person im Workspace
    # (ADR-0053 6.4.1, W5 = a). Antwort nur die Anzahl, nie Inhalt oder IDs
    # (Owner 3a); `audit_log` bekommt eine inhaltsfreie Zeile
    # `memory.user_purged`. Bewusst ohne Mitgliedschaftspruefung: das
    # Nutzergedaechtnis ueberlebt das Entfernen des Mitglieds und muss danach
    # loeschbar bleiben; eine unbekannte Person ergibt `{deleted: 0}`.
    require_role(ctx, WorkspaceRole.admin)
    deny_agent_bound_workspace_admin(ctx)
    return await memory.purge_user_memories(ctx, user_id)
