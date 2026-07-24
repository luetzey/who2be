"""Unit-Tests fuer `PersonaService` mit einem In-Memory-Fake-Repository."""

import asyncio
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import asyncpg
import pytest
from fastapi import HTTPException

from who2be_api.core.security import WorkspaceContext
from who2be_api.repositories.persona_repository import PersonaListCounts, PersonaUpdateOutcome
from who2be_api.services.persona_service import PersonaService
from who2be_models import (
    AgentToolPolicy,
    PersonaContent,
    PersonaCreate,
    PersonaMode,
    PersonaRead,
    PersonaUpdate,
    PersonaVersionContent,
    PersonaVersionRead,
    ResourceBlock,
    SkillRef,
    VersionStatus,
    WorkspaceRole,
)


def _content(description: str = "Tester") -> PersonaVersionContent:
    return PersonaVersionContent(description=description, system_prompt="Be helpful.")


def _ctx(
    workspace_id: UUID,
    user_id: UUID | None = None,
    is_api_token: bool = False,
    tool_policy: AgentToolPolicy | None = None,
    agent_id: UUID | None = None,
) -> WorkspaceContext:
    return WorkspaceContext(
        workspace_id=workspace_id,
        user_id=user_id or uuid4(),
        role=WorkspaceRole.admin,
        is_api_token=is_api_token,
        tool_policy=tool_policy,
        agent_id=agent_id,
    )


class FakePersonaRepository:
    """In-Memory-Stub von `PersonaRepository`."""

    def __init__(self) -> None:
        self._personas: dict[UUID, PersonaRead] = {}
        self._versions: dict[UUID, list[PersonaVersionRead]] = {}
        self.last_active_only: bool | None = None
        # Card-Pill-Zaehler pro Persona-ID (vom Test gesetzt); ohne Eintrag
        # bleibt das Read auf den Defaults (0).
        self.counts: dict[UUID, PersonaListCounts] = {}

    async def insert(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        name: str,
        content: PersonaVersionContent,
        locale: str,
    ) -> PersonaRead:
        now = datetime.now(UTC)
        persona = PersonaRead(
            id=uuid4(),
            workspace_id=workspace_id,
            owner_id=owner_id,
            name=name,
            current_version=1,
            locale=locale,
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
        locale: str | None = None,
        restrict_ids: list[UUID] | None = None,
    ) -> list[PersonaRead]:
        self.last_active_only = active_only
        own = sorted(
            (p for p in self._personas.values() if p.workspace_id == workspace_id),
            key=lambda p: (p.created_at, p.id),
            reverse=True,
        )
        if active_only:
            own = [p for p in own if p.current_status == VersionStatus.active]
        if restrict_ids is not None:
            own = [p for p in own if p.id in set(restrict_ids)]
        if after is not None:
            own = [p for p in own if (p.created_at, p.id) < after]
        return own[:limit]

    async def list_counts(
        self, workspace_id: UUID, persona_ids: list[UUID]
    ) -> dict[UUID, PersonaListCounts]:
        return {pid: self.counts[pid] for pid in persona_ids if pid in self.counts}

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
        new_locale: str | None = None,
    ) -> PersonaUpdateOutcome:
        persona = self._personas.get(persona_id)
        if persona is None or persona.workspace_id != workspace_id:
            return PersonaUpdateOutcome(persona=None)
        if any(v.status == VersionStatus.draft for v in self._versions[persona_id]):
            return PersonaUpdateOutcome(persona=None, conflict="draft_exists")
        if new_locale is not None:
            persona = persona.model_copy(update={"locale": new_locale})
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

    async def restore_version(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        persona_id: UUID,
        content: PersonaVersionContent,
    ) -> PersonaUpdateOutcome:
        persona = self._personas.get(persona_id)
        if persona is None or persona.workspace_id != workspace_id:
            return PersonaUpdateOutcome(persona=None)
        if any(v.status == VersionStatus.draft for v in self._versions[persona_id]):
            return PersonaUpdateOutcome(persona=None, conflict="draft_exists")
        version = persona.current_version + 1
        updated = persona.model_copy(
            update={
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

    async def upsert_draft(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        persona_id: UUID,
        name: str | None,
        content: PersonaVersionContent,
        new_locale: str | None = None,
    ) -> PersonaUpdateOutcome:
        persona = self._personas.get(persona_id)
        if persona is None or persona.workspace_id != workspace_id:
            return PersonaUpdateOutcome(persona=None)
        if new_locale is not None:
            persona = self._personas[persona_id] = persona.model_copy(update={"locale": new_locale})
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

    async def delete(self, workspace_id: UUID, persona_id: UUID) -> bool:
        persona = self._personas.get(persona_id)
        if persona is None or persona.workspace_id != workspace_id:
            return False
        del self._personas[persona_id]
        return True

    async def is_managed(self, workspace_id: UUID, entity_id: UUID) -> bool:
        persona = self._personas.get(entity_id)
        return persona is not None and persona.is_managed


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


def test_list_enriches_playbook_and_agent_counts() -> None:
    """List-Card-Pills: `list_all` joint die Batch-Aggregat-Zaehler in die Reads.

    Persona "A" wird von 2 Agenten genutzt und verlinkt 3 Playbooks; "B" hat
    keinen Eintrag im Aggregat und bleibt auf den Defaults (0/0).
    """
    repo = FakePersonaRepository()
    service = PersonaService(repo)
    ctx = _ctx(uuid4())
    a = asyncio.run(service.create(ctx, PersonaCreate(name="A", content=_content())))
    b = asyncio.run(service.create(ctx, PersonaCreate(name="B", content=_content())))
    repo.counts[a.id] = PersonaListCounts(playbook_count=3, agent_count=2)
    items, _ = asyncio.run(service.list_all(ctx, 100, None))
    by_id = {p.id: p for p in items}
    assert by_id[a.id].playbook_count == 3
    assert by_id[a.id].agent_count == 2
    assert by_id[b.id].playbook_count == 0
    assert by_id[b.id].agent_count == 0


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


def test_agent_with_persona_write_sees_drafts() -> None:
    """Editor-/Meta-Agent (persona_write): Reads zeigen die Current-Version
    inkl. Draft; ein Konsum-Agent ohne persona_write bleibt auf `active`."""
    repo = FakePersonaRepository()
    service = PersonaService(repo)
    ws = uuid4()
    user = uuid4()
    web_ctx = _ctx(ws, user_id=user)
    draft = asyncio.run(service.create(web_ctx, PersonaCreate(name="D", content=_content())))
    active = asyncio.run(service.create(web_ctx, PersonaCreate(name="A", content=_content())))
    repo.promote_current_to_active(active.id)

    editor = AgentToolPolicy(persona_write=True)
    editor_ctx = _ctx(ws, user_id=user, is_api_token=True, tool_policy=editor, agent_id=uuid4())
    items, _ = asyncio.run(service.list_all(editor_ctx, 100, None))
    assert {p.id for p in items} == {draft.id, active.id}
    assert repo.last_active_only is False
    assert asyncio.run(service.get(editor_ctx, draft.id)).id == draft.id

    consumer = AgentToolPolicy(persona_write=False)
    consumer_ctx = _ctx(ws, user_id=user, is_api_token=True, tool_policy=consumer, agent_id=uuid4())
    items2, _ = asyncio.run(service.list_all(consumer_ctx, 100, None))
    assert [p.id for p in items2] == [active.id]
    assert repo.last_active_only is True


# --- Track F: Render-Pfad (Persona-Pills + Skills-Tabelle) -------------------


class _FakeAcquire:
    """Async-Contextmanager-Stub fuer `pool.acquire()` — liefert eine None-Conn.

    Fuer text-only Profil-Bloecke (ohne Katalog-Pills) beruehrt der Renderer die
    Conn nicht; ein No-Op-Handle reicht.
    """

    async def __aenter__(self) -> object:
        return None

    async def __aexit__(self, *args: object) -> None:
        return None


class _FakePool:
    def acquire(self) -> _FakeAcquire:
        return _FakeAcquire()


def _service_with_pool() -> tuple[PersonaService, WorkspaceContext]:
    repo = FakePersonaRepository()
    pool = cast("asyncpg.Pool", _FakePool())
    return PersonaService(repo, pool), _ctx(uuid4())


def _profile_block(text: str) -> ResourceBlock:
    return ResourceBlock.model_validate(
        {
            "id": "b1",
            "type": "paragraph",
            "content": [{"type": "text", "text": text, "styles": {}}],
        }
    )


def test_render_profile_body_text_expands_to_plain() -> None:
    service, ctx = _service_with_pool()
    content = PersonaVersionContent(
        description="Coach",
        content=PersonaContent(blocks=[_profile_block("Hallo"), _profile_block("Welt")]),
    )
    created = asyncio.run(service.create(ctx, PersonaCreate(name="Coach", content=content)))

    result = asyncio.run(service.render(ctx, created.id))

    assert result.body_rendered == "Hallo\n\nWelt"
    assert result.unresolved == []


def test_render_skills_disabled_by_default_not_appended() -> None:
    # Coming Soon (ADR-0026): Skills-Tabelle wird ohne aktiviertes Flag nicht
    # an den Briefing-Body angehaengt.
    service, ctx = _service_with_pool()
    content = PersonaVersionContent(
        description="Coach",
        content=PersonaContent(blocks=[_profile_block("Profil-Text")]),
        skills=[
            SkillRef(name="Aktives Zuhören", note="paraphrasiert vor jeder Antwort"),
            SkillRef(name="Refactoring"),
        ],
    )
    created = asyncio.run(service.create(ctx, PersonaCreate(name="Coach", content=content)))

    result = asyncio.run(service.render(ctx, created.id))

    assert result.body_rendered == "Profil-Text"
    assert "## Skills" not in result.body_rendered


def test_render_appends_skills_table_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    # Flag lokal aktivieren — testet die Render-Logik, die bei Reaktivierung greift.
    monkeypatch.setattr("who2be_api.services.placeholders._core.SKILLS_ENABLED", True)
    service, ctx = _service_with_pool()
    content = PersonaVersionContent(
        description="Coach",
        content=PersonaContent(blocks=[_profile_block("Profil-Text")]),
        skills=[
            SkillRef(name="Aktives Zuhören", note="paraphrasiert vor jeder Antwort"),
            SkillRef(name="Refactoring"),
        ],
    )
    created = asyncio.run(service.create(ctx, PersonaCreate(name="Coach", content=content)))

    result = asyncio.run(service.render(ctx, created.id))

    assert "Profil-Text" in result.body_rendered
    assert "## Skills" in result.body_rendered
    assert "| Skill | Hinweis |" in result.body_rendered
    assert "| Aktives Zuhören | paraphrasiert vor jeder Antwort |" in result.body_rendered
    assert "| Refactoring |  |" in result.body_rendered


def test_render_empty_profile_and_no_skills_is_empty() -> None:
    service, ctx = _service_with_pool()
    created = asyncio.run(
        service.create(ctx, PersonaCreate(name="Leer", content=PersonaVersionContent()))
    )

    result = asyncio.run(service.render(ctx, created.id))

    assert result.body_rendered == ""
    assert result.unresolved == []


def test_render_skills_only_when_body_empty_and_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("who2be_api.services.placeholders._core.SKILLS_ENABLED", True)
    service, ctx = _service_with_pool()
    content = PersonaVersionContent(skills=[SkillRef(name="Python", note="fortgeschritten")])
    created = asyncio.run(service.create(ctx, PersonaCreate(name="Skill", content=content)))

    result = asyncio.run(service.render(ctx, created.id))

    # Ohne Profil-Body beginnt der Output direkt mit der Skills-Sektion (kein
    # fuehrender Doppel-Newline).
    assert result.body_rendered.startswith("## Skills")
    assert "| Python | fortgeschritten |" in result.body_rendered


def test_render_unknown_persona_raises_404() -> None:
    service, ctx = _service_with_pool()
    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.render(ctx, uuid4()))
    assert exc.value.status_code == 404


# --- WP-F: Modus-Auswahl im Render-Pfad (`render(mode=…)`) -------------------


def _mode_persona_content(modes: "list[PersonaMode]") -> PersonaVersionContent:
    return PersonaVersionContent(
        description="Coach",
        content=PersonaContent(blocks=[_profile_block("Basis-Profil")]),
        modes=modes,
    )


def test_render_mode_appends_identity_add() -> None:
    service, ctx = _service_with_pool()
    content = _mode_persona_content(
        [PersonaMode(name="Sparring", identity_add=[_profile_block("Du bist provokant")])]
    )
    created = asyncio.run(service.create(ctx, PersonaCreate(name="Coach", content=content)))

    result = asyncio.run(service.render(ctx, created.id, mode="Sparring"))

    assert result.mode == "Sparring"
    assert result.body_rendered.startswith("Basis-Profil")
    assert "## Aktiver Modus: Sparring" in result.body_rendered
    assert "**Identity-Ergaenzung:** Du bist provokant" in result.body_rendered


def test_render_mode_output_style_override_marked_as_replacement() -> None:
    service, ctx = _service_with_pool()
    content = _mode_persona_content(
        [
            PersonaMode(
                name="Kurzform",
                output_style_override=[_profile_block("Max. drei Saetze")],
            )
        ]
    )
    created = asyncio.run(service.create(ctx, PersonaCreate(name="Coach", content=content)))

    result = asyncio.run(service.render(ctx, created.id, mode="Kurzform"))

    assert "**Output-Stil:** Max. drei Saetze" in result.body_rendered
    # Die Anwendungszeile macht die Ersetzungs-Semantik explizit.
    assert "ERSETZT den Basis-Output-Stil" in result.body_rendered


def test_render_mode_includes_anti_patterns() -> None:
    service, ctx = _service_with_pool()
    content = _mode_persona_content(
        [PersonaMode(name="Review", anti_patterns=[_profile_block("Keine Lobhudelei")])]
    )
    created = asyncio.run(service.create(ctx, PersonaCreate(name="Coach", content=content)))

    result = asyncio.run(service.render(ctx, created.id, mode="Review"))

    assert "**Anti-Patterns:** Keine Lobhudelei" in result.body_rendered


def test_render_mode_default_gets_marker() -> None:
    service, ctx = _service_with_pool()
    content = _mode_persona_content(
        [
            PersonaMode(name="Standard", is_default=True, trigger="alltag"),
            PersonaMode(name="Deep-Dive"),
        ]
    )
    created = asyncio.run(service.create(ctx, PersonaCreate(name="Coach", content=content)))

    result = asyncio.run(service.render(ctx, created.id, mode="Standard"))

    assert "## Aktiver Modus: Standard (Default)" in result.body_rendered
    assert "**Trigger:** alltag" in result.body_rendered


def test_render_mode_name_matches_case_insensitively() -> None:
    service, ctx = _service_with_pool()
    content = _mode_persona_content([PersonaMode(name="Sparring")])
    created = asyncio.run(service.create(ctx, PersonaCreate(name="Coach", content=content)))

    result = asyncio.run(service.render(ctx, created.id, mode="sPaRrInG"))

    # Kanonischer Name aus dem Content, nicht die Eingabe-Schreibweise.
    assert result.mode == "Sparring"
    assert "## Aktiver Modus: Sparring" in result.body_rendered


def test_render_unknown_mode_raises_422_with_available_modes() -> None:
    service, ctx = _service_with_pool()
    content = _mode_persona_content([PersonaMode(name="Sparring"), PersonaMode(name="Kurzform")])
    created = asyncio.run(service.create(ctx, PersonaCreate(name="Coach", content=content)))

    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.render(ctx, created.id, mode="Ghost"))

    assert exc.value.status_code == 422
    assert "Ghost" in str(exc.value.detail)
    assert "Sparring" in str(exc.value.detail)
    assert "Kurzform" in str(exc.value.detail)


def test_render_mode_on_persona_without_modes_raises_422() -> None:
    service, ctx = _service_with_pool()
    content = PersonaVersionContent(
        description="Coach", content=PersonaContent(blocks=[_profile_block("Basis-Profil")])
    )
    created = asyncio.run(service.create(ctx, PersonaCreate(name="Coach", content=content)))

    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.render(ctx, created.id, mode="Sparring"))

    assert exc.value.status_code == 422
    assert "keine" in str(exc.value.detail)


def test_render_without_mode_param_stays_unchanged() -> None:
    service, ctx = _service_with_pool()
    content = _mode_persona_content(
        [PersonaMode(name="Sparring", identity_add=[_profile_block("Provokant")])]
    )
    created = asyncio.run(service.create(ctx, PersonaCreate(name="Coach", content=content)))

    result = asyncio.run(service.render(ctx, created.id))

    assert result.body_rendered == "Basis-Profil"
    assert result.mode is None
    assert "Aktiver Modus" not in result.body_rendered
