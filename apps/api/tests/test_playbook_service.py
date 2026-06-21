"""Unit-Tests fuer `PlaybookService` mit einem In-Memory-Fake-Repository."""

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

import asyncpg
import pytest
from fastapi import HTTPException

from who2be_api.core.security import WorkspaceContext
from who2be_api.repositories.playbook_composition_repository import SetCompositionResult
from who2be_api.repositories.playbook_repository import PlaybookUpdateOutcome
from who2be_api.repositories.playbook_resource_link_repository import SetLinksResult
from who2be_api.services.playbook_composition_service import PlaybookCompositionService
from who2be_api.services.playbook_resource_link_service import PlaybookResourceLinkService
from who2be_api.services.playbook_service import PlaybookService
from who2be_models import (
    PlaybookContent,
    PlaybookCreate,
    PlaybookRead,
    PlaybookRef,
    PlaybookUpdate,
    PlaybookVersionRead,
    ResourceLinkItem,
    ResourceLinkRead,
    TriggerOverview,
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
        locales: list[str] | None = None,
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
        locale: str = "de",
        restrict_ids: list[UUID] | None = None,
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
        if restrict_ids is not None:
            allowed = set(restrict_ids)
            result = [p for p in result if p.id in allowed]
        result.sort(key=lambda p: (p.created_at, p.id), reverse=True)
        if after is not None:
            result = [p for p in result if (p.created_at, p.id) < after]
        return result[:limit]

    async def fetch(
        self,
        workspace_id: UUID,
        playbook_id: UUID,
        active_only: bool = False,
        locale: str = "de",
        restrict_ids: list[UUID] | None = None,
    ) -> PlaybookRead | None:
        self.last_active_only = active_only
        playbook = self._playbooks.get(playbook_id)
        if playbook is None or playbook.workspace_id != workspace_id:
            return None
        if active_only and playbook.current_status != VersionStatus.active:
            return None
        if restrict_ids is not None and playbook_id not in set(restrict_ids):
            return None
        return playbook

    async def update(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        playbook_id: UUID,
        name: str | None,
        content: PlaybookContent,
        locale: str = "de",
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

    async def restore_version(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        playbook_id: UUID,
        content: PlaybookContent,
        locale: str = "de",
    ) -> PlaybookUpdateOutcome:
        playbook = self._playbooks.get(playbook_id)
        if playbook is None or playbook.workspace_id != workspace_id:
            return PlaybookUpdateOutcome(playbook=None)
        if any(v.status == VersionStatus.draft for v in self._versions[playbook_id]):
            return PlaybookUpdateOutcome(playbook=None, conflict="draft_exists")
        version = playbook.current_version + 1
        updated = playbook.model_copy(
            update={
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

    async def upsert_draft(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        playbook_id: UUID,
        name: str | None,
        content: PlaybookContent,
        locale: str = "de",
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
        self, workspace_id: UUID, playbook_id: UUID, locale: str = "de"
    ) -> list[PlaybookVersionRead] | None:
        playbook = self._playbooks.get(playbook_id)
        if playbook is None or playbook.workspace_id != workspace_id:
            return None
        return list(reversed(self._versions[playbook_id]))

    async def fetch_version(
        self, workspace_id: UUID, playbook_id: UUID, version: int, locale: str = "de"
    ) -> PlaybookVersionRead | None:
        playbook = self._playbooks.get(playbook_id)
        if playbook is None or playbook.workspace_id != workspace_id:
            return None
        return next((v for v in self._versions[playbook_id] if v.version == version), None)

    async def list_distinct_tags(
        self,
        workspace_id: UUID,
        locale: str = "de",
        restrict_ids: list[UUID] | None = None,
    ) -> list[str]:
        allowed = None if restrict_ids is None else set(restrict_ids)
        tags: set[str] = set()
        for playbook in self._playbooks.values():
            if playbook.workspace_id != workspace_id:
                continue
            if allowed is not None and playbook.id not in allowed:
                continue
            tags.update(playbook.tags)
        return sorted(tags)

    async def list_triggers_with_playbooks(self, workspace_id: UUID) -> list[TriggerOverview]:
        bucket: dict[str, list[PlaybookRef]] = {}
        for playbook in self._playbooks.values():
            if playbook.workspace_id != workspace_id:
                continue
            if not playbook.triggers:
                continue
            for raw in playbook.triggers.split(","):
                trigger = raw.strip()
                if not trigger:
                    continue
                bucket.setdefault(trigger, []).append(
                    PlaybookRef(id=playbook.id, name=playbook.name)
                )
        return [TriggerOverview(trigger=t, playbooks=p) for t, p in sorted(bucket.items())]

    async def delete(self, workspace_id: UUID, playbook_id: UUID) -> bool:
        playbook = self._playbooks.get(playbook_id)
        if playbook is None or playbook.workspace_id != workspace_id:
            return False
        del self._playbooks[playbook_id]
        return True


class FakeCompositionRepo:
    """In-Memory-Stub: erfasst die zuletzt gesetzte Composition-Kinderliste.

    `parent_belongs_to` ist immer True; `set_composition` simuliert den Zyklus-
    Guard ueber `cycle_for`-IDs, damit der Save-Sync-Pfad einen 409 ausloesen kann.
    """

    def __init__(self) -> None:
        self.last_child_ids: list[UUID] | None = None
        self.cycle_for: set[UUID] = set()

    async def parent_belongs_to(self, workspace_id: UUID, parent_id: UUID) -> bool:
        return True

    async def list_children(self, parent_id: UUID, active_only: bool = False) -> list[PlaybookRead]:
        return []

    async def list_parents(self, child_id: UUID) -> list[PlaybookRef]:
        return []

    async def set_composition(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        parent_id: UUID,
        child_ids: list[UUID],
    ) -> SetCompositionResult:
        if any(cid in self.cycle_for for cid in child_ids):
            return SetCompositionResult(parent_found=True, cycle=True)
        self.last_child_ids = list(child_ids)
        return SetCompositionResult(parent_found=True)


class FakeResourceLinkRepo:
    """In-Memory-Stub: erfasst die zuletzt gesetzten Resource-Links."""

    def __init__(self) -> None:
        self.last_links: list[ResourceLinkItem] | None = None

    async def list_links(
        self, workspace_id: UUID, playbook_id: UUID
    ) -> list[ResourceLinkRead] | None:
        return []

    async def load_resource_blocks(
        self, workspace_id: UUID, resource_ids: Sequence[UUID]
    ) -> dict[UUID, list[dict[str, Any]]]:
        return {}

    async def set_links(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        playbook_id: UUID,
        links: Sequence[ResourceLinkItem],
    ) -> SetLinksResult:
        self.last_links = list(links)
        return SetLinksResult(playbook_found=True)


def _make_service(
    repo: FakePlaybookRepository,
    composition_repo: FakeCompositionRepo | None = None,
    link_repo: FakeResourceLinkRepo | None = None,
) -> PlaybookService:
    comp = PlaybookCompositionService(composition_repo or FakeCompositionRepo())
    links = PlaybookResourceLinkService(link_repo or FakeResourceLinkRepo())
    return PlaybookService(repo, cast("asyncpg.Pool", None), comp, links)


def _service() -> tuple[PlaybookService, WorkspaceContext]:
    return _make_service(FakePlaybookRepository()), _ctx(uuid4())


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
    service = _make_service(repo)
    ctx = _ctx(uuid4())
    created = asyncio.run(service.create(ctx, PlaybookCreate(name="PB", content=_content("v1"))))
    repo.promote_current_to_active(created.id)
    updated = asyncio.run(service.update(ctx, created.id, PlaybookUpdate(content=_content("v2"))))
    assert updated.current_version == 2
    assert updated.current_status == VersionStatus.draft
    assert updated.has_pending_draft is True


def test_update_on_active_with_existing_draft_raises_409() -> None:
    repo = FakePlaybookRepository()
    service = _make_service(repo)
    ctx = _ctx(uuid4())
    created = asyncio.run(service.create(ctx, PlaybookCreate(name="PB", content=_content("v1"))))
    repo.promote_current_to_active(created.id)
    asyncio.run(service.update(ctx, created.id, PlaybookUpdate(content=_content("v2"))))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.update(ctx, created.id, PlaybookUpdate(content=_content("v3"))))
    assert exc.value.status_code == 409


def test_list_triggers_excludes_triggerless_playbook() -> None:
    """B3: Ein Playbook ohne Trigger erscheint NICHT in list_triggers (Discovery-Liste).

    Applied-Playbooks (via Pill im System-Prompt-Template eingebettet) fuehren
    typischerweise keine `triggers`-Felder, da sie immer geladen sind und nicht
    on-demand getriggert werden. Diese Eigenschaft garantiert, dass applied-
    Playbooks sauber von triggered-Playbooks getrennt bleiben.
    """
    service, ctx = _service()
    asyncio.run(
        service.create(
            ctx,
            PlaybookCreate(name="Applied-Playbook", content=_content(triggers=None)),
        )
    )
    asyncio.run(
        service.create(
            ctx,
            PlaybookCreate(name="Triggered-Playbook", content=_content(triggers="reset, logout")),
        )
    )

    triggers = asyncio.run(service.list_triggers(ctx))

    trigger_names = {t.trigger for t in triggers}
    playbook_names_in_triggers = {pb.name for t in triggers for pb in t.playbooks}

    # Trigger-los → erscheint nicht in der Discovery-Liste.
    assert "Applied-Playbook" not in playbook_names_in_triggers
    # Triggered-Playbook erscheint mit beiden Keywords.
    assert "reset" in trigger_names
    assert "logout" in trigger_names
    assert "Triggered-Playbook" in playbook_names_in_triggers


def test_api_token_context_filters_to_active_only() -> None:
    repo = FakePlaybookRepository()
    service = _make_service(repo)
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


# --- B3: Save-Sync „Body treibt" ------------------------------------------


def _blocknote_content(body: str, description: str = "Flow") -> PlaybookContent:
    return PlaybookContent(
        description=description,
        body=body,
        type="workflow",
        tags=[],
        triggers=None,
    )


def _pill_body(child_id: UUID, resource_id: UUID, block_id: str = "h1") -> str:
    """BlockNote-Body mit einer Playbook-Pill und einer Block-Resource-Pill."""
    import json

    return json.dumps(
        [
            {
                "type": "paragraph",
                "content": [
                    {
                        "type": "placeholder",
                        "props": {
                            "kind": "playbook",
                            "target_id": str(child_id),
                            "label": "Sub",
                        },
                    },
                    {
                        "type": "placeholder",
                        "props": {
                            "kind": "resource",
                            "target_id": f"{resource_id}#{block_id}",
                            "label": "Res",
                        },
                    },
                ],
            }
        ]
    )


def test_blocknote_create_syncs_composition_and_resource_links() -> None:
    repo = FakePlaybookRepository()
    comp = FakeCompositionRepo()
    links = FakeResourceLinkRepo()
    service = _make_service(repo, comp, links)
    ctx = _ctx(uuid4())
    child = uuid4()
    resource = uuid4()
    body = _pill_body(child, resource)
    asyncio.run(
        service.create(ctx, PlaybookCreate(name="Composite", content=_blocknote_content(body)))
    )
    assert comp.last_child_ids == [child]
    assert links.last_links is not None
    assert len(links.last_links) == 1
    assert links.last_links[0].resource_id == resource
    assert links.last_links[0].link_scope == "block"
    assert links.last_links[0].block_id == "h1"


def test_create_with_pill_free_body_syncs_empty_links() -> None:
    repo = FakePlaybookRepository()
    comp = FakeCompositionRepo()
    links = FakeResourceLinkRepo()
    service = _make_service(repo, comp, links)
    ctx = _ctx(uuid4())
    asyncio.run(service.create(ctx, PlaybookCreate(name="Plain", content=_content())))
    # Track B: der Body treibt immer — ein pill-freier (hier leerer/nicht-JSON)
    # Body synct leere Link-Sets (idempotenter No-Op fuer ein frisches Playbook).
    assert comp.last_child_ids == []
    assert links.last_links == []


def test_blocknote_update_syncs_links() -> None:
    repo = FakePlaybookRepository()
    comp = FakeCompositionRepo()
    links = FakeResourceLinkRepo()
    service = _make_service(repo, comp, links)
    ctx = _ctx(uuid4())
    created = asyncio.run(service.create(ctx, PlaybookCreate(name="PB", content=_content())))
    child = uuid4()
    resource = uuid4()
    body = _pill_body(child, resource)
    asyncio.run(service.update(ctx, created.id, PlaybookUpdate(content=_blocknote_content(body))))
    assert comp.last_child_ids == [child]
    assert links.last_links is not None and len(links.last_links) == 1


# --- B5: Render-Endpoint ----------------------------------------------------


class _FakeAcquire:
    """Async-Contextmanager-Stub fuer `pool.acquire()` — liefert eine None-Conn.

    Der Renderer beruehrt die Conn nur fuer Placeholder-Resolver; bei Bodies ohne
    Pills (Text-only) bleibt sie ungenutzt, daher reicht ein No-Op-Handle.
    """

    async def __aenter__(self) -> object:
        return None

    async def __aexit__(self, *args: object) -> None:
        return None


class _FakePool:
    def acquire(self) -> _FakeAcquire:
        return _FakeAcquire()


def _service_with_pool(pool: object) -> tuple[PlaybookService, WorkspaceContext]:
    repo = FakePlaybookRepository()
    comp = PlaybookCompositionService(FakeCompositionRepo())
    links = PlaybookResourceLinkService(FakeResourceLinkRepo())
    return PlaybookService(repo, cast("asyncpg.Pool", pool), comp, links), _ctx(uuid4())


def test_render_plain_body_returns_raw() -> None:
    service, ctx = _service_with_pool(_FakePool())
    created = asyncio.run(
        service.create(ctx, PlaybookCreate(name="Plain", content=_content("Desc")))
    )
    result = asyncio.run(service.render(ctx, created.id))
    assert result.body_rendered == "1. Do it."
    assert result.unresolved == []


def test_render_blocknote_text_expands_to_plain() -> None:
    service, ctx = _service_with_pool(_FakePool())
    import json

    body = json.dumps(
        [
            {"type": "paragraph", "content": [{"type": "text", "text": "Hallo", "styles": {}}]},
            {"type": "paragraph", "content": [{"type": "text", "text": "Welt", "styles": {}}]},
        ]
    )
    created = asyncio.run(
        service.create(ctx, PlaybookCreate(name="BN", content=_blocknote_content(body)))
    )
    result = asyncio.run(service.render(ctx, created.id))
    assert result.body_rendered == "Hallo\n\nWelt"
    assert result.unresolved == []


def test_render_unknown_playbook_raises_404() -> None:
    service, ctx = _service_with_pool(_FakePool())
    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.render(ctx, uuid4()))
    assert exc.value.status_code == 404


def test_blocknote_create_with_cycle_pill_raises_409() -> None:
    repo = FakePlaybookRepository()
    comp = FakeCompositionRepo()
    links = FakeResourceLinkRepo()
    service = _make_service(repo, comp, links)
    ctx = _ctx(uuid4())
    cyclic_child = uuid4()
    comp.cycle_for = {cyclic_child}
    resource = uuid4()
    body = _pill_body(cyclic_child, resource)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            service.create(ctx, PlaybookCreate(name="Cyclic", content=_blocknote_content(body)))
        )
    assert exc.value.status_code == 409
