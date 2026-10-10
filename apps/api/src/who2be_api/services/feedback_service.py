"""Geschaeftslogik fuer das Usage-/Feedback-Flywheel (ADR-0038).

`record_usage`/`submit_feedback` sind append-only Telemetrie-Writes, gated ueber
die `feedback_write`-Capability (No-Op fuer ungebundene/Mensch-Tokens). Ein
Ereignis wird nur fuer eine Entitaet des eigenen Workspaces akzeptiert (sonst
404 — kein Cross-Workspace-Schreiben, kein Enumerieren). `get_feedback` liefert
das Kurations-Aggregat und ist `editor`-gated (Pflege-Sicht).

Telemetrie fliesst NIE in einen gerenderten System-Prompt (kein Injection-Vektor).
"""

from uuid import UUID

from fastapi import status

from who2be_api.core.errors import ApiError, ApiGateError
from who2be_api.core.security import (
    WorkspaceContext,
    is_agent_bound,
    require_capability,
    require_role,
)
from who2be_api.core.workarea_scope import agent_not_found
from who2be_api.repositories.feedback_repository import FeedbackRepository
from who2be_models import (
    AgentCapability,
    AgentFeedbackRead,
    FeedbackCreate,
    FeedbackDetailRead,
    FeedbackEvents,
    FeedbackItemCounts,
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
    WorkspaceRole,
)

# Maximale Anzahl Einzel-Ereignisse je Liste in der Drill-down-Sicht.
_EVENTS_LIMIT = 50
# Obergrenze fuer den workspace-weiten Feedback-Posteingang.
_ITEMS_LIMIT = 500


def _entity_not_found() -> ApiError:
    return ApiError(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Element nicht gefunden.",
        reason="feedback_element_not_found",
    )


class FeedbackService:
    """Schreibt Usage-/Feedback-Ereignisse und liefert das Kurations-Aggregat."""

    def __init__(self, repo: FeedbackRepository) -> None:
        self._repo = repo

    async def record_usage(self, ctx: WorkspaceContext, data: UsageEventCreate) -> UsageEventRead:
        require_capability(ctx, AgentCapability.feedback_write)
        if not await self._repo.entity_belongs_to(
            ctx.workspace_id, data.entity_type, data.entity_id
        ):
            raise _entity_not_found()
        return await self._repo.insert_usage(
            ctx.workspace_id,
            ctx.agent_id,
            ctx.user_id,
            data.entity_type,
            data.entity_id,
            data.version,
            data.outcome.value if data.outcome is not None else None,
        )

    async def submit_feedback(
        self, ctx: WorkspaceContext, data: FeedbackCreate
    ) -> AgentFeedbackRead:
        # Inhalts-Feedback ist eine Kurations-Handlung → editor+ (viewer darf nicht
        # schreiben). Agent-gebundene Tokens brauchen zusaetzlich die feedback_write-
        # Capability (No-Op fuer Mensch/JWT und ungebundene Tokens).
        require_role(ctx, WorkspaceRole.editor)
        require_capability(ctx, AgentCapability.feedback_write)
        if not await self._repo.entity_belongs_to(
            ctx.workspace_id, data.entity_type, data.entity_id
        ):
            raise _entity_not_found()
        return await self._repo.insert_feedback(
            ctx.workspace_id,
            ctx.agent_id,
            ctx.user_id,
            data.entity_type,
            data.entity_id,
            data.version,
            data.signal.value,
            data.note,
        )

    async def submit_system_feedback(
        self, ctx: WorkspaceContext, data: SystemFeedbackCreate
    ) -> AgentFeedbackRead:
        # Zielloses System-/MCP-Problem — wie das Inhalts-Feedback ueber die
        # feedback_write-Capability gated (No-Op fuer Mensch/JWT; ein
        # agent-gebundener Token braucht die Capability). Kein entity-belongs-to-
        # Check, da das Feedback an keinem Inhalt haengt.
        require_capability(ctx, AgentCapability.feedback_write)
        return await self._repo.insert_system_feedback(
            ctx.workspace_id,
            ctx.agent_id,
            ctx.user_id,
            data.category.value,
            data.note,
        )

    async def get_feedback(
        self, ctx: WorkspaceContext, entity_type: FeedbackTarget, entity_id: UUID
    ) -> FeedbackSummary:
        # Kurations-Sicht: editor+ (Pflege-Entscheidungen leiten sich hieraus ab).
        require_role(ctx, WorkspaceRole.editor)
        if not await self._repo.entity_belongs_to(ctx.workspace_id, entity_type, entity_id):
            raise _entity_not_found()
        return await self._repo.summarize(ctx.workspace_id, entity_type, entity_id)

    async def get_events(
        self, ctx: WorkspaceContext, entity_type: FeedbackTarget, entity_id: UUID
    ) -> FeedbackEvents:
        # Drill-down auf Einzel-Ereignisse — wie das Aggregat editor-gated.
        require_role(ctx, WorkspaceRole.editor)
        if not await self._repo.entity_belongs_to(ctx.workspace_id, entity_type, entity_id):
            raise _entity_not_found()
        return await self._repo.list_events(ctx.workspace_id, entity_type, entity_id, _EVENTS_LIMIT)

    async def get_overview(
        self, ctx: WorkspaceContext, agent_id: UUID | None = None, days: int | None = None
    ) -> FeedbackOverview:
        # Workspace-weite Kurations-Uebersicht (Dashboard-Kacheln + Feedback-Seite).
        # Navigation A6: optional je Agent (`agent_id`) und Zeitraum (`days`).
        # Rechte bleiben editor+ (PM-Weiche W2) — die Rolle wird VOR dem
        # Agent-Lookup geprueft, damit ein viewer keine Agent-IDs enumeriert.
        require_role(ctx, WorkspaceRole.editor)
        if agent_id is not None and not await self._repo.agent_exists(ctx.workspace_id, agent_id):
            raise agent_not_found()
        items = await self._repo.overview(ctx.workspace_id, agent_id=agent_id, days=days)
        return FeedbackOverview(items=items)

    async def get_unused(self, ctx: WorkspaceContext) -> FeedbackUnused:
        # Veroeffentlichte, aber ungenutzte Elemente (Stale-Kandidaten).
        require_role(ctx, WorkspaceRole.editor)
        items = await self._repo.unused(ctx.workspace_id)
        return FeedbackUnused(items=items)

    async def get_items(self, ctx: WorkspaceContext) -> FeedbackItems:
        # Zentraler Posteingang: alle Feedbacks + Status-Zaehler fuer die KPI-
        # Leiste. Die Zaehler leiten sich aus derselben (gekappten) Liste ab —
        # bei realistischem Kurations-Volumen exakt.
        require_role(ctx, WorkspaceRole.editor)
        items = await self._repo.list_items(ctx.workspace_id, _ITEMS_LIMIT)
        counts = FeedbackItemCounts(
            open=sum(1 for i in items if i.resolution is None),
            in_progress=sum(1 for i in items if i.resolution == "in_progress"),
            addressed=sum(1 for i in items if i.resolution == "addressed"),
            dismissed=sum(1 for i in items if i.resolution == "dismissed"),
        )
        return FeedbackItems(items=items, counts=counts)

    async def get_detail(self, ctx: WorkspaceContext, feedback_id: UUID) -> FeedbackDetailRead:
        # Einzel-Feedback-Detailsicht: wie der Posteingang (get_items) editor-gated
        # (Kurations-Sicht). 404, wenn das Feedback nicht im eigenen Workspace liegt
        # (kein Enumerieren) — deckt auch das geloeschte Inhalts-Element ab, dessen
        # Namens-JOIN dann leer bleibt.
        require_role(ctx, WorkspaceRole.editor)
        detail = await self._repo.get_detail(ctx.workspace_id, feedback_id)
        if detail is None:
            raise _entity_not_found()
        return detail

    async def set_resolution(
        self, ctx: WorkspaceContext, feedback_id: UUID, data: FeedbackResolutionCreate
    ) -> AgentFeedbackRead:
        # Triage ist eine Kurations-Handlung → editor+. Agent-gebundene Tokens
        # brauchen zusaetzlich die feedback_resolve-Capability (Default aus;
        # No-Op fuer Mensch/JWT und ungebundene Tokens). Append-only Event; das
        # Feedback muss im eigenen Workspace liegen (sonst 404, kein Enumerieren).
        require_role(ctx, WorkspaceRole.editor)
        require_capability(ctx, AgentCapability.feedback_resolve)
        if not await self._repo.feedback_belongs_to(ctx.workspace_id, feedback_id):
            raise _entity_not_found()
        return await self._repo.insert_resolution(
            ctx.workspace_id,
            feedback_id,
            ctx.user_id,
            data.resolution.value,
            data.note,
        )

    async def delete_feedback(self, ctx: WorkspaceContext, feedback_id: UUID) -> None:
        # Hard-Delete eines Feedback-Eintrags ist eine Kurations-Handlung →
        # editor+ (Admin/Editor). Das Feedback muss im eigenen Workspace liegen
        # (sonst 404, kein Enumerieren). Die Triage-Events (feedback_resolution)
        # raeumt der FK ON DELETE CASCADE mit.
        require_role(ctx, WorkspaceRole.editor)
        if not await self._repo.feedback_belongs_to(ctx.workspace_id, feedback_id):
            raise _entity_not_found()
        await self._repo.delete_feedback(ctx.workspace_id, feedback_id)

    async def get_usage(
        self, ctx: WorkspaceContext, entity_type: UsageEntityType, entity_id: UUID
    ) -> UsageStats:
        # Nutzung U1: Zaehler je Element. Ab viewer (Spec §3.2 „Nutzung · ab
        # viewer“) — reine Zaehler ohne Personenbezug. Agent-gebundene Tokens
        # bleiben draussen: die Liste nennt alle Elemente des Workspace und
        # umginge den Lese-Scope ihrer Policy; die Zaehler sind eine Web-Sicht.
        _deny_agent_bound_usage(ctx)
        require_role(ctx, WorkspaceRole.viewer)
        if not await self._repo.entity_belongs_to(ctx.workspace_id, entity_type, entity_id):
            raise _entity_not_found()
        return await self._repo.usage_stats(ctx.workspace_id, entity_type, entity_id)

    async def list_usage(
        self, ctx: WorkspaceContext, entity_type: UsageEntityType | None = None
    ) -> UsageList:
        # Nutzung U1 fuer Listenspalten („Zuletzt genutzt“, „30 Tage“).
        _deny_agent_bound_usage(ctx)
        require_role(ctx, WorkspaceRole.viewer)
        items = await self._repo.usage_list(ctx.workspace_id, entity_type)
        return UsageList(items=items)


def _deny_agent_bound_usage(ctx: WorkspaceContext) -> None:
    """403 fuer agent-gebundene Tokens auf den Nutzungszaehlern (`is_agent_bound`)."""
    if is_agent_bound(ctx):
        raise ApiGateError(
            status=status.HTTP_403_FORBIDDEN,
            reason="missing_capability",
            actionable_by="human",
            detail=(
                "Nutzungszaehler sind eine Sicht fuer Menschen im Web — ein "
                "agent-gebundener Token liest sie nicht."
            ),
        )
