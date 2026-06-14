"""Unit-Tests fuer `PersonaPlaybookService` mit einem Fake-Repository."""

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from who2be_api.core.security import WorkspaceContext
from who2be_api.repositories.persona_playbook_repository import SetLinksResult
from who2be_api.services.persona_playbook_service import PersonaPlaybookService
from who2be_models import (
    PersonaPlaybookLinkSet,
    PlaybookContent,
    PlaybookRead,
    WorkspaceRole,
)


def _ctx(workspace_id: UUID, user_id: UUID | None = None) -> WorkspaceContext:
    return WorkspaceContext(
        workspace_id=workspace_id, user_id=user_id or uuid4(), role=WorkspaceRole.admin
    )


def _playbook_read(playbook_id: UUID, workspace_id: UUID, owner_id: UUID) -> PlaybookRead:
    now = datetime.now(UTC)
    content = PlaybookContent(description="d", body="b", type="workflow")
    return PlaybookRead(
        id=playbook_id,
        workspace_id=workspace_id,
        owner_id=owner_id,
        name="PB",
        current_version=1,
        type="workflow",
        tags=[],
        triggers=None,
        content=content,
        created_at=now,
        updated_at=now,
    )


class FakePersonaPlaybookRepository:
    """In-Memory-Stub von `PersonaPlaybookRepository`."""

    def __init__(self, personas: dict[UUID, UUID], playbooks: dict[UUID, UUID]) -> None:
        # persona_id -> workspace_id bzw. playbook_id -> workspace_id
        self._personas = personas
        self._playbooks = playbooks
        self.links: dict[UUID, list[UUID]] = {}
        self.last_active_only: bool | None = None
        self.last_workspace_id: UUID | None = None

    async def persona_belongs_to(self, workspace_id: UUID, persona_id: UUID) -> bool:
        return self._personas.get(persona_id) == workspace_id

    async def list_linked(
        self, workspace_id: UUID, persona_id: UUID, active_only: bool = False
    ) -> list[PlaybookRead]:
        self.last_active_only = active_only
        self.last_workspace_id = workspace_id
        owner = uuid4()
        return [
            _playbook_read(pid, self._playbooks[pid], owner)
            for pid in self.links.get(persona_id, [])
        ]

    async def set_links(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        persona_id: UUID,
        playbook_ids: Sequence[UUID],
    ) -> SetLinksResult:
        if self._personas.get(persona_id) != workspace_id:
            return SetLinksResult(persona_found=False)
        ids = list(playbook_ids)
        missing = [pid for pid in ids if self._playbooks.get(pid) != workspace_id]
        if missing:
            return SetLinksResult(persona_found=True, missing_playbook_ids=missing)
        self.links[persona_id] = ids
        return SetLinksResult(persona_found=True)


def test_list_links_unknown_persona_raises_404() -> None:
    repo = FakePersonaPlaybookRepository({}, {})
    service = PersonaPlaybookService(repo)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.list_links(_ctx(uuid4()), uuid4()))
    assert exc.value.status_code == 404


def test_list_links_scopes_lookup_to_context_workspace() -> None:
    # F-Phase2-02: der Service muss `ctx.workspace_id` an den Reverse-Lookup
    # durchreichen, damit der Repo-SQL-Filter (Defense-in-Depth) greift.
    workspace, persona_id = uuid4(), uuid4()
    repo = FakePersonaPlaybookRepository({persona_id: workspace}, {})
    service = PersonaPlaybookService(repo)
    asyncio.run(service.list_links(_ctx(workspace), persona_id))
    assert repo.last_workspace_id == workspace


def test_set_links_unknown_persona_raises_404() -> None:
    repo = FakePersonaPlaybookRepository({}, {})
    service = PersonaPlaybookService(repo)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.set_links(_ctx(uuid4()), uuid4(), PersonaPlaybookLinkSet()))
    assert exc.value.status_code == 404


def test_set_links_with_foreign_playbook_raises_404() -> None:
    workspace, persona_id, foreign_playbook = uuid4(), uuid4(), uuid4()
    repo = FakePersonaPlaybookRepository({persona_id: workspace}, {foreign_playbook: uuid4()})
    service = PersonaPlaybookService(repo)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            service.set_links(
                _ctx(workspace),
                persona_id,
                PersonaPlaybookLinkSet(playbook_ids=[foreign_playbook]),
            )
        )
    assert exc.value.status_code == 404


def test_set_links_replaces_and_returns_linked_playbooks() -> None:
    workspace, persona_id = uuid4(), uuid4()
    pb_a, pb_b = uuid4(), uuid4()
    repo = FakePersonaPlaybookRepository(
        {persona_id: workspace}, {pb_a: workspace, pb_b: workspace}
    )
    service = PersonaPlaybookService(repo)
    linked = asyncio.run(
        service.set_links(
            _ctx(workspace),
            persona_id,
            PersonaPlaybookLinkSet(playbook_ids=[pb_a, pb_b]),
        )
    )
    assert {p.id for p in linked} == {pb_a, pb_b}


def test_set_links_empty_clears_links() -> None:
    workspace, persona_id, pb = uuid4(), uuid4(), uuid4()
    repo = FakePersonaPlaybookRepository({persona_id: workspace}, {pb: workspace})
    repo.links[persona_id] = [pb]
    service = PersonaPlaybookService(repo)
    linked = asyncio.run(service.set_links(_ctx(workspace), persona_id, PersonaPlaybookLinkSet()))
    assert linked == []


def test_set_links_deduplicates_playbook_ids() -> None:
    workspace, persona_id, pb = uuid4(), uuid4(), uuid4()
    repo = FakePersonaPlaybookRepository({persona_id: workspace}, {pb: workspace})
    service = PersonaPlaybookService(repo)
    asyncio.run(
        service.set_links(
            _ctx(workspace),
            persona_id,
            PersonaPlaybookLinkSet(playbook_ids=[pb, pb]),
        )
    )
    assert repo.links[persona_id] == [pb]
