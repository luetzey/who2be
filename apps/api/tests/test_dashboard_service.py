"""Unit-Test fuer `DashboardService` — Pagination-Mathematik ohne DB.

Deckt die Offset-/Seiten-Berechnung (Track G) gegen ein Fake-Repo ab, damit
die Logik auch ohne erreichbare Datenbank in CI gruen laeuft (der
DB-gebundene Pfad lebt in `test_dashboard_endpoint.py`).
"""

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

from who2be_api.core.security import WorkspaceContext
from who2be_api.repositories.dashboard_repository import DashboardActivityRow
from who2be_api.services.dashboard_service import DashboardService
from who2be_models import VersionStatus, WorkspaceRole


def _ctx() -> WorkspaceContext:
    return WorkspaceContext(
        workspace_id=uuid4(),
        user_id=uuid4(),
        role=WorkspaceRole.admin,
    )


def _row(name: str) -> DashboardActivityRow:
    return DashboardActivityRow(
        entity_type="persona",
        entity_id=uuid4(),
        changed_at=datetime.now(UTC),
        changed_by=uuid4(),
        from_status=VersionStatus.draft,
        to_status=VersionStatus.review,
        entity_name=name,
        user_email="qa@example.com",
        user_meta={"name": "QA"},
    )


class _FakeRepo:
    """Repo-Doppel: merkt sich die zuletzt erfragten (limit, offset)."""

    def __init__(
        self,
        rows: list[DashboardActivityRow],
        total: int,
        attention: tuple[int, int] = (0, 0),
    ) -> None:
        self._rows = rows
        self._total = total
        self._attention = attention
        self.last_limit: int | None = None
        self.last_offset: int | None = None

    async def status_distribution(
        self, workspace_id: UUID
    ) -> tuple[dict[VersionStatus, int], dict[VersionStatus, int], dict[VersionStatus, int]]:
        return ({VersionStatus.active: 1}, {}, {})

    async def recent_activity(
        self, workspace_id: UUID, limit: int, offset: int
    ) -> tuple[list[DashboardActivityRow], int]:
        self.last_limit = limit
        self.last_offset = offset
        return self._rows, self._total

    async def attention_counts(self, workspace_id: UUID) -> tuple[int, int]:
        return self._attention


def test_fetch_defaults_to_first_page_size_20() -> None:
    repo = _FakeRepo([_row("A")], total=1)
    service = DashboardService(repo)

    response = asyncio.run(service.fetch(_ctx()))

    assert repo.last_limit == 20
    assert repo.last_offset == 0
    assert response.activity_pagination.page == 1
    assert response.activity_pagination.page_size == 20
    assert response.activity_pagination.total == 1
    assert response.activity_pagination.total_pages == 1
    assert response.kpis.active_personas == 1


def test_fetch_computes_offset_and_total_pages() -> None:
    repo = _FakeRepo([_row("B")], total=45)
    service = DashboardService(repo)

    response = asyncio.run(service.fetch(_ctx(), page=3, page_size=20))

    assert repo.last_offset == 40  # (3 - 1) * 20
    assert repo.last_limit == 20
    assert response.activity_pagination.page == 3
    # ceil(45 / 20) == 3
    assert response.activity_pagination.total_pages == 3


def test_fetch_empty_activity_has_zero_pages() -> None:
    repo = _FakeRepo([], total=0)
    service = DashboardService(repo)

    response = asyncio.run(service.fetch(_ctx()))

    assert response.activity == []
    assert response.activity_pagination.total == 0
    assert response.activity_pagination.total_pages == 0
    # Ohne Aufmerksamkeits-Signale bleiben die neuen KPI-Felder 0.
    assert response.kpis.pending_memories == 0
    assert response.kpis.pending_system_prompts == 0


def test_fetch_maps_attention_counts_into_kpis() -> None:
    repo = _FakeRepo([], total=0, attention=(3, 2))
    service = DashboardService(repo)

    response = asyncio.run(service.fetch(_ctx()))

    assert response.kpis.pending_memories == 3
    assert response.kpis.pending_system_prompts == 2
