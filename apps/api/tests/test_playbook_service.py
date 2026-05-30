"""Unit-Tests fuer `PlaybookService` mit einem In-Memory-Fake-Repository."""

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from who2be_api.core.security import WorkspaceContext
from who2be_api.repositories.playbook_repository import PlaybookUpdateOutcome
from who2be_api.services.playbook_service import PlaybookService
from who2be_models import (
    PlaybookContent,
    PlaybookCreate,
    PlaybookRead,
    PlaybookUpdate,
    PlaybookVersionRead,
    VersionStatus,
    WorkspaceRole,
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


def _ctx(
    workspace_id: UUID, user_id: UUID | None = None, is_api_token: bool = False
) -> WorkspaceContext:
    return WorkspaceContext(
        workspace_id=workspace_id,
        user_id=user_id or uuid4(),
        role=WorkspaceRole.admin,
        is_api_token=is_api_token,
    )


class FakePlaybookRepository:
    """In-Memory-Stub von `PlaybookRepository`."""

    def __init__(self) -> None:
        self._playbooks: dict[UUID, PlaybookRead] = {}
        self._versions: dict[UUID, list[PlaybookVersionRead]] = {}
        self.last_active_only: bool | None = None

    async def insert(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        name: str,
        content: PlaybookContent,
    ) -> PlaybookRead:
        now = datetime.now(UTC)
        playbook = PlaybookRead(
            id=uuid4(),
            workspace_id=workspace_id,
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

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        tag: str | None,
        trigger: str | None,
        limit: int,
        after: tuple[datetime, UUID] | None,
        active_only: bool = False,
    ) -> list[PlaybookRead]:
        self.last_active_only = active_only
        result = [p for p in self._playbooks.values() if p.workspace_id == workspace_id]
        if active_only:
            result = [p for p in result if p.current_status == VersionStatus.active]
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

    async def fetch(
        self, workspace_id: UUID, playbook_id: UUID, active_only: bool = False
    ) -> PlaybookRead | None:
        self.last_active_only = active_only
        playbook = self._playbooks.get(playbook_id)
        if playbook is None or playbook.workspace_id != workspace_id:
            return None
        if active_only and playbook.current_status != VersionStatus.active:
            return None
        return playbook

    async def update(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        playbook_id: UUID,
        name: str | None,
        content: PlaybookContent,
    ) -> PlaybookUpdateOutcome:
        playbook = self._playbooks.get(playbook_id)
        if playbook is None or playbook.workspace_id != workspace_id:
            return PlaybookUpdateOutcome(playbook=None)
        if any(v.status == VersionStatus.draft for v in self._versions[playbook_id]):
            return PlaybookUpdateOutcome(playbook=None, conflict="draft_exists")
        if playbook.current_status == VersionStatus.active:
            new_status = VersionStatus.draft
        else:
            new_status = VersionStatus.inactive
        version = playbook.current_version + 1
        updated = playbook.model_copy(
            update={
                "name": name if name is not None else playbook.name,
                "current_version": version,
                "current_status": new_status,
                "has_pending_draft": new_status == VersionStatus.draft,
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
                status=new_status,
                content=content,
                created_by=owner_id,
                created_at=datetime.now(UTC),
            )
        )
        return PlaybookUpdateOutcome(playbook=updated)

    async def upsert_draft(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        playbook_id: UUID,
        name: str | None,
        content: PlaybookContent,
    ) -> PlaybookUpdateOutcome:
        playbook = self._playbooks.get(playbook_id)
        if playbook is None or playbook.workspace_id != workspace_id:
            return PlaybookUpdateOutcome(playbook=None)
        existing_draft = next(
            (v for v in self._versions[playbook_id] if v.status == VersionStatus.draft),
            None,
        )
        if existing_draft is not None:
            updated_version = existing_draft.model_copy(
                update={"content": content, "created_by": owner_id, "created_at": datetime.now(UTC)}
            )
            self._versions[playbook_id] = [
                updated_version if v.version == existing_draft.version else v
                for v in self._versions[playbook_id]
            ]
            updated = playbook.model_copy(
                update={
                    "name": name if name is not None else playbook.name,
                    "type": content.type,
                    "tags": content.tags,
                    "triggers": content.triggers,
                    "content": content,
                    "current_status": VersionStatus.draft,
                    "has_pending_draft": True,
                    "updated_at": datetime.now(UTC),
                }
            )
            self._playbooks[playbook_id] = updated
            return PlaybookUpdateOutcome(playbook=updated)
        if playbook.current_status == VersionStatus.review:
            return PlaybookUpdateOutcome(playbook=None, conflict="review_pending")
        version = playbook.current_version + 1
        updated = playbook.model_copy(
            update={
                "name": name if name is not None else playbook.name,
                "current_version": version,
                "current_status": VersionStatus.draft,
                "has_pending_draft": True,
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
                status=VersionStatus.draft,
                content=content,
                created_by=owner_id,
                created_at=datetime.now(UTC),
            )
        )
        return PlaybookUpdateOutcome(playbook=updated)

    def promote_current_to_active(self, playbook_id: UUID) -> None:
        playbook = self._playbooks[playbook_id]
        self._versions[playbook_id] = [
            v.model_copy(
                update={
                    "status": VersionStatus.active
                    if v.version == playbook.current_version
                    else VersionStatus.inactive
                }
            )
            for v in self._versions[playbook_id]
        ]
        self._playbooks[playbook_id] = playbook.model_copy(
            update={"current_status": VersionStatus.active, "has_pending_draft": False}
        )

    async def list_versions(
        self, workspace_id: UUID, playbook_id: UUID
    ) -> list[PlaybookVersionRead] | None:
        playbook = self._playbooks.get(playbook_id)
        if playbook is None or playbook.workspace_id != workspace_id:
            return None
        return list(reversed(self._versions[playbook_id]))

    async def fetch_version(
        self, workspace_id: UUID, playbook_id: UUID, version: int
    ) -> PlaybookVersionRead | None:
        playbook = self._playbooks.get(playbook_id)
        if playbook is None or playbook.workspace_id != workspace_id:
            return None
        return next((v for v in self._versions[playbook_id] if v.version == version), None)

    async def list_distinct_tags(self, workspace_id: UUID) -> list[str]:
        tags: set[str] = set()
        for playbook in self._playbooks.values():
            if playbook.workspace_id == workspace_id:
                tags.update(playbook.tags)
        return sorted(tags)


def _service() -> tuple[PlaybookService, WorkspaceContext]:
    return PlaybookService(FakePlaybookRepository()), _ctx(uuid4())


def test_create_denormalises_content_fields() -> None:
    service, ctx = _service()
    playbook = asyncio.run(
        service.create(
            ctx,
            PlaybookCreate(name="PB", content=_content(tags=["a"], triggers="hi")),
        )
    )
    assert playbook.current_version == 1
    assert playbook.tags == ["a"]
    assert playbook.triggers == "hi"


def test_get_unknown_playbook_raises_404() -> None:
    service, ctx = _service()
    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.get(ctx, uuid4()))
    assert exc.value.status_code == 404


def test_get_foreign_playbook_raises_404() -> None:
    service, ctx = _service()
    created = asyncio.run(service.create(ctx, PlaybookCreate(name="PB", content=_content())))
    other = _ctx(uuid4())
    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.get(other, created.id))
    assert exc.value.status_code == 404


def test_list_filters_by_tag() -> None:
    service, ctx = _service()
    asyncio.run(service.create(ctx, PlaybookCreate(name="A", content=_content(tags=["x"]))))
    asyncio.run(service.create(ctx, PlaybookCreate(name="B", content=_content(tags=["y"]))))
    matched, next_cursor = asyncio.run(service.list_all(ctx, "x", None, 100, None))
    assert [p.name for p in matched] == ["A"]
    assert next_cursor is None


def test_list_filters_by_trigger_substring() -> None:
    service, ctx = _service()
    asyncio.run(
        service.create(ctx, PlaybookCreate(name="A", content=_content(triggers="new user")))
    )
    asyncio.run(
        service.create(ctx, PlaybookCreate(name="B", content=_content(triggers="on error")))
    )
    matched, next_cursor = asyncio.run(service.list_all(ctx, None, "USER", 100, None))
    assert [p.name for p in matched] == ["A"]
    assert next_cursor is None


def test_update_bumps_version_and_records_snapshot() -> None:
    service, ctx = _service()
    created = asyncio.run(service.create(ctx, PlaybookCreate(name="PB", content=_content("v1"))))
    updated = asyncio.run(service.update(ctx, created.id, PlaybookUpdate(content=_content("v2"))))
    assert updated.current_version == 2
    versions = asyncio.run(service.list_versions(ctx, created.id))
    assert [v.version for v in versions] == [2, 1]


def test_update_unknown_playbook_raises_404() -> None:
    service, ctx = _service()
    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.update(ctx, uuid4(), PlaybookUpdate(content=_content())))
    assert exc.value.status_code == 404


def test_get_version_returns_requested_snapshot() -> None:
    service, ctx = _service()
    created = asyncio.run(service.create(ctx, PlaybookCreate(name="PB", content=_content("v1"))))
    asyncio.run(service.update(ctx, created.id, PlaybookUpdate(content=_content("v2"))))
    first = asyncio.run(service.get_version(ctx, created.id, 1))
    assert first.content.description == "v1"


def test_update_on_active_creates_draft_without_overwriting() -> None:
    repo = FakePlaybookRepository()
    service = PlaybookService(repo)
    ctx = _ctx(uuid4())
    created = asyncio.run(service.create(ctx, PlaybookCreate(name="PB", content=_content("v1"))))
    repo.promote_current_to_active(created.id)
    updated = asyncio.run(service.update(ctx, created.id, PlaybookUpdate(content=_content("v2"))))
    assert updated.current_version == 2
    assert updated.current_status == VersionStatus.draft
    assert updated.has_pending_draft is True


def test_update_on_active_with_existing_draft_raises_409() -> None:
    repo = FakePlaybookRepository()
    service = PlaybookService(repo)
    ctx = _ctx(uuid4())
    created = asyncio.run(service.create(ctx, PlaybookCreate(name="PB", content=_content("v1"))))
    repo.promote_current_to_active(created.id)
    asyncio.run(service.update(ctx, created.id, PlaybookUpdate(content=_content("v2"))))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.update(ctx, created.id, PlaybookUpdate(content=_content("v3"))))
    assert exc.value.status_code == 409


def test_api_token_context_filters_to_active_only() -> None:
    repo = FakePlaybookRepository()
    service = PlaybookService(repo)
    ws = uuid4()
    user = uuid4()
    web_ctx = _ctx(ws, user_id=user)
    inactive = asyncio.run(service.create(web_ctx, PlaybookCreate(name="I", content=_content())))
    active = asyncio.run(service.create(web_ctx, PlaybookCreate(name="A", content=_content())))
    repo.promote_current_to_active(active.id)

    web_items, _ = asyncio.run(service.list_all(web_ctx, None, None, 100, None))
    assert {p.id for p in web_items} == {inactive.id, active.id}

    token_ctx = _ctx(ws, user_id=user, is_api_token=True)
    mcp_items, _ = asyncio.run(service.list_all(token_ctx, None, None, 100, None))
    assert [p.id for p in mcp_items] == [active.id]
    assert repo.last_active_only is True
    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.get(token_ctx, inactive.id))
    assert exc.value.status_code == 404
