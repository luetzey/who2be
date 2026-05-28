"""REST-Endpoint fuers Workspace-Dashboard (Phase 2.1b-B).

Pfad: `GET /v1/workspaces/{workspace_id}/dashboard` (Prefix kommt aus
`main.py`). Read-only — die Membership-Pruefung uebernimmt
`get_current_workspace`, exakt wie bei `personas.py`.
"""

from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends

from who2be_api.core.db import get_pool
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.repositories.dashboard_repository import PgDashboardRepository
from who2be_api.services.dashboard_service import DashboardService
from who2be_models import DashboardResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def get_dashboard_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> DashboardService:
    return DashboardService(PgDashboardRepository(pool))


Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]
Service = Annotated[DashboardService, Depends(get_dashboard_service)]


@router.get("")
async def get_dashboard(ctx: Ctx, service: Service) -> DashboardResponse:
    return await service.fetch(ctx)
