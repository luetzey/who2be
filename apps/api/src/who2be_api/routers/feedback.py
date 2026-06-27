"""Usage-/Feedback-Flywheel-Endpunkte (ADR-0038).

Append-only Telemetrie: Agenten melden Nutzung + Feedback; Kuratoren lesen das
Aggregat. Autorisierung (feedback_write-Capability bzw. editor-Rolle) liegt im
Service. Mount unter `/v1/workspaces/{ws_id}`.
"""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends

from who2be_api.core.db import get_pool
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.repositories.feedback_repository import PgFeedbackRepository
from who2be_api.services.feedback_service import FeedbackService
from who2be_models import (
    AgentFeedbackRead,
    FeedbackCreate,
    FeedbackEvents,
    FeedbackItems,
    FeedbackOverview,
    FeedbackResolutionCreate,
    FeedbackSummary,
    FeedbackTarget,
    FeedbackUnused,
    UsageEventCreate,
    UsageEventRead,
)

router = APIRouter(tags=["feedback"])


def get_feedback_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> FeedbackService:
    return FeedbackService(PgFeedbackRepository(pool))


Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]
Service = Annotated[FeedbackService, Depends(get_feedback_service)]


@router.post("/usage-events", status_code=201)
async def record_usage(data: UsageEventCreate, ctx: Ctx, service: Service) -> UsageEventRead:
    return await service.record_usage(ctx, data)


@router.post("/feedback", status_code=201)
async def submit_feedback(data: FeedbackCreate, ctx: Ctx, service: Service) -> AgentFeedbackRead:
    return await service.submit_feedback(ctx, data)


@router.get("/feedback-items")
async def get_feedback_items(ctx: Ctx, service: Service) -> FeedbackItems:
    return await service.get_items(ctx)


@router.get("/feedback-overview")
async def get_feedback_overview(ctx: Ctx, service: Service) -> FeedbackOverview:
    return await service.get_overview(ctx)


@router.get("/feedback-unused")
async def get_feedback_unused(ctx: Ctx, service: Service) -> FeedbackUnused:
    return await service.get_unused(ctx)


@router.get("/feedback/{entity_type}/{entity_id}")
async def get_feedback(
    entity_type: FeedbackTarget, entity_id: UUID, ctx: Ctx, service: Service
) -> FeedbackSummary:
    return await service.get_feedback(ctx, entity_type, entity_id)


@router.get("/feedback/{entity_type}/{entity_id}/events")
async def get_feedback_events(
    entity_type: FeedbackTarget, entity_id: UUID, ctx: Ctx, service: Service
) -> FeedbackEvents:
    return await service.get_events(ctx, entity_type, entity_id)


@router.post("/feedback/{feedback_id}/resolution", status_code=201)
async def set_feedback_resolution(
    feedback_id: UUID, data: FeedbackResolutionCreate, ctx: Ctx, service: Service
) -> AgentFeedbackRead:
    return await service.set_resolution(ctx, feedback_id, data)
