"""Service-Tests fuer Gespraechsprotokolle: einreichen und lesen (ADR-0053 3.5/3.6/6.6, E2b-1).

Echte DB unter der Laufzeitrolle `who2be_app` (RLS aktiv), Repository aus
E2a-1, Mandant ueber `tenant_scope` (Fixture `_with_repo` aus
`test_feedback_session_schema`). Belegt:

- **Rechte-Matrix:** viewer nein, editor ja, Agent ohne `case_triage` nein,
  Agent mit `case_triage` ja, agent-gebundener Token ohne Policy nein — fuer
  Einreichen und Lesen. Schreibrate des Agenten wie bei `report_case`.
- **Pruefungen:** fremde, unbekannte oder fremd-agentische Faelle und Faelle
  einer Massnahme ausserhalb des Protokolls (`session_cases_invalid`),
  Pruefall fehlt bzw. fremd (`measure_test_case_required`), `supersedes_id`
  eines anderen Agenten (`session_not_found`), fremder Workspace.
- **Atomaritaet:** ein Fehler in der dritten Massnahme hinterlaesst nichts,
  auch kein Fall-Event.
- **in_progress-Automatik (W-E2 = a):** triaged und reopened gehen auf
  `in_progress` (Event mit `measure_id`), open mit Zuordnung ueber `triaged`,
  open ohne Zuordnung und alle anderen Status bleiben und stehen im Ergebnis.
- **Fall-Sperre:** zwei gleichzeitige Protokolle auf denselben Fall ergeben
  genau ein `in_progress` (Review E2b-1).

Ohne DB greift der zentrale Skip; mit `WHO2BE_REQUIRE_DB=1` schlaegt er hart fehl.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from uuid import UUID, uuid4

import asyncpg
import pytest
from test_feedback_session_schema import (  # type: ignore[import-not-found]
    _TABLES,
    _insert_test_case,
    _measure,
    _protocol,
    _with_repo,
)

from who2be_api.core.errors import ApiError, ApiGateError
from who2be_api.core.security import WorkspaceContext
from who2be_api.repositories.case_repository import PgCaseRepository
from who2be_api.repositories.session_repository import CaseStart, PgSessionRepository
from who2be_api.services.case_service import CaseService, CaseTransitionRequest
from who2be_api.services.session_service import SessionService
from who2be_models import (
    AgentToolPolicy,
    CaseActorKind,
    CaseCreate,
    CaseElementInput,
    CaseEventCreate,
    CaseEventKind,
    CaseStatus,
    CaseTarget,
    SessionCreate,
    SessionSubmitterKind,
    WorkspaceRole,
)

pytestmark = pytest.mark.integration


class _World:
    """Kontexte und Helfer fuer einen Testlauf in Workspace A."""

    def __init__(self, repo: PgSessionRepository, pool: asyncpg.Pool, env: object) -> None:
        self.repo = repo
        self.env = env
        self.seed = env.seed  # type: ignore[attr-defined]
        self.owner: asyncpg.Connection = env.owner  # type: ignore[attr-defined]
        self.svc = SessionService(repo)
        self.cases = PgCaseRepository(pool)
        self.case_svc = CaseService(self.cases)
        ws = self.seed.ws_a
        self.viewer = WorkspaceContext(ws, uuid4(), WorkspaceRole.viewer)
        self.editor = WorkspaceContext(ws, uuid4(), WorkspaceRole.editor)
        self.agent = self._agent(self.seed.agent_a, AgentToolPolicy())
        self.builder = self._agent(self.seed.agent_a2, AgentToolPolicy(case_triage=True))
        # Agent-gebunden, aber ohne geladene Policy (Race mit Agent-Delete).
        self.no_policy = self._agent(self.seed.agent_a2, None)

    def _agent(self, agent_id: UUID, policy: AgentToolPolicy | None) -> WorkspaceContext:
        return WorkspaceContext(
            self.seed.ws_a,
            uuid4(),
            WorkspaceRole.editor,  # Snapshot-Rolle ist gedeckelt; massgeblich ist die Policy
            is_api_token=True,
            agent_id=agent_id,
            tool_policy=policy,
        )

    async def case(self, agent_id: UUID | None = None) -> UUID:
        created = await self.case_svc.report_case(
            self.editor,
            CaseCreate(
                agent_id=agent_id or self.seed.agent_a,
                situation="Kunde fragt nach der Frist.",
                behavior="Keine Frist genannt.",
                expected_behavior="Nennt die Frist.",
            ),
        )
        return created.id

    async def case_in(self, state: CaseStatus, *, element: bool = True) -> UUID:
        """Fall im Zustand `state`; `element`: mit `model_limit`-Zuordnung."""
        case_id = await self.case()
        if element:
            await self.case_svc.set_elements(
                self.editor, case_id, [CaseElementInput(target=CaseTarget.model_limit)]
            )
        version = await self.persona_version()

        async def go(to: CaseStatus) -> None:
            await self.case_svc.transition(
                self.editor,
                case_id,
                CaseTransitionRequest(
                    to=to,
                    note="Begruendung"
                    if to in (CaseStatus.dismissed, CaseStatus.reopened)
                    else None,
                    version_entity_type="persona" if to is CaseStatus.addressed else None,
                    version_id=version if to is CaseStatus.addressed else None,
                ),
            )

        path = {
            CaseStatus.open: [],
            CaseStatus.triaged: [CaseStatus.triaged],
            CaseStatus.addressed: [CaseStatus.triaged, CaseStatus.addressed],
            CaseStatus.reopened: [CaseStatus.triaged, CaseStatus.addressed, CaseStatus.reopened],
            CaseStatus.dismissed: [CaseStatus.dismissed],
        }
        if state is CaseStatus.in_progress:
            await go(CaseStatus.triaged)
            await self.cases.append_event(
                self.seed.ws_a,
                case_id,
                CaseEventCreate(event=CaseEventKind.in_progress, measure_id=uuid4()),
                actor_kind=CaseActorKind.human,
                actor_id=self.editor.user_id,
            )
            return case_id
        for step in path[state]:
            await go(step)
        return case_id

    async def persona_version(self) -> UUID:
        persona_id: UUID = await self.owner.fetchval(
            "INSERT INTO persona (workspace_id, owner_id, name) VALUES ($1, $2, $3) RETURNING id",
            self.seed.ws_a,
            self.seed.user,
            f"p-{uuid4().hex[:6]}",
        )
        version_id: UUID = await self.owner.fetchval(
            "INSERT INTO persona_version (persona_id, version, content, status, created_by) "
            "VALUES ($1, 1, '{}'::jsonb, 'draft', $2) RETURNING id",
            persona_id,
            self.seed.user,
        )
        return version_id

    async def test_case(self, agent_id: UUID | None = None) -> UUID:
        test_case_id: UUID = await _insert_test_case(
            self.owner, self.seed.ws_a, agent_id or self.seed.agent_a
        )
        return test_case_id

    async def status(self, case_id: UUID) -> CaseStatus:
        case = await self.cases.get_case(self.seed.ws_a, case_id)
        assert case is not None
        return case.status

    async def events(self, case_id: UUID) -> list[tuple[str, UUID | None]]:
        rows = await self.owner.fetch(
            "SELECT event, measure_id FROM agent_case_event WHERE case_id = $1 "
            "ORDER BY created_at, id",
            case_id,
        )
        return [(r["event"], r["measure_id"]) for r in rows]

    async def simple(self, agent_id: UUID | None = None) -> SessionCreate:
        """Gueltiges Protokoll mit einem Fall und einer Massnahme."""
        agent = agent_id or self.seed.agent_a
        case_id = await self.case(agent)
        test_case = await self.test_case(agent)
        data: SessionCreate = _protocol(agent, [case_id], [_measure([case_id], test_case)])
        return data


def _run(body: Callable[[_World], Awaitable[None]]) -> None:
    async def outer(repo: PgSessionRepository, pool: asyncpg.Pool, env: object) -> None:
        await body(_World(repo, pool, env))

    _with_repo(outer)


def _reason(exc: pytest.ExceptionInfo[BaseException]) -> str:
    err = exc.value
    if isinstance(err, ApiGateError):
        return err.reason
    assert isinstance(err, ApiError)
    return str(err.reason)


def _code(exc: pytest.ExceptionInfo[BaseException]) -> int:
    err = exc.value
    if isinstance(err, ApiGateError):
        return err.status
    assert isinstance(err, ApiError)
    return err.status_code


# --- Rechte ------------------------------------------------------------------


def test_rights_matrix_for_submit_and_read() -> None:
    async def body(w: _World) -> None:
        for ctx in (w.viewer, w.agent, w.no_policy):
            data = await w.simple()
            with pytest.raises((ApiError, ApiGateError)) as exc:
                await w.svc.submit_protocol(ctx, data)
            assert _code(exc) == 403
            with pytest.raises((ApiError, ApiGateError)) as listing:
                await w.svc.list_sessions(ctx)
            assert _code(listing) == 403
        assert await w.owner.fetchval("SELECT count(*) FROM feedback_session") == 0

        by_editor = await w.svc.submit_protocol(w.editor, await w.simple())
        session = by_editor.detail.session
        assert session.submitted_by_kind is SessionSubmitterKind.human
        assert session.submitted_by == w.editor.user_id

        builder_case = await w.case_in(CaseStatus.triaged)
        by_builder = await w.svc.submit_protocol(
            w.builder,
            _protocol(
                w.seed.agent_a, [builder_case], [_measure([builder_case], await w.test_case())]
            ),
        )
        assert by_builder.cases_started == [builder_case]
        assert by_builder.detail.session.submitted_by_kind is SessionSubmitterKind.agent
        assert by_builder.detail.session.submitted_by == w.seed.agent_a2
        actors = await w.owner.fetch(
            "SELECT DISTINCT actor_kind, actor_id FROM agent_case_event "
            "WHERE event = 'in_progress' AND case_id = ANY($1::uuid[])",
            by_builder.detail.session.case_ids,
        )
        assert [(r["actor_kind"], r["actor_id"]) for r in actors] == [("agent", w.seed.agent_a2)]

        # Lesen: editor und Builder ja, die anderen nie — auch nicht je ID.
        for ctx in (w.editor, w.builder):
            got = await w.svc.get_session(ctx, session.id)
            assert got == await w.repo.get_session(w.seed.ws_a, session.id)
            listed = await w.svc.list_sessions(ctx, agent_id=w.seed.agent_a)
            assert {s.id for s in listed} == {session.id, by_builder.detail.session.id}
        for ctx in (w.viewer, w.agent, w.no_policy):
            with pytest.raises((ApiError, ApiGateError)) as exc:
                await w.svc.get_session(ctx, session.id)
            assert _code(exc) == 403
        with pytest.raises(ApiError) as missing:
            await w.svc.get_session(w.editor, uuid4())
        assert _reason(missing) == "session_not_found"

    _run(body)


def test_agent_write_rate_applies_like_report_case() -> None:
    async def body(w: _World) -> None:
        limited = w._agent(w.seed.agent_a2, AgentToolPolicy(case_triage=True, write_rate_limit=1))
        await w.svc.submit_protocol(limited, await w.simple())
        with pytest.raises(ApiError) as exc:
            await w.svc.submit_protocol(limited, await w.simple())
        assert (_reason(exc), _code(exc)) == ("write_rate_limited", 429)
        # Menschen drosselt die Agenten-Rate nicht.
        await w.svc.submit_protocol(w.editor, await w.simple())
        await w.svc.submit_protocol(w.editor, await w.simple())

    _run(body)


# --- Pruefungen -----------------------------------------------------------------


def test_references_must_belong_to_the_discussed_agent_and_workspace() -> None:
    async def body(w: _World) -> None:
        s = w.seed
        own = await w.case()
        other_agent_case = await w.case(s.agent_a2)
        test_case = await w.test_case()
        foreign_test_case = await w.test_case(s.agent_a2)
        foreign_ws_case = await w.owner.fetchval(
            "INSERT INTO agent_case (workspace_id, agent_id, reporter_kind, reporter_agent_id, "
            " situation, behavior, expected_behavior) "
            "VALUES ($1, $2, 'agent', $2, 's', 'b', 'e') RETURNING id",
            s.ws_b,
            s.agent_b,
        )

        async def fails(data: SessionCreate, reason: str, status_code: int) -> ApiError:
            with pytest.raises(ApiError) as exc:
                await w.svc.submit_protocol(w.editor, data)
            assert (_reason(exc), _code(exc)) == (reason, status_code)
            return exc.value

        measure = _measure([own], test_case)
        for bad in (other_agent_case, foreign_ws_case, uuid4()):
            err = await fails(
                _protocol(s.agent_a, [own, bad], [measure]), "session_cases_invalid", 422
            )
            assert err.params == {"case_ids": [str(bad)]}
        # Massnahme mit Fall ausserhalb des Protokolls (auch ein eigener Fall).
        other_own = await w.case()
        err = await fails(
            _protocol(s.agent_a, [own], [measure, _measure([other_own], test_case)]),
            "session_cases_invalid",
            422,
        )
        assert err.params == {"case_ids": [str(other_own)], "measure_index": 1}
        # Pruefall unbekannt oder von einem anderen Agenten.
        for bad_test in (uuid4(), foreign_test_case):
            err = await fails(
                _protocol(s.agent_a, [own], [_measure([own], bad_test)]),
                "measure_test_case_required",
                422,
            )
            assert err.params == {"measure_index": 0}
        # Korrektur eines Protokolls eines anderen Agenten.
        foreign_session = await w.svc.submit_protocol(w.editor, await w.simple(s.agent_a2))
        err = await fails(
            _protocol(s.agent_a, [own], [measure], supersedes_id=foreign_session.detail.session.id),
            "session_not_found",
            404,
        )
        assert err.params == {"field": "supersedes_id"}
        # Agent eines fremden Workspace.
        await fails(_protocol(s.agent_b, [], []), "agent_not_found", 404)

        # Nichts davon hat etwas hinterlassen (ausser dem einen gueltigen Protokoll).
        assert await w.owner.fetchval("SELECT count(*) FROM feedback_session") == 1
        assert await w.status(own) is CaseStatus.open

        # Gueltige Korrektur desselben Agenten.
        first = await w.svc.submit_protocol(w.editor, _protocol(s.agent_a, [own], [measure]))
        fix = await w.svc.submit_protocol(
            w.editor,
            _protocol(s.agent_a, [own], [], supersedes_id=first.detail.session.id),
        )
        assert fix.detail.session.supersedes_id == first.detail.session.id

    _run(body)


def test_foreign_workspace_sees_nothing() -> None:
    async def body(w: _World) -> None:
        result = await w.svc.submit_protocol(w.editor, await w.simple())
        session_id = result.detail.session.id
        other = WorkspaceContext(w.seed.ws_b, uuid4(), WorkspaceRole.editor)
        with pytest.raises(ApiError) as exc:
            await w.svc.get_session(other, session_id)
        assert _reason(exc) == "session_not_found"
        assert await w.svc.list_sessions(other) == []

    _run(body)


# --- Atomaritaet ---------------------------------------------------------------


def test_error_in_third_measure_leaves_nothing() -> None:
    async def body(w: _World) -> None:
        triaged = await w.case_in(CaseStatus.triaged)
        reopened = await w.case_in(CaseStatus.reopened)
        test_case = await w.test_case()
        events_before = await w.owner.fetchval("SELECT count(*) FROM agent_case_event")
        data = _protocol(
            w.seed.agent_a,
            [triaged, reopened],
            [
                _measure([triaged], test_case),
                _measure([reopened], test_case),
                _measure([triaged, reopened], uuid4()),  # Pruefall gibt es nicht
            ],
        )
        with pytest.raises(ApiError) as exc:
            await w.svc.submit_protocol(w.editor, data)
        assert _reason(exc) == "measure_test_case_required"
        assert exc.value.params == {"measure_index": 2}
        for table in _TABLES:
            count = await w.owner.fetchval(f"SELECT count(*) FROM {table}")  # noqa: S608
            assert count == 0, table
        assert await w.owner.fetchval("SELECT count(*) FROM agent_case_event") == events_before
        assert await w.status(triaged) is CaseStatus.triaged
        assert await w.status(reopened) is CaseStatus.reopened

    _run(body)


def test_database_error_after_writes_rolls_back_everything() -> None:
    """Auch ein Fehler NACH dem Schreiben (hier: aus der DB) laesst nichts stehen."""

    async def body(w: _World) -> None:
        triaged = await w.case_in(CaseStatus.triaged)
        test_case = await w.test_case()
        data = _protocol(w.seed.agent_a, [triaged], [_measure([triaged], test_case)])

        original = w.repo.start_cases

        async def broken(
            conn: asyncpg.Connection,
            workspace_id: UUID,
            starts: Sequence[tuple[UUID, UUID]],
            *,
            actor_kind: CaseActorKind,
            actor_id: UUID,
        ) -> list[CaseStart]:
            await original(conn, workspace_id, starts, actor_kind=actor_kind, actor_id=actor_id)
            raise RuntimeError("Abbruch nach den Fall-Events")

        w.repo.start_cases = broken  # type: ignore[method-assign]
        with pytest.raises(RuntimeError):
            await w.svc.submit_protocol(w.editor, data)
        for table in _TABLES:
            count = await w.owner.fetchval(f"SELECT count(*) FROM {table}")  # noqa: S608
            assert count == 0, table
        assert await w.status(triaged) is CaseStatus.triaged

    _run(body)


# --- in_progress-Automatik (W-E2 = a) ----------------------------------------------


def test_cases_of_measures_go_to_in_progress() -> None:
    async def body(w: _World) -> None:
        triaged = await w.case_in(CaseStatus.triaged)
        reopened = await w.case_in(CaseStatus.reopened)
        open_assigned = await w.case_in(CaseStatus.open)
        open_bare = await w.case_in(CaseStatus.open, element=False)
        addressed = await w.case_in(CaseStatus.addressed)
        dismissed = await w.case_in(CaseStatus.dismissed)
        running = await w.case_in(CaseStatus.in_progress)
        only_discussed = await w.case_in(CaseStatus.triaged)  # ohne Massnahme
        test_case = await w.test_case()
        all_cases = [
            triaged, reopened, open_assigned, open_bare, addressed, dismissed, running,
            only_discussed,
        ]  # fmt: skip
        data = _protocol(
            w.seed.agent_a,
            all_cases,
            [
                _measure([triaged, reopened, open_assigned], test_case),
                _measure([triaged, open_bare, addressed, dismissed, running], test_case),
            ],
        )
        result = await w.svc.submit_protocol(w.editor, data)
        m_1, m_2 = (m.id for m in result.detail.measures)

        assert set(result.cases_started) == {triaged, reopened, open_assigned}
        assert {(c.case_id, c.status) for c in result.cases_unchanged} == {
            (open_bare, CaseStatus.open),
            (addressed, CaseStatus.addressed),
            (dismissed, CaseStatus.dismissed),
            (running, CaseStatus.in_progress),
        }
        for case_id in (triaged, reopened, open_assigned):
            assert await w.status(case_id) is CaseStatus.in_progress
        for case_id, expected in (
            (open_bare, CaseStatus.open),
            (addressed, CaseStatus.addressed),
            (dismissed, CaseStatus.dismissed),
            (only_discussed, CaseStatus.triaged),
        ):
            assert await w.status(case_id) is expected

        # Event mit der ersten Massnahme, die den Fall enthaelt; open laeuft
        # ueber triaged (3.3), reopened ebenfalls.
        assert (await w.events(triaged))[-1] == ("in_progress", m_1)
        assert (await w.events(reopened))[-2:] == [("triaged", None), ("in_progress", m_1)]
        assert (await w.events(open_assigned))[-2:] == [("triaged", None), ("in_progress", m_1)]
        assert [e for e, _ in await w.events(open_bare)] == ["reported"]
        # Bereits laufender Fall: kein zweites in_progress-Event.
        assert [e for e, _ in await w.events(running)].count("in_progress") == 1
        assert m_2 not in {m for _, m in await w.events(running)}

    _run(body)


def test_protocol_without_measures_changes_no_case() -> None:
    async def body(w: _World) -> None:
        triaged = await w.case_in(CaseStatus.triaged)
        result = await w.svc.submit_protocol(w.editor, _protocol(w.seed.agent_a, [triaged], []))
        assert (result.cases_started, result.cases_unchanged) == ([], [])
        assert result.detail.session.case_ids == [triaged]
        assert await w.status(triaged) is CaseStatus.triaged

    _run(body)


def test_concurrent_submits_start_a_case_exactly_once() -> None:
    """Fall-Sperre (Review E2b-1): zwei gleichzeitige Protokolle, ein `in_progress`.

    Beide Transaktionen haben geschrieben und warten an derselben Stelle, bevor
    eine den Fallstatus liest. Ohne `_lock_case` in `start_cases` saehen beide
    `triaged` und schrieben je ein Event.
    """

    async def body(w: _World) -> None:
        triaged = await w.case_in(CaseStatus.triaged)
        test_case = await w.test_case()
        barrier = asyncio.Barrier(2)
        original = w.repo.start_cases

        async def gated(
            conn: asyncpg.Connection,
            workspace_id: UUID,
            starts: Sequence[tuple[UUID, UUID]],
            *,
            actor_kind: CaseActorKind,
            actor_id: UUID,
        ) -> list[CaseStart]:
            await barrier.wait()
            return await original(
                conn, workspace_id, starts, actor_kind=actor_kind, actor_id=actor_id
            )

        w.repo.start_cases = gated  # type: ignore[method-assign]
        data = _protocol(w.seed.agent_a, [triaged], [_measure([triaged], test_case)])
        first, second = await asyncio.gather(
            w.svc.submit_protocol(w.editor, data), w.svc.submit_protocol(w.editor, data)
        )
        assert sorted([len(first.cases_started), len(second.cases_started)]) == [0, 1]
        unchanged = first.cases_unchanged + second.cases_unchanged
        assert [(c.case_id, c.status) for c in unchanged] == [(triaged, CaseStatus.in_progress)]
        assert [e for e, _ in await w.events(triaged)].count("in_progress") == 1

    _run(body)
