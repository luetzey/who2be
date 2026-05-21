"""Unit-Tests fuer `PersonaPlaybookService` mit einem Fake-Repository."""

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from who2be_api.repositories.persona_playbook_repository import SetLinksResult
from who2be_api.services.persona_playbook_service import PersonaPlaybookService
from who2be_models import PersonaPlaybookLinkSet, PlaybookContent, PlaybookRead


def _playbook_read(playbook_id: UUID, owner_id: UUID) -> PlaybookRead:
    now = datetime.now(UTC)
    content = PlaybookContent(description="d", body="b", type="workflow")
    return PlaybookRead(
        id=playbook_id,
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

    def __init__(
        self, personas: dict[UUID, UUID], playbooks: dict[UUID, UUID]
    ) -> None:
        # persona_id -> owner_id bzw. playbook_id -> owner_id
        self._personas = personas
        self._playbooks = playbooks
        self.links: dict[UUID, list[UUID]] = {}

    async def persona_belongs_to(self, owner_id: UUID, persona_id: UUID) -> bool:
        return self._personas.get(persona_id) == owner_id

    async def list_linked(self, persona_id: UUID) -> list[PlaybookRead]:
        return [
            _playbook_read(pid, self._playbooks[pid])
            for pid in self.links.get(persona_id, [])
        ]

    async def set_links(
        self, owner_id: UUID, persona_id: UUID, playbook_ids: Sequence[UUID]
    ) -> SetLinksResult:
        if self._personas.get(persona_id) != owner_id:
            return SetLinksResult(persona_found=False)
        ids = list(playbook_ids)
        missing = [pid for pid in ids if self._playbooks.get(pid) != owner_id]
        if missing:
            return SetLinksResult(persona_found=True, missing_playbook_ids=missing)
        self.links[persona_id] = ids
        return SetLinksResult(persona_found=True)


def test_list_links_unknown_persona_raises_404() -> None:
    repo = FakePersonaPlaybookRepository({}, {})
    service = PersonaPlaybookService(repo)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.list_links(uuid4(), uuid4()))
    assert exc.value.status_code == 404


def test_set_links_unknown_persona_raises_404() -> None:
    repo = FakePersonaPlaybookRepository({}, {})
    service = PersonaPlaybookService(repo)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            service.set_links(uuid4(), uuid4(), PersonaPlaybookLinkSet())
        )
    assert exc.value.status_code == 404


def test_set_links_with_foreign_playbook_raises_404() -> None:
    owner, persona_id, foreign_playbook = uuid4(), uuid4(), uuid4()
    repo = FakePersonaPlaybookRepository(
        {persona_id: owner}, {foreign_playbook: uuid4()}
    )
    service = PersonaPlaybookService(repo)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            service.set_links(
                owner,
                persona_id,
                PersonaPlaybookLinkSet(playbook_ids=[foreign_playbook]),
            )
        )
    assert exc.value.status_code == 404


def test_set_links_replaces_and_returns_linked_playbooks() -> None:
    owner, persona_id = uuid4(), uuid4()
    pb_a, pb_b = uuid4(), uuid4()
    repo = FakePersonaPlaybookRepository(
        {persona_id: owner}, {pb_a: owner, pb_b: owner}
    )
    service = PersonaPlaybookService(repo)
    linked = asyncio.run(
        service.set_links(
            owner, persona_id, PersonaPlaybookLinkSet(playbook_ids=[pb_a, pb_b])
        )
    )
    assert {p.id for p in linked} == {pb_a, pb_b}


def test_set_links_empty_clears_links() -> None:
    owner, persona_id, pb = uuid4(), uuid4(), uuid4()
    repo = FakePersonaPlaybookRepository({persona_id: owner}, {pb: owner})
    repo.links[persona_id] = [pb]
    service = PersonaPlaybookService(repo)
    linked = asyncio.run(
        service.set_links(owner, persona_id, PersonaPlaybookLinkSet())
    )
    assert linked == []


def test_set_links_deduplicates_playbook_ids() -> None:
    owner, persona_id, pb = uuid4(), uuid4(), uuid4()
    repo = FakePersonaPlaybookRepository({persona_id: owner}, {pb: owner})
    service = PersonaPlaybookService(repo)
    asyncio.run(
        service.set_links(
            owner, persona_id, PersonaPlaybookLinkSet(playbook_ids=[pb, pb])
        )
    )
    assert repo.links[persona_id] == [pb]
