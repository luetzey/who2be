"""Aggregation fuers Workspace-Dashboard (Phase 2.1b-B).

Holt Distribution + Activity parallel, leitet die drei KPI-Zahlen aus der
Distribution ab und mapped in `DashboardResponse`. Keine eigene
Geschaeftslogik — die Status-State-Machine lebt in `who2be_models.status`.
"""

import asyncio

from who2be_api.core.security import WorkspaceContext
from who2be_api.repositories.dashboard_repository import DashboardRepository
from who2be_models import (
    DashboardKpis,
    DashboardResponse,
    DashboardStatusDistribution,
    EntityStatusDistribution,
    VersionStatus,
)


def _to_distribution(counts: dict[VersionStatus, int]) -> EntityStatusDistribution:
    return EntityStatusDistribution(
        draft=counts.get(VersionStatus.draft, 0),
        review=counts.get(VersionStatus.review, 0),
        active=counts.get(VersionStatus.active, 0),
        inactive=counts.get(VersionStatus.inactive, 0),
    )


class DashboardService:
    """Liest die Dashboard-Antwort fuer einen Workspace zusammen."""

    def __init__(self, repo: DashboardRepository) -> None:
        self._repo = repo

    async def fetch(self, ctx: WorkspaceContext) -> DashboardResponse:
        (persona_counts, playbook_counts), activity = await asyncio.gather(
            self._repo.status_distribution(ctx.workspace_id),
            self._repo.recent_activity(ctx.workspace_id),
        )
        persona = _to_distribution(persona_counts)
        playbook = _to_distribution(playbook_counts)
        return DashboardResponse(
            kpis=DashboardKpis(
                active_personas=persona.active,
                active_playbooks=playbook.active,
                pending_reviews=persona.review + playbook.review,
            ),
            activity=activity,
            status_distribution=DashboardStatusDistribution(persona=persona, playbook=playbook),
        )
