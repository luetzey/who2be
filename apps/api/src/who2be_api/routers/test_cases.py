"""Pruefaelle, Prueflaeufe und Pruefbericht (ADR-0053 6.2, Lernschleife B2).

Rechte, Sichtbarkeit und `attestation` entscheidet `TestCaseService`; der
Router reicht nur durch. Mount unter `/v1/workspaces/{ws_id}`.
"""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query, Request, status

from who2be_api.core.db import get_pool
from who2be_api.core.rate_limit import limiter, write_limit
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.repositories.test_case_repository import PgTestCaseRepository
from who2be_api.services.test_case_service import (
    TestCaseCreateRequest,
    TestCaseService,
    TestReport,
    TestRunSubmit,
)
from who2be_models import EntityType, TestCaseRead, TestCaseStatus, TestRunRead

router = APIRouter(tags=["test-cases"])


def get_test_case_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> TestCaseService:
    return TestCaseService(PgTestCaseRepository(pool))


Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]
Service = Annotated[TestCaseService, Depends(get_test_case_service)]


@router.post("/test-cases", status_code=status.HTTP_201_CREATED)
@limiter.limit(write_limit)
async def create_test_case(
    request: Request, data: TestCaseCreateRequest, ctx: Ctx, service: Service
) -> TestCaseRead:
    # Mit `supersedes_id` eine Korrektur: neuer Pruefall + retire des alten
    # in einer Transaktion (nur Menschen mit editor).
    return await service.create_case(ctx, data)


@router.get("/test-cases")
async def list_test_cases(
    ctx: Ctx,
    service: Service,
    agent_id: UUID | None = None,
    entity_type: EntityType | None = None,
    entity_id: UUID | None = None,
    status_filter: Annotated[TestCaseStatus | None, Query(alias="status")] = None,
    origin_case_id: UUID | None = None,
) -> list[TestCaseRead]:
    # `origin_case_id`: die aus einem Fall abgeleiteten Pruefaelle (D6-API2).
    return await service.list_cases(
        ctx,
        agent_id=agent_id,
        entity_type=entity_type,
        entity_id=entity_id,
        status_filter=status_filter,
        origin_case_id=origin_case_id,
    )


@router.get("/test-cases/{case_id}")
async def get_test_case(case_id: UUID, ctx: Ctx, service: Service) -> TestCaseRead:
    return await service.get_case(ctx, case_id)


@router.post("/test-cases/{case_id}/retire")
@limiter.limit(write_limit)
async def retire_test_case(
    request: Request, case_id: UUID, ctx: Ctx, service: Service
) -> TestCaseRead:
    return await service.retire_case(ctx, case_id)


@router.post("/test-runs", status_code=status.HTTP_201_CREATED)
@limiter.limit(write_limit)
async def submit_test_runs(
    request: Request, data: TestRunSubmit, ctx: Ctx, service: Service
) -> list[TestRunRead]:
    # `attestation` setzt der Service aus dem Aufrufweg; der Body kennt kein
    # solches Feld (extra="forbid" -> 422, wenn eins mitkommt).
    return await service.submit_runs(ctx, data)


@router.get("/versions/{entity_type}/{version_id}/test-report")
async def get_test_report(
    entity_type: EntityType, version_id: UUID, ctx: Ctx, service: Service
) -> TestReport:
    return await service.get_test_report(ctx, entity_type, version_id)
