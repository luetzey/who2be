"""Not-Aus: Ruecknahme automatisch aktivierter Eintraege (ADR-0053 6.4.1, C3b-2a).

Service-Tests gegen echtes Postgres (`WHO2BE_REQUIRE_DB=1`). Kritische
Zusicherungen, je mit Rot-Probe im Review belegt:

- `dry_run` aendert nichts und liefert Anzahl, Stichprobe (<= 5) und
  `hidden_count`.
- Ohne `dry_run` und mit abweichendem `expected_count`: 409
  `memory_batch_count_mismatch` mit `params={count}`, nichts geaendert.
- Die Ruecknahme ist atomar: faellt ein Schritt aus, bleibt alles, wie es war.
  Je Eintrag entsteht ein Ereignis `auto_revoked` (Mensch, before/after).
- Betroffen ist nur aktiv-unbestaetigt mit `auto_activated` im Zeitraum.
- Nutzergedaechtnis anderer Personen (Owner-Entscheidung 3a): ohne
  `include_other_users` nie betroffen; mit nur fuer `admin`, und auch dann nur
  als Zahl (`hidden_count`) — weder Inhalt noch ID in Vorschau oder Ergebnis.
- `viewer` und agent-gebundene Tokens: 403.

Die Router-Seite folgt mit C3b-2b.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest
from pydantic import ValidationError

from who2be_api.core.config import get_settings
from who2be_api.core.errors import ApiError, ApiGateError
from who2be_api.core.security import WorkspaceContext
from who2be_api.repositories import memory_repository
from who2be_api.repositories.memory_repository import PgMemoryRepository
from who2be_api.services.memory_service import MemoryService
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace
from who2be_models import MemoryMode, MemoryStatus, WorkspaceRole
from who2be_models.memory import (
    MemoryOrigin,
    MemoryRevokeAuto,
    MemoryRevokeAutoPreview,
    MemoryRevokeAutoResult,
    MemoryRollback,
)
from who2be_models.tool_policy import AgentToolPolicy

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("migrated_db")]

_NOW = datetime.now(UTC)
_SINCE = _NOW - timedelta(hours=2)


# ------------------------------------------------------------------ Umgebung


@dataclass
class Env:
    pool: asyncpg.Pool
    service: MemoryService
    ws: UUID
    owner: UUID  # admin
    editor: UUID
    viewer: UUID
    agent: UUID
    other_agent: UUID

    def human(self, user: UUID, role: WorkspaceRole) -> WorkspaceContext:
        # aal2: `include_other_users` verlangt admin, admin verlangt MFA.
        return WorkspaceContext(workspace_id=self.ws, user_id=user, role=role, aal="aal2")

    def agent_ctx(self) -> WorkspaceContext:
        return WorkspaceContext(
            workspace_id=self.ws,
            user_id=self.owner,
            role=WorkspaceRole.admin,
            is_api_token=True,
            agent_id=self.agent,
            tool_policy=AgentToolPolicy(memory_mode=MemoryMode.auto),
        )

    async def memory(
        self,
        fact: str,
        *,
        agent: UUID | None = None,
        subject: UUID | None = None,
        status: str = "active",
        origin: str = "user_stated",
        confirmed: bool = False,
        auto_at: datetime | None = _NOW - timedelta(hours=1),
    ) -> UUID:
        """Legt einen Eintrag samt `created`/`auto_activated` an (an der Logik vorbei).

        `auto_at=None`: kein `auto_activated` (z. B. von Hand freigegeben).
        """
        scope = "user" if subject is not None else "agent"
        submitter = agent or self.agent
        memory_id: UUID = await self.pool.fetchval(
            "INSERT INTO agent_memory (workspace_id, agent_id, created_by_agent_id, status, "
            " fact, category, importance, kind, scope, origin, source, subject_user_id, "
            " confirmed_at, confirmed_by, expires_at) "
            "VALUES ($1, $2, $3, $4, $5, 'preference', 6, 'user_fact', $6, $7, 'agent', $8, "
            "        CASE WHEN $9 THEN now() END, CASE WHEN $9 THEN $10::uuid END, "
            "        CASE WHEN NOT $9 THEN now() + interval '30 days' END) "
            "RETURNING id",
            self.ws,
            None if subject is not None else submitter,
            submitter,
            status,
            fact,
            scope,
            origin,
            subject,
            confirmed,
            self.owner,
        )
        await self.pool.execute(
            "INSERT INTO agent_memory_event (workspace_id, memory_id, event, actor_kind, "
            " agent_id, after) VALUES ($1, $2, 'created', 'agent', $3, '{}'::jsonb)",
            self.ws,
            memory_id,
            submitter,
        )
        if auto_at is not None:
            await self.pool.execute(
                "INSERT INTO agent_memory_event (workspace_id, memory_id, event, actor_kind, "
                " agent_id, after, created_at) "
                "VALUES ($1, $2, 'auto_activated', 'system', $3, '{}'::jsonb, $4)",
                self.ws,
                memory_id,
                submitter,
                auto_at,
            )
        return memory_id

    async def statuses(self, *ids: UUID) -> dict[UUID, str]:
        rows = await self.pool.fetch(
            "SELECT id, status FROM agent_memory WHERE id = ANY($1::uuid[])", list(ids)
        )
        return {r["id"]: r["status"] for r in rows}

    async def revoked_events(self) -> int:
        count: int = await self.pool.fetchval(
            "SELECT COUNT(*)::int FROM agent_memory_event "
            "WHERE workspace_id = $1 AND event = 'auto_revoked'",
            self.ws,
        )
        return count


async def _init(conn: asyncpg.Connection) -> None:
    from who2be_api.core.db import init_connection

    await init_connection(conn)


def _run(case: Callable[[Env], Awaitable[Any]]) -> Any:
    owner, editor, viewer = fresh_user_id(), fresh_user_id(), fresh_user_id()
    ws = setup_workspace(owner)

    async def _go() -> Any:
        pool = await asyncpg.create_pool(
            get_settings().database_url, min_size=1, max_size=3, init=_init
        )
        assert pool is not None
        try:
            for user, role in ((editor, "editor"), (viewer, "viewer")):
                await pool.execute(
                    "INSERT INTO workspace_member (workspace_id, user_id, role) "
                    "VALUES ($1, $2, $3)",
                    ws,
                    user,
                    role,
                )
            agents = [
                await pool.fetchval(
                    "INSERT INTO agent (workspace_id, owner_id, name) VALUES ($1, $2, $3) "
                    "RETURNING id",
                    ws,
                    owner,
                    name,
                )
                for name in ("C3b2-Agent", "C3b2-Zweiter")
            ]
            env = Env(
                pool,
                MemoryService(PgMemoryRepository(pool)),
                ws,
                owner,
                editor,
                viewer,
                agents[0],
                agents[1],
            )
            return await case(env)
        finally:
            await pool.close()

    try:
        return asyncio.run(_go())
    finally:
        cleanup_workspaces([owner, editor, viewer])


def _body(**kwargs: Any) -> MemoryRevokeAuto:
    return MemoryRevokeAuto(since=_SINCE, **kwargs)


async def _preview(env: Env, ctx: WorkspaceContext, **kwargs: Any) -> MemoryRevokeAutoPreview:
    result = await env.service.revoke_auto(ctx, _body(dry_run=True, **kwargs))
    assert isinstance(result, MemoryRevokeAutoPreview)
    return result


async def _revoke(env: Env, ctx: WorkspaceContext, **kwargs: Any) -> MemoryRevokeAutoResult:
    result = await env.service.revoke_auto(ctx, _body(**kwargs))
    assert isinstance(result, MemoryRevokeAutoResult)
    return result


# ------------------------------------------------------------------- Auswahl


def test_selection_only_auto_activated_unconfirmed_in_window() -> None:
    async def case(env: Env) -> None:
        hit = await env.memory("Treffer A")
        hit_other_agent = await env.memory("Treffer B", agent=env.other_agent)
        await env.memory("Bestaetigt", confirmed=True)
        await env.memory("Von Hand freigegeben", auto_at=None)
        await env.memory("Schon offen", status="pending")
        await env.memory("Vor dem Zeitraum", auto_at=_NOW - timedelta(days=1))
        editor = env.human(env.editor, WorkspaceRole.editor)

        preview = await _preview(env, editor)
        assert (preview.count, preview.hidden_count) == (2, 0)
        assert {m.id for m in preview.sample} == {hit, hit_other_agent}

        # `until` ist exklusiv: ein Ende vor dem Ereignis schliesst es aus.
        assert (await _preview(env, editor, until=_NOW - timedelta(hours=1, minutes=1))).count == 0
        assert (await _preview(env, editor, agent_id=env.agent)).count == 1
        assert (await _preview(env, editor, origin=[MemoryOrigin.inferred])).count == 0
        assert (await _preview(env, editor, origin=[MemoryOrigin.user_stated])).count == 2

    _run(case)


def test_dry_run_changes_nothing_and_caps_the_sample() -> None:
    async def case(env: Env) -> None:
        ids = [await env.memory(f"Auto-Fakt {i}") for i in range(7)]
        preview = await _preview(env, env.human(env.editor, WorkspaceRole.editor))
        assert preview.count == 7
        assert len(preview.sample) == 5
        assert set((await env.statuses(*ids)).values()) == {"active"}
        assert await env.revoked_events() == 0

    _run(case)


# --------------------------------------------------------------- Ruecknahme


def test_revoke_sets_pending_writes_auto_revoked_and_is_rollbackable() -> None:
    async def case(env: Env) -> None:
        a = await env.memory("Nutzer mag Tee")
        b = await env.memory("Nutzer mag Jazz", agent=env.other_agent)
        untouched = await env.memory("Bestaetigt", confirmed=True)
        editor = env.human(env.editor, WorkspaceRole.editor)

        result = await _revoke(env, editor, expected_count=2)
        assert (result.count, result.hidden_count) == (2, 0)
        assert {r.id for r in result.results} == {a, b}
        assert all(r.ok and r.reason is None for r in result.results)
        assert await env.statuses(a, b, untouched) == {
            a: "pending",
            b: "pending",
            untouched: "active",
        }

        history = await env.service.history(editor, env.agent, a)
        revoked = history[-1]
        assert revoked.event.value == "auto_revoked"
        assert (revoked.actor_kind.value, revoked.actor_id) == ("human", env.editor)
        assert revoked.before is not None and revoked.before["status"] == "active"
        assert revoked.after is not None and revoked.after["status"] == "pending"
        assert await env.revoked_events() == 2
        memory = await env.service._repo.get(env.ws, env.agent, a)
        assert memory is not None and memory.expires_at is not None  # Verfall laeuft weiter

        # Ein zweiter Lauf findet nichts mehr (jetzt `pending`).
        assert (await _preview(env, editor)).count == 0

        # Rollback auf `auto_revoked` stellt den aktiven, unbestaetigten Stand her.
        restored = await env.service.rollback(
            editor, env.agent, a, MemoryRollback(event_id=revoked.id)
        )
        assert restored.status == MemoryStatus.active
        assert restored.confirmed_at is None and restored.expires_at is not None

    _run(case)


def test_count_mismatch_conflicts_and_changes_nothing() -> None:
    async def case(env: Env) -> None:
        ids = [await env.memory(f"Auto-Fakt {i}") for i in range(3)]
        editor = env.human(env.editor, WorkspaceRole.editor)
        for wrong in (2, 4, 0):
            with pytest.raises(ApiError) as exc:
                await _revoke(env, editor, expected_count=wrong)
            assert exc.value.status_code == 409
            assert exc.value.reason == "memory_batch_count_mismatch"
            assert exc.value.params == {"count": 3}
        assert set((await env.statuses(*ids)).values()) == {"active"}
        assert await env.revoked_events() == 0

    _run(case)


def test_revoke_is_atomic_all_or_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Faellt das Schreiben der Historie beim zweiten Eintrag aus, bleibt alles stehen."""
    real = memory_repository._insert_human_event
    calls = {"n": 0}

    async def failing(*args: Any, **kwargs: Any) -> None:
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("simulierter Ausfall")
        await real(*args, **kwargs)

    monkeypatch.setattr(memory_repository, "_insert_human_event", failing)

    async def case(env: Env) -> None:
        ids = [await env.memory(f"Auto-Fakt {i}") for i in range(3)]
        with pytest.raises(RuntimeError, match="simulierter Ausfall"):
            await _revoke(env, env.human(env.editor, WorkspaceRole.editor), expected_count=3)
        assert calls["n"] == 2
        assert set((await env.statuses(*ids)).values()) == {"active"}
        assert await env.revoked_events() == 0

    _run(case)


# ---------------------------------------------- Fremdes Nutzergedaechtnis (3a)


def test_other_users_memory_only_admin_and_only_as_a_number() -> None:
    async def case(env: Env) -> None:
        agent_mem = await env.memory("Agentenfakt")
        mine = await env.memory("Editor mag Tabellen", subject=env.editor)
        theirs = await env.memory("Viewer mag Hoerbuecher", subject=env.viewer)
        editor = env.human(env.editor, WorkspaceRole.editor)
        admin = env.human(env.owner, WorkspaceRole.admin)

        # editor: eigenes Nutzergedaechtnis ja, fremdes gar nicht (auch nicht gezaehlt).
        preview = await _preview(env, editor)
        assert (preview.count, preview.hidden_count) == (2, 0)
        assert {m.id for m in preview.sample} == {agent_mem, mine}
        with pytest.raises(ApiGateError) as gate:
            await _preview(env, editor, include_other_users=True)
        assert gate.value.status == 403 and gate.value.reason == "insufficient_role"

        # admin ohne Schalter: fremdes Nutzergedaechtnis gehoert nicht dazu.
        assert (await _preview(env, admin)).count == 1

        # admin mit Schalter: nur die Anzahl, nie Inhalt oder ID.
        preview = await _preview(env, admin, include_other_users=True)
        assert (preview.count, preview.hidden_count) == (3, 2)
        assert [m.id for m in preview.sample] == [agent_mem]
        dumped = preview.model_dump_json()
        assert str(theirs) not in dumped and "Hoerbuecher" not in dumped
        assert str(mine) not in dumped and "Tabellen" not in dumped

        result = await _revoke(env, admin, include_other_users=True, expected_count=3)
        assert (result.count, result.hidden_count) == (3, 2)
        assert [r.id for r in result.results] == [agent_mem]
        assert str(theirs) not in result.model_dump_json()
        assert set((await env.statuses(agent_mem, mine, theirs)).values()) == {"pending"}

    _run(case)


def test_editor_revoke_leaves_other_users_memory_untouched() -> None:
    async def case(env: Env) -> None:
        mine = await env.memory("Editor mag Tabellen", subject=env.editor)
        theirs = await env.memory("Viewer mag Hoerbuecher", subject=env.viewer)
        result = await _revoke(env, env.human(env.editor, WorkspaceRole.editor), expected_count=1)
        assert [r.id for r in result.results] == [mine]
        assert await env.statuses(mine, theirs) == {mine: "pending", theirs: "active"}

    _run(case)


# ------------------------------------------------------------------- Rechte


def test_viewer_agent_token_and_foreign_agent_are_rejected() -> None:
    async def case(env: Env) -> None:
        mem = await env.memory("Auto-Fakt")
        with pytest.raises(ApiGateError) as gate:
            await _preview(env, env.human(env.viewer, WorkspaceRole.viewer))
        assert gate.value.status == 403 and gate.value.reason == "insufficient_role"
        with pytest.raises(ApiGateError) as gate:
            await _revoke(env, env.agent_ctx(), expected_count=1)
        assert gate.value.status == 403 and gate.value.reason == "missing_capability"
        with pytest.raises(ApiError) as exc:
            await _preview(env, env.human(env.editor, WorkspaceRole.editor), agent_id=uuid4())
        assert exc.value.reason == "agent_not_found"
        assert await env.statuses(mem) == {mem: "active"}

    _run(case)


def test_body_validation() -> None:
    with pytest.raises(ValidationError, match="expected_count"):
        MemoryRevokeAuto(since=_SINCE)
    with pytest.raises(ValidationError, match="Zeitzone"):
        MemoryRevokeAuto(since=datetime(2026, 10, 1), dry_run=True)  # noqa: DTZ001
    with pytest.raises(ValidationError, match="until"):
        MemoryRevokeAuto(since=_SINCE, until=_SINCE, dry_run=True)
    with pytest.raises(ValidationError):
        MemoryRevokeAuto(since=_SINCE, expected_count=-1)
    with pytest.raises(ValidationError):
        MemoryRevokeAuto(since=_SINCE, dry_run=True, origin=[])
    assert MemoryRevokeAuto(since=_SINCE, expected_count=0).expected_count == 0
