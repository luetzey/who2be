"""Aufgaben-Zaehler (`GET /inbox/counts`, Navigation & Transparenz W1).

Spec `navigation-transparenz-design-2026-10.md` §2.2 (Arten und Rollen),
§2.6 a (ein Endpunkt statt 5–6 Einzel-Requests), §5 A1. Weiche N1 a: eine
Aufgabe ist ein offener Zustand, kein gespeicherter Eintrag — deshalb keine
Tabelle, nur Zaehlungen ueber bestehende Abfragen.

Sichtbarkeit wird nicht neu erfunden: jede Zahl kommt ueber den Service, der
auch die zugehoerige Liste liefert (`MemoryService`, `CaseService`,
`PatternService`). Ein viewer sieht damit genau die Zahl, die ihm seine Liste
zeigt (nur eigenes Nutzergedaechtnis). Neu ist nur die Faellig-Zaehlung der
Massnahmen; die Regel steht in `PgSessionRepository.count_due_measures`.

Nur Menschen: der Eingang ist eine Web-Sicht (N10 a). Ein agent-gebundener
Token bekommt 403 wie bei der Memory-Verwaltung.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime
from uuid import UUID

from fastapi import status

from who2be_api.core.errors import ApiGateError
from who2be_api.core.security import (
    WorkspaceContext,
    is_agent_bound,
    require_role,
    role_satisfies,
)
from who2be_api.repositories.dashboard_repository import DashboardRepository
from who2be_api.repositories.session_repository import SessionRepository
from who2be_api.services.case_service import CaseService
from who2be_api.services.memory_service import MemoryService
from who2be_api.services.pattern_service import PatternService
from who2be_models import CaseStatus, VersionStatus, WorkspaceRole
from who2be_models.inbox import InboxCounts
from who2be_models.memory import MemoryFilter, MemoryProposalStatus, MemoryScope, MemoryStatus

# Art 4 „Rueckmeldungen, nicht eingeordnet“ (Spec §2.2): neu oder wieder offen.
INBOX_CASE_STATUSES: frozenset[CaseStatus] = frozenset({CaseStatus.open, CaseStatus.reopened})


def _today_utc() -> date:
    return datetime.now(UTC).date()


def _agent_bound_forbidden() -> ApiGateError:
    return ApiGateError(
        status=status.HTTP_403_FORBIDDEN,
        reason="missing_capability",
        actionable_by="human",
        detail="Der Aufgaben-Eingang ist Menschen vorbehalten.",
    )


class InboxService:
    """Zaehlt offene Aufgaben je Art, rollengerecht (Spec §2.2)."""

    def __init__(
        self,
        *,
        memories: MemoryService,
        cases: CaseService,
        patterns: PatternService,
        dashboard: DashboardRepository,
        sessions: SessionRepository,
        today: Callable[[], date] = _today_utc,
    ) -> None:
        self._memories = memories
        self._cases = cases
        self._patterns = patterns
        self._dashboard = dashboard
        self._sessions = sessions
        self._today = today

    async def counts(self, ctx: WorkspaceContext, *, agent_id: UUID | None = None) -> InboxCounts:
        if is_agent_bound(ctx):
            raise _agent_bound_forbidden()
        require_role(ctx, WorkspaceRole.viewer)
        # Zuerst: prueft `agent_id` (404 `agent_not_found` fuer fremde/unbekannte
        # Agenten), bevor eine andere Zahl entsteht.
        memory_approval = await self._memory_approval(ctx, agent_id)
        if not role_satisfies(ctx.role, WorkspaceRole.editor):
            # viewer: nur Art 2, eigenes Nutzergedaechtnis (Spec §2.2/§2.4).
            return InboxCounts(memory_approval=memory_approval, total=memory_approval)

        case_counts = await self._cases.count_by_status(ctx, agent_id=agent_id)
        cases_open = sum(case_counts[s] for s in INBOX_CASE_STATUSES)
        follow_ups_due = await self._sessions.count_due_measures(
            ctx.workspace_id, today=self._today(), agent_id=agent_id
        )
        patterns = len(await self._patterns.list_patterns(ctx, agent_id=agent_id))

        versions_review: int | None = None
        system_prompts_review: int | None = None
        if agent_id is None:
            # Eine Version gehoert keinem einzelnen Agenten; am Agenten
            # entfaellt die Art deshalb (Spec §3.1 Aufgaben-Zeile).
            persona, playbook, resource = await self._dashboard.status_distribution(
                ctx.workspace_id
            )
            versions_review = sum(d.get(_REVIEW, 0) for d in (persona, playbook, resource))
            system_prompts_review = await self._dashboard.attention_counts(ctx.workspace_id)

        total = memory_approval + cases_open + follow_ups_due
        if role_satisfies(ctx.role, WorkspaceRole.admin):
            # Versionen zaehlen nur fuer admin in die Glocke: nur admin darf
            # `review -> active` (Spec §2.2). Muster zaehlen nie.
            total += (versions_review or 0) + (system_prompts_review or 0)
        return InboxCounts(
            follow_ups_due=follow_ups_due,
            memory_approval=memory_approval,
            versions_review=versions_review,
            system_prompts_review=system_prompts_review,
            cases_open=cases_open,
            patterns=patterns,
            total=total,
        )

    async def _memory_approval(self, ctx: WorkspaceContext, agent_id: UUID | None) -> int:
        """Dieselbe Menge wie der Tab „Zur Freigabe“ (`countApprovalQueue` im Web).

        `status=pending` (ohne Lernvorschlaege) plus offene Aenderungs- und
        Loeschvorschlaege. viewer: nur `scope=user`; die Services filtern
        fremdes Nutzergedaechtnis ohnehin fuer jede Rolle heraus.
        """
        is_editor = role_satisfies(ctx.role, WorkspaceRole.editor)
        filters = MemoryFilter(
            status=MemoryStatus.pending,
            scope=None if is_editor else MemoryScope.user,
            agent_id=agent_id,
        )
        pending = await self._memories.count_workspace_memories(ctx, filters)
        proposals = await self._memories.list_proposals(
            ctx, agent_id=agent_id, status_filter=MemoryProposalStatus.pending
        )
        return pending.total + sum(1 for p in proposals if p.status is MemoryProposalStatus.pending)


# Status-Wert der Versionen „zur Freigabe“ (heute „zur Review“).
_REVIEW = VersionStatus.review
