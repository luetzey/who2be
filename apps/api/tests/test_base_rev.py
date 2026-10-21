"""Konflikt-Token `base_rev` im Speicherkern (ADR-0058 §6.2/§6.3, W1-P2a).

Belegt:

- **Hash-Form:** 16 Hex, kanonisch (Schluesselreihenfolge egal), aendert sich
  mit Inhalt, Name und Sprache.
- **Kontextmanager:** der erwartete Wert gilt nur im Block und ist danach
  zurueckgesetzt, auch nach einer Exception; Tasks sehen nur ihren Wert.
- **Pruefung unter der Sperre:** ein unpassender Wert wird in `_upsert_draft`
  und `_update` abgelehnt, bevor geschrieben wird; ohne Wert bleibt alles
  wie bisher.
- **Nebenlaeufigkeit:** zwei Transaktionen mit demselben `base_rev` auf
  denselben Draft. Mit der Sperre verliert die zweite. Die Rot-Probe nimmt
  `FOR UPDATE` aus dem Lese-SQL: dann gewinnen beide und die erste Aenderung
  ist still weg (der Autosave-Verlust aus §6.3).
- **System-Prompt:** Draft-in-place-Pfad ueber Repository und Service,
  Versionierung bleibt korrekt, `base_rev` wird auch dort geprueft.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

import asyncpg
import pytest

from who2be_api.core.config import get_settings
from who2be_api.core.db import init_connection
from who2be_api.core.errors import ApiError
from who2be_api.core.security import WorkspaceContext
from who2be_api.repositories.persona_repository import PgPersonaRepository
from who2be_api.repositories.system_prompt_template_repository import (
    PgSystemPromptTemplateRepository,
)
from who2be_api.repositories.versioned_repository import (
    BASE_REV_LENGTH,
    BaseRevConflictError,
    check_base_rev,
    compute_base_rev,
    current_expected_base_rev,
    expected_base_rev,
)
from who2be_api.services.system_prompt_template_service import SystemPromptTemplateService
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace
from who2be_models import (
    PersonaVersionContent,
    SystemPromptTemplateContent,
    SystemPromptTemplateUpdate,
    VersionStatus,
    WorkspaceRole,
)

# --- Hash-Form (ohne DB) ------------------------------------------------------


def test_base_rev_is_16_hex_and_canonical() -> None:
    rev = compute_base_rev({"b": 1, "a": [1, "ü"]}, "Name", "de")
    assert re.fullmatch(r"[0-9a-f]{16}", rev)
    assert len(rev) == BASE_REV_LENGTH
    # Schluesselreihenfolge spielt keine Rolle (kanonische JSON-Form).
    assert rev == compute_base_rev({"a": [1, "ü"], "b": 1}, "Name", "de")


def test_base_rev_changes_with_content_name_and_locale() -> None:
    base = compute_base_rev({"body": "x"}, "Name", "de")
    assert compute_base_rev({"body": "y"}, "Name", "de") != base
    assert compute_base_rev({"body": "x"}, "Anderer Name", "de") != base
    assert compute_base_rev({"body": "x"}, "Name", "en") != base


# --- Kontextmanager (ohne DB) -------------------------------------------------


def test_expected_base_rev_is_reset_after_block() -> None:
    assert current_expected_base_rev() is None
    with expected_base_rev("abc"):
        assert current_expected_base_rev() == "abc"
        with expected_base_rev("def"):
            assert current_expected_base_rev() == "def"
        assert current_expected_base_rev() == "abc"
    assert current_expected_base_rev() is None


def test_expected_base_rev_is_reset_after_exception() -> None:
    with pytest.raises(RuntimeError), expected_base_rev("abc"):
        assert current_expected_base_rev() == "abc"
        raise RuntimeError("boom")
    assert current_expected_base_rev() is None


def test_expected_base_rev_is_task_local() -> None:
    async def _reader(seen: list[str | None]) -> None:
        await asyncio.sleep(0)
        seen.append(current_expected_base_rev())

    async def _run() -> list[str | None]:
        seen: list[str | None] = []
        with expected_base_rev("in-task"):
            inside = asyncio.create_task(_reader(seen))
        outside = asyncio.create_task(_reader(seen))
        await asyncio.gather(inside, outside)
        return seen

    # Die Task erbt den Wert zum Erzeugungszeitpunkt, die zweite nicht.
    assert set(asyncio.run(_run())) == {"in-task", None}


def test_check_base_rev_without_expectation_is_noop() -> None:
    check_base_rev(3, {"body": "x"}, "Name", "de")


def test_check_base_rev_mismatch_carries_current_state() -> None:
    current = compute_base_rev({"body": "x"}, "Name", "de")
    with pytest.raises(BaseRevConflictError) as exc, expected_base_rev("0" * 16):
        check_base_rev(3, {"body": "x"}, "Name", "de")
    assert exc.value.current_version == 3
    assert exc.value.current_base_rev == current


# --- Gegen Postgres ------------------------------------------------------------


async def _pool() -> asyncpg.Pool:
    pool = await asyncpg.create_pool(
        get_settings().database_url, min_size=1, max_size=4, init=init_connection
    )
    assert pool is not None
    return pool


def _with_pool(body: Callable[[asyncpg.Pool], Awaitable[None]]) -> None:
    async def _run() -> None:
        pool = await _pool()
        try:
            await body(pool)
        finally:
            await pool.close()

    asyncio.run(_run())


@pytest.fixture
def workspace(migrated_db: None) -> Any:
    user = fresh_user_id()
    ws = setup_workspace(user)
    yield user, ws
    cleanup_workspaces([user])


def _persona(text: str) -> PersonaVersionContent:
    return PersonaVersionContent(description=text)


async def _persona_draft_description(pool: asyncpg.Pool, persona_id: UUID) -> list[tuple[int, str]]:
    rows = await pool.fetch(
        "SELECT version, content->>'description' AS d FROM persona_version "
        "WHERE persona_id = $1 ORDER BY version",
        persona_id,
    )
    return [(r["version"], r["d"]) for r in rows]


@pytest.mark.integration
def test_upsert_draft_checks_base_rev(workspace: tuple[UUID, UUID]) -> None:
    user, ws = workspace

    async def body(pool: asyncpg.Pool) -> None:
        repo = PgPersonaRepository(pool)
        created = await repo.insert(ws, user, "P", _persona("v1"), "de")
        state = await repo.fetch_base_rev(ws, created.id)
        assert state is not None
        version, rev = state
        assert version == 1
        assert rev == compute_base_rev(created.content.model_dump(mode="json"), "P", "de")
        assert await repo.fetch_base_rev(fresh_user_id(), created.id) is None

        # Passender Token: Draft in place, keine neue Version, neuer Token.
        with expected_base_rev(rev):
            outcome = await repo.upsert_draft(ws, user, created.id, None, _persona("v1b"))
        assert outcome.persona is not None
        assert outcome.persona.current_version == 1
        new_state = await repo.fetch_base_rev(ws, created.id)
        assert new_state is not None
        assert new_state[0] == 1
        assert new_state[1] != rev

        # Veralteter Token: abgelehnt, nichts geschrieben.
        with pytest.raises(BaseRevConflictError) as exc, expected_base_rev(rev):
            await repo.upsert_draft(ws, user, created.id, "Neu", _persona("verloren"))
        assert exc.value.current_version == 1
        assert exc.value.current_base_rev == new_state[1]
        assert await _persona_draft_description(pool, created.id) == [(1, "v1b")]
        fetched = await repo.fetch(ws, created.id)
        assert fetched is not None
        assert fetched.name == "P"

        # Ohne Token: Verhalten wie bisher.
        outcome = await repo.upsert_draft(ws, user, created.id, None, _persona("frei"))
        assert outcome.persona is not None
        assert await _persona_draft_description(pool, created.id) == [(1, "frei")]

    _with_pool(body)


@pytest.mark.integration
def test_update_checks_base_rev(workspace: tuple[UUID, UUID]) -> None:
    user, ws = workspace

    async def body(pool: asyncpg.Pool) -> None:
        repo = PgPersonaRepository(pool)
        created = await repo.insert(ws, user, "P", _persona("v1"), "de")
        await pool.execute(
            "UPDATE persona_version SET status = 'active' WHERE persona_id = $1",
            created.id,
        )
        state = await repo.fetch_base_rev(ws, created.id)
        assert state is not None
        _, rev = state

        with pytest.raises(BaseRevConflictError), expected_base_rev("f" * 16):
            await repo.update(ws, user, created.id, None, _persona("v2"))
        assert await _persona_draft_description(pool, created.id) == [(1, "v1")]

        with expected_base_rev(rev):
            outcome = await repo.update(ws, user, created.id, None, _persona("v2"))
        assert outcome.persona is not None
        assert outcome.persona.current_version == 2
        assert outcome.persona.current_status == VersionStatus.draft
        # Schreibziel ist jetzt der neue Draft v2.
        after = await repo.fetch_base_rev(ws, created.id)
        assert after is not None
        assert after[0] == 2

    _with_pool(body)


def _without_row_lock(sql: str) -> str:
    """Rot-Probe: dasselbe Lese-SQL ohne Zeilensperre."""
    assert " FOR UPDATE OF e" in sql
    return sql.replace(" FOR UPDATE OF e", "")


async def _race(pool: asyncpg.Pool, ws: UUID, user: UUID, *, with_lock: bool) -> dict[str, Any]:
    """Zwei Autosaves mit demselben `base_rev` auf denselben Draft.

    A prueft zuerst und haelt dann an (Sperre gehalten, noch nichts
    geschrieben). B startet mit demselben Token. Erst wenn B auf A wartet (mit
    Sperre) bzw. fertig ist (ohne Sperre), laeuft A weiter.
    """
    repo = PgPersonaRepository(pool)
    created = await repo.insert(ws, user, "P", _persona("start"), "de")
    state = await repo.fetch_base_rev(ws, created.id)
    assert state is not None
    rev = state[1]

    if not with_lock:
        original_sql = repo._current_version_sql
        repo._current_version_sql = lambda: _without_row_lock(original_sql())  # type: ignore[method-assign]

    a_checked = asyncio.Event()
    release_a = asyncio.Event()
    a_pid: list[int] = []
    original_check = repo._check_base_rev_locked

    async def gated(conn: asyncpg.Connection, workspace_id: UUID, entity_id: UUID) -> None:
        await original_check(conn, workspace_id, entity_id)
        task = asyncio.current_task()
        if task is not None and task.get_name() == "A":
            a_pid.append(conn.get_server_pid())
            a_checked.set()
            await release_a.wait()

    repo._check_base_rev_locked = gated  # type: ignore[method-assign]

    async def write(text: str) -> str:
        with expected_base_rev(rev):
            try:
                await repo.upsert_draft(ws, user, created.id, None, _persona(text))
            except BaseRevConflictError:
                return "conflict"
        return "ok"

    task_a = asyncio.create_task(write("A"), name="A")
    await asyncio.wait_for(a_checked.wait(), timeout=10)
    task_b = asyncio.create_task(write("B"), name="B")

    # Warten, bis B von A blockiert wird oder (ohne Sperre) schon fertig ist.
    async def b_waits_or_done() -> None:
        while not task_b.done():
            blocked = await pool.fetchval(
                "SELECT count(*) FROM pg_stat_activity WHERE $1 = ANY(pg_blocking_pids(pid))",
                a_pid[0],
            )
            if blocked:
                return
            await asyncio.sleep(0.02)

    await asyncio.wait_for(b_waits_or_done(), timeout=10)
    b_blocked = not task_b.done()
    release_a.set()
    result_a, result_b = await asyncio.gather(task_a, task_b)
    return {
        "a": result_a,
        "b": result_b,
        "b_blocked": b_blocked,
        "rows": await _persona_draft_description(pool, created.id),
    }


@pytest.mark.integration
def test_concurrent_writers_second_loses(workspace: tuple[UUID, UUID]) -> None:
    user, ws = workspace
    out: dict[str, Any] = {}

    async def body(pool: asyncpg.Pool) -> None:
        out.update(await _race(pool, ws, user, with_lock=True))

    _with_pool(body)
    assert out["b_blocked"] is True
    assert (out["a"], out["b"]) == ("ok", "conflict")
    assert out["rows"] == [(1, "A")]


@pytest.mark.integration
def test_concurrent_writers_red_probe_without_lock(workspace: tuple[UUID, UUID]) -> None:
    """Rot-Probe: ohne `FOR UPDATE` pruefen beide gegen den alten Stand.

    Beide Schreiber kommen durch, B's Aenderung ist danach still weg. Genau
    diese Luecke schliesst die Pruefung unter der Sperre.
    """
    user, ws = workspace
    out: dict[str, Any] = {}

    async def body(pool: asyncpg.Pool) -> None:
        out.update(await _race(pool, ws, user, with_lock=False))

    _with_pool(body)
    assert out["b_blocked"] is False
    assert (out["a"], out["b"]) == ("ok", "ok")
    assert out["rows"] == [(1, "A")]


# --- System-Prompt: Draft-in-place-Pfad ---------------------------------------


def _sp(body: str) -> SystemPromptTemplateContent:
    return SystemPromptTemplateContent(body=body)


async def _sp_versions(pool: asyncpg.Pool, template_id: UUID) -> list[tuple[int, str, str]]:
    rows = await pool.fetch(
        "SELECT version, status, content->>'body' AS b FROM system_prompt_template_version "
        "WHERE template_id = $1 ORDER BY version",
        template_id,
    )
    return [(r["version"], r["status"], r["b"]) for r in rows]


@pytest.mark.integration
def test_system_prompt_draft_in_place(workspace: tuple[UUID, UUID]) -> None:
    user, ws = workspace

    async def body(pool: asyncpg.Pool) -> None:
        repo = PgSystemPromptTemplateRepository(pool)
        service = SystemPromptTemplateService(repo)
        ctx = WorkspaceContext(workspace_id=ws, user_id=user, role=WorkspaceRole.editor)
        slug = f"bt-{user.hex[:8]}"
        created = await repo.insert(ws, user, "T", slug, _sp("eins"), "de")

        # Offener Draft v1: in place, keine neue Version (PUT wuerde 409 geben).
        updated = await service.update_draft(
            ctx, created.id, SystemPromptTemplateUpdate(name="T2", content=_sp("zwei"))
        )
        assert updated.current_version == 1
        assert updated.name == "T2"
        assert updated.current_status == VersionStatus.draft
        assert updated.has_pending_draft is True
        assert await _sp_versions(pool, created.id) == [(1, "draft", "zwei")]
        fetched = await service.get(ctx, created.id)
        assert fetched.content.body == "zwei"
        assert fetched.current_version == 1

        # Aktiv: Draft-Pfad legt v2 als Draft an, v1 bleibt aktiv.
        await pool.execute(
            "UPDATE system_prompt_template_version SET status = 'active' WHERE template_id = $1",
            created.id,
        )
        state = await repo.fetch_base_rev(ws, created.id)
        assert state is not None
        assert state[0] == 1
        with expected_base_rev(state[1]):
            v2 = await service.update_draft(
                ctx, created.id, SystemPromptTemplateUpdate(content=_sp("drei"))
            )
        assert v2.current_version == 2
        assert await _sp_versions(pool, created.id) == [
            (1, "active", "zwei"),
            (2, "draft", "drei"),
        ]

        # Weiterer Autosave in v2 in place; veralteter Token wird abgelehnt.
        with pytest.raises(BaseRevConflictError) as exc, expected_base_rev(state[1]):
            await service.update_draft(
                ctx, created.id, SystemPromptTemplateUpdate(content=_sp("verloren"))
            )
        assert exc.value.current_version == 2
        v2b = await service.update_draft(
            ctx, created.id, SystemPromptTemplateUpdate(content=_sp("vier"))
        )
        assert v2b.current_version == 2
        assert await _sp_versions(pool, created.id) == [
            (1, "active", "zwei"),
            (2, "draft", "vier"),
        ]

        # PUT-Pfad bleibt bei offenem Draft bei 409 draft_conflict.
        with pytest.raises(ApiError) as put_exc:
            await service.update(ctx, created.id, SystemPromptTemplateUpdate(content=_sp("x")))
        assert put_exc.value.status_code == 409

        # Review ohne offenen Draft: 409 review_conflict.
        await pool.execute(
            "UPDATE system_prompt_template_version SET status = 'review' "
            "WHERE template_id = $1 AND version = 2",
            created.id,
        )
        with pytest.raises(ApiError) as review_exc:
            await service.update_draft(
                ctx, created.id, SystemPromptTemplateUpdate(content=_sp("y"))
            )
        assert review_exc.value.status_code == 409
        assert await _sp_versions(pool, created.id) == [
            (1, "active", "zwei"),
            (2, "review", "vier"),
        ]

        # Fremder Workspace: 404, kein Schreiben.
        other = WorkspaceContext(
            workspace_id=fresh_user_id(), user_id=user, role=WorkspaceRole.editor
        )
        with pytest.raises(ApiError) as nf_exc:
            await service.update_draft(
                other, created.id, SystemPromptTemplateUpdate(content=_sp("z"))
            )
        assert nf_exc.value.status_code == 404

    _with_pool(body)


@pytest.mark.integration
def test_system_prompt_update_checks_base_rev(workspace: tuple[UUID, UUID]) -> None:
    user, ws = workspace

    async def body(pool: asyncpg.Pool) -> None:
        repo = PgSystemPromptTemplateRepository(pool)
        created = await repo.insert(ws, user, "T", f"bu-{user.hex[:8]}", _sp("eins"), "de")
        await pool.execute(
            "UPDATE system_prompt_template_version SET status = 'active' WHERE template_id = $1",
            created.id,
        )
        with pytest.raises(BaseRevConflictError), expected_base_rev("0" * 16):
            await repo.update(ws, user, created.id, None, _sp("zwei"))
        assert await _sp_versions(pool, created.id) == [(1, "active", "eins")]
        state = await repo.fetch_base_rev(ws, created.id)
        assert state is not None
        with expected_base_rev(state[1]):
            outcome = await repo.update(ws, user, created.id, None, _sp("zwei"))
        assert outcome.template is not None
        assert outcome.template.current_version == 2
        assert await repo.fetch_base_rev(fresh_user_id(), created.id) is None

    _with_pool(body)
