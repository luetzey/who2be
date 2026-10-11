"""Service-Tests fuer den Verlauf einer Massnahme (ADR-0053 3.6/6.6, E2b-2).

Echte DB unter der Laufzeitrolle `who2be_app` (RLS aktiv), Fixtures aus
`test_session_service`/`test_feedback_session_schema`. Belegt:

- **Rechte-Matrix:** link-draft und follow-up fuer editor und Agent mit
  `case_triage`; review und withdraw nur Mensch ab editor — ein Agent-Token
  bekommt immer 403, auch mit `case_triage` (Mutationsprobe: ohne die
  `is_agent_bound`-Pruefung wird `test_review_and_withdraw_are_human_only` rot).
- **link-draft:** Version eines anderen Elements oder einer anderen Art bzw.
  unbekannt -> `test_subject_version_not_found`; unbekannte Massnahme ->
  `measure_not_found`; neu verknuepfen bis `activated`, der juengste gilt.
- **Event-Folge (QE4 a / QE6 a):** review erst nach `activated`, genau einmal;
  danach und nach withdraw nur noch Lesen (409 `measure_transition_forbidden`).
  Ziele ohne Versionen ab dem Nachschau-Datum.
- **QE5 a:** withdraw setzt Faelle `in_progress` -> `triaged` (System-Event mit
  `measure_id`), ausser eine andere offene Massnahme enthaelt sie.
- **Kennzahlen (6.6, QE8 a):** juengster Pruefall-Lauf je Version, Nutzungen nur
  `source='server'`, Faelle im Zeitfenster, Wiederauftreten; `follow_up_prepared`
  nur durch den Agenten und nur bei geaenderten Zahlen.
- **Sperre je Massnahme:** zwei gleichzeitige Einstufungen ergeben genau ein
  `reviewed`.

Ohne DB greift der zentrale Skip; mit `WHO2BE_REQUIRE_DB=1` schlaegt er hart fehl.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import date, timedelta
from uuid import UUID, uuid4

import asyncpg
import pytest
from test_feedback_session_schema import (  # type: ignore[import-not-found]
    _FOLLOW_UP,
    _measure,
    _protocol,
    _with_repo,
)
from test_session_service import _code, _reason, _World  # type: ignore[import-not-found]

from who2be_api.core.errors import ApiError, ApiGateError
from who2be_api.core.security import WorkspaceContext
from who2be_api.repositories.session_repository import PgSessionRepository
from who2be_api.services.measure_service import FOLLOW_UP_MIN_USES, MeasureService
from who2be_models import (
    CaseElementInput,
    CaseStatus,
    CaseTarget,
    MeasureActorKind,
    MeasureEventCreate,
    MeasureEventKind,
    MeasureState,
    MeasureVerdict,
    WorkspaceRole,
)

pytestmark = pytest.mark.integration


class _MWorld(_World):  # type: ignore[misc]  # _World kommt aus einem Testmodul (Any)
    """`_World` plus Massnahmen-Service mit fester Uhr und Persona-Versionen."""

    def __init__(self, repo: PgSessionRepository, pool: asyncpg.Pool, env: object) -> None:
        super().__init__(repo, pool, env)
        self.today = _FOLLOW_UP - timedelta(days=1)
        self.msvc = MeasureService(repo, today=lambda: self.today)

    async def persona(self, versions: int = 2) -> tuple[UUID, list[UUID]]:
        persona_id: UUID = await self.owner.fetchval(
            "INSERT INTO persona (workspace_id, owner_id, name) VALUES ($1, $2, $3) RETURNING id",
            self.seed.ws_a,
            self.seed.user,
            f"p-{uuid4().hex[:6]}",
        )
        ids: list[UUID] = []
        for number in range(1, versions + 1):
            # Je Persona hoechstens eine aktive und eine Entwurfs-Version (0011).
            status = "draft" if number == versions else "active" if number == 1 else "inactive"
            ids.append(
                await self.owner.fetchval(
                    "INSERT INTO persona_version (persona_id, version, content, status, "
                    " created_by) VALUES ($1, $2, '{}'::jsonb, $3, $4) RETURNING id",
                    persona_id,
                    number,
                    status,
                    self.seed.user,
                )
            )
        return persona_id, ids

    async def measure(
        self, *, target: str = "persona", entity_id: UUID | None = None, cases: int = 1
    ) -> tuple[UUID, list[UUID]]:
        """Massnahme ueber ein eingereichtes Protokoll; Faelle `triaged` -> `in_progress`."""
        case_ids = [await self.case_in(CaseStatus.triaged) for _ in range(cases)]
        test_case = await self.test_case()
        result = await self.svc.submit_protocol(
            self.editor,
            _protocol(
                self.seed.agent_a,
                case_ids,
                [_measure(case_ids, test_case, target=target, entity_id=entity_id)],
            ),
        )
        return result.detail.measures[0].id, case_ids

    async def activate(self, measure_id: UUID, version_id: UUID) -> None:
        """`activated` wie E3 es schreibt (System, mit Version)."""
        await self.repo.append_measure_event(
            self.seed.ws_a,
            measure_id,
            MeasureEventCreate(
                event=MeasureEventKind.activated,
                version_entity_type="persona",
                version_id=version_id,
            ),
            actor_kind=MeasureActorKind.system,
            actor_id=None,
        )

    async def state(self, measure_id: UUID) -> MeasureState:
        measure = await self.repo.get_measure(self.seed.ws_a, measure_id)
        assert measure is not None
        state: MeasureState = measure.state
        return state

    async def measure_events(self, measure_id: UUID) -> list[str]:
        rows = await self.owner.fetch(
            "SELECT event FROM measure_event WHERE measure_id = $1 ORDER BY created_at, id",
            measure_id,
        )
        return [r["event"] for r in rows]


def _run(body: Callable[[_MWorld], Awaitable[None]]) -> None:
    async def outer(repo: PgSessionRepository, pool: asyncpg.Pool, env: object) -> None:
        await body(_MWorld(repo, pool, env))

    _with_repo(outer)


# --- Rechte ------------------------------------------------------------------


def test_link_draft_and_follow_up_rights() -> None:
    async def body(w: _MWorld) -> None:
        persona_id, (v1, _) = await w.persona()
        measure_id, _ = await w.measure(entity_id=persona_id)
        for ctx in (w.viewer, w.agent, w.no_policy):
            with pytest.raises((ApiError, ApiGateError)) as exc:
                await w.msvc.link_draft(ctx, measure_id, "persona", v1)
            assert _code(exc) == 403
            with pytest.raises((ApiError, ApiGateError)) as read:
                await w.msvc.follow_up(ctx, measure_id)
            assert _code(read) == 403
        assert await w.measure_events(measure_id) == []

        by_editor = await w.msvc.link_draft(w.editor, measure_id, "persona", v1)
        assert (by_editor.actor_kind, by_editor.actor_id) == (
            MeasureActorKind.human,
            w.editor.user_id,
        )
        by_builder = await w.msvc.link_draft(w.builder, measure_id, "persona", v1)
        assert (by_builder.actor_kind, by_builder.actor_id) == (
            MeasureActorKind.agent,
            w.seed.agent_a2,
        )
        for ctx in (w.editor, w.builder):
            report = await w.msvc.follow_up(ctx, measure_id)
            assert report.state is MeasureState.draft_linked
            assert report.reviewable is False

    _run(body)


def test_review_and_withdraw_are_human_only() -> None:
    async def body(w: _MWorld) -> None:
        persona_id, (_, v2) = await w.persona()
        measure_id, _ = await w.measure(entity_id=persona_id)
        await w.msvc.link_draft(w.editor, measure_id, "persona", v2)
        await w.activate(measure_id, v2)
        # Auch der Builder MIT case_triage nicht — Partei, nicht Richter (E4 = a).
        for ctx in (w.builder, w.agent, w.no_policy):
            with pytest.raises(ApiGateError) as exc:
                await w.msvc.review(ctx, measure_id, MeasureVerdict.effective)
            assert (exc.value.status, exc.value.reason, exc.value.actionable_by) == (
                403,
                "missing_capability",
                "none",
            )
            with pytest.raises(ApiGateError) as wexc:
                await w.msvc.withdraw(ctx, measure_id, "Aufgegeben.")
            assert (wexc.value.status, wexc.value.reason) == (403, "missing_capability")
        for action in ("review", "withdraw"):
            with pytest.raises(ApiGateError) as vexc:
                if action == "review":
                    await w.msvc.review(w.viewer, measure_id, MeasureVerdict.effective)
                else:
                    await w.msvc.withdraw(w.viewer, measure_id, "Aufgegeben.")
            assert vexc.value.reason == "insufficient_role"
        assert await w.measure_events(measure_id) == ["draft_linked", "activated"]

        event = await w.msvc.review(w.editor, measure_id, MeasureVerdict.effective)
        assert (event.event, event.verdict, event.actor_id) == (
            MeasureEventKind.reviewed,
            MeasureVerdict.effective,
            w.editor.user_id,
        )
        assert await w.state(measure_id) is MeasureState.effective

    _run(body)


# --- Entwurf verknuepfen -----------------------------------------------------------


def test_link_draft_checks_element_and_measure() -> None:
    async def body(w: _MWorld) -> None:
        persona_id, (v1, v2) = await w.persona()
        _, (other_version,) = await w.persona(versions=1)
        measure_id, _ = await w.measure(entity_id=persona_id)

        for entity_type, version_id in (
            ("persona", other_version),  # anderes Element
            ("playbook", v1),  # andere Art
            ("persona", uuid4()),  # unbekannt
        ):
            with pytest.raises(ApiError) as exc:
                await w.msvc.link_draft(w.editor, measure_id, entity_type, version_id)  # type: ignore[arg-type]
            assert (_reason(exc), _code(exc)) == ("test_subject_version_not_found", 404)
        with pytest.raises(ApiError) as missing:
            await w.msvc.link_draft(w.editor, uuid4(), "persona", v1)
        assert (_reason(missing), _code(missing)) == ("measure_not_found", 404)
        assert await w.measure_events(measure_id) == []

        # Beliebig oft bis activated, der juengste gilt (QE4 a).
        await w.msvc.link_draft(w.editor, measure_id, "persona", v1)
        await w.msvc.link_draft(w.editor, measure_id, "persona", v2)
        assert [m.id for m in await w.repo.measures_for_version(w.seed.ws_a, "persona", v2)] == [
            measure_id
        ]
        assert await w.repo.measures_for_version(w.seed.ws_a, "persona", v1) == []
        # Versions-Tabellen bleiben unberuehrt (E2 = a).
        assert await w.owner.fetchval(
            "SELECT array_agg(status ORDER BY version) FROM persona_version WHERE persona_id = $1",
            persona_id,
        ) == ["active", "draft"]

        await w.activate(measure_id, v2)
        with pytest.raises(ApiError) as late:
            await w.msvc.link_draft(w.editor, measure_id, "persona", v1)
        assert (_reason(late), _code(late)) == ("measure_transition_forbidden", 409)
        assert late.value.params == {"state": "activated", "action": "link_draft"}

        # Fremder Workspace: die Massnahme gibt es dort nicht.
        other_editor = WorkspaceContext(w.seed.ws_b, uuid4(), WorkspaceRole.editor)
        with pytest.raises(ApiError) as foreign:
            await w.msvc.follow_up(other_editor, measure_id)
        assert _reason(foreign) == "measure_not_found"

    _run(body)


# --- Event-Folge -----------------------------------------------------------------


def test_review_only_after_activation_and_exactly_once() -> None:
    async def body(w: _MWorld) -> None:
        persona_id, (_, v2) = await w.persona()
        measure_id, _ = await w.measure(entity_id=persona_id)

        async def review_fails(state: str) -> None:
            with pytest.raises(ApiError) as exc:
                await w.msvc.review(w.editor, measure_id, MeasureVerdict.not_measurable)
            assert (_reason(exc), _code(exc)) == ("measure_transition_forbidden", 409)
            assert exc.value.params == {"state": state, "action": "review"}

        w.today = date(2099, 1, 1)  # Faelligkeit allein reicht bei Versionen nicht
        await review_fails("agreed")
        await w.msvc.link_draft(w.editor, measure_id, "persona", v2)
        await review_fails("draft_linked")
        await w.activate(measure_id, v2)

        with pytest.raises(ValueError, match="Begruendung"):
            await w.msvc.review(w.editor, measure_id, MeasureVerdict.ineffective)
        await w.msvc.review(w.editor, measure_id, MeasureVerdict.not_measurable)
        assert await w.state(measure_id) is MeasureState.not_measurable

        # Abgeschlossen: nur noch Lesen.
        await review_fails("not_measurable")
        with pytest.raises(ApiError) as withdraw:
            await w.msvc.withdraw(w.editor, measure_id, "Doch aufgeben.")
        assert withdraw.value.params == {"state": "not_measurable", "action": "withdraw"}
        with pytest.raises(ApiError) as link:
            await w.msvc.link_draft(w.editor, measure_id, "persona", v2)
        assert _reason(link) == "measure_transition_forbidden"
        report = await w.msvc.follow_up(w.builder, measure_id)
        assert report.reviewable is False
        assert await w.measure_events(measure_id) == ["draft_linked", "activated", "reviewed"]

    _run(body)


def test_unversioned_target_reviewable_from_due_date() -> None:
    async def body(w: _MWorld) -> None:
        measure_id, _ = await w.measure(target="tool_policy", entity_id=None)
        w.today = _FOLLOW_UP - timedelta(days=1)
        report = await w.msvc.follow_up(w.editor, measure_id)
        assert (report.due, report.reviewable, report.follow_up_at) == (False, False, _FOLLOW_UP)
        with pytest.raises(ApiError) as early:
            await w.msvc.review(w.editor, measure_id, MeasureVerdict.effective)
        assert early.value.params == {"state": "agreed", "action": "review"}

        w.today = _FOLLOW_UP
        report = await w.msvc.follow_up(w.editor, measure_id)
        assert (report.due, report.reviewable) == (True, True)
        assert (report.before, report.after, report.recurrence) == (None, None, 0)
        await w.msvc.review(w.editor, measure_id, MeasureVerdict.effective)
        assert await w.state(measure_id) is MeasureState.effective

    _run(body)


# --- Zurueckziehen (QE5 a) --------------------------------------------------------


def test_withdraw_resets_cases_unless_another_open_measure_holds_them() -> None:
    async def body(w: _MWorld) -> None:
        persona_id, (v1, _) = await w.persona()
        measure_id, (alone, shared) = await w.measure(entity_id=persona_id, cases=2)
        # Zweite offene Massnahme haelt `shared`.
        test_case = await w.test_case()
        second = await w.svc.submit_protocol(
            w.editor,
            _protocol(
                w.seed.agent_a,
                [shared],
                [_measure([shared], test_case, target="persona", entity_id=persona_id)],
            ),
        )
        second_id = second.detail.measures[0].id
        await w.msvc.link_draft(w.editor, measure_id, "persona", v1)
        assert await w.status(alone) is CaseStatus.in_progress

        event, reset = await w.msvc.withdraw(w.editor, measure_id, "Wird anders geloest.")
        assert (event.event, event.note) == (MeasureEventKind.withdrawn, "Wird anders geloest.")
        assert reset == [alone]
        assert await w.status(alone) is CaseStatus.triaged
        assert await w.status(shared) is CaseStatus.in_progress
        row = await w.owner.fetchrow(
            "SELECT actor_kind, actor_id, measure_id, note FROM agent_case_event "
            "WHERE case_id = $1 ORDER BY created_at DESC, id DESC LIMIT 1",
            alone,
        )
        assert dict(row) == {
            "actor_kind": "system",
            "actor_id": None,
            "measure_id": measure_id,
            "note": "Wird anders geloest.",
        }
        assert await w.state(measure_id) is MeasureState.withdrawn
        with pytest.raises(ApiError) as again:
            await w.msvc.withdraw(w.editor, measure_id, "Nochmal.")
        assert again.value.params == {"state": "withdrawn", "action": "withdraw"}

        # Die zweite Massnahme zurueckziehen: jetzt haelt niemand `shared` mehr.
        _, reset_second = await w.msvc.withdraw(w.editor, second_id, "Auch weg.")
        assert reset_second == [shared]
        assert await w.status(shared) is CaseStatus.triaged

    _run(body)


# --- Kennzahlen (6.6, QE8 a) --------------------------------------------------------


def test_follow_up_figures_and_prepared_snapshot() -> None:
    async def body(w: _MWorld) -> None:
        s = w.seed
        persona_id, (v1, v2) = await w.persona()
        await w.owner.execute(
            "INSERT INTO status_history (entity_type, entity_id, version, from_status, "
            " to_status, changed_by, changed_at) "
            "VALUES ('persona', $1, 1, 'draft', 'active', $2, now() - interval '2 days')",
            persona_id,
            s.user,
        )
        measure_id, _ = await w.measure(entity_id=persona_id)
        measure = await w.repo.get_measure(s.ws_a, measure_id)
        assert measure is not None

        async def runs(version_id: UUID, rows: list[tuple[int, int, str, int]]) -> None:
            for total, passed, verdict, days_ago in rows:
                await w.owner.execute(
                    "INSERT INTO test_run (workspace_id, test_case_id, subject_entity_type, "
                    " subject_version_id, runs_total, runs_passed, verdict, attestation, "
                    " reported_by_agent_id, created_at) "
                    "VALUES ($1, $2, 'persona', $3, $4, $5, $6, 'client_self_report', $7, "
                    "        now() - make_interval(days => $8))",
                    s.ws_a,
                    measure.test_case_id,
                    version_id,
                    total,
                    passed,
                    verdict,
                    s.agent_a,
                    days_ago,
                )

        async def uses(version: int, count: int, source: str = "server") -> None:
            for _ in range(count):
                await w.owner.execute(
                    "INSERT INTO usage_event (workspace_id, agent_id, entity_type, entity_id, "
                    " version, source) VALUES ($1, $2, 'persona', $3, $4, $5)",
                    s.ws_a,
                    s.agent_a,
                    persona_id,
                    version,
                    source,
                )

        async def element_case(agent_id: UUID) -> UUID:
            case_id: UUID = await w.case(agent_id)
            await w.case_svc.set_elements(
                w.editor,
                case_id,
                [CaseElementInput(target=CaseTarget.persona, entity_id=persona_id)],
            )
            return case_id

        await runs(v1, [(3, 1, "fail", 1)])
        await runs(v2, [(3, 0, "fail", 2), (3, 3, "pass", 0)])
        await uses(1, 3)
        await uses(2, 2)
        await uses(2, 5, "agent_report")  # zaehlt nicht als Nutzung (3.4)
        await element_case(s.agent_a)  # vorher: im Fenster der alten Version

        await w.msvc.link_draft(w.editor, measure_id, "persona", v2)
        before_activation = await w.msvc.follow_up(w.editor, measure_id)
        assert before_activation.after is not None
        assert before_activation.after.cases is None
        assert before_activation.recurrence is None
        assert before_activation.insufficient is True

        await w.activate(measure_id, v2)
        await element_case(s.agent_a)  # Wiederauftreten beim besprochenen Agenten
        await element_case(s.agent_a2)  # nur Fallrate, kein Wiederauftreten

        report = await w.msvc.follow_up(w.editor, measure_id)
        assert report.state is MeasureState.activated
        assert report.reviewable is True
        assert report.before is not None and report.after is not None
        assert (report.before.version_id, report.before.version) == (v1, 1)
        assert (report.after.version_id, report.after.version) == (v2, 2)
        assert report.before.test_run is not None and report.after.test_run is not None
        assert (report.before.test_run.runs_passed, report.before.test_run.runs_total) == (1, 3)
        # Juengster Lauf zaehlt (3.2), nicht der aeltere fail-Lauf.
        assert (report.after.test_run.verdict, report.after.test_run.runs_passed) == ("pass", 3)
        assert (report.before.uses, report.after.uses) == (3, 2)
        assert (report.before.cases, report.after.cases) == (1, 2)
        assert report.recurrence == 1
        assert (report.min_uses, report.insufficient) == (FOLLOW_UP_MIN_USES, True)
        # Ein Mensch liest nur.
        assert await w.measure_events(measure_id) == ["draft_linked", "activated"]

        # Der Builder bereitet die Nachschau vor — genau einmal je Zahlenstand.
        prepared = await w.msvc.follow_up(w.builder, measure_id)
        assert prepared.state is MeasureState.follow_up_prepared
        await w.msvc.follow_up(w.builder, measure_id)
        events = await w.measure_events(measure_id)
        assert events == ["draft_linked", "activated", "follow_up_prepared"]
        metrics = await w.owner.fetchval(
            "SELECT metrics FROM measure_event WHERE measure_id = $1 "
            "AND event = 'follow_up_prepared'",
            measure_id,
        )
        assert '"recurrence": 1' in metrics
        await uses(2, FOLLOW_UP_MIN_USES)
        changed = await w.msvc.follow_up(w.builder, measure_id)
        assert changed.insufficient is False
        assert (await w.measure_events(measure_id)).count("follow_up_prepared") == 2
        # Nach follow_up_prepared bleibt die Einstufung moeglich.
        await w.msvc.review(w.editor, measure_id, MeasureVerdict.effective)

    _run(body)


# --- Sperre je Massnahme --------------------------------------------------------------


def test_concurrent_reviews_write_exactly_one_event() -> None:
    async def body(w: _MWorld) -> None:
        persona_id, (_, v2) = await w.persona()
        measure_id, _ = await w.measure(entity_id=persona_id)
        await w.msvc.link_draft(w.editor, measure_id, "persona", v2)
        await w.activate(measure_id, v2)

        # Beide Aufrufe haben die Massnahme gelesen, bevor einer schreibt. Mit
        # Sperre kommt der zweite nicht an die Barriere (er wartet auf die
        # Sperre); der erste laeuft nach dem Timeout weiter und schreibt.
        barrier = asyncio.Barrier(2)
        original = w.repo.lock_measure

        async def gated(conn: asyncpg.Connection, workspace_id: UUID, mid: UUID) -> object:
            locked = await original(conn, workspace_id, mid)
            try:
                await asyncio.wait_for(barrier.wait(), timeout=1.0)
            except (TimeoutError, asyncio.BrokenBarrierError):
                pass
            return locked

        w.repo.lock_measure = gated
        results = await asyncio.gather(
            w.msvc.review(w.editor, measure_id, MeasureVerdict.effective),
            w.msvc.review(w.editor, measure_id, MeasureVerdict.not_measurable),
            return_exceptions=True,
        )
        errors = [r for r in results if isinstance(r, BaseException)]
        assert len(errors) == 1
        assert isinstance(errors[0], ApiError)
        assert errors[0].reason == "measure_transition_forbidden"
        assert (await w.measure_events(measure_id)).count("reviewed") == 1

    _run(body)
