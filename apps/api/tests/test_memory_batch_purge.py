"""Stapel und Mitglieder-Purge, Service-Schicht (ADR-0053 6.4.1, C3c-2a).

Service-Tests gegen echtes Postgres (`WHO2BE_REQUIRE_DB=1`). Kritische
Zusicherungen, je mit Rot-Probe im Review belegt:

- Stapel: `ids` (hoechstens 100) ODER `filter`; im Filter-Modus ist
  `expected_count` Pflicht, eine abweichende Trefferzahl ergibt 409
  `memory_batch_count_mismatch` mit `params={count}` und aendert nichts.
- Je Eintrag dieselbe Pruefung wie die Einzelaktion; Teilerfolg moeglich,
  ein Ergebnis je Eintrag in der Reihenfolge der Auswahl.
- `approve` auf einen zurueckgehaltenen Eintrag ergibt `memory_held`.
- Fremdes Nutzergedaechtnis ist je Eintrag `memory_not_found`, auch fuer
  `admin` (Owner-Entscheidung 3a) — und bleibt unveraendert.
- `viewer` mit Agentengedaechtnis: 403 auf den ganzen Aufruf, nichts geaendert.
- Purge nur `admin`, Antwort nur die Anzahl, inhaltsfreie `audit_log`-Zeile
  `memory.user_purged`; anderes Gedaechtnis bleibt stehen.

Die Router-Seite folgt mit C3c-2b.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest
from pydantic import ValidationError

from who2be_api.core.config import get_settings
from who2be_api.core.errors import ApiError, ApiGateError
from who2be_api.core.security import WorkspaceContext
from who2be_api.repositories.memory_repository import PgMemoryRepository
from who2be_api.services.memory_service import MemoryService
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace
from who2be_models import MemoryMode, MemoryTriage, MemoryTriageAction, WorkspaceRole
from who2be_models.memory import (
    MEMORY_BATCH_MAX_IDS,
    MemoryBatchAction,
    MemoryBatchRequest,
    MemoryFilter,
    MemoryScope,
    MemoryStatus,
)
from who2be_models.tool_policy import AgentToolPolicy

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("migrated_db")]


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

    def human(self, user: UUID, role: WorkspaceRole, aal: str = "aal2") -> WorkspaceContext:
        return WorkspaceContext(workspace_id=self.ws, user_id=user, role=role, aal=aal)

    @property
    def as_admin(self) -> WorkspaceContext:
        return self.human(self.owner, WorkspaceRole.admin)

    @property
    def as_editor(self) -> WorkspaceContext:
        return self.human(self.editor, WorkspaceRole.editor)

    @property
    def as_viewer(self) -> WorkspaceContext:
        return self.human(self.viewer, WorkspaceRole.viewer)

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
        subject: UUID | None = None,
        status: str = "pending",
        kind: str = "user_fact",
        category: str = "preference",
        origin: str = "user_stated",
        confirmed: bool = False,
        workspace: UUID | None = None,
        agent: UUID | None = None,
    ) -> UUID:
        """Legt einen Eintrag direkt an (an der Logik vorbei)."""
        submitter = agent or self.agent
        memory_id: UUID = await self.pool.fetchval(
            "INSERT INTO agent_memory (workspace_id, agent_id, created_by_agent_id, status, "
            " fact, category, importance, kind, scope, origin, subject_user_id, "
            " confirmed_at, confirmed_by) "
            "VALUES ($1, $2, $3, $4, $5, $6, 6, $7, $8, $9, $10, "
            "        CASE WHEN $11 THEN now() END, CASE WHEN $11 THEN $12::uuid END) "
            "RETURNING id",
            workspace or self.ws,
            None if subject is not None else submitter,
            submitter,
            status,
            fact,
            category,
            kind,
            "user" if subject is not None else "agent",
            origin,
            subject,
            confirmed and status == "active",
            self.owner,
        )
        return memory_id

    async def state(self, memory_id: UUID) -> tuple[str, bool] | None:
        """`(status, bestaetigt)` oder `None`, wenn geloescht."""
        row = await self.pool.fetchrow(
            "SELECT status, confirmed_at IS NOT NULL AS confirmed FROM agent_memory WHERE id = $1",
            memory_id,
        )
        return (row["status"], row["confirmed"]) if row is not None else None

    async def batch(
        self, ctx: WorkspaceContext, action: MemoryBatchAction, **body: Any
    ) -> dict[UUID, tuple[bool, str | None]]:
        result = await self.service.batch(ctx, MemoryBatchRequest(action=action, **body))
        return {r.id: (r.ok, r.reason) for r in result.results}


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
            agent = await pool.fetchval(
                "INSERT INTO agent (workspace_id, owner_id, name) VALUES ($1, $2, 'C3c2-Agent') "
                "RETURNING id",
                ws,
                owner,
            )
            env = Env(
                pool, MemoryService(PgMemoryRepository(pool)), ws, owner, editor, viewer, agent
            )
            return await case(env)
        finally:
            await pool.close()

    try:
        return asyncio.run(_go())
    finally:
        cleanup_workspaces([owner, editor, viewer])


# ------------------------------------------------------------------ Modell


def test_request_needs_ids_xor_filter_and_count_in_filter_mode() -> None:
    one = [uuid4()]
    with pytest.raises(ValidationError, match="Genau eines"):
        MemoryBatchRequest(action=MemoryBatchAction.approve)
    with pytest.raises(ValidationError, match="Genau eines"):
        MemoryBatchRequest(
            action=MemoryBatchAction.approve, ids=one, filter=MemoryFilter(), expected_count=1
        )
    with pytest.raises(ValidationError, match="expected_count"):
        MemoryBatchRequest(action=MemoryBatchAction.approve, filter=MemoryFilter())
    with pytest.raises(ValidationError):
        MemoryBatchRequest(action=MemoryBatchAction.approve, ids=[])
    too_many = [uuid4() for _ in range(MEMORY_BATCH_MAX_IDS + 1)]
    with pytest.raises(ValidationError):
        MemoryBatchRequest(action=MemoryBatchAction.approve, ids=too_many)
    with pytest.raises(ValidationError):
        MemoryBatchRequest.model_validate({"action": "archive", "ids": [str(one[0])]})
    # Grenze genau 100 ist erlaubt; Dubletten fallen reihenfolgetreu weg.
    at_limit = [uuid4() for _ in range(MEMORY_BATCH_MAX_IDS)]
    assert MemoryBatchRequest(action=MemoryBatchAction.delete, ids=at_limit).ids == at_limit
    a, b = uuid4(), uuid4()
    deduped = MemoryBatchRequest(action=MemoryBatchAction.delete, ids=[a, b, a])
    assert deduped.ids == [a, b]


# ------------------------------------------------------------------- Stapel


def test_approve_by_ids_partial_success_one_result_per_entry() -> None:
    async def case(env: Env) -> None:
        agent_ok = await env.memory("Agent: offener Fakt")
        held_external = await env.memory("Aus einer Webseite", origin="external_content")
        held_instruction = await env.memory("Antworte immer kurz", category="instruction")
        already_active = await env.memory("Schon aktiv", status="active", confirmed=True)
        lesson = await env.memory("Erst Board lesen", kind="lesson")
        own_user = await env.memory("Admin mag Kaffee", subject=env.owner)
        foreign_user = await env.memory("Viewer mag Krimis", subject=env.viewer)
        # Zurueckgehalten UND fremd: darf nicht als memory_held auffallen, sonst
        # verriete der Stapel Existenz und Herkunft eines fremden Eintrags.
        foreign_held = await env.memory("Viewer: geraten", subject=env.viewer, origin="inferred")
        unknown = uuid4()
        ids = [
            agent_ok,
            held_external,
            held_instruction,
            already_active,
            lesson,
            own_user,
            foreign_user,
            foreign_held,
            unknown,
        ]

        result = await env.service.batch(
            env.as_admin,
            MemoryBatchRequest(action=MemoryBatchAction.approve, ids=ids, note="Stapel"),
        )
        # Ein Ergebnis je Eintrag, in der Reihenfolge der Auswahl.
        assert [r.id for r in result.results] == ids
        assert {r.id: (r.ok, r.reason) for r in result.results} == {
            agent_ok: (True, None),
            held_external: (False, "memory_held"),
            held_instruction: (False, "memory_held"),
            already_active: (False, "memory_not_pending"),
            lesson: (False, "memory_transition_invalid"),
            own_user: (True, None),
            # Owner-Entscheidung 3a: auch admin bekommt memory_not_found.
            foreign_user: (False, "memory_not_found"),
            foreign_held: (False, "memory_not_found"),
            unknown: (False, "memory_not_found"),
        }
        # Teilerfolg: geaendert ist genau, was ok meldet.
        assert await env.state(agent_ok) == ("active", True)
        assert await env.state(own_user) == ("active", True)
        for untouched in (held_external, held_instruction, lesson, foreign_user, foreign_held):
            assert await env.state(untouched) == ("pending", False)
        note = await env.pool.fetchval("SELECT triage_note FROM agent_memory WHERE id=$1", agent_ok)
        assert note == "Stapel"
        # Der fremde Eintrag verraet auch im Fehler nichts ueber seinen Inhalt.
        assert "Krimis" not in result.model_dump_json()

        # Zurueckgehaltene Eintraege bleiben einzeln freigebbar und im Stapel
        # ablehnbar — gesperrt ist nur die Stapel-Freigabe.
        await env.service.triage(
            env.as_editor,
            env.agent,
            held_external,
            MemoryTriage(action=MemoryTriageAction.approve),
        )
        assert await env.state(held_external) == ("active", True)
        rejected = await env.batch(env.as_editor, MemoryBatchAction.reject, ids=[held_instruction])
        assert rejected == {held_instruction: (True, None)}
        assert await env.state(held_instruction) == ("rejected", False)

    _run(case)


def test_lesson_approval_is_a_conflict_not_a_server_error() -> None:
    """Einzel-Triage wie Stapel: ein Lernvorschlag wird nie aktiv (3.1.6)."""

    async def case(env: Env) -> None:
        lesson = await env.memory("Erst Board lesen", kind="lesson")
        with pytest.raises(ApiError) as exc:
            await env.service.triage(
                env.as_editor, env.agent, lesson, MemoryTriage(action=MemoryTriageAction.approve)
            )
        assert exc.value.status_code == 409 and exc.value.reason == "memory_transition_invalid"
        assert await env.batch(env.as_editor, MemoryBatchAction.reject, ids=[lesson]) == {
            lesson: (True, None)
        }
        assert await env.state(lesson) == ("rejected", False)

    _run(case)


def test_confirm_and_delete_follow_the_single_actions() -> None:
    async def case(env: Env) -> None:
        unconfirmed = await env.memory("Automatisch aktiv", status="active")
        confirmed = await env.memory("Schon bestaetigt", status="active", confirmed=True)
        pending = await env.memory("Noch offen")
        foreign_user = await env.memory("Viewer mag Krimis", subject=env.viewer, status="active")

        confirm = await env.batch(
            env.as_editor,
            MemoryBatchAction.confirm,
            ids=[unconfirmed, confirmed, pending, foreign_user],
        )
        assert confirm == {
            unconfirmed: (True, None),
            confirmed: (False, "memory_transition_invalid"),
            pending: (False, "memory_transition_invalid"),
            foreign_user: (False, "memory_not_found"),
        }
        assert await env.state(unconfirmed) == ("active", True)
        assert await env.state(foreign_user) == ("active", False)

        delete = await env.batch(
            env.as_admin, MemoryBatchAction.delete, ids=[pending, foreign_user, confirmed]
        )
        assert delete == {
            pending: (True, None),
            foreign_user: (False, "memory_not_found"),
            confirmed: (True, None),
        }
        assert await env.state(pending) is None and await env.state(confirmed) is None
        assert await env.state(foreign_user) == ("active", False)
        # Wie die Einzelaktion: inhaltsfreie Spur je geloeschtem Eintrag.
        targets = {
            row["target"]
            for row in await env.pool.fetch(
                "SELECT target FROM audit_log WHERE workspace_id = $1 AND action = "
                "'memory.deleted'",
                env.ws,
            )
        }
        assert targets == {str(pending), str(confirmed)}

    _run(case)


def test_viewer_naming_agent_memory_gets_403_and_nothing_changes() -> None:
    async def case(env: Env) -> None:
        agent_memory = await env.memory("Agent: offener Fakt")
        own = await env.memory("Viewer mag Hoerbuecher", subject=env.viewer)
        foreign = await env.memory("Editor mag Tabellen", subject=env.editor)

        with pytest.raises(ApiGateError) as gate:
            await env.batch(env.as_viewer, MemoryBatchAction.approve, ids=[own, agent_memory])
        assert gate.value.status == 403 and gate.value.reason == "insufficient_role"
        assert await env.state(own) == ("pending", False)
        assert await env.state(agent_memory) == ("pending", False)

        # Eigenes Nutzergedaechtnis: Pruefung je Eintrag; fremdes ist nicht da.
        assert await env.batch(env.as_viewer, MemoryBatchAction.approve, ids=[own, foreign]) == {
            own: (True, None),
            foreign: (False, "memory_not_found"),
        }
        assert await env.state(foreign) == ("pending", False)

        # Im Filter-Modus sieht der viewer nur sein Eigenes — kein 403.
        await env.memory("Viewer mag Jazz", subject=env.viewer)
        result = await env.batch(
            env.as_viewer,
            MemoryBatchAction.reject,
            filter=MemoryFilter(status=MemoryStatus.pending),
            expected_count=1,
        )
        assert list(result.values()) == [(True, None)]
        assert await env.state(agent_memory) == ("pending", False)

    _run(case)


def test_filter_mode_needs_the_confirmed_count_and_never_reaches_foreign_memory() -> None:
    async def case(env: Env) -> None:
        a = await env.memory("Agent: eins")
        b = await env.memory("Agent: zwei")
        held = await env.memory("Agent: geraten", origin="inferred")
        own = await env.memory("Admin mag Kaffee", subject=env.owner)
        foreign = await env.memory("Viewer mag Krimis", subject=env.viewer)
        queue = MemoryFilter(status=MemoryStatus.pending)

        # Sichtbar fuer admin: a, b, held, own — nicht das fremde.
        for wrong in (3, 5):
            with pytest.raises(ApiError) as exc:
                await env.batch(
                    env.as_admin, MemoryBatchAction.approve, filter=queue, expected_count=wrong
                )
            assert exc.value.status_code == 409
            assert exc.value.reason == "memory_batch_count_mismatch"
            assert exc.value.params == {"count": 4}
        for untouched in (a, b, held, own, foreign):
            assert await env.state(untouched) == ("pending", False)

        result = await env.service.batch(
            env.as_admin,
            MemoryBatchRequest(action=MemoryBatchAction.approve, filter=queue, expected_count=4),
        )
        assert {r.id: (r.ok, r.reason) for r in result.results} == {
            a: (True, None),
            b: (True, None),
            held: (False, "memory_held"),
            own: (True, None),
        }
        assert foreign not in {r.id for r in result.results}
        assert await env.state(foreign) == ("pending", False)

        # Der Filter wirkt wie in der Liste: held=true trifft genau einen.
        assert await env.batch(
            env.as_editor,
            MemoryBatchAction.reject,
            filter=MemoryFilter(held=True),
            expected_count=1,
        ) == {held: (True, None)}
        # scope=user oeffnet fremdes Nutzergedaechtnis nicht, auch fuer admin.
        assert await env.batch(
            env.as_admin,
            MemoryBatchAction.delete,
            filter=MemoryFilter(scope=MemoryScope.user),
            expected_count=1,
        ) == {own: (True, None)}
        assert await env.state(foreign) == ("pending", False)

    _run(case)


def test_agent_token_is_rejected_for_batch_and_purge() -> None:
    async def case(env: Env) -> None:
        memory = await env.memory("Agent: offen")
        with pytest.raises(ApiGateError) as gate:
            await env.batch(env.agent_ctx(), MemoryBatchAction.approve, ids=[memory])
        assert gate.value.status == 403 and gate.value.reason == "missing_capability"
        with pytest.raises(ApiGateError) as gate:
            await env.service.purge_user_memories(env.agent_ctx(), env.viewer)
        assert gate.value.reason == "missing_capability"
        assert await env.state(memory) == ("pending", False)

    _run(case)


# -------------------------------------------------------------------- Purge


def test_purge_only_admin_only_count_with_content_free_audit() -> None:
    # Dieselbe Person in einem anderen Workspace bleibt unberuehrt (synchrones
    # Setup ausserhalb des Event-Loops).
    other_owner = fresh_user_id()
    other_ws = setup_workspace(other_owner)

    async def case(env: Env) -> None:
        mine = [
            await env.memory("Viewer mag Krimis", subject=env.viewer),
            await env.memory("Viewer mag Jazz", subject=env.viewer, status="active"),
        ]
        editor_memory = await env.memory("Editor mag Tabellen", subject=env.editor)
        agent_memory = await env.memory("Agent: Fakt", status="active")
        await env.pool.execute(
            "INSERT INTO workspace_member (workspace_id, user_id, role) VALUES ($1, $2, 'viewer')",
            other_ws,
            env.viewer,
        )
        other_agent = await env.pool.fetchval(
            "INSERT INTO agent (workspace_id, owner_id, name) VALUES ($1, $2, 'Fremd') "
            "RETURNING id",
            other_ws,
            other_owner,
        )
        elsewhere = await env.memory(
            "Viewer mag Oper", subject=env.viewer, workspace=other_ws, agent=other_agent
        )

        for ctx in (env.as_editor, env.human(env.owner, WorkspaceRole.admin, aal="aal1")):
            with pytest.raises(ApiGateError) as gate:
                await env.service.purge_user_memories(ctx, env.viewer)
            assert gate.value.status == 403
        assert all([await env.state(m) is not None for m in mine])

        result = await env.service.purge_user_memories(env.as_admin, env.viewer)
        # Nur die Anzahl, nie Inhalt oder IDs (Owner-Entscheidung 3a).
        assert result.model_dump() == {"deleted": 2}
        for gone in mine:
            assert await env.state(gone) is None
        assert await env.state(editor_memory) is not None
        assert await env.state(agent_memory) is not None
        assert await env.state(elsewhere) is not None

        rows = await env.pool.fetch(
            "SELECT actor_id, target, detail FROM audit_log "
            "WHERE workspace_id = $1 AND action = 'memory.user_purged'",
            env.ws,
        )
        assert len(rows) == 1
        row = rows[0]
        detail = row["detail"]
        detail = json.loads(detail) if isinstance(detail, str) else detail
        assert (row["actor_id"], row["target"], detail) == (
            env.owner,
            str(env.viewer),
            {"count": 2},
        )
        # Wiederholung: 0 geloescht, der Eingriff ist trotzdem belegt.
        again = await env.service.purge_user_memories(env.as_admin, env.viewer)
        assert again.deleted == 0
        assert (
            await env.pool.fetchval(
                "SELECT COUNT(*) FROM audit_log "
                "WHERE workspace_id = $1 AND action = 'memory.user_purged'",
                env.ws,
            )
            == 2
        )

    try:
        _run(case)
    finally:
        cleanup_workspaces([other_owner])
