"""Faelle: melden, Liste, Zaehler, Detail, Uebergang, Zuordnung, Schilderung.

ADR-0053 6.5 (Phase D, Paket D2b). Rechte, Sichtbarkeit und Uebergaenge
entscheidet `CaseService` (D2a); der Router reicht nur durch. Mount unter
`/v1/workspaces/{ws_id}`. Nicht hier: Alt-Feedback uebernehmen (D2c) und
Muster (D5b).

Liste nach Repo-Konvention als Keyset-Seite: `list[CaseRead]`, der Cursor der
naechsten Seite im Header `X-Next-Cursor` (`core/pagination.py`). Zaehler je
Status unter `/cases/counts` (PM-Entscheidung Q1), Loeschen ab `editor` (Q6).
"""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from who2be_api.core.db import get_pool
from who2be_api.core.pagination import MAX_LIMIT, PageCursor
from who2be_api.core.rate_limit import limiter, write_limit
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.repositories.case_repository import PgCaseRepository
from who2be_api.services.case_service import CaseService, CaseTransitionRequest
from who2be_models import (
    CaseCreate,
    CaseDetail,
    CaseElementInput,
    CaseElementRead,
    CaseRead,
    CaseStatementCreate,
    CaseStatementRead,
    CaseStatus,
    CaseTarget,
    encode_cursor,
)

router = APIRouter(tags=["cases"])

# Seitengroesse der Fall-Liste (Spec S7: 50 je Seite).
CASE_LIST_LIMIT_DEFAULT = 50
# Obergrenze einer Zuordnung je Fall in einem Aufruf.
CASE_ELEMENTS_MAX = 50


class CaseElementsReplace(BaseModel):
    """`PUT /cases/{id}/elements`: die vollstaendige neue Zuordnung (Replace)."""

    model_config = ConfigDict(extra="forbid")

    elements: list[CaseElementInput] = Field(max_length=CASE_ELEMENTS_MAX)


def get_case_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> CaseService:
    return CaseService(PgCaseRepository(pool))


Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]
Service = Annotated[CaseService, Depends(get_case_service)]


@router.post("/cases", status_code=status.HTTP_201_CREATED)
@limiter.limit(write_limit)
async def report_case(request: Request, data: CaseCreate, ctx: Ctx, service: Service) -> CaseRead:
    # Melden ohne Zuordnung (Q2); Melder setzt der Service aus dem Aufrufweg.
    return await service.report_case(ctx, data)


@router.get("/cases")
async def list_cases(
    ctx: Ctx,
    service: Service,
    response: Response,
    cursor: PageCursor,
    agent_id: UUID | None = None,
    status_filter: Annotated[CaseStatus | None, Query(alias="status")] = None,
    target: CaseTarget | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = CASE_LIST_LIMIT_DEFAULT,
) -> list[CaseRead]:
    # Neueste zuerst. `limit + 1`-Peek wie im Bestand: gibt es eine
    # Folgezeile, entsteht der Cursor aus der letzten Zeile der Seite.
    rows = await service.list_cases(
        ctx,
        agent_id=agent_id,
        status_filter=status_filter,
        target=target,
        limit=limit + 1,
        cursor=cursor,
    )
    if len(rows) > limit:
        rows = rows[:limit]
        response.headers["X-Next-Cursor"] = encode_cursor(rows[-1].created_at, rows[-1].id)
    return rows


@router.get("/cases/counts")
async def count_cases(
    ctx: Ctx, service: Service, agent_id: UUID | None = None
) -> dict[CaseStatus, int]:
    # Je Status (auch 0), dieselbe Sichtbarkeit wie die Liste (Q1).
    return await service.count_by_status(ctx, agent_id=agent_id)


@router.get("/cases/{case_id}")
async def get_case(case_id: UUID, ctx: Ctx, service: Service) -> CaseDetail:
    return await service.get_case(ctx, case_id)


@router.delete("/cases/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(write_limit)
async def delete_case(request: Request, case_id: UUID, ctx: Ctx, service: Service) -> None:
    # Loeschen samt Verlauf, ab editor, Agenten nie (Q6).
    await service.delete_case(ctx, case_id)


@router.post("/cases/{case_id}/transition")
@limiter.limit(write_limit)
async def transition_case(
    request: Request, case_id: UUID, data: CaseTransitionRequest, ctx: Ctx, service: Service
) -> CaseRead:
    return await service.transition(ctx, case_id, data)


@router.put("/cases/{case_id}/elements")
@limiter.limit(write_limit)
async def replace_case_elements(
    request: Request, case_id: UUID, data: CaseElementsReplace, ctx: Ctx, service: Service
) -> list[CaseElementRead]:
    # Replace-Semantik: die Liste ersetzt die bisherige Zuordnung vollstaendig.
    return await service.set_elements(ctx, case_id, data.elements)


@router.post("/cases/{case_id}/statement", status_code=status.HTTP_201_CREATED)
@limiter.limit(write_limit)
async def add_case_statement(
    request: Request, case_id: UUID, data: CaseStatementCreate, ctx: Ctx, service: Service
) -> CaseStatementRead:
    return await service.add_statement(ctx, case_id, data)
