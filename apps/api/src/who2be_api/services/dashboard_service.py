"""Aggregation fuers Workspace-Dashboard (Phase 2.1b-B).

Holt Distribution + Activity parallel, leitet die drei KPI-Zahlen aus der
Distribution ab und mapped in `DashboardResponse`. Die Status-State-Machine
selbst lebt in `who2be_models.status` — hier nur die UI-seitige Uebersetzung
von (`from_status`, `to_status`)-Paaren in stabile Event-Strings (Phase 3
Fix Track 1) und der `display_name`-Fallback.
"""

import asyncio
from uuid import UUID

from who2be_api.core.security import WorkspaceContext
from who2be_api.repositories.dashboard_repository import (
    DashboardActivityRow,
    DashboardRepository,
)
from who2be_models import (
    DashboardActivity,
    DashboardActor,
    DashboardKpis,
    DashboardResponse,
    DashboardStatusDistribution,
    EntityStatusDistribution,
    VersionStatus,
)

# Mapping (from_status, to_status) → stabiler Event-String fuers Frontend.
# Default-Fall siehe `_event_for` — unbekannte Uebergaenge bleiben
# rueckwaerts-lesbar, statt eine Pflicht-Map zu erzwingen.
_EVENT_MAP: dict[tuple[VersionStatus | None, VersionStatus], str] = {
    (VersionStatus.draft, VersionStatus.review): "submitted_for_review",
    (VersionStatus.review, VersionStatus.active): "promoted_to_active",
    (VersionStatus.review, VersionStatus.draft): "rejected",
    (VersionStatus.active, VersionStatus.inactive): "deactivated",
    (VersionStatus.inactive, VersionStatus.draft): "returned_to_draft",
}


def _event_for(from_status: VersionStatus | None, to_status: VersionStatus) -> str:
    """Stabiler Event-String fuer die UI; Default fuer unbekannte Paare."""
    mapped = _EVENT_MAP.get((from_status, to_status))
    if mapped is not None:
        return mapped
    return f"set_to_{to_status.value}"


def _display_name(user_meta: dict[str, object] | None, email: str | None, user_id: UUID) -> str:
    """Fallback-Kette `raw_user_meta_data->>'name'` → Email-Local-Part → User-ID."""
    if user_meta is not None:
        candidate = user_meta.get("name")
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    if email and "@" in email:
        local = email.split("@", 1)[0].strip()
        if local:
            return local
    return str(user_id)


def _entity_name(entity_name: str | None, entity_id: UUID) -> str | None:
    """Tombstone-Fallback: geloeschte/fehlende Entities tragen den ID-Tail."""
    if entity_name is not None:
        return entity_name
    tail = str(entity_id).split("-")[-1]
    return f"(geloescht: {tail})"


def _to_distribution(counts: dict[VersionStatus, int]) -> EntityStatusDistribution:
    return EntityStatusDistribution(
        draft=counts.get(VersionStatus.draft, 0),
        review=counts.get(VersionStatus.review, 0),
        active=counts.get(VersionStatus.active, 0),
        inactive=counts.get(VersionStatus.inactive, 0),
    )


def _to_activity(row: DashboardActivityRow) -> DashboardActivity:
    return DashboardActivity(
        ts=row.changed_at,
        actor=DashboardActor(
            user_id=row.changed_by,
            display_name=_display_name(row.user_meta, row.user_email, row.changed_by),
        ),
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        entity_name=_entity_name(row.entity_name, row.entity_id),
        event=_event_for(row.from_status, row.to_status),
    )


class DashboardService:
    """Liest die Dashboard-Antwort fuer einen Workspace zusammen."""

    def __init__(self, repo: DashboardRepository) -> None:
        self._repo = repo

    async def fetch(self, ctx: WorkspaceContext) -> DashboardResponse:
        (persona_counts, playbook_counts, resource_counts), rows = await asyncio.gather(
            self._repo.status_distribution(ctx.workspace_id),
            self._repo.recent_activity(ctx.workspace_id),
        )
        persona = _to_distribution(persona_counts)
        playbook = _to_distribution(playbook_counts)
        resource = _to_distribution(resource_counts)
        return DashboardResponse(
            kpis=DashboardKpis(
                active_personas=persona.active,
                active_playbooks=playbook.active,
                active_resources=resource.active,
                pending_reviews=persona.review + playbook.review + resource.review,
            ),
            activity=[_to_activity(row) for row in rows],
            status_distribution=DashboardStatusDistribution(
                persona=persona, playbook=playbook, resource=resource
            ),
        )
