"""Geschaeftslogik fuer das Usage-/Feedback-Flywheel (ADR-0038).

`record_usage`/`submit_feedback` sind append-only Telemetrie-Writes, gated ueber
die `feedback_write`-Capability (No-Op fuer ungebundene/Mensch-Tokens). Ein
Ereignis wird nur fuer eine Entitaet des eigenen Workspaces akzeptiert (sonst
404 — kein Cross-Workspace-Schreiben, kein Enumerieren). `get_feedback` liefert
das Kurations-Aggregat und ist `editor`-gated (Pflege-Sicht).

Telemetrie fliesst NIE in einen gerenderten System-Prompt (kein Injection-Vektor).
"""

from uuid import UUID

from fastapi import HTTPException, status

from who2be_api.core.security import WorkspaceContext, require_capability, require_role
from who2be_api.repositories.feedback_repository import FeedbackRepository
from who2be_models import (
    AgentCapability,
    AgentFeedbackRead,
    FeedbackCreate,
    FeedbackEvents,
    FeedbackItemCounts,
    FeedbackItems,
    FeedbackOverview,
    FeedbackResolutionCreate,
    FeedbackSummary,
    FeedbackTarget,
    FeedbackUnused,
    SystemFeedbackCreate,
    UsageEventCreate,
    UsageEventRead,
    WorkspaceRole,
)

# Maximale Anzahl Einzel-Ereignisse je Liste in der Drill-down-Sicht.
_EVENTS_LIMIT = 50
# Obergrenze fuer den workspace-weiten Feedback-Posteingang.
_ITEMS_LIMIT = 500


def _entity_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Element nicht gefunden.")


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
        return await self._repo.list_events(
            ctx.workspace_id, entity_type, entity_id, _EVENTS_LIMIT
        )

    async def get_overview(self, ctx: WorkspaceContext) -> FeedbackOverview:
        # Workspace-weite Kurations-Uebersicht (Dashboard-Kacheln + Feedback-Seite).
        require_role(ctx, WorkspaceRole.editor)
        items = await self._repo.overview(ctx.workspace_id)
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

    async def set_resolution(
        self, ctx: WorkspaceContext, feedback_id: UUID, data: FeedbackResolutionCreate
    ) -> AgentFeedbackRead:
        # Triage ist eine Kurations-Handlung → editor+. Append-only Event; das
        # Feedback muss im eigenen Workspace liegen (sonst 404, kein Enumerieren).
        require_role(ctx, WorkspaceRole.editor)
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
