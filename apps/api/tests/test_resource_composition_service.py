"""Unit-Tests fuer `ResourceCompositionService` mit einem Fake-Repository.

Deckt ab: role-gate (viewer->403), 404 (Parent/Kind), 409 (Zyklus),
Dedupe ueber (child_id, scope, block_id) + Reihenfolge-Erhaltung, Self-ID-Filter,
leere Liste loest alle. Kein DB-Zugriff — laeuft immer.
"""

import asyncio
from collections.abc import Sequence
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from who2be_api.core.errors import ApiGateError
from who2be_api.core.security import WorkspaceContext
from who2be_api.repositories.resource_composition_repository import SetSubResourcesResult
from who2be_api.services.resource_composition_service import ResourceCompositionService
from who2be_models import (
    ResourceRef,
    SubResourceLinkItem,
    SubResourceLinkSet,
    SubResourceRead,
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


def _link(child_id: UUID) -> SubResourceLinkItem:
    return SubResourceLinkItem(child_id=child_id, link_scope="resource")


class FakeResourceCompositionRepository:
    """In-Memory-Stub von `ResourceCompositionRepository`."""

    def __init__(self, resources: dict[UUID, UUID]) -> None:
        self._resources = resources  # resource_id -> workspace_id
        # parent_id -> [SubResourceLinkItem, ...] (so wie der Service sie reicht)
        self.links: dict[UUID, list[SubResourceLinkItem]] = {}
        self.simulate_cycle = False
        self.last_active_only: bool | None = None

    async def parent_belongs_to(self, workspace_id: UUID, resource_id: UUID) -> bool:
        return self._resources.get(resource_id) == workspace_id

    async def list_children(
        self, workspace_id: UUID, parent_id: UUID, active_only: bool = False
    ) -> list[SubResourceRead]:
        self.last_active_only = active_only
        return [
            SubResourceRead(
                id=item.child_id,
                name="Child",
                link_scope=item.link_scope,
                block_id=item.block_id,
                position=index,
            )
            for index, item in enumerate(self.links.get(parent_id, []))
        ]

    async def list_parents(self, workspace_id: UUID, child_id: UUID) -> list[ResourceRef]:
        return [
            ResourceRef(id=pid, name="Parent")
            for pid, items in self.links.items()
            if any(i.child_id == child_id for i in items)
        ]

    async def set_links(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        parent_id: UUID,
        links: Sequence[SubResourceLinkItem],
    ) -> SetSubResourcesResult:
        if self._resources.get(parent_id) != workspace_id:
            return SetSubResourcesResult(parent_found=False)
        items = list(links)
        missing = [i.child_id for i in items if self._resources.get(i.child_id) != workspace_id]
        if missing:
            return SetSubResourcesResult(parent_found=True, missing_child_ids=missing)
        if self.simulate_cycle:
            return SetSubResourcesResult(parent_found=True, cycle=True)
        self.links[parent_id] = items
        return SetSubResourcesResult(parent_found=True)


def test_set_links_viewer_raises_403() -> None:
    ws, parent = uuid4(), uuid4()
    repo = FakeResourceCompositionRepository({parent: ws})
    service = ResourceCompositionService(repo)
    ctx = _ctx(ws, role=WorkspaceRole.viewer)
    with pytest.raises(ApiGateError) as exc:
        asyncio.run(service.set_links(ctx, parent, SubResourceLinkSet()))
    assert exc.value.status == 403
    assert exc.value.reason == "insufficient_role"


def test_list_children_unknown_parent_raises_404() -> None:
    repo = FakeResourceCompositionRepository({})
    service = ResourceCompositionService(repo)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.list_children(_ctx(uuid4()), uuid4()))
    assert exc.value.status_code == 404


def test_list_parents_unknown_child_raises_404() -> None:
    repo = FakeResourceCompositionRepository({})
    service = ResourceCompositionService(repo)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.list_parents(_ctx(uuid4()), uuid4()))
    assert exc.value.status_code == 404


def test_set_links_foreign_child_raises_404() -> None:
    ws, parent, foreign = uuid4(), uuid4(), uuid4()
    repo = FakeResourceCompositionRepository({parent: ws, foreign: uuid4()})
    service = ResourceCompositionService(repo)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.set_links(_ctx(ws), parent, SubResourceLinkSet(links=[_link(foreign)])))
    assert exc.value.status_code == 404


def test_set_links_cycle_raises_409() -> None:
    ws, parent, child = uuid4(), uuid4(), uuid4()
    repo = FakeResourceCompositionRepository({parent: ws, child: ws})
    repo.simulate_cycle = True
    service = ResourceCompositionService(repo)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.set_links(_ctx(ws), parent, SubResourceLinkSet(links=[_link(child)])))
    assert exc.value.status_code == 409


def test_set_links_deduplicates_preserving_order() -> None:
    ws, parent = uuid4(), uuid4()
    c1, c2, c3 = uuid4(), uuid4(), uuid4()
    repo = FakeResourceCompositionRepository({parent: ws, c1: ws, c2: ws, c3: ws})
    service = ResourceCompositionService(repo)
    asyncio.run(
        service.set_links(
            _ctx(ws),
            parent,
            SubResourceLinkSet(links=[_link(c2), _link(c1), _link(c3), _link(c1), _link(c2)]),
        )
    )
    assert [i.child_id for i in repo.links[parent]] == [c2, c1, c3]


def test_set_links_keeps_distinct_block_anchors_for_same_child() -> None:
    """Selbes Kind, verschiedene Block-Anker -> beide bleiben erhalten."""
    ws, parent, child = uuid4(), uuid4(), uuid4()
    repo = FakeResourceCompositionRepository({parent: ws, child: ws})
    service = ResourceCompositionService(repo)
    asyncio.run(
        service.set_links(
            _ctx(ws),
            parent,
            SubResourceLinkSet(
                links=[
                    SubResourceLinkItem(child_id=child, block_id="b1", link_scope="block"),
                    SubResourceLinkItem(child_id=child, block_id="b2", link_scope="block"),
                    SubResourceLinkItem(child_id=child, block_id="b1", link_scope="block"),  # dup
                ]
            ),
        )
    )
    anchors = [i.block_id for i in repo.links[parent]]
    assert anchors == ["b1", "b2"]


def test_set_links_filters_self_id() -> None:
    ws, parent, child = uuid4(), uuid4(), uuid4()
    repo = FakeResourceCompositionRepository({parent: ws, child: ws})
    service = ResourceCompositionService(repo)
    asyncio.run(
        service.set_links(
            _ctx(ws),
            parent,
            SubResourceLinkSet(links=[_link(parent), _link(child)]),
        )
    )
    assert [i.child_id for i in repo.links[parent]] == [child]


def test_set_links_empty_clears_children() -> None:
    ws, parent, child = uuid4(), uuid4(), uuid4()
    repo = FakeResourceCompositionRepository({parent: ws, child: ws})
    repo.links[parent] = [_link(child)]
    service = ResourceCompositionService(repo)
    result = asyncio.run(service.set_links(_ctx(ws), parent, SubResourceLinkSet()))
    assert result == []
    assert repo.links[parent] == []


def test_list_children_passes_active_only_for_api_token() -> None:
    """MCP-/API-Token-Pfad filtert auf aktive Kind-Versionen (Invariante 2.1b)."""
    ws, parent = uuid4(), uuid4()
    repo = FakeResourceCompositionRepository({parent: ws})
    service = ResourceCompositionService(repo)
    ctx = WorkspaceContext(
        workspace_id=ws, user_id=uuid4(), role=WorkspaceRole.viewer, is_api_token=True
    )
    asyncio.run(service.list_children(ctx, parent))
    assert repo.last_active_only is True


def test_list_children_not_active_only_for_jwt() -> None:
    """Operator-/Web-Pfad zeigt alle Sub-Resource-Links (kein Status-Filter)."""
    ws, parent = uuid4(), uuid4()
    repo = FakeResourceCompositionRepository({parent: ws})
    service = ResourceCompositionService(repo)
    ctx = WorkspaceContext(
        workspace_id=ws, user_id=uuid4(), role=WorkspaceRole.viewer, is_api_token=False
    )
    asyncio.run(service.list_children(ctx, parent))
    assert repo.last_active_only is False
