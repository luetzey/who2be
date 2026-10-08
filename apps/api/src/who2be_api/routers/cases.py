"""Faelle: melden, Liste, Zaehler, Detail, Uebergang, Zuordnung, Schilderung.

ADR-0053 6.5 (Phase D, Paket D2b). Rechte, Sichtbarkeit und Uebergaenge
entscheidet `CaseService` (D2a); der Router reicht nur durch. Mount unter
`/v1/workspaces/{ws_id}`.

Paket D2c-2: die zwei Wege, auf denen aus Bestehendem ein Fall wird —
`POST /agents/{agent_id}/memories/{memory_id}/convert` (Lernvorschlag, 6.4)
und `POST /feedback/{feedback_id}/promote` (Alt-Feedback, 6.5). Beide stehen
hier statt in `memory.py`/`feedback.py`, weil sie nur `CaseService` rufen und
einen `CaseRead` liefern (PM-Schnitt 2026-10-08).

Liste nach Repo-Konvention als Keyset-Seite: `list[CaseRead]`, der Cursor der
naechsten Seite im Header `X-Next-Cursor` (`core/pagination.py`). Zaehler je
Status unter `/cases/counts` (PM-Entscheidung Q1), Loeschen ab `editor` (Q6).

Paket D5b: `GET /patterns?agent_id` (6.5) steht ebenfalls hier, wie ADR-0053
Anhang A.2 es fuer D5 vorsieht. Muster sind eine berechnete Sicht ueber Faelle
und Lernvorschlaege ohne eigenes Aggregat; ein eigener Router fuer eine
einzige lesende Route waere eine zweite Mount-Stelle in `main.py` ohne Gewinn.
Recht und Berechnung entscheidet `PatternService` (D5a).
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
from who2be_api.repositories.memory_repository import PgMemoryRepository
from who2be_api.services.case_service import CaseService, CaseTransitionRequest
from who2be_api.services.pattern_service import PatternService
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
from who2be_models.case import CaseConvertRequest
from who2be_models.pattern import PATTERN_CASE_WINDOW_DAYS, PATTERN_MIN_COUNT, PatternList

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


def get_pattern_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> PatternService:
    return PatternService(PgCaseRepository(pool), PgMemoryRepository(pool))


Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]
Service = Annotated[CaseService, Depends(get_case_service)]
Patterns = Annotated[PatternService, Depends(get_pattern_service)]


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


# --- Umwandeln / Uebernehmen (D2c-2) ---------------------------------------


@router.post("/agents/{agent_id}/memories/{memory_id}/convert", status_code=status.HTTP_201_CREATED)
@limiter.limit(write_limit)
async def convert_memory_to_case(
    request: Request,
    agent_id: UUID,
    memory_id: UUID,
    data: CaseConvertRequest,
    ctx: Ctx,
    service: Service,
) -> CaseRead:
    # Body ohne agent_id: der Agent kommt aus dem Lernvorschlag (PM-Weiche 1).
    # Nur Mensch ab editor; zweites convert -> 409 memory_not_convertible.
    return await service.convert_lesson(ctx, agent_id, memory_id, data)


@router.post("/feedback/{feedback_id}/promote", status_code=status.HTTP_201_CREATED)
@limiter.limit(write_limit)
async def promote_feedback_to_case(
    request: Request, feedback_id: UUID, data: CaseCreate, ctx: Ctx, service: Service
) -> CaseRead:
    # Den Agenten nennt der Mensch (ein Alt-Feedback betrifft ein Element).
    # Nur Mensch ab editor; erneut -> 409 feedback_not_promotable.
    return await service.promote_feedback(ctx, feedback_id, data)


# --- Muster (D5b) -----------------------------------------------------------


@router.get("/patterns")
async def list_patterns(ctx: Ctx, service: Patterns, agent_id: UUID | None = None) -> PatternList:
    # editor bzw. case_triage (6.5), sonst 403 aus dem Service. Schwelle und
    # Zeitfenster gehen mit (Q8), damit die UI sie nicht fest kodiert.
    patterns = await service.list_patterns(ctx, agent_id=agent_id)
    return PatternList(
        threshold=PATTERN_MIN_COUNT, window_days=PATTERN_CASE_WINDOW_DAYS, patterns=patterns
    )
