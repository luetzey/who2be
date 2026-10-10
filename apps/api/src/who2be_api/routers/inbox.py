"""Aufgaben-Zaehler: `GET /inbox/counts[?agent_id]` (Navigation & Transparenz W1).

Eine lesende Route fuer Glocke, Dashboard-Zeile und Agent-Ueberblick (Spec
§2.6 a: ein Request statt 5–6). Rollen und Arten entscheidet `InboxService`;
der Router reicht nur durch. Mount unter `/v1/workspaces/{ws_id}`.
"""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends

from who2be_api.core.db import get_pool
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.repositories.case_repository import PgCaseRepository
from who2be_api.repositories.dashboard_repository import PgDashboardRepository
from who2be_api.repositories.memory_repository import PgMemoryRepository
from who2be_api.repositories.session_repository import PgSessionRepository
from who2be_api.services.case_service import CaseService
from who2be_api.services.inbox_service import InboxService
from who2be_api.services.memory_service import MemoryService
from who2be_api.services.pattern_service import PatternService
from who2be_models.inbox import InboxCounts

router = APIRouter(prefix="/inbox", tags=["inbox"])


def get_inbox_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> InboxService:
    cases = PgCaseRepository(pool)
    memories = PgMemoryRepository(pool)
    return InboxService(
        memories=MemoryService(memories),
        cases=CaseService(cases),
        patterns=PatternService(cases, memories),
        dashboard=PgDashboardRepository(pool),
        sessions=PgSessionRepository(pool),
    )


Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]
Service = Annotated[InboxService, Depends(get_inbox_service)]


@router.get("/counts")
async def get_inbox_counts(ctx: Ctx, service: Service, agent_id: UUID | None = None) -> InboxCounts:
    # Je Art eine Zahl oder `null` (Art fuer diese Rolle nicht vorhanden);
    # `total` ist die Zahl an der Glocke (Spec §2.2).
    return await service.counts(ctx, agent_id=agent_id)
