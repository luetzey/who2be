"""Unit-Tests fuer `PersonaService` mit einem In-Memory-Fake-Repository."""

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from who2be_api.core.security import WorkspaceContext
from who2be_api.repositories.persona_repository import PersonaUpdateOutcome
from who2be_api.services.persona_service import PersonaService
from who2be_models import (
    PersonaCreate,
    PersonaRead,
    PersonaUpdate,
    PersonaVersionContent,
    PersonaVersionRead,
    VersionStatus,
    WorkspaceRole,
)


def _content(description: str = "Tester") -> PersonaVersionContent:
    return PersonaVersionContent(description=description, system_prompt="Be helpful.")


def _ctx(
    workspace_id: UUID, user_id: UUID | None = None, is_api_token: bool = False
) -> WorkspaceContext:
    return WorkspaceContext(
        workspace_id=workspace_id,
        user_id=user_id or uuid4(),
        role=WorkspaceRole.admin,
        is_api_token=is_api_token,
    )


class FakePersonaRepository:
    """In-Memory-Stub von `PersonaRepository`."""

    def __init__(self) -> None:
        self._personas: dict[UUID, PersonaRead] = {}
        self._versions: dict[UUID, list[PersonaVersionRead]] = {}
        self.last_active_only: bool | None = None

    async def insert(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        name: str,
        content: PersonaVersionContent,
    ) -> PersonaRead:
        now = datetime.now(UTC)
        persona = PersonaRead(
            id=uuid4(),
            workspace_id=workspace_id,
            owner_id=owner_id,
            name=name,
            current_version=1,
            content=content,
            created_at=now,
            updated_at=now,
        )
        self._personas[persona.id] = persona
        self._versions[persona.id] = [
            PersonaVersionRead(version=1, content=content, created_by=owner_id, created_at=now)
        ]
        return persona

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        limit: int,
        after: tuple[datetime, UUID] | None,
        active_only: bool = False,
    ) -> list[PersonaRead]:
        self.last_active_only = active_only
        own = sorted(
            (p for p in self._personas.values() if p.workspace_id == workspace_id),
            key=lambda p: (p.created_at, p.id),
            reverse=True,
        )
        if active_only:
            own = [p for p in own if p.current_status == VersionStatus.active]
        if after is not None:
            own = [p for p in own if (p.created_at, p.id) < after]
        return own[:limit]

    async def fetch(
        self, workspace_id: UUID, persona_id: UUID, active_only: bool = False
    ) -> PersonaRead | None:
        self.last_active_only = active_only
        persona = self._personas.get(persona_id)
        if persona is None or persona.workspace_id != workspace_id:
            return None
        if active_only and persona.current_status != VersionStatus.active:
            return None
        return persona

    async def update(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        persona_id: UUID,
        name: str | None,
        content: PersonaVersionContent,
    ) -> PersonaUpdateOutcome:
        persona = self._personas.get(persona_id)
        if persona is None or persona.workspace_id != workspace_id:
            return PersonaUpdateOutcome(persona=None)
        if any(v.status == VersionStatus.draft for v in self._versions[persona_id]):
            return PersonaUpdateOutcome(persona=None, conflict="draft_exists")
        if persona.current_status == VersionStatus.active:
            new_status = VersionStatus.draft
        else:
            new_status = VersionStatus.inactive
        version = persona.current_version + 1
        updated = persona.model_copy(
            update={
                "name": name if name is not None else persona.name,
                "current_version": version,
                "current_status": new_status,
                "has_pending_draft": new_status == VersionStatus.draft,
                "content": content,
                "updated_at": datetime.now(UTC),
            }
        )
        self._personas[persona_id] = updated
        self._versions[persona_id].append(
            PersonaVersionRead(
                version=version,
                status=new_status,
                content=content,
                created_by=owner_id,
                created_at=datetime.now(UTC),
            )
        )
        return PersonaUpdateOutcome(persona=updated)

    async def upsert_draft(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        persona_id: UUID,
        name: str | None,
        content: PersonaVersionContent,
    ) -> PersonaUpdateOutcome:
        persona = self._personas.get(persona_id)
        if persona is None or persona.workspace_id != workspace_id:
            return PersonaUpdateOutcome(persona=None)
        existing_draft = next(
            (v for v in self._versions[persona_id] if v.status == VersionStatus.draft),
            None,
        )
        if existing_draft is not None:
            updated_version = existing_draft.model_copy(
                update={"content": content, "created_by": owner_id, "created_at": datetime.now(UTC)}
            )
            self._versions[persona_id] = [
                updated_version if v.version == existing_draft.version else v
                for v in self._versions[persona_id]
            ]
            updated = persona.model_copy(
                update={
                    "name": name if name is not None else persona.name,
                    "content": content,
                    "current_status": VersionStatus.draft,
                    "has_pending_draft": True,
                    "updated_at": datetime.now(UTC),
                }
            )
            self._personas[persona_id] = updated
            return PersonaUpdateOutcome(persona=updated)
        if persona.current_status == VersionStatus.review:
            return PersonaUpdateOutcome(persona=None, conflict="review_pending")
        version = persona.current_version + 1
        updated = persona.model_copy(
            update={
                "name": name if name is not None else persona.name,
                "current_version": version,
                "current_status": VersionStatus.draft,
                "has_pending_draft": True,
                "content": content,
                "updated_at": datetime.now(UTC),
            }
        )
        self._personas[persona_id] = updated
        self._versions[persona_id].append(
            PersonaVersionRead(
                version=version,
                status=VersionStatus.draft,
                content=content,
                created_by=owner_id,
                created_at=datetime.now(UTC),
            )
        )
        return PersonaUpdateOutcome(persona=updated)

    def promote_current_to_active(self, persona_id: UUID) -> None:
        """Testhelfer: hebt die Current-Version auf 'active'."""
        persona = self._personas[persona_id]
        self._versions[persona_id] = [
            v.model_copy(
                update={
                    "status": VersionStatus.active
                    if v.version == persona.current_version
                    else VersionStatus.inactive
                }
            )
            for v in self._versions[persona_id]
        ]
        self._personas[persona_id] = persona.model_copy(
            update={"current_status": VersionStatus.active, "has_pending_draft": False}
        )

    async def list_versions(
        self, workspace_id: UUID, persona_id: UUID
    ) -> list[PersonaVersionRead] | None:
        persona = self._personas.get(persona_id)
        if persona is None or persona.workspace_id != workspace_id:
            return None
        return list(reversed(self._versions[persona_id]))

    async def fetch_version(
        self, workspace_id: UUID, persona_id: UUID, version: int
    ) -> PersonaVersionRead | None:
        persona = self._personas.get(persona_id)
        if persona is None or persona.workspace_id != workspace_id:
            return None
        return next((v for v in self._versions[persona_id] if v.version == version), None)

    async def list_distinct_tags(self, workspace_id: UUID) -> list[str]:
        tags: set[str] = set()
        for persona in self._personas.values():
            if persona.workspace_id == workspace_id:
                tags.update(persona.content.tags)
        return sorted(tags)


def _service() -> tuple[PersonaService, WorkspaceContext]:
    return PersonaService(FakePersonaRepository()), _ctx(uuid4())


def test_create_starts_at_version_one() -> None:
    service, ctx = _service()
    persona = asyncio.run(service.create(ctx, PersonaCreate(name="QA", content=_content())))
    assert persona.current_version == 1
    assert persona.workspace_id == ctx.workspace_id
    assert persona.owner_id == ctx.user_id


def test_get_returns_created_persona() -> None:
    service, ctx = _service()
    created = asyncio.run(service.create(ctx, PersonaCreate(name="QA", content=_content())))
    assert asyncio.run(service.get(ctx, created.id)) == created


def test_get_unknown_persona_raises_404() -> None:
    service, ctx = _service()
    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.get(ctx, uuid4()))
    assert exc.value.status_code == 404


def test_get_foreign_persona_raises_404() -> None:
    service, ctx = _service()
    created = asyncio.run(service.create(ctx, PersonaCreate(name="QA", content=_content())))
    other = _ctx(uuid4())
    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.get(other, created.id))
    assert exc.value.status_code == 404


def test_list_returns_only_own_personas() -> None:
    service, ctx = _service()
    asyncio.run(service.create(ctx, PersonaCreate(name="A", content=_content())))
    other = _ctx(uuid4())
    asyncio.run(service.create(other, PersonaCreate(name="B", content=_content())))
    own, next_cursor = asyncio.run(service.list_all(ctx, 100, None))
    assert [p.name for p in own] == ["A"]
    assert next_cursor is None


def test_list_returns_next_cursor_when_more_items_available() -> None:
    service, ctx = _service()
    for name in ("A", "B", "C"):
        asyncio.run(service.create(ctx, PersonaCreate(name=name, content=_content())))
    page1, cursor = asyncio.run(service.list_all(ctx, 2, None))
    assert len(page1) == 2
    assert cursor is not None
    page2, cursor2 = asyncio.run(service.list_all(ctx, 2, (page1[-1].created_at, page1[-1].id)))
    assert len(page2) == 1
    assert cursor2 is None
    assert {p.name for p in page1 + page2} == {"A", "B", "C"}


def test_update_bumps_version_and_records_snapshot() -> None:
    service, ctx = _service()
    created = asyncio.run(service.create(ctx, PersonaCreate(name="QA", content=_content("v1"))))
    updated = asyncio.run(service.update(ctx, created.id, PersonaUpdate(content=_content("v2"))))
    assert updated.current_version == 2
    assert updated.name == "QA"  # name war None -> bleibt erhalten
    versions = asyncio.run(service.list_versions(ctx, created.id))
    assert [v.version for v in versions] == [2, 1]


def test_update_unknown_persona_raises_404() -> None:
    service, ctx = _service()
    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.update(ctx, uuid4(), PersonaUpdate(content=_content())))
    assert exc.value.status_code == 404


def test_get_version_returns_requested_snapshot() -> None:
    service, ctx = _service()
    created = asyncio.run(service.create(ctx, PersonaCreate(name="QA", content=_content("v1"))))
    asyncio.run(service.update(ctx, created.id, PersonaUpdate(content=_content("v2"))))
    first = asyncio.run(service.get_version(ctx, created.id, 1))
    assert first.content.description == "v1"


def test_get_unknown_version_raises_404() -> None:
    service, ctx = _service()
    created = asyncio.run(service.create(ctx, PersonaCreate(name="QA", content=_content())))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.get_version(ctx, created.id, 99))
    assert exc.value.status_code == 404


def test_list_versions_unknown_persona_raises_404() -> None:
    service, ctx = _service()
    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.list_versions(ctx, uuid4()))
    assert exc.value.status_code == 404


def test_update_on_active_creates_draft_without_overwriting() -> None:
    repo = FakePersonaRepository()
    service = PersonaService(repo)
    ctx = _ctx(uuid4())
    created = asyncio.run(service.create(ctx, PersonaCreate(name="QA", content=_content("v1"))))
    repo.promote_current_to_active(created.id)
    updated = asyncio.run(service.update(ctx, created.id, PersonaUpdate(content=_content("v2"))))
    assert updated.current_version == 2
    assert updated.current_status == VersionStatus.draft
    assert updated.has_pending_draft is True


def test_update_on_active_with_existing_draft_raises_409() -> None:
    repo = FakePersonaRepository()
    service = PersonaService(repo)
    ctx = _ctx(uuid4())
    created = asyncio.run(service.create(ctx, PersonaCreate(name="QA", content=_content("v1"))))
    repo.promote_current_to_active(created.id)
    asyncio.run(service.update(ctx, created.id, PersonaUpdate(content=_content("v2"))))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.update(ctx, created.id, PersonaUpdate(content=_content("v3"))))
    assert exc.value.status_code == 409


def test_api_token_context_filters_to_active_only() -> None:
    repo = FakePersonaRepository()
    service = PersonaService(repo)
    ws = uuid4()
    user = uuid4()
    web_ctx = _ctx(ws, user_id=user)
    inactive = asyncio.run(service.create(web_ctx, PersonaCreate(name="I", content=_content())))
    active = asyncio.run(service.create(web_ctx, PersonaCreate(name="A", content=_content())))
    repo.promote_current_to_active(active.id)

    # JWT-Pfad (Web) sieht beide.
    web_items, _ = asyncio.run(service.list_all(web_ctx, 100, None))
    assert {p.id for p in web_items} == {inactive.id, active.id}

    # API-Token-Pfad (MCP) sieht nur Active.
    token_ctx = _ctx(ws, user_id=user, is_api_token=True)
    mcp_items, _ = asyncio.run(service.list_all(token_ctx, 100, None))
    assert [p.id for p in mcp_items] == [active.id]
    assert repo.last_active_only is True
    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.get(token_ctx, inactive.id))
    assert exc.value.status_code == 404
