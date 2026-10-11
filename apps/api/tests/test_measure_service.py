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
- **Atomaritaet:** ein Fehler mitten in withdraw bzw. nach dem Insert in
  link-draft hinterlaesst weder Massnahmen- noch Fall-Events.
- **Fremder Workspace:** alle vier Aktionen -> 404 `measure_not_found`.

Ohne DB greift der zentrale Skip; mit `WHO2BE_REQUIRE_DB=1` schlaegt er hart fehl.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from datetime import date, timedelta
from typing import Any
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
from who2be_api.repositories.case_repository import apply_system_status
from who2be_api.repositories.session_repository import PgSessionRepository
from who2be_api.repositories.status_history_repository import PgStatusHistoryRepository
from who2be_api.services.case_service import CaseTransitionRequest
from who2be_api.services.measure_service import FOLLOW_UP_MIN_USES, MeasureService
from who2be_api.services.status_history_service import StatusHistoryService
from who2be_api.services.version_status import VersionStatusService
from who2be_models import (
    CaseActorKind,
    CaseElementInput,
    CaseEventKind,
    CaseStatus,
    CaseTarget,
    MeasureActorKind,
    MeasureEventCreate,
    MeasureEventKind,
    MeasureState,
    MeasureVerdict,
    VersionStatus,
    WorkspaceRole,
)

pytestmark = pytest.mark.integration


class _MWorld(_World):  # type: ignore[misc]  # _World kommt aus einem Testmodul (Any)
    """`_World` plus Massnahmen-Service mit fester Uhr und Persona-Versionen."""

    def __init__(self, repo: PgSessionRepository, pool: asyncpg.Pool, env: object) -> None:
        super().__init__(repo, pool, env)
        self.pool = pool
        self.today = _FOLLOW_UP - timedelta(days=1)
        self.msvc = MeasureService(repo, today=lambda: self.today)
        self.versions = VersionStatusService(
            pool, StatusHistoryService(PgStatusHistoryRepository())
        )
        # Promote verlangt `admin` (ADR-0023) mit zweitem Faktor.
        self.admin = WorkspaceContext(
            self.seed.ws_a, self.seed.user, WorkspaceRole.admin, aal="aal2"
        )

    async def to_review(self, persona_id: UUID, version: int) -> None:
        """Version direkt auf `review` (die Promote-Pflichtfelder sind hier nicht Thema)."""
        await self.owner.execute(
            "UPDATE persona_version SET status = 'review' WHERE persona_id = $1 AND version = $2",
            persona_id,
            version,
        )

    async def activate_version(
        self, persona_id: UUID, version: int, ctx: WorkspaceContext | None = None
    ) -> None:
        """`review -> active` ueber den echten Versions-Service (E3-Ausloeser)."""
        await self.versions.transition_persona_version(
            ctx or self.admin, persona_id, version, VersionStatus.active, None
        )

    async def case_events(self, case_id: UUID) -> list[dict[str, Any]]:
        rows = await self.owner.fetch(
            "SELECT event, actor_kind, actor_id, version_entity_type, version_id, measure_id, "
            "note FROM agent_case_event WHERE case_id = $1 "
            "AND event NOT IN ('reported', 'element_assigned', 'element_unassigned') "
            "ORDER BY created_at, id",
            case_id,
        )
        return [dict(r) for r in rows]

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


def test_unversioned_target_closed_is_not_reviewable_again() -> None:
    """Ohne Versionen entscheidet nur der Abschluss, nicht die Faelligkeit.

    Mutationsprobe: ohne die Pruefung auf abgeschlossene Zustaende in
    `is_reviewable` liesse sich die Massnahme nach Faelligkeit erneut
    einstufen bzw. nach withdraw noch einstufen.
    """

    async def body(w: _MWorld) -> None:
        reviewed, _ = await w.measure(target="tool_policy", entity_id=None)
        withdrawn, _ = await w.measure(target="tool_policy", entity_id=None)
        w.today = _FOLLOW_UP
        await w.msvc.review(w.editor, reviewed, MeasureVerdict.effective)
        with pytest.raises(ApiError) as again:
            await w.msvc.review(w.editor, reviewed, MeasureVerdict.not_measurable)
        assert (_reason(again), _code(again)) == ("measure_transition_forbidden", 409)

        await w.msvc.withdraw(w.editor, withdrawn, "weg")
        with pytest.raises(ApiError) as after_withdraw:
            await w.msvc.review(w.editor, withdrawn, MeasureVerdict.effective)
        assert (_reason(after_withdraw), _code(after_withdraw)) == (
            "measure_transition_forbidden",
            409,
        )
        assert (await w.msvc.follow_up(w.builder, reviewed)).reviewable is False
        assert (await w.msvc.follow_up(w.builder, withdrawn)).reviewable is False
        assert await w.measure_events(reviewed) == ["reviewed"]
        assert await w.measure_events(withdrawn) == ["withdrawn"]

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


def test_withdraw_leaves_cases_outside_in_progress_untouched() -> None:
    """Nur `in_progress` geht zurueck; ein inzwischen erledigter Fall bleibt.

    Mutationsprobe: ohne die Status-Pruefung in `reset_cases_after_withdraw`
    wird der verworfene Fall wieder `triaged` und dieser Test rot.
    """

    async def body(w: _MWorld) -> None:
        persona_id, _ = await w.persona()
        measure_id, (kept, done) = await w.measure(entity_id=persona_id, cases=2)
        await w.case_svc.transition(
            w.editor,
            done,
            CaseTransitionRequest(to=CaseStatus.dismissed, note="Kein Fehler des Agenten."),
        )
        assert await w.status(done) is CaseStatus.dismissed

        _, reset = await w.msvc.withdraw(w.editor, measure_id, "Wird anders geloest.")
        assert reset == [kept]
        assert await w.status(kept) is CaseStatus.triaged
        assert await w.status(done) is CaseStatus.dismissed

    _run(body)


# --- Atomaritaet -------------------------------------------------------------------


def test_withdraw_is_atomic_on_error_mid_transaction(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fehler nach dem Zuruecksetzen: weder `withdrawn` noch Fall-Events bleiben.

    Mutationsprobe: schreibt withdraw das Event ohne `conn=conn`, liegt es
    ausserhalb der Transaktion und `measure_events` ist nicht leer.
    """

    async def body(w: _MWorld) -> None:
        persona_id, _ = await w.persona()
        measure_id, cases = await w.measure(entity_id=persona_id, cases=2)
        original = w.repo.reset_cases_after_withdraw
        done: list[UUID] = []

        async def boom(
            conn: asyncpg.Connection,
            workspace_id: UUID,
            mid: UUID,
            case_ids: Sequence[UUID],
            *,
            note: str,
        ) -> list[UUID]:
            done.extend(await original(conn, workspace_id, mid, case_ids, note=note))
            raise RuntimeError("Fehler mitten in der Transaktion")

        monkeypatch.setattr(w.repo, "reset_cases_after_withdraw", boom)
        with pytest.raises(RuntimeError):
            await w.msvc.withdraw(w.editor, measure_id, "weg")
        assert sorted(done) == sorted(cases)  # beide waren in der Transaktion zurueckgesetzt
        assert await w.measure_events(measure_id) == []
        for case_id in cases:
            assert await w.status(case_id) is CaseStatus.in_progress

    _run(body)


def test_link_draft_is_atomic_on_error_after_insert(monkeypatch: pytest.MonkeyPatch) -> None:
    async def body(w: _MWorld) -> None:
        persona_id, (v1, _) = await w.persona()
        measure_id, _ = await w.measure(entity_id=persona_id)
        original = w.repo.append_measure_event

        async def boom(*args: Any, **kwargs: Any) -> None:
            await original(*args, **kwargs)
            raise RuntimeError("nach dem Insert")

        monkeypatch.setattr(w.repo, "append_measure_event", boom)
        with pytest.raises(RuntimeError):
            await w.msvc.link_draft(w.editor, measure_id, "persona", v1)
        assert await w.measure_events(measure_id) == []

    _run(body)


# --- Fremder Workspace ------------------------------------------------------------


def test_foreign_workspace_is_404_for_every_action() -> None:
    async def body(w: _MWorld) -> None:
        persona_id, (_, v2) = await w.persona()
        measure_id, _ = await w.measure(entity_id=persona_id)
        await w.msvc.link_draft(w.editor, measure_id, "persona", v2)
        await w.activate(measure_id, v2)
        other = WorkspaceContext(w.seed.ws_b, uuid4(), WorkspaceRole.editor)
        calls: list[Callable[[], Awaitable[object]]] = [
            lambda: w.msvc.link_draft(other, measure_id, "persona", v2),
            lambda: w.msvc.follow_up(other, measure_id),
            lambda: w.msvc.review(other, measure_id, MeasureVerdict.effective),
            lambda: w.msvc.withdraw(other, measure_id, "x"),
        ]
        for call in calls:
            with pytest.raises(ApiError) as exc:
                await call()
            assert (_reason(exc), _code(exc)) == ("measure_not_found", 404)
        assert await w.measure_events(measure_id) == ["draft_linked", "activated"]

    _run(body)


def test_link_draft_rejects_version_from_other_workspace() -> None:
    async def body(w: _MWorld) -> None:
        persona_id, _ = await w.persona()
        measure_id, _ = await w.measure(entity_id=persona_id)
        foreign_persona: UUID = await w.owner.fetchval(
            "INSERT INTO persona (workspace_id, owner_id, name) VALUES ($1, $2, $3) RETURNING id",
            w.seed.ws_b,
            w.seed.user,
            f"p-{uuid4().hex[:6]}",
        )
        foreign_version: UUID = await w.owner.fetchval(
            "INSERT INTO persona_version (persona_id, version, content, status, created_by) "
            "VALUES ($1, 1, '{}'::jsonb, 'draft', $2) RETURNING id",
            foreign_persona,
            w.seed.user,
        )
        with pytest.raises(ApiError) as exc:
            await w.msvc.link_draft(w.editor, measure_id, "persona", foreign_version)
        assert (_reason(exc), _code(exc)) == ("test_subject_version_not_found", 404)
        assert await w.measure_events(measure_id) == []

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


# --- Statusfolgen (E3, ADR-0053 3.3/3.6) -------------------------------------------


async def _activated_measure(w: _MWorld, cases: int = 1) -> tuple[UUID, list[UUID], UUID]:
    """Massnahme an Entwurf v2, v2 durch einen Menschen aktiviert (echter Pfad)."""
    persona_id, (_, v2) = await w.persona()
    measure_id, case_ids = await w.measure(entity_id=persona_id, cases=cases)
    await w.msvc.link_draft(w.editor, measure_id, "persona", v2)
    await w.to_review(persona_id, 2)
    await w.activate_version(persona_id, 2)
    return measure_id, case_ids, v2


def test_activation_writes_activated_and_addressed() -> None:
    """F3 a: aktiv durch einen Menschen -> `activated` + `addressed` (System).

    Mutationsprobe: ohne `_activate_measures` in `_transition` bleibt die
    Massnahme `draft_linked` und der Fall `in_progress`.
    """

    async def body(w: _MWorld) -> None:
        persona_id, (_, v2) = await w.persona()
        measure_id, (moved, done) = await w.measure(entity_id=persona_id, cases=2)
        await w.case_svc.transition(
            w.editor, done, CaseTransitionRequest(to=CaseStatus.dismissed, note="Kein Fehler.")
        )
        await w.msvc.link_draft(w.editor, measure_id, "persona", v2)
        await w.to_review(persona_id, 2)
        await w.activate_version(persona_id, 2)

        assert await w.measure_events(measure_id) == ["draft_linked", "activated"]
        activated = await w.owner.fetchrow(
            "SELECT actor_kind, actor_id, version_entity_type, version_id FROM measure_event "
            "WHERE measure_id = $1 AND event = 'activated'",
            measure_id,
        )
        assert dict(activated) == {
            "actor_kind": "system",
            "actor_id": None,
            "version_entity_type": "persona",
            "version_id": v2,
        }
        assert await w.state(measure_id) is MeasureState.activated
        assert await w.status(moved) is CaseStatus.addressed
        last = (await w.case_events(moved))[-1]
        assert last == {
            "event": "addressed",
            "actor_kind": CaseActorKind.system.value,
            "actor_id": None,
            "version_entity_type": "persona",
            "version_id": v2,
            "measure_id": measure_id,
            "note": None,
        }
        # `dismissed` bleibt unveraendert (Karte: addressed/verified/dismissed bleiben).
        assert await w.status(done) is CaseStatus.dismissed
        assert [e["event"] for e in await w.case_events(done)] == [
            "triaged",
            "in_progress",
            "dismissed",
        ]

    _run(body)


def test_activation_of_unlinked_or_superseded_version_changes_nothing() -> None:
    """Nur das JUENGSTE `draft_linked` zaehlt (QE4 a); andere Versionen loesen nichts aus."""

    async def body(w: _MWorld) -> None:
        persona_id, (_, _, v3) = await w.persona(versions=3)
        measure_id, (case_id,) = await w.measure(entity_id=persona_id)
        await w.msvc.link_draft(w.editor, measure_id, "persona", v3)
        # v2 ist `inactive`: zurueck auf review und aktiv — nicht verknuepft.
        await w.to_review(persona_id, 2)
        await w.owner.execute(
            "UPDATE persona_version SET status = 'inactive' WHERE persona_id = $1 AND version = 3",
            persona_id,
        )
        await w.activate_version(persona_id, 2)
        assert await w.measure_events(measure_id) == ["draft_linked"]
        assert await w.status(case_id) is CaseStatus.in_progress

    _run(body)


def test_activation_twice_writes_activated_once() -> None:
    """Eine schon aktivierte Massnahme loest bei erneuter Aktivierung nichts aus.

    Mutationsprobe: ohne die `draft_linked`-Pruefung in `_activate_measures`
    entsteht ein zweites `activated`.
    """

    async def body(w: _MWorld) -> None:
        measure_id, (case_id,), v2 = await _activated_measure(w)
        persona_id: UUID = await w.owner.fetchval(
            "SELECT persona_id FROM persona_version WHERE id = $1", v2
        )
        # v1 wieder aktiv (v2 inactive), dann v2 erneut ueber review aktiv.
        await w.owner.execute(
            "UPDATE persona_version SET status = 'inactive' WHERE persona_id = $1", persona_id
        )
        await w.to_review(persona_id, 2)
        await w.activate_version(persona_id, 2)
        assert (await w.measure_events(measure_id)).count("activated") == 1
        assert [e["event"] for e in await w.case_events(case_id)].count("addressed") == 1

    _run(body)


def test_system_status_goes_via_triage_only_with_element() -> None:
    """`open`/`reopened` -> `triaged` -> `addressed` nur mit Zuordnung (3.3)."""

    async def body(w: _MWorld) -> None:
        with_element = await w.case_in(CaseStatus.open)
        without = await w.case_in(CaseStatus.open, element=False)
        reopened = await w.case_in(CaseStatus.reopened)
        persona_id, (_, v2) = await w.persona()
        measure_id, _ = await w.measure(entity_id=persona_id)
        async with w.pool.acquire() as conn, conn.transaction():
            moved = await apply_system_status(
                conn,
                w.seed.ws_a,
                [without, with_element, reopened],
                event=CaseEventKind.addressed,
                sources=(CaseStatus.triaged, CaseStatus.in_progress),
                via_triage=(CaseStatus.open, CaseStatus.reopened),
                measure_id=measure_id,
                version_entity_type="persona",
                version_id=v2,
            )
        assert sorted(moved) == sorted([with_element, reopened])
        assert await w.status(with_element) is CaseStatus.addressed
        assert await w.status(reopened) is CaseStatus.addressed
        assert await w.status(without) is CaseStatus.open
        tail = [(e["event"], e["actor_kind"]) for e in await w.case_events(with_element)][-2:]
        assert tail == [("triaged", "system"), ("addressed", "system")]

    _run(body)


def test_review_effective_sets_verified() -> None:
    """Mutationsprobe: ohne `_REVIEW_CASE_EVENT` bleibt der Fall `addressed`."""

    async def body(w: _MWorld) -> None:
        measure_id, (case_id,), _ = await _activated_measure(w)
        assert await w.status(case_id) is CaseStatus.addressed
        await w.msvc.review(w.editor, measure_id, MeasureVerdict.effective)
        assert await w.status(case_id) is CaseStatus.verified
        last = (await w.case_events(case_id))[-1]
        assert (last["event"], last["actor_kind"], last["actor_id"], last["measure_id"]) == (
            "verified",
            "system",
            None,
            measure_id,
        )

    _run(body)


def test_review_ineffective_reopens_with_reason() -> None:
    async def body(w: _MWorld) -> None:
        measure_id, (case_id,), _ = await _activated_measure(w)
        await w.msvc.review(
            w.editor, measure_id, MeasureVerdict.ineffective, note="Frist fehlt weiter."
        )
        assert await w.status(case_id) is CaseStatus.reopened
        last = (await w.case_events(case_id))[-1]
        assert (last["event"], last["actor_kind"], last["note"], last["measure_id"]) == (
            "reopened",
            "system",
            "Frist fehlt weiter.",
            measure_id,
        )

    _run(body)


def test_review_not_measurable_and_cases_outside_addressed_stay() -> None:
    async def body(w: _MWorld) -> None:
        measure_id, (case_id,), _ = await _activated_measure(w)
        await w.msvc.review(w.editor, measure_id, MeasureVerdict.not_measurable)
        assert await w.status(case_id) is CaseStatus.addressed

        # Ein Fall, der nicht mehr `addressed` ist, bleibt auch bei `effective`.
        other_id, (reopened,), _ = await _activated_measure(w)
        await w.case_svc.transition(
            w.editor, reopened, CaseTransitionRequest(to=CaseStatus.reopened, note="Noch da.")
        )
        await w.msvc.review(w.editor, other_id, MeasureVerdict.effective)
        assert await w.status(reopened) is CaseStatus.reopened

    _run(body)


def test_manual_in_progress_needs_measure_holding_the_case() -> None:
    """PM-5: `in_progress` von Hand nur mit einer Massnahme, die den Fall enthaelt.

    Mutationsprobe: ohne `require_measure_case` geht die fremde Massnahme durch.
    """

    async def body(w: _MWorld) -> None:
        persona_id, _ = await w.persona()
        measure_id, (case_id,) = await w.measure(entity_id=persona_id)
        foreign_id, _ = await w.measure(entity_id=persona_id)
        # Zurueckziehen setzt den Fall auf `triaged`; die Verknuepfung bleibt.
        await w.msvc.withdraw(w.editor, measure_id, "Neu ansetzen.")
        assert await w.status(case_id) is CaseStatus.triaged

        for measure, params in (
            (None, {"missing": "measure"}),
            (foreign_id, {"invalid": "measure"}),
            (uuid4(), {"invalid": "measure"}),
        ):
            with pytest.raises(ApiError) as exc:
                await w.case_svc.transition(
                    w.editor,
                    case_id,
                    CaseTransitionRequest(to=CaseStatus.in_progress, measure_id=measure),
                )
            assert (_reason(exc), _code(exc)) == ("case_transition_forbidden", 409)
            assert exc.value.params is not None
            assert params.items() <= exc.value.params.items()
            assert await w.status(case_id) is CaseStatus.triaged

        updated = await w.case_svc.transition(
            w.editor,
            case_id,
            CaseTransitionRequest(to=CaseStatus.in_progress, measure_id=measure_id),
        )
        assert updated.status is CaseStatus.in_progress
        assert (await w.case_events(case_id))[-1]["measure_id"] == measure_id

    _run(body)


def test_verified_by_hand_is_409_and_agents_never_judge() -> None:
    """PM-5: `verified` nur per Einstufung; Agent-Tokens setzen nie addressed/verified."""

    async def body(w: _MWorld) -> None:
        _, (case_id,), _ = await _activated_measure(w)
        with pytest.raises(ApiError) as exc:
            await w.case_svc.transition(
                w.editor, case_id, CaseTransitionRequest(to=CaseStatus.verified)
            )
        assert (_reason(exc), _code(exc)) == ("case_transition_forbidden", 409)
        assert exc.value.params is not None and exc.value.params["requires"] == "review"
        for target in (CaseStatus.addressed, CaseStatus.verified):
            with pytest.raises(ApiGateError) as gate:
                await w.case_svc.transition(w.builder, case_id, CaseTransitionRequest(to=target))
            assert (gate.value.status, gate.value.reason) == (403, "case_transition_human_only")
        assert await w.status(case_id) is CaseStatus.addressed

    _run(body)
