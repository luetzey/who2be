"""Unit-Tests fuer `PlaybookService` mit einem In-Memory-Fake-Repository."""

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from who2be_api.services.playbook_service import PlaybookService
from who2be_models import (
    PlaybookContent,
    PlaybookCreate,
    PlaybookRead,
    PlaybookUpdate,
    PlaybookVersionRead,
)


def _content(
    description: str = "Flow",
    tags: list[str] | None = None,
    triggers: str | None = None,
) -> PlaybookContent:
    return PlaybookContent(
        description=description,
        body="1. Do it.",
        type="workflow",
        tags=tags if tags is not None else [],
        triggers=triggers,
    )


class FakePlaybookRepository:
    """In-Memory-Stub von `PlaybookRepository`."""

    def __init__(self) -> None:
        self._playbooks: dict[UUID, PlaybookRead] = {}
        self._versions: dict[UUID, list[PlaybookVersionRead]] = {}

    async def insert(self, owner_id: UUID, name: str, content: PlaybookContent) -> PlaybookRead:
        now = datetime.now(UTC)
        playbook = PlaybookRead(
            id=uuid4(),
            owner_id=owner_id,
            name=name,
            current_version=1,
            type=content.type,
            tags=content.tags,
            triggers=content.triggers,
            content=content,
            created_at=now,
            updated_at=now,
        )
        self._playbooks[playbook.id] = playbook
        self._versions[playbook.id] = [
            PlaybookVersionRead(version=1, content=content, created_by=owner_id, created_at=now)
        ]
        return playbook

    async def list_by_owner(
        self,
        owner_id: UUID,
        tag: str | None,
        trigger: str | None,
        limit: int,
        after: tuple[datetime, UUID] | None,
    ) -> list[PlaybookRead]:
        result = [p for p in self._playbooks.values() if p.owner_id == owner_id]
        if tag is not None:
            result = [p for p in result if tag in p.tags]
        if trigger is not None:
            result = [
                p
                for p in result
                if p.triggers is not None and trigger.lower() in p.triggers.lower()
            ]
        result.sort(key=lambda p: (p.created_at, p.id), reverse=True)
        if after is not None:
            result = [p for p in result if (p.created_at, p.id) < after]
        return result[:limit]

    async def fetch(self, owner_id: UUID, playbook_id: UUID) -> PlaybookRead | None:
        playbook = self._playbooks.get(playbook_id)
        return playbook if playbook is not None and playbook.owner_id == owner_id else None

    async def update(
        self,
        owner_id: UUID,
        playbook_id: UUID,
        name: str | None,
        content: PlaybookContent,
    ) -> PlaybookRead | None:
        playbook = self._playbooks.get(playbook_id)
        if playbook is None or playbook.owner_id != owner_id:
            return None
        version = playbook.current_version + 1
        updated = playbook.model_copy(
            update={
                "name": name if name is not None else playbook.name,
                "current_version": version,
                "type": content.type,
                "tags": content.tags,
                "triggers": content.triggers,
                "content": content,
                "updated_at": datetime.now(UTC),
            }
        )
        self._playbooks[playbook_id] = updated
        self._versions[playbook_id].append(
            PlaybookVersionRead(
                version=version,
                content=content,
                created_by=owner_id,
                created_at=datetime.now(UTC),
            )
        )
        return updated

    async def list_versions(
        self, owner_id: UUID, playbook_id: UUID
    ) -> list[PlaybookVersionRead] | None:
        playbook = self._playbooks.get(playbook_id)
        if playbook is None or playbook.owner_id != owner_id:
            return None
        return list(reversed(self._versions[playbook_id]))

    async def fetch_version(
        self, owner_id: UUID, playbook_id: UUID, version: int
    ) -> PlaybookVersionRead | None:
        playbook = self._playbooks.get(playbook_id)
        if playbook is None or playbook.owner_id != owner_id:
            return None
        return next((v for v in self._versions[playbook_id] if v.version == version), None)


def _service() -> tuple[PlaybookService, UUID]:
    return PlaybookService(FakePlaybookRepository()), uuid4()


def test_create_denormalises_content_fields() -> None:
    service, owner = _service()
    playbook = asyncio.run(
        service.create(
            owner,
            PlaybookCreate(name="PB", content=_content(tags=["a"], triggers="hi")),
        )
    )
    assert playbook.current_version == 1
    assert playbook.tags == ["a"]
    assert playbook.triggers == "hi"


def test_get_unknown_playbook_raises_404() -> None:
    service, owner = _service()
    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.get(owner, uuid4()))
    assert exc.value.status_code == 404


def test_get_foreign_playbook_raises_404() -> None:
    service, owner = _service()
    created = asyncio.run(service.create(owner, PlaybookCreate(name="PB", content=_content())))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.get(uuid4(), created.id))
    assert exc.value.status_code == 404


def test_list_filters_by_tag() -> None:
    service, owner = _service()
    asyncio.run(service.create(owner, PlaybookCreate(name="A", content=_content(tags=["x"]))))
    asyncio.run(service.create(owner, PlaybookCreate(name="B", content=_content(tags=["y"]))))
    matched, next_cursor = asyncio.run(service.list_all(owner, "x", None, 100, None))
    assert [p.name for p in matched] == ["A"]
    assert next_cursor is None


def test_list_filters_by_trigger_substring() -> None:
    service, owner = _service()
    asyncio.run(
        service.create(owner, PlaybookCreate(name="A", content=_content(triggers="new user")))
    )
    asyncio.run(
        service.create(owner, PlaybookCreate(name="B", content=_content(triggers="on error")))
    )
    matched, next_cursor = asyncio.run(service.list_all(owner, None, "USER", 100, None))
    assert [p.name for p in matched] == ["A"]
    assert next_cursor is None


def test_update_bumps_version_and_records_snapshot() -> None:
    service, owner = _service()
    created = asyncio.run(service.create(owner, PlaybookCreate(name="PB", content=_content("v1"))))
    updated = asyncio.run(service.update(owner, created.id, PlaybookUpdate(content=_content("v2"))))
    assert updated.current_version == 2
    versions = asyncio.run(service.list_versions(owner, created.id))
    assert [v.version for v in versions] == [2, 1]


def test_update_unknown_playbook_raises_404() -> None:
    service, owner = _service()
    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.update(owner, uuid4(), PlaybookUpdate(content=_content())))
    assert exc.value.status_code == 404


def test_get_version_returns_requested_snapshot() -> None:
    service, owner = _service()
    created = asyncio.run(service.create(owner, PlaybookCreate(name="PB", content=_content("v1"))))
    asyncio.run(service.update(owner, created.id, PlaybookUpdate(content=_content("v2"))))
    first = asyncio.run(service.get_version(owner, created.id, 1))
    assert first.content.description == "v1"
