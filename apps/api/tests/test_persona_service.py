"""Unit-Tests fuer `PersonaService` mit einem In-Memory-Fake-Repository."""

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from who2be_api.services.persona_service import PersonaService
from who2be_models import (
    PersonaContent,
    PersonaCreate,
    PersonaRead,
    PersonaUpdate,
    PersonaVersionRead,
)


def _content(description: str = "Tester") -> PersonaContent:
    return PersonaContent(description=description, system_prompt="Be helpful.")


class FakePersonaRepository:
    """In-Memory-Stub von `PersonaRepository`."""

    def __init__(self) -> None:
        self._personas: dict[UUID, PersonaRead] = {}
        self._versions: dict[UUID, list[PersonaVersionRead]] = {}

    async def insert(
        self, owner_id: UUID, name: str, content: PersonaContent
    ) -> PersonaRead:
        now = datetime.now(UTC)
        persona = PersonaRead(
            id=uuid4(),
            owner_id=owner_id,
            name=name,
            current_version=1,
            content=content,
            created_at=now,
            updated_at=now,
        )
        self._personas[persona.id] = persona
        self._versions[persona.id] = [
            PersonaVersionRead(
                version=1, content=content, created_by=owner_id, created_at=now
            )
        ]
        return persona

    async def list_by_owner(self, owner_id: UUID) -> list[PersonaRead]:
        return [p for p in self._personas.values() if p.owner_id == owner_id]

    async def fetch(self, owner_id: UUID, persona_id: UUID) -> PersonaRead | None:
        persona = self._personas.get(persona_id)
        return persona if persona is not None and persona.owner_id == owner_id else None

    async def update(
        self,
        owner_id: UUID,
        persona_id: UUID,
        name: str | None,
        content: PersonaContent,
    ) -> PersonaRead | None:
        persona = self._personas.get(persona_id)
        if persona is None or persona.owner_id != owner_id:
            return None
        version = persona.current_version + 1
        updated = persona.model_copy(
            update={
                "name": name if name is not None else persona.name,
                "current_version": version,
                "content": content,
                "updated_at": datetime.now(UTC),
            }
        )
        self._personas[persona_id] = updated
        self._versions[persona_id].append(
            PersonaVersionRead(
                version=version,
                content=content,
                created_by=owner_id,
                created_at=datetime.now(UTC),
            )
        )
        return updated

    async def list_versions(
        self, owner_id: UUID, persona_id: UUID
    ) -> list[PersonaVersionRead] | None:
        persona = self._personas.get(persona_id)
        if persona is None or persona.owner_id != owner_id:
            return None
        return list(reversed(self._versions[persona_id]))

    async def fetch_version(
        self, owner_id: UUID, persona_id: UUID, version: int
    ) -> PersonaVersionRead | None:
        persona = self._personas.get(persona_id)
        if persona is None or persona.owner_id != owner_id:
            return None
        return next(
            (v for v in self._versions[persona_id] if v.version == version), None
        )


def _service() -> tuple[PersonaService, UUID]:
    return PersonaService(FakePersonaRepository()), uuid4()


def test_create_starts_at_version_one() -> None:
    service, owner = _service()
    persona = asyncio.run(
        service.create(owner, PersonaCreate(name="QA", content=_content()))
    )
    assert persona.current_version == 1
    assert persona.owner_id == owner


def test_get_returns_created_persona() -> None:
    service, owner = _service()
    created = asyncio.run(
        service.create(owner, PersonaCreate(name="QA", content=_content()))
    )
    assert asyncio.run(service.get(owner, created.id)) == created


def test_get_unknown_persona_raises_404() -> None:
    service, owner = _service()
    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.get(owner, uuid4()))
    assert exc.value.status_code == 404


def test_get_foreign_persona_raises_404() -> None:
    service, owner = _service()
    created = asyncio.run(
        service.create(owner, PersonaCreate(name="QA", content=_content()))
    )
    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.get(uuid4(), created.id))
    assert exc.value.status_code == 404


def test_list_returns_only_own_personas() -> None:
    service, owner = _service()
    asyncio.run(service.create(owner, PersonaCreate(name="A", content=_content())))
    asyncio.run(service.create(uuid4(), PersonaCreate(name="B", content=_content())))
    own = asyncio.run(service.list_all(owner))
    assert [p.name for p in own] == ["A"]


def test_update_bumps_version_and_records_snapshot() -> None:
    service, owner = _service()
    created = asyncio.run(
        service.create(owner, PersonaCreate(name="QA", content=_content("v1")))
    )
    updated = asyncio.run(
        service.update(
            owner, created.id, PersonaUpdate(content=_content("v2"))
        )
    )
    assert updated.current_version == 2
    assert updated.name == "QA"  # name war None -> bleibt erhalten
    versions = asyncio.run(service.list_versions(owner, created.id))
    assert [v.version for v in versions] == [2, 1]


def test_update_unknown_persona_raises_404() -> None:
    service, owner = _service()
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            service.update(owner, uuid4(), PersonaUpdate(content=_content()))
        )
    assert exc.value.status_code == 404


def test_get_version_returns_requested_snapshot() -> None:
    service, owner = _service()
    created = asyncio.run(
        service.create(owner, PersonaCreate(name="QA", content=_content("v1")))
    )
    asyncio.run(
        service.update(owner, created.id, PersonaUpdate(content=_content("v2")))
    )
    first = asyncio.run(service.get_version(owner, created.id, 1))
    assert first.content.description == "v1"


def test_get_unknown_version_raises_404() -> None:
    service, owner = _service()
    created = asyncio.run(
        service.create(owner, PersonaCreate(name="QA", content=_content()))
    )
    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.get_version(owner, created.id, 99))
    assert exc.value.status_code == 404


def test_list_versions_unknown_persona_raises_404() -> None:
    service, owner = _service()
    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.list_versions(owner, uuid4()))
    assert exc.value.status_code == 404
