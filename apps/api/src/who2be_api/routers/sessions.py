"""Gespraechsprotokolle und Massnahmen: REST nach ADR-0053 6.6 (Paket E2b-3).

Sieben Routen, Mount unter `/v1/workspaces/{ws_id}`:

- `POST /feedback-sessions` — Protokoll einreichen (Sitzung, Faelle,
  Massnahmen in einer Transaktion; Faelle auf `in_progress`, W-E2 = a).
- `GET /feedback-sessions?agent_id&case_id&due` — Liste, neueste zuerst,
  je Zeile mit Zaehlern (QE1/QE2 = a).
- `GET /feedback-sessions/{id}` — Protokoll mit Massnahmen (QE1 = a).
- `POST /measures/{id}/link-draft` — Entwurf verknuepfen (Weiche E2 = a).
- `GET /measures/{id}/follow-up` — Kennzahlen als Rohzahlen (QE8 = a).
- `POST /measures/{id}/review` — Einstufung, nur Mensch ab `editor`.
- `POST /measures/{id}/withdraw` — Zurueckziehen, nur Mensch ab `editor`.

Rechte, Sichtbarkeit, Event-Folge und die Schreibrate des Agenten entscheiden
`SessionService` (E2b-1) und `MeasureService` (E2b-2); der Router prueft
nichts davon ein zweites Mal und reicht nur durch. Er setzt nur, was die
HTTP-Schicht ausmacht: `write_limit` an jeder schreibenden Route, die
Keyset-Seite der Liste (Cursor im Header `X-Next-Cursor`, Muster
`GET /cases`) und die Form der Request-Bodys.

Der Dossier-Endpunkt `GET /agents/{agent_id}/dossier` aus derselben Tabelle
gehoert nicht zu diesem Paket.
"""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, model_validator

from who2be_api.core.db import get_pool
from who2be_api.core.pagination import MAX_LIMIT, PageCursor
from who2be_api.core.rate_limit import limiter, write_limit
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.repositories.session_repository import PgSessionRepository
from who2be_api.services.measure_service import FollowUpReport, MeasureService
from who2be_api.services.session_service import SessionService, SessionSubmitResult
from who2be_models import (
    EntityType,
    MeasureEventRead,
    MeasureVerdict,
    SessionCreate,
    SessionDetail,
    SessionListItem,
    encode_cursor,
)
from who2be_models.session import MEASURE_EVENT_NOTE_MAX_LENGTH

router = APIRouter(tags=["feedback-sessions"])

# Seitengroesse der Protokoll-Liste, wie die Fall-Liste (Spec S7: 50 je Seite).
SESSION_LIST_LIMIT_DEFAULT = 50


class MeasureLinkDraftRequest(BaseModel):
    """`POST /measures/{id}/link-draft` (6.6): die Version des Entwurfs."""

    model_config = ConfigDict(extra="forbid")

    version_entity_type: EntityType
    version_id: UUID


class MeasureReviewRequest(BaseModel):
    """`POST /measures/{id}/review` (6.6): Einstufung, `ineffective` mit Begruendung."""

    model_config = ConfigDict(extra="forbid")

    verdict: MeasureVerdict
    note: str | None = Field(default=None, min_length=1, max_length=MEASURE_EVENT_NOTE_MAX_LENGTH)

    @model_validator(mode="after")
    def _reason_for_ineffective(self) -> "MeasureReviewRequest":
        # Dieselbe Regel wie `MeasureEventCreate` und der DB-CHECK
        # `measure_event_reason_check` — hier, damit sie als 422 ankommt
        # und nicht erst im Service als Validierungsfehler.
        if self.verdict is MeasureVerdict.ineffective and self.note is None:
            raise ValueError("ineffective verlangt eine Begruendung (note).")
        return self


class MeasureWithdrawRequest(BaseModel):
    """`POST /measures/{id}/withdraw` (6.6): Zurueckziehen braucht eine Begruendung."""

    model_config = ConfigDict(extra="forbid")

    note: str = Field(min_length=1, max_length=MEASURE_EVENT_NOTE_MAX_LENGTH)


class MeasureWithdrawResult(BaseModel):
    """Ergebnis des Zurueckziehens: das Event und die Faelle, die auf `triaged` zurueckgingen."""

    event: MeasureEventRead
    cases_reset: list[UUID]


def _repo(pool: asyncpg.Pool) -> PgSessionRepository:
    return PgSessionRepository(pool)


def get_session_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> SessionService:
    return SessionService(_repo(pool))


def get_measure_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> MeasureService:
    return MeasureService(_repo(pool))


Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]
Sessions = Annotated[SessionService, Depends(get_session_service)]
Measures = Annotated[MeasureService, Depends(get_measure_service)]


# --- Protokolle ---------------------------------------------------------------


@router.post("/feedback-sessions", status_code=status.HTTP_201_CREATED)
@limiter.limit(write_limit)
async def submit_session_protocol(
    request: Request, data: SessionCreate, ctx: Ctx, service: Sessions
) -> SessionSubmitResult:
    # Einreicher setzt der Service aus dem Aufrufweg (Mensch oder Builder).
    return await service.submit_protocol(ctx, data)


@router.get("/feedback-sessions")
async def list_sessions(
    ctx: Ctx,
    service: Sessions,
    response: Response,
    cursor: PageCursor,
    agent_id: UUID | None = None,
    case_id: UUID | None = None,
    due: Annotated[
        bool,
        Query(
            description=(
                "Nur Protokolle mit mindestens einer faelligen Massnahme: Nachschau-Datum "
                "heute oder frueher, weder eingestuft noch zurueckgezogen."
            )
        ),
    ] = False,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = SESSION_LIST_LIMIT_DEFAULT,
) -> list[SessionListItem]:
    # `limit + 1`-Peek wie `GET /cases`: gibt es eine Folgezeile, entsteht
    # der Cursor aus der letzten Zeile der Seite. Mit `due` gilt derselbe
    # Keyset — der Filter wirkt vor dem LIMIT.
    rows = await service.list_sessions(
        ctx, agent_id=agent_id, case_id=case_id, due=due, limit=limit + 1, cursor=cursor
    )
    if len(rows) > limit:
        rows = rows[:limit]
        response.headers["X-Next-Cursor"] = encode_cursor(rows[-1].created_at, rows[-1].id)
    return rows


@router.get("/feedback-sessions/{session_id}")
async def get_session(session_id: UUID, ctx: Ctx, service: Sessions) -> SessionDetail:
    return await service.get_session(ctx, session_id)


# --- Massnahmen ---------------------------------------------------------------


@router.post("/measures/{measure_id}/link-draft", status_code=status.HTTP_201_CREATED)
@limiter.limit(write_limit)
async def link_measure_draft(
    request: Request,
    measure_id: UUID,
    data: MeasureLinkDraftRequest,
    ctx: Ctx,
    service: Measures,
) -> MeasureEventRead:
    return await service.link_draft(ctx, measure_id, data.version_entity_type, data.version_id)


@router.get("/measures/{measure_id}/follow-up")
async def get_measure_follow_up(measure_id: UUID, ctx: Ctx, service: Measures) -> FollowUpReport:
    # Fuer Menschen nur Lesen, deshalb ohne `write_limit` wie jede GET-Route.
    # Ruft der Builder auf, kann ein `follow_up_prepared` entstehen (3.6);
    # diesen Schreibweg bremst der Service ueber die Agent-Schreibrate.
    return await service.follow_up(ctx, measure_id)


@router.post("/measures/{measure_id}/review", status_code=status.HTTP_201_CREATED)
@limiter.limit(write_limit)
async def review_measure(
    request: Request,
    measure_id: UUID,
    data: MeasureReviewRequest,
    ctx: Ctx,
    service: Measures,
) -> MeasureEventRead:
    return await service.review(ctx, measure_id, data.verdict, data.note)


@router.post("/measures/{measure_id}/withdraw")
@limiter.limit(write_limit)
async def withdraw_measure(
    request: Request,
    measure_id: UUID,
    data: MeasureWithdrawRequest,
    ctx: Ctx,
    service: Measures,
) -> MeasureWithdrawResult:
    event, reset = await service.withdraw(ctx, measure_id, data.note)
    return MeasureWithdrawResult(event=event, cases_reset=reset)
