"""Reverse-Lookup-Endpunkte (Phase 3-A) fuer Playbook- und Resource-Backlinks.

Eigene Router-Datei, weil die Endpunkte zwei verschiedene Prefixe teilen
(`/playbooks/{id}/usages` und `/resources/{id}/usages`) und in
`routers/playbooks.py`/`routers/resources.py` mit dem CRUD-Pfad kollidieren
wuerden (UUID-Validation auf `/{playbook_id}`).
"""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends

from who2be_api.core.db import get_pool
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.repositories.usage_repository import PgUsageRepository
from who2be_api.services.usage_service import UsageService
from who2be_models import PlaybookUsage, ResourceUsage

router = APIRouter(tags=["usages"])


def get_usage_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> UsageService:
    return UsageService(PgUsageRepository(pool))


Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]
Service = Annotated[UsageService, Depends(get_usage_service)]


@router.get("/playbooks/{playbook_id}/usages")
async def list_playbook_usages(
    playbook_id: UUID, ctx: Ctx, service: Service
) -> list[PlaybookUsage]:
    return await service.list_playbook_usages(ctx, playbook_id)


@router.get("/resources/{resource_id}/usages")
async def list_resource_usages(
    resource_id: UUID, ctx: Ctx, service: Service
) -> list[ResourceUsage]:
    return await service.list_resource_usages(ctx, resource_id)
