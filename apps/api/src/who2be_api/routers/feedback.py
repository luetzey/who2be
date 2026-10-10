"""Usage-/Feedback-Flywheel-Endpunkte (ADR-0038).

Append-only Telemetrie: Agenten melden Nutzung + Feedback; Kuratoren lesen das
Aggregat. Autorisierung (feedback_write-Capability bzw. editor-Rolle) liegt im
Service. Mount unter `/v1/workspaces/{ws_id}`.
"""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query

from who2be_api.core.db import get_pool
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.repositories.feedback_repository import PgFeedbackRepository
from who2be_api.services.feedback_service import FeedbackService
from who2be_models import (
    AgentFeedbackRead,
    AgentUsageStats,
    ApiErrorBody,
    FeedbackCreate,
    FeedbackDetailRead,
    FeedbackEvents,
    FeedbackItems,
    FeedbackOverview,
    FeedbackResolutionCreate,
    FeedbackSummary,
    FeedbackTarget,
    FeedbackUnused,
    SystemFeedbackCreate,
    UsageEntityType,
    UsageEventCreate,
    UsageEventRead,
    UsageList,
    UsageStats,
    WorkAreaUsageStats,
)

router = APIRouter(tags=["feedback"])


def get_feedback_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> FeedbackService:
    return FeedbackService(PgFeedbackRepository(pool), pool)


Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]
Service = Annotated[FeedbackService, Depends(get_feedback_service)]


@router.post("/usage-events", status_code=201)
async def record_usage(data: UsageEventCreate, ctx: Ctx, service: Service) -> UsageEventRead:
    return await service.record_usage(ctx, data)


@router.post("/feedback", status_code=201)
async def submit_feedback(data: FeedbackCreate, ctx: Ctx, service: Service) -> AgentFeedbackRead:
    return await service.submit_feedback(ctx, data)


@router.post("/system-feedback", status_code=201)
async def submit_system_feedback(
    data: SystemFeedbackCreate, ctx: Ctx, service: Service
) -> AgentFeedbackRead:
    # Zielloses System-/MCP-Problem (kein entity-Bezug). feedback_write-Gate im
    # Service (No-Op fuer Mensch/JWT). Erscheint im Kurations-Posteingang.
    return await service.submit_system_feedback(ctx, data)


@router.get("/feedback-items")
async def get_feedback_items(ctx: Ctx, service: Service) -> FeedbackItems:
    return await service.get_items(ctx)


@router.get(
    "/feedback-overview",
    # ADR-0051: der Fehler-Body ist Teil des Vertrags. Nur deklarativ — den
    # `reason` setzt der Service.
    responses={404: {"model": ApiErrorBody, "description": "reason: agent_not_found"}},
)
async def get_feedback_overview(
    ctx: Ctx,
    service: Service,
    agent_id: Annotated[
        UUID | None,
        Query(description="Nur Ereignisse dieses Agenten (Nutzung und Feedback)."),
    ] = None,
    days: Annotated[
        int | None,
        Query(ge=1, le=365, description="Nur Ereignisse der letzten N Tage (1..365)."),
    ] = None,
) -> FeedbackOverview:
    # Navigation A6: ohne Parameter unveraendert die Gesamtsumme des Workspace.
    return await service.get_overview(ctx, agent_id=agent_id, days=days)


@router.get("/feedback-unused")
async def get_feedback_unused(ctx: Ctx, service: Service) -> FeedbackUnused:
    return await service.get_unused(ctx)


@router.get("/feedback/{feedback_id}")
async def get_feedback_detail(feedback_id: UUID, ctx: Ctx, service: Service) -> FeedbackDetailRead:
    # Detailsicht auf ein einzelnes Feedback (Absender + Triage-Historie). Ein
    # Pfadsegment — kollidiert nicht mit der zwei-segmentigen Aggregat-Route
    # `/feedback/{entity_type}/{entity_id}`. 404, wenn nicht im eigenen Workspace.
    return await service.get_detail(ctx, feedback_id)


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


@router.delete("/feedback/{feedback_id}", status_code=204)
async def delete_feedback(feedback_id: UUID, ctx: Ctx, service: Service) -> None:
    # Hard-Delete eines Feedback-Eintrags (editor+). 404, wenn das Feedback
    # nicht im eigenen Workspace liegt; 204 bei Erfolg.
    await service.delete_feedback(ctx, feedback_id)


@router.get("/usage")
async def list_usage(
    ctx: Ctx,
    service: Service,
    entity_type: Annotated[
        UsageEntityType | None,
        Query(description="Nur Elemente dieses Typs; ohne Angabe alle drei."),
    ] = None,
) -> UsageList:
    # Nutzung U1: Zaehler je Element fuer Listen (ohne Tagesreihe).
    return await service.list_usage(ctx, entity_type)


@router.get(
    "/usage/{entity_type}/{entity_id}",
    responses={404: {"model": ApiErrorBody, "description": "reason: feedback_element_not_found"}},
)
async def get_usage(
    entity_type: UsageEntityType, entity_id: UUID, ctx: Ctx, service: Service
) -> UsageStats:
    # Nutzung U1: 7/30 Tage, zuletzt genutzt, Agenten, Tagesreihe 30 Tage.
    return await service.get_usage(ctx, entity_type, entity_id)


@router.get(
    "/agents/{agent_id}/usage",
    responses={404: {"model": ApiErrorBody, "description": "reason: agent_not_found"}},
)
async def get_agent_usage(agent_id: UUID, ctx: Ctx, service: Service) -> AgentUsageStats:
    # Nutzung U2: Abrufe 7/30 Tage, je Art, aktive Tage, zuletzt genutzt/aktiv,
    # Arbeitsbereiche mit Zugriffstagen. Ab viewer, nicht fuer Agent-Tokens.
    return await service.get_agent_usage(ctx, agent_id)


@router.get(
    "/work-areas/{area_id}/usage",
    responses={404: {"model": ApiErrorBody, "description": "reason: area_not_found"}},
)
async def get_work_area_usage(area_id: UUID, ctx: Ctx, service: Service) -> WorkAreaUsageStats:
    # Nutzung U2: Zugriffstage, Lese-/Schreibzugriffe, Agentenzahl, zuletzt am
    # (Datum) aus dem Zugriffslog. Ab viewer (nur sichtbare Bereiche).
    return await service.get_work_area_usage(ctx, area_id)
