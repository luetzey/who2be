"""PUT-Pfad bei offenem Review (Kanban t_1f5dae56, ADR-0020).

Belegt:

- **Review ohne Draft:** steht die hoechste Version in `review` und ist kein
  Draft offen, lehnt der PUT-Pfad (`update`) ab, wie der Auto-Save-Pfad
  (`upsert_draft`). Er legt keine Version an und zieht `current_version` nicht
  nach. Vorher entstand hier still eine `inactive`-Version, die kein Leser
  sieht. Geprueft fuer alle fuenf Arten direkt am Repository.
- **Service:** derselbe 409 wie beim Auto-Save (`reason=review_conflict`),
  der Text nennt den naechsten Schritt. Geprueft fuer zwei Arten.
- **Bestand:** eine `inactive`-Basis ohne Draft erzeugt weiter eine neue
  `inactive`-Version (der Zweig bleibt unveraendert).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

import asyncpg
import pytest

from who2be_api.core.config import get_settings
from who2be_api.core.db import init_connection
from who2be_api.core.errors import ApiError
from who2be_api.core.security import WorkspaceContext
from who2be_api.repositories.external_tool_repository import PgExternalToolRepository
from who2be_api.repositories.persona_repository import PgPersonaRepository
from who2be_api.repositories.playbook_repository import PgPlaybookRepository
from who2be_api.repositories.resource_repository import PgResourceRepository
from who2be_api.repositories.system_prompt_template_repository import (
    PgSystemPromptTemplateRepository,
)
from who2be_api.services.external_tool_service import ExternalToolService
from who2be_api.services.system_prompt_template_service import SystemPromptTemplateService
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace
from who2be_models import (
    ExternalToolContent,
    ExternalToolUpdate,
    PersonaVersionContent,
    PlaybookContent,
    ResourceContent,
    SystemPromptTemplateContent,
    SystemPromptTemplateUpdate,
    WorkspaceRole,
)

KINDS = ["persona", "playbook", "resource", "external_tool", "system_prompt"]

# Versions-Tabelle und Fremdschluessel je Art.
_TABLES = {
    "persona": ("persona_version", "persona_id"),
    "playbook": ("playbook_version", "playbook_id"),
    "resource": ("resource_version", "resource_id"),
    "external_tool": ("external_tool_version", "external_tool_id"),
    "system_prompt": ("system_prompt_template_version", "template_id"),
}
_ENTITY = {
    "persona": "persona",
    "playbook": "playbook",
    "resource": "resource",
    "external_tool": "external_tool",
    "system_prompt": "system_prompt_template",
}


def _make_repo(kind: str, pool: asyncpg.Pool) -> tuple[Any, Callable[[str], Any]]:
    if kind == "persona":
        return PgPersonaRepository(pool), lambda t: PersonaVersionContent(description=t)
    if kind == "playbook":
        return PgPlaybookRepository(pool), lambda t: PlaybookContent(description=t)
    if kind == "resource":
        return PgResourceRepository(pool), lambda t: ResourceContent(description=t)
    if kind == "external_tool":
        return PgExternalToolRepository(pool), lambda t: ExternalToolContent(display_name=t)
    return PgSystemPromptTemplateRepository(pool), lambda t: SystemPromptTemplateContent(body=t)


async def _insert(kind: str, repo: Any, ws: UUID, user: UUID, content: Any) -> Any:
    tag = f"{kind[:2]}-{fresh_user_id().hex[:8]}"
    if kind == "resource":
        return await repo.insert(ws, user, "E", content, "de", slug=tag)
    if kind == "external_tool":
        return await repo.insert(ws, user, "E", content, "de", alias=tag)
    if kind == "system_prompt":
        return await repo.insert(ws, user, "E", tag, content, "de")
    return await repo.insert(ws, user, "E", content, "de")


async def _versions(pool: asyncpg.Pool, kind: str, entity_id: UUID) -> list[tuple[int, str]]:
    table, fk = _TABLES[kind]
    rows = await pool.fetch(
        f"SELECT version, status FROM {table} WHERE {fk} = $1 ORDER BY version", entity_id
    )
    return [(r["version"], r["status"]) for r in rows]


async def _pointer(pool: asyncpg.Pool, kind: str, entity_id: UUID) -> int:
    value = await pool.fetchval(
        f"SELECT current_version FROM {_ENTITY[kind]} WHERE id = $1", entity_id
    )
    assert isinstance(value, int)
    return value


async def _set_status(
    pool: asyncpg.Pool, kind: str, entity_id: UUID, version: int, status: str
) -> None:
    table, fk = _TABLES[kind]
    await pool.execute(
        f"UPDATE {table} SET status = $1 WHERE {fk} = $2 AND version = $3",
        status,
        entity_id,
        version,
    )


async def _active_then_review(pool: asyncpg.Pool, kind: str, ws: UUID, user: UUID) -> Any:
    """v1 aktiv, v2 in Review, kein Draft offen. Gibt `(repo, make, id)` zurueck."""
    repo, make = _make_repo(kind, pool)
    created = await _insert(kind, repo, ws, user, make("eins"))
    await _set_status(pool, kind, created.id, 1, "active")
    await repo.update(ws, user, created.id, None, make("zwei"))
    await _set_status(pool, kind, created.id, 2, "review")
    assert await _versions(pool, kind, created.id) == [(1, "active"), (2, "review")]
    return repo, make, created.id


def _run(ws_user: tuple[UUID, UUID], body: Callable[[asyncpg.Pool], Awaitable[None]]) -> None:
    async def _go() -> None:
        pool = await asyncpg.create_pool(
            get_settings().database_url, min_size=1, max_size=2, init=init_connection
        )
        assert pool is not None
        try:
            await body(pool)
        finally:
            await pool.close()

    asyncio.run(_go())


@pytest.fixture
def workspace(migrated_db: None) -> Any:
    user = fresh_user_id()
    ws = setup_workspace(user)
    yield user, ws
    cleanup_workspaces([user])


@pytest.mark.integration
@pytest.mark.parametrize("kind", KINDS)
def test_put_on_open_review_is_rejected_without_new_version(
    workspace: tuple[UUID, UUID], kind: str
) -> None:
    user, ws = workspace

    async def body(pool: asyncpg.Pool) -> None:
        repo, make, eid = await _active_then_review(pool, kind, ws, user)
        pointer = await _pointer(pool, kind, eid)

        outcome = await repo.update(ws, user, eid, None, make("unsichtbar"))

        assert outcome.conflict == "review_pending"
        assert await _versions(pool, kind, eid) == [(1, "active"), (2, "review")]
        assert await _pointer(pool, kind, eid) == pointer
        # Gleiches Urteil wie der Auto-Save-Pfad.
        draft = await repo.upsert_draft(ws, user, eid, None, make("unsichtbar"))
        assert draft.conflict == "review_pending"

    _run(workspace, body)


@pytest.mark.integration
@pytest.mark.parametrize("kind", KINDS)
def test_put_on_inactive_base_still_creates_inactive_version(
    workspace: tuple[UUID, UUID], kind: str
) -> None:
    """Bestandszweig: Basis weder aktiv noch in Review → neue Version `inactive`."""
    user, ws = workspace

    async def body(pool: asyncpg.Pool) -> None:
        repo, make = _make_repo(kind, pool)
        created = await _insert(kind, repo, ws, user, make("eins"))
        await _set_status(pool, kind, created.id, 1, "inactive")

        outcome = await repo.update(ws, user, created.id, None, make("zwei"))

        assert outcome.conflict is None
        assert await _versions(pool, kind, created.id) == [(1, "inactive"), (2, "inactive")]

    _run(workspace, body)


@pytest.mark.integration
@pytest.mark.parametrize("kind", ["system_prompt", "external_tool"])
def test_service_put_on_open_review_returns_same_409_as_autosave(
    workspace: tuple[UUID, UUID], kind: str
) -> None:
    user, ws = workspace
    ctx = WorkspaceContext(workspace_id=ws, user_id=user, role=WorkspaceRole.editor)

    async def body(pool: asyncpg.Pool) -> None:
        repo, make, eid = await _active_then_review(pool, kind, ws, user)
        service: Any
        update: Any
        if kind == "system_prompt":
            service = SystemPromptTemplateService(repo)
            update = SystemPromptTemplateUpdate(content=make("unsichtbar"))
        else:
            service = ExternalToolService(repo)
            update = ExternalToolUpdate(content=make("unsichtbar"))

        with pytest.raises(ApiError) as put_exc:
            await service.update(ctx, eid, update)
        with pytest.raises(ApiError) as draft_exc:
            await service.update_draft(ctx, eid, update)

        assert put_exc.value.status_code == 409
        assert put_exc.value.reason == "review_conflict"
        assert put_exc.value.reason == draft_exc.value.reason
        assert put_exc.value.detail == draft_exc.value.detail
        # Der Text nennt den naechsten Schritt.
        assert "transition" in str(put_exc.value.detail)
        assert await _versions(pool, kind, eid) == [(1, "active"), (2, "review")]

    _run(workspace, body)
