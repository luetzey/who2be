"""Service-Tests: Lernvorschlag -> Fall (convert) und Alt-Feedback -> Fall (promote).

ADR-0053 6.4 (`convert`), 6.5 und 5.2 (`promote`), 3.1.6 (Wiederholung);
Lernschleife Phase D, Paket D2c-1. Echte DB unter der Laufzeitrolle
`who2be_app` (RLS aktiv), Fixture `_with_repo` aus `test_agent_case_schema`.
Belegt:

- **Atomar:** Fall, Status, `converted_case_id` und Event bzw. Fall und
  Triage-Ereignis entstehen gemeinsam; bricht der letzte Schritt ab, ist
  nichts geaendert (Mutationsprobe ueber einen Fehler im letzten Schritt).
- **Wiederholung:** eine erneut eingereichte Lektion trifft den
  `converted`-Eintrag und laesst ihn `converted`.
- **Eigene Fehlergruende:** `memory_not_convertible`,
  `feedback_not_promotable` (409).
- **Rechte:** Agent-Token 403 (auch mit `case_triage`), viewer 403; fremder
  Workspace ist nicht da (404).

Ohne DB greift der zentrale Skip; mit `WHO2BE_REQUIRE_DB=1` schlaegt er hart fehl.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest
from test_agent_case_schema import (  # type: ignore[import-not-found]
    _insert_lesson,
    _report,
    _with_repo,
)

from who2be_api.core.errors import ApiError, ApiGateError
from who2be_api.core.security import WorkspaceContext
from who2be_api.repositories import case_repository
from who2be_api.repositories.case_repository import PROMOTED_NOTE_PREFIX, PgCaseRepository
from who2be_api.repositories.memory_repository import PgMemoryRepository
from who2be_api.services.case_service import CaseService
from who2be_models import (
    AgentToolPolicy,
    CaseReporterKind,
    CaseStatus,
    WorkspaceRole,
)
from who2be_models.case import CaseConvertRequest

pytestmark = pytest.mark.integration


class _World:
    def __init__(self, repo: PgCaseRepository, env: Any) -> None:
        self.repo = repo
        self.seed = env.seed
        self.owner: asyncpg.Connection = env.owner
        self.svc = CaseService(repo)
        ws = self.seed.ws_a
        self.viewer = WorkspaceContext(ws, uuid4(), WorkspaceRole.viewer)
        self.editor = WorkspaceContext(ws, uuid4(), WorkspaceRole.editor)
        self.agent = self._agent(AgentToolPolicy())
        self.triage = self._agent(AgentToolPolicy(case_triage=True, feedback_resolve=True))

    def _agent(self, policy: AgentToolPolicy) -> WorkspaceContext:
        return WorkspaceContext(
            self.seed.ws_a,
            uuid4(),
            WorkspaceRole.admin,  # Snapshot-Rolle egal: Agent-Tokens sind gesperrt
            is_api_token=True,
            agent_id=self.seed.agent_a,
            tool_policy=policy,
        )

    async def lesson(self, agent_id: UUID | None = None, kind: str = "lesson") -> UUID:
        memory_id: UUID = await _insert_lesson(
            self.owner, self.seed.ws_a, agent_id or self.seed.agent_a, kind=kind
        )
        return memory_id

    async def memory(self, memory_id: UUID) -> asyncpg.Record:
        row = await self.owner.fetchrow(
            "SELECT status, converted_case_id, occurrence_count FROM agent_memory WHERE id = $1",
            memory_id,
        )
        assert row is not None
        return row

    async def memory_events(self, memory_id: UUID) -> list[asyncpg.Record]:
        return list(
            await self.owner.fetch(
                "SELECT event, actor_kind, actor_id, before, after FROM agent_memory_event "
                "WHERE memory_id = $1 ORDER BY created_at, id",
                memory_id,
            )
        )

    async def feedback(self, workspace_id: UUID | None = None) -> UUID:
        feedback_id: UUID = await self.owner.fetchval(
            "INSERT INTO agent_feedback "
            "(workspace_id, agent_id, actor_id, entity_type, entity_id, signal, note) "
            "VALUES ($1, NULL, $2, 'playbook', $3, 'incorrect', 'Schritt 3 stimmt nicht') "
            "RETURNING id",
            workspace_id or self.seed.ws_a,
            self.seed.user,
            uuid4(),
        )
        return feedback_id

    async def resolutions(self, feedback_id: UUID) -> list[asyncpg.Record]:
        return list(
            await self.owner.fetch(
                "SELECT resolution, actor_id, note FROM feedback_resolution "
                "WHERE feedback_id = $1 ORDER BY created_at",
                feedback_id,
            )
        )

    async def case_count(self) -> int:
        n: int = await self.owner.fetchval("SELECT count(*) FROM agent_case")
        return n


def _run(body: Callable[[_World], Awaitable[None]]) -> None:
    async def outer(repo: PgCaseRepository, env: object) -> None:
        await body(_World(repo, env))

    _with_repo(outer)


def _convert_body() -> CaseConvertRequest:
    return CaseConvertRequest(
        situation="Kunde fragt nach der Frist.",
        behavior="Keine Frist genannt.",
        expected_behavior="Nennt die Frist.",
    )


def _json(value: object) -> dict[str, Any]:
    raw = json.loads(value) if isinstance(value, str) else value
    assert isinstance(raw, dict)
    return raw


class _Boom(RuntimeError):
    pass


async def _fail(*_args: object, **_kwargs: object) -> None:
    raise _Boom("Abbruch im letzten Schritt")


# --- convert ----------------------------------------------------------------


def test_convert_sets_status_case_and_event_together() -> None:
    async def body(w: _World) -> None:
        memory_id = await w.lesson()
        case = await w.svc.convert_lesson(w.editor, w.seed.agent_a, memory_id, _convert_body())

        assert case.agent_id == w.seed.agent_a
        assert case.source_memory_id == memory_id
        assert case.source_feedback_id is None
        assert case.status is CaseStatus.open
        assert case.reporter_kind is CaseReporterKind.human
        assert case.reporter_user_id == w.editor.user_id

        memory = await w.memory(memory_id)
        assert memory["status"] == "converted"
        assert memory["converted_case_id"] == case.id

        events = await w.memory_events(memory_id)
        assert [e["event"] for e in events] == ["converted"]
        assert events[0]["actor_kind"] == "human"
        assert events[0]["actor_id"] == w.editor.user_id
        assert _json(events[0]["before"])["status"] == "pending"
        assert _json(events[0]["after"])["status"] == "converted"

        detail = await w.svc.get_case(w.editor, case.id)
        assert [e.event.value for e in detail.events] == ["reported"]

    _run(body)


def test_convert_aborted_in_last_step_changes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mutationsprobe: Fehler beim Event-Schreiben -> kein Fall, Eintrag unveraendert."""

    async def body(w: _World) -> None:
        memory_id = await w.lesson()
        before_cases = await w.case_count()
        monkeypatch.setattr(case_repository, "_insert_human_event", _fail)
        with pytest.raises(_Boom):
            await w.svc.convert_lesson(w.editor, w.seed.agent_a, memory_id, _convert_body())
        monkeypatch.undo()

        assert await w.case_count() == before_cases
        memory = await w.memory(memory_id)
        assert (memory["status"], memory["converted_case_id"]) == ("pending", None)
        assert await w.memory_events(memory_id) == []

        # Danach geht der Weg normal — die Sperre ist freigegeben.
        case = await w.svc.convert_lesson(w.editor, w.seed.agent_a, memory_id, _convert_body())
        assert (await w.memory(memory_id))["converted_case_id"] == case.id

    _run(body)


def test_repetition_after_convert_stays_converted() -> None:
    async def body(w: _World) -> None:
        memory_id = await w.lesson()
        case = await w.svc.convert_lesson(w.editor, w.seed.agent_a, memory_id, _convert_body())

        pool = w.repo._pool  # noqa: SLF001 — derselbe App-Pool wie der Fall-Pfad
        merged = await PgMemoryRepository(pool).merge_lesson(w.seed.ws_a, w.seed.agent_a, memory_id)
        assert merged is not None
        assert merged.status.value == "converted"
        memory = await w.memory(memory_id)
        assert (memory["status"], memory["converted_case_id"]) == ("converted", case.id)
        assert memory["occurrence_count"] == 2

        # Ein zweites convert macht keinen zweiten Fall.
        before_cases = await w.case_count()
        with pytest.raises(ApiError) as exc:
            await w.svc.convert_lesson(w.editor, w.seed.agent_a, memory_id, _convert_body())
        assert exc.value.status_code == 409
        assert exc.value.reason == "memory_not_convertible"
        assert exc.value.params == {"kind": "lesson", "status": "converted"}
        assert await w.case_count() == before_cases

    _run(body)


def test_convert_only_pending_lessons() -> None:
    async def body(w: _World) -> None:
        note_id = await w.lesson(kind="agent_note")
        rejected_id = await w.lesson()
        await w.owner.execute(
            "UPDATE agent_memory SET status = 'rejected' WHERE id = $1", rejected_id
        )
        cases: list[tuple[UUID, dict[str, str]]] = [
            (note_id, {"kind": "agent_note", "status": "pending"}),
            (rejected_id, {"kind": "lesson", "status": "rejected"}),
        ]
        for memory_id, params in cases:
            with pytest.raises(ApiError) as exc:
                await w.svc.convert_lesson(w.editor, w.seed.agent_a, memory_id, _convert_body())
            assert (exc.value.status_code, exc.value.reason) == (409, "memory_not_convertible")
            assert exc.value.params == params
            assert (await w.memory(memory_id))["converted_case_id"] is None
        assert await w.case_count() == 0

    _run(body)


def test_convert_rights_and_scope() -> None:
    async def body(w: _World) -> None:
        memory_id = await w.lesson()
        for ctx in (w.agent, w.triage):
            with pytest.raises(ApiGateError) as gate:
                await w.svc.convert_lesson(ctx, w.seed.agent_a, memory_id, _convert_body())
            assert gate.value.status == 403
            assert gate.value.reason == "missing_capability"
        with pytest.raises(ApiGateError) as viewer:
            await w.svc.convert_lesson(w.viewer, w.seed.agent_a, memory_id, _convert_body())
        assert viewer.value.status == 403

        # Eintrag gehoert einem anderen Agenten als im Pfad -> nicht da.
        with pytest.raises(ApiError) as other:
            await w.svc.convert_lesson(w.editor, w.seed.agent_a2, memory_id, _convert_body())
        assert (other.value.status_code, other.value.reason) == (404, "memory_not_found")
        with pytest.raises(ApiError) as unknown:
            await w.svc.convert_lesson(w.editor, w.seed.agent_a, uuid4(), _convert_body())
        assert unknown.value.reason == "memory_not_found"
        # Agent aus Workspace B ist fuer A nicht da.
        with pytest.raises(ApiError) as foreign:
            await w.svc.convert_lesson(w.editor, w.seed.agent_b, memory_id, _convert_body())
        assert (foreign.value.status_code, foreign.value.reason) == (404, "agent_not_found")

        memory = await w.memory(memory_id)
        assert (memory["status"], memory["converted_case_id"]) == ("pending", None)
        assert await w.case_count() == 0

    _run(body)


# --- promote ----------------------------------------------------------------


def test_promote_creates_case_and_addresses_feedback() -> None:
    async def body(w: _World) -> None:
        feedback_id = await w.feedback()
        case = await w.svc.promote_feedback(w.editor, feedback_id, _report(w.seed.agent_a2))

        assert case.agent_id == w.seed.agent_a2
        assert case.source_feedback_id == feedback_id
        assert case.source_memory_id is None
        assert case.status is CaseStatus.open
        assert (case.reporter_kind, case.reporter_user_id) == (
            CaseReporterKind.human,
            w.editor.user_id,
        )
        resolutions = await w.resolutions(feedback_id)
        assert [(r["resolution"], r["actor_id"], r["note"]) for r in resolutions] == [
            ("addressed", w.editor.user_id, f"{PROMOTED_NOTE_PREFIX}{case.id}")
        ]
        # Das Alt-Feedback selbst bleibt unveraendert (append-only).
        note = await w.owner.fetchval("SELECT note FROM agent_feedback WHERE id = $1", feedback_id)
        assert note == "Schritt 3 stimmt nicht"

    _run(body)


def test_promote_aborted_in_last_step_changes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mutationsprobe: Fehler beim Triage-Ereignis -> kein Fall, Feedback offen."""

    async def body(w: _World) -> None:
        feedback_id = await w.feedback()
        monkeypatch.setattr(case_repository, "_insert_resolution", _fail)
        with pytest.raises(_Boom):
            await w.svc.promote_feedback(w.editor, feedback_id, _report(w.seed.agent_a))
        monkeypatch.undo()

        assert await w.case_count() == 0
        assert await w.resolutions(feedback_id) == []

    _run(body)


def test_promote_only_open_feedback() -> None:
    async def body(w: _World) -> None:
        feedback_id = await w.feedback()
        await w.svc.promote_feedback(w.editor, feedback_id, _report(w.seed.agent_a))
        with pytest.raises(ApiError) as again:
            await w.svc.promote_feedback(w.editor, feedback_id, _report(w.seed.agent_a))
        assert (again.value.status_code, again.value.reason) == (409, "feedback_not_promotable")
        assert again.value.params == {"resolution": "addressed"}

        dismissed = await w.feedback()
        await w.owner.execute(
            "INSERT INTO feedback_resolution (workspace_id, feedback_id, resolution, note) "
            "VALUES ($1, $2, 'dismissed', 'kein Fall')",
            w.seed.ws_a,
            dismissed,
        )
        with pytest.raises(ApiError) as triaged:
            await w.svc.promote_feedback(w.editor, dismissed, _report(w.seed.agent_a))
        assert triaged.value.reason == "feedback_not_promotable"
        assert triaged.value.params == {"resolution": "dismissed"}
        assert await w.case_count() == 1

    _run(body)


def test_promote_rights_and_scope() -> None:
    async def body(w: _World) -> None:
        feedback_id = await w.feedback()
        for ctx in (w.agent, w.triage):
            with pytest.raises(ApiGateError) as gate:
                await w.svc.promote_feedback(ctx, feedback_id, _report(w.seed.agent_a))
            assert (gate.value.status, gate.value.reason) == (403, "missing_capability")
        with pytest.raises(ApiGateError) as viewer:
            await w.svc.promote_feedback(w.viewer, feedback_id, _report(w.seed.agent_a))
        assert viewer.value.status == 403

        foreign_feedback = await w.feedback(w.seed.ws_b)
        with pytest.raises(ApiError) as foreign:
            await w.svc.promote_feedback(w.editor, foreign_feedback, _report(w.seed.agent_a))
        assert (foreign.value.status_code, foreign.value.reason) == (
            404,
            "feedback_element_not_found",
        )
        with pytest.raises(ApiError) as foreign_agent:
            await w.svc.promote_feedback(w.editor, feedback_id, _report(w.seed.agent_b))
        assert foreign_agent.value.reason == "agent_not_found"

        assert await w.case_count() == 0
        assert await w.resolutions(feedback_id) == []
        assert await w.resolutions(foreign_feedback) == []

    _run(body)
