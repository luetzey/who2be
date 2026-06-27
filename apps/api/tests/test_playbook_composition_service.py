"""Unit-Tests fuer `PlaybookCompositionService` mit einem Fake-Repository.

Deckt ab: role-gate (viewer→403), 404 (Parent/Kind), 409 (Zyklus),
Dedupe + Reihenfolge-Erhaltung, Self-ID-Filter.
"""

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from who2be_api.core.errors import ApiGateError
from who2be_api.core.security import WorkspaceContext
from who2be_api.repositories.playbook_composition_repository import SetCompositionResult
from who2be_api.services.playbook_composition_service import PlaybookCompositionService
from who2be_models import (
    PlaybookCompositionLinkSet,
    PlaybookContent,
    PlaybookRead,
    PlaybookRef,
    WorkspaceRole,
)


def _ctx(
    workspace_id: UUID,
    user_id: UUID | None = None,
    role: WorkspaceRole = WorkspaceRole.admin,
) -> WorkspaceContext:
    return WorkspaceContext(
        workspace_id=workspace_id,
        user_id=user_id or uuid4(),
        role=role,
    )


def _playbook_read(playbook_id: UUID, workspace_id: UUID) -> PlaybookRead:
    now = datetime.now(UTC)
    return PlaybookRead(
        id=playbook_id,
        workspace_id=workspace_id,
        owner_id=uuid4(),
        name="PB",
        current_version=1,
        type="workflow",
        tags=[],
        triggers=None,
        content=PlaybookContent(description="d", body="b", type="workflow"),  # type: ignore[arg-type]
        created_at=now,
        updated_at=now,
    )


class FakePlaybookCompositionRepository:
    """In-Memory-Stub von `PlaybookCompositionRepository`."""

    def __init__(
        self,
        playbooks: dict[UUID, UUID],  # playbook_id -> workspace_id
    ) -> None:
        self._playbooks = playbooks
        # parent_id -> [child_id, ...]
        self.composition: dict[UUID, list[UUID]] = {}
        self.last_active_only: bool | None = None
        # Steuerbar von Tests:
        self.simulate_cycle: bool = False

    async def parent_belongs_to(self, workspace_id: UUID, parent_id: UUID) -> bool:
        return self._playbooks.get(parent_id) == workspace_id

    async def list_children(self, parent_id: UUID, active_only: bool = False) -> list[PlaybookRead]:
        self.last_active_only = active_only
        return [
            _playbook_read(cid, self._playbooks.get(cid, uuid4()))
            for cid in self.composition.get(parent_id, [])
        ]

    async def list_parents(self, child_id: UUID) -> list[PlaybookRef]:
        return [
            PlaybookRef(id=pid, name="Parent")
            for pid, children in self.composition.items()
            if child_id in children
        ]

    async def set_composition(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        parent_id: UUID,
        child_ids: Sequence[UUID],
    ) -> SetCompositionResult:
        if self._playbooks.get(parent_id) != workspace_id:
            return SetCompositionResult(parent_found=False)
        ids = list(child_ids)
        missing = [cid for cid in ids if self._playbooks.get(cid) != workspace_id]
        if missing:
            return SetCompositionResult(parent_found=True, missing_child_ids=missing)
        if self.simulate_cycle:
            return SetCompositionResult(parent_found=True, cycle=True)
        self.composition[parent_id] = ids
        return SetCompositionResult(parent_found=True)


# ── Role-Gate ──────────────────────────────────────────────────────────────────


def test_set_composition_viewer_raises_403() -> None:
    workspace, parent_id = uuid4(), uuid4()
    repo = FakePlaybookCompositionRepository({parent_id: workspace})
    service = PlaybookCompositionService(repo)
    ctx = _ctx(workspace, role=WorkspaceRole.viewer)
    with pytest.raises(ApiGateError) as exc:
        asyncio.run(service.set_composition(ctx, parent_id, PlaybookCompositionLinkSet()))
    assert exc.value.status == 403
    assert exc.value.reason == "insufficient_role"


def test_set_composition_editor_allowed() -> None:
    workspace, parent_id = uuid4(), uuid4()
    repo = FakePlaybookCompositionRepository({parent_id: workspace})
    service = PlaybookCompositionService(repo)
    ctx = _ctx(workspace, role=WorkspaceRole.editor)
    result = asyncio.run(service.set_composition(ctx, parent_id, PlaybookCompositionLinkSet()))
    assert result == []


# ── 404 — Parent nicht gefunden ────────────────────────────────────────────────


def test_list_children_unknown_parent_raises_404() -> None:
    repo = FakePlaybookCompositionRepository({})
    service = PlaybookCompositionService(repo)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.list_children(_ctx(uuid4()), uuid4()))
    assert exc.value.status_code == 404


def test_set_composition_unknown_parent_raises_404() -> None:
    repo = FakePlaybookCompositionRepository({})
    service = PlaybookCompositionService(repo)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.set_composition(_ctx(uuid4()), uuid4(), PlaybookCompositionLinkSet()))
    assert exc.value.status_code == 404


def test_list_parents_unknown_child_raises_404() -> None:
    repo = FakePlaybookCompositionRepository({})
    service = PlaybookCompositionService(repo)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.list_parents(_ctx(uuid4()), uuid4()))
    assert exc.value.status_code == 404


# ── 404 — Kind nicht im Workspace ──────────────────────────────────────────────


def test_set_composition_foreign_child_raises_404() -> None:
    workspace, parent_id = uuid4(), uuid4()
    foreign_child = uuid4()
    repo = FakePlaybookCompositionRepository({parent_id: workspace, foreign_child: uuid4()})
    service = PlaybookCompositionService(repo)
    ctx = _ctx(workspace)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            service.set_composition(
                ctx, parent_id, PlaybookCompositionLinkSet(child_ids=[foreign_child])
            )
        )
    assert exc.value.status_code == 404


# ── 409 — Zyklus ───────────────────────────────────────────────────────────────


def test_set_composition_cycle_raises_409() -> None:
    workspace, parent_id, child_id = uuid4(), uuid4(), uuid4()
    repo = FakePlaybookCompositionRepository({parent_id: workspace, child_id: workspace})
    repo.simulate_cycle = True
    service = PlaybookCompositionService(repo)
    ctx = _ctx(workspace)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            service.set_composition(
                ctx, parent_id, PlaybookCompositionLinkSet(child_ids=[child_id])
            )
        )
    assert exc.value.status_code == 409


# ── Dedupe + Reihenfolge ────────────────────────────────────────────────────────


def test_set_composition_deduplicates_preserving_order() -> None:
    workspace, parent_id = uuid4(), uuid4()
    c1, c2, c3 = uuid4(), uuid4(), uuid4()
    repo = FakePlaybookCompositionRepository(
        {parent_id: workspace, c1: workspace, c2: workspace, c3: workspace}
    )
    service = PlaybookCompositionService(repo)
    asyncio.run(
        service.set_composition(
            _ctx(workspace),
            parent_id,
            PlaybookCompositionLinkSet(child_ids=[c2, c1, c3, c1, c2]),  # dupes am Ende
        )
    )
    # Nach Dedupe: c2, c1, c3 (erste Vorkommen-Reihenfolge)
    assert repo.composition[parent_id] == [c2, c1, c3]


def test_set_composition_filters_self_id() -> None:
    """Parent-ID wird defensiv aus der child_ids-Liste entfernt."""
    workspace, parent_id, child_id = uuid4(), uuid4(), uuid4()
    repo = FakePlaybookCompositionRepository({parent_id: workspace, child_id: workspace})
    service = PlaybookCompositionService(repo)
    asyncio.run(
        service.set_composition(
            _ctx(workspace),
            parent_id,
            # parent_id ist auch in der Liste — wird gefiltert
            PlaybookCompositionLinkSet(child_ids=[parent_id, child_id]),
        )
    )
    assert parent_id not in repo.composition[parent_id]
    assert repo.composition[parent_id] == [child_id]


# ── Leere Liste loest alle ──────────────────────────────────────────────────────


def test_set_composition_empty_clears_children() -> None:
    workspace, parent_id, child_id = uuid4(), uuid4(), uuid4()
    repo = FakePlaybookCompositionRepository({parent_id: workspace, child_id: workspace})
    repo.composition[parent_id] = [child_id]
    service = PlaybookCompositionService(repo)
    result = asyncio.run(
        service.set_composition(_ctx(workspace), parent_id, PlaybookCompositionLinkSet())
    )
    assert result == []
    assert repo.composition[parent_id] == []


# ── active_only via is_api_token ───────────────────────────────────────────────


def test_list_children_passes_active_only_for_api_token() -> None:
    workspace, parent_id = uuid4(), uuid4()
    repo = FakePlaybookCompositionRepository({parent_id: workspace})
    service = PlaybookCompositionService(repo)
    ctx = WorkspaceContext(
        workspace_id=workspace, user_id=uuid4(), role=WorkspaceRole.viewer, is_api_token=True
    )
    asyncio.run(service.list_children(ctx, parent_id))
    assert repo.last_active_only is True


def test_list_children_not_active_only_for_jwt() -> None:
    workspace, parent_id = uuid4(), uuid4()
    repo = FakePlaybookCompositionRepository({parent_id: workspace})
    service = PlaybookCompositionService(repo)
    ctx = WorkspaceContext(
        workspace_id=workspace, user_id=uuid4(), role=WorkspaceRole.viewer, is_api_token=False
    )
    asyncio.run(service.list_children(ctx, parent_id))
    assert repo.last_active_only is False
