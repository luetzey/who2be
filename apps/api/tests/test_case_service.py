"""Service-Tests fuer Faelle (ADR-0053 3.3, 6.5; Paket D2a).

Echte DB unter der Laufzeitrolle `who2be_app` (RLS aktiv), Repository aus
D1a, Mandant ueber `tenant_scope` (Fixture `_with_repo` aus
`test_agent_case_schema`). Belegt:

- **Kanten:** jede erlaubte Kante geht, jede andere endet mit
  `case_transition_forbidden` — von jedem Zustand aus, auch von den in D2
  nur per Repository erreichbaren `in_progress` und `verified`.
  `in_progress`/`verified` als Ziel: Phase E.
- **Pflichtfelder:** Begruendung bei `dismissed`/`reopened`, Version bei
  `addressed` (auch: Version aus fremdem Workspace), Zuordnung bei `triaged`.
- **Rechte je Rolle:** viewer, editor, Agent ohne und mit `case_triage`,
  betroffener und fremder Agent; Agent nie Richter (`is_agent_bound`).
- **Sichtbarkeit:** viewer nur selbst gemeldete, Agent ohne `case_triage`
  nur Faelle ueber sich; nicht lesbar = `case_not_found`.

Ohne DB greift der zentrale Skip; mit `WHO2BE_REQUIRE_DB=1` schlaegt er hart fehl.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
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
from who2be_api.repositories.case_repository import PgCaseRepository
from who2be_api.services.case_service import CaseService, CaseTransitionRequest
from who2be_models import (
    AgentToolPolicy,
    CaseActorKind,
    CaseAssignedByKind,
    CaseElementInput,
    CaseEventCreate,
    CaseEventKind,
    CaseReporterKind,
    CaseStatementCreate,
    CaseStatus,
    CaseTarget,
    WorkspaceRole,
)

pytestmark = pytest.mark.integration

# Erlaubte Kanten in D2 (3.3 plus Uebergangskante triaged -> addressed).
_ALLOWED: set[tuple[CaseStatus, CaseStatus]] = {
    (CaseStatus.open, CaseStatus.triaged),
    (CaseStatus.open, CaseStatus.dismissed),
    (CaseStatus.triaged, CaseStatus.addressed),
    (CaseStatus.triaged, CaseStatus.dismissed),
    (CaseStatus.in_progress, CaseStatus.addressed),
    (CaseStatus.in_progress, CaseStatus.dismissed),
    (CaseStatus.addressed, CaseStatus.reopened),
    (CaseStatus.reopened, CaseStatus.triaged),
}


class _World:
    """Kontexte und Helfer fuer einen Testlauf in Workspace A."""

    def __init__(self, repo: PgCaseRepository, env: object) -> None:
        self.repo = repo
        self.env = env
        seed = env.seed  # type: ignore[attr-defined]
        self.seed = seed
        self.owner: asyncpg.Connection = env.owner  # type: ignore[attr-defined]
        self.svc = CaseService(repo)
        ws = seed.ws_a
        self.viewer = WorkspaceContext(ws, uuid4(), WorkspaceRole.viewer)
        self.viewer2 = WorkspaceContext(ws, uuid4(), WorkspaceRole.viewer)
        self.editor = WorkspaceContext(ws, uuid4(), WorkspaceRole.editor)
        self.admin = WorkspaceContext(ws, uuid4(), WorkspaceRole.admin, aal="aal2")
        # Agent ohne case_triage (Default-Policy: feedback_write an).
        self.agent = self._agent(seed.agent_a, AgentToolPolicy())
        # Builder-artig: case_triage an, anderer Agent als `agent`.
        self.triage = self._agent(seed.agent_a2, AgentToolPolicy(case_triage=True))
        self.mute = self._agent(seed.agent_a, AgentToolPolicy(feedback_write=False))

    def _agent(self, agent_id: UUID, policy: AgentToolPolicy) -> WorkspaceContext:
        return WorkspaceContext(
            self.seed.ws_a,
            uuid4(),
            WorkspaceRole.editor,  # Snapshot-Rolle ist gedeckelt; massgeblich ist die Policy
            is_api_token=True,
            agent_id=agent_id,
            tool_policy=policy,
        )

    async def report(self, ctx: WorkspaceContext | None = None, agent: UUID | None = None) -> UUID:
        case = await self.svc.report_case(ctx or self.editor, _report(agent or self.seed.agent_a))
        return case.id

    async def persona_version(self, workspace_id: UUID | None = None) -> UUID:
        ws = workspace_id or self.seed.ws_a
        persona_id: UUID = await self.owner.fetchval(
            "INSERT INTO persona (workspace_id, owner_id, name) VALUES ($1, $2, $3) RETURNING id",
            ws,
            self.seed.user,
            f"p-{uuid4().hex[:6]}",
        )
        version_id: UUID = await self.owner.fetchval(
            "INSERT INTO persona_version (persona_id, version, content, status, created_by) "
            "VALUES ($1, 1, $2::jsonb, 'draft', $3) RETURNING id",
            persona_id,
            json.dumps({}),
            self.seed.user,
        )
        return version_id

    async def persona(self, workspace_id: UUID | None = None) -> UUID:
        persona_id: UUID = await self.owner.fetchval(
            "INSERT INTO persona (workspace_id, owner_id, name) VALUES ($1, $2, $3) RETURNING id",
            workspace_id or self.seed.ws_a,
            self.seed.user,
            f"p-{uuid4().hex[:6]}",
        )
        return persona_id

    async def model_limit(self, case_id: UUID) -> None:
        await self.svc.set_elements(
            self.editor, case_id, [CaseElementInput(target=CaseTarget.model_limit)]
        )

    def request(self, to: CaseStatus, version_id: UUID | None) -> CaseTransitionRequest:
        """Gueltige Pflichtfelder fuer `to` — Fehler kommen dann nur aus der Kante."""
        return CaseTransitionRequest(
            to=to,
            note="Begruendung" if to in (CaseStatus.dismissed, CaseStatus.reopened) else None,
            version_entity_type="persona" if to is CaseStatus.addressed else None,
            version_id=version_id if to is CaseStatus.addressed else None,
        )

    async def case_in(self, state: CaseStatus) -> UUID:
        """Fall im Zustand `state`, mit `model_limit`-Zuordnung.

        `in_progress` und `verified` sind ueber den Service in D2 nicht
        erreichbar und werden per Repository gesetzt (Massnahme = Platzhalter).
        """
        case_id = await self.report()
        await self.model_limit(case_id)
        version = await self.persona_version()
        path: dict[CaseStatus, list[CaseStatus]] = {
            CaseStatus.open: [],
            CaseStatus.triaged: [CaseStatus.triaged],
            CaseStatus.addressed: [CaseStatus.triaged, CaseStatus.addressed],
            CaseStatus.reopened: [CaseStatus.triaged, CaseStatus.addressed, CaseStatus.reopened],
            CaseStatus.dismissed: [CaseStatus.dismissed],
        }
        if state in (CaseStatus.in_progress, CaseStatus.verified):
            await self.svc.transition(self.editor, case_id, self.request(CaseStatus.triaged, None))
            await self.repo.append_event(
                self.seed.ws_a,
                case_id,
                CaseEventCreate(event=CaseEventKind(state.value), measure_id=uuid4()),
                actor_kind=CaseActorKind.human,
                actor_id=self.editor.user_id,
            )
            return case_id
        for step in path[state]:
            await self.svc.transition(self.editor, case_id, self.request(step, version))
        return case_id


def _run(body: Callable[[_World], Awaitable[None]]) -> None:
    async def outer(repo: PgCaseRepository, env: object) -> None:
        await body(_World(repo, env))

    _with_repo(outer)


async def _status(w: _World, case_id: UUID) -> CaseStatus:
    case = await w.repo.get_case(w.seed.ws_a, case_id)
    assert case is not None
    return case.status


# --- Melden ----------------------------------------------------------------


def test_report_rights_and_reporter_kind() -> None:
    async def body(w: _World) -> None:
        s = w.seed
        human = await w.svc.report_case(w.viewer, _report(s.agent_a))
        assert human.reporter_kind is CaseReporterKind.human
        assert (human.reporter_user_id, human.reporter_agent_id) == (w.viewer.user_id, None)
        assert human.status is CaseStatus.open

        # Agent meldet einen ANDEREN Agenten des Workspace (F2 = a).
        other = await w.svc.report_case(w.agent, _report(s.agent_a2))
        assert other.reporter_kind is CaseReporterKind.agent
        assert (other.reporter_user_id, other.reporter_agent_id) == (None, s.agent_a)
        assert other.agent_id == s.agent_a2

        builder = await w.svc.report_case(w.triage, _report(s.agent_a))
        assert builder.reporter_kind is CaseReporterKind.builder

        with pytest.raises(ApiGateError) as gate:
            await w.svc.report_case(w.mute, _report(s.agent_a))
        assert gate.value.reason == "missing_capability"

        for agent_id in (uuid4(), s.agent_b):  # unbekannt / fremder Workspace
            with pytest.raises(ApiError) as err:
                await w.svc.report_case(w.viewer, _report(agent_id))
            assert err.value.reason == "agent_not_found"

    _run(body)


# --- Lesen -----------------------------------------------------------------


def test_read_visibility_per_role() -> None:
    async def body(w: _World) -> None:
        s = w.seed
        mine = await w.report(w.viewer, s.agent_a)
        theirs = await w.report(w.viewer2, s.agent_a2)
        by_agent = await w.report(w.agent, s.agent_a2)

        # viewer: nur selbst gemeldete — Liste, Zaehler, Detail.
        assert [c.id for c in await w.svc.list_cases(w.viewer)] == [mine]
        assert sum((await w.svc.count_by_status(w.viewer)).values()) == 1
        assert (await w.svc.get_case(w.viewer, mine)).case.id == mine
        for hidden in (theirs, by_agent):
            with pytest.raises(ApiError) as err:
                await w.svc.get_case(w.viewer, hidden)
            assert err.value.reason == "case_not_found"
        # Ein agent_id-Filter erweitert die Sicht nicht.
        assert await w.svc.list_cases(w.viewer, agent_id=s.agent_a2) == []

        # editor und admin: alle.
        for ctx in (w.editor, w.admin):
            assert {c.id for c in await w.svc.list_cases(ctx)} == {mine, theirs, by_agent}
            assert sum((await w.svc.count_by_status(ctx)).values()) == 3

        # Agent ohne case_triage: Faelle ueber sich selbst (agent_a).
        assert [c.id for c in await w.svc.list_cases(w.agent)] == [mine]
        assert (await w.svc.get_case(w.agent, mine)).case.id == mine
        with pytest.raises(ApiError) as err:
            await w.svc.get_case(w.agent, by_agent)  # selbst gemeldet, aber ueber agent_a2
        assert err.value.reason == "case_not_found"
        with pytest.raises(ApiGateError) as gate:
            await w.svc.list_cases(w.agent, agent_id=s.agent_a2)
        assert gate.value.reason == "missing_capability"
        with pytest.raises(ApiGateError) as gate:
            await w.svc.count_by_status(w.agent, agent_id=s.agent_a2)
        assert gate.value.reason == "missing_capability"

        # Agent mit case_triage: alle, Filter wirkt.
        assert {c.id for c in await w.svc.list_cases(w.triage)} == {mine, theirs, by_agent}
        assert {c.id for c in await w.svc.list_cases(w.triage, agent_id=s.agent_a2)} == {
            theirs,
            by_agent,
        }

        with pytest.raises(ApiError) as err:
            await w.svc.get_case(w.editor, uuid4())
        assert err.value.reason == "case_not_found"

    _run(body)


# --- Kanten ----------------------------------------------------------------


def test_every_allowed_edge() -> None:
    async def body(w: _World) -> None:
        version = await w.persona_version()
        for source, target in sorted(_ALLOWED):
            case_id = await w.case_in(source)
            assert await _status(w, case_id) is source
            updated = await w.svc.transition(w.editor, case_id, w.request(target, version))
            assert updated.status is target, (source, target)
            last = (await w.svc.get_case(w.editor, case_id)).events[-1]
            assert last.event.value == target.value
            assert (last.actor_kind, last.actor_id) == (CaseActorKind.human, w.editor.user_id)
            if target is CaseStatus.addressed:
                assert (last.version_entity_type, last.version_id) == ("persona", version)

    _run(body)


def test_every_forbidden_edge() -> None:
    async def body(w: _World) -> None:
        version = await w.persona_version()
        checked = 0
        for source in CaseStatus:
            case_id = await w.case_in(source)
            for target in CaseStatus:
                if (source, target) in _ALLOWED:
                    continue
                with pytest.raises(ApiError) as err:
                    await w.svc.transition(w.editor, case_id, w.request(target, version))
                assert err.value.reason == "case_transition_forbidden", (source, target)
                assert err.value.status_code == 409
                assert err.value.params is not None
                assert err.value.params["from"] == source.value
                assert err.value.params["to"] == target.value
                if target in (CaseStatus.in_progress, CaseStatus.verified):
                    assert err.value.params["requires"] == "phase_e"
                assert await _status(w, case_id) is source  # nichts geschrieben
                checked += 1
        assert checked == len(CaseStatus) ** 2 - len(_ALLOWED)

    _run(body)


# --- Pflichtfelder ---------------------------------------------------------


def test_required_fields_per_transition() -> None:
    async def body(w: _World) -> None:
        s = w.seed

        async def refused(case_id: UUID, req: CaseTransitionRequest) -> ApiError:
            with pytest.raises(ApiError) as err:
                await w.svc.transition(w.editor, case_id, req)
            return err.value

        # triaged ohne Zuordnung.
        bare = await w.report()
        err = await refused(bare, CaseTransitionRequest(to=CaseStatus.triaged))
        assert (err.reason, err.params and err.params["missing"]) == (
            "case_transition_forbidden",
            "element",
        )
        assert await _status(w, bare) is CaseStatus.open
        # ... mit einem Element (nicht model_limit) geht es.
        await w.svc.set_elements(
            w.editor,
            bare,
            [CaseElementInput(target=CaseTarget.persona, entity_id=await w.persona())],
        )
        await w.svc.transition(w.editor, bare, CaseTransitionRequest(to=CaseStatus.triaged))
        assert await _status(w, bare) is CaseStatus.triaged
        # Zuordnung wieder leeren: reopened -> triaged verlangt sie erneut.
        version = await w.persona_version()
        await w.svc.transition(w.editor, bare, w.request(CaseStatus.addressed, version))
        await w.svc.transition(w.editor, bare, w.request(CaseStatus.reopened, None))
        await w.svc.set_elements(w.editor, bare, [])
        err = await refused(bare, CaseTransitionRequest(to=CaseStatus.triaged))
        assert err.params is not None and err.params["missing"] == "element"

        # dismissed und reopened ohne Begruendung.
        fresh = await w.report()
        err = await refused(fresh, CaseTransitionRequest(to=CaseStatus.dismissed))
        assert err.params is not None and err.params["missing"] == "note"
        addressed = await w.case_in(CaseStatus.addressed)
        err = await refused(addressed, CaseTransitionRequest(to=CaseStatus.reopened))
        assert err.params is not None and err.params["missing"] == "note"

        # addressed ohne Version, mit fremder und mit unbekannter Version.
        triaged = await w.case_in(CaseStatus.triaged)
        err = await refused(triaged, CaseTransitionRequest(to=CaseStatus.addressed))
        assert err.params is not None and err.params["missing"] == "version"
        for foreign in (await w.persona_version(s.ws_b), uuid4()):
            err = await refused(
                triaged,
                CaseTransitionRequest(
                    to=CaseStatus.addressed, version_entity_type="persona", version_id=foreign
                ),
            )
            assert err.reason == "entity_version_not_found"
        # Version nur bei addressed.
        err = await refused(
            triaged,
            CaseTransitionRequest(
                to=CaseStatus.dismissed,
                note="x",
                version_entity_type="persona",
                version_id=await w.persona_version(),
            ),
        )
        assert err.params is not None and err.params["unexpected"] == "version"
        # Eine Massnahme gibt es in D2 nicht, auch nicht als Beigabe.
        err = await refused(
            triaged, CaseTransitionRequest(to=CaseStatus.dismissed, note="x", measure_id=uuid4())
        )
        assert err.params is not None and err.params["requires"] == "phase_e"
        assert await _status(w, triaged) is CaseStatus.triaged

    _run(body)


# --- Rechte an Uebergaengen ------------------------------------------------


def test_transition_rights_per_role() -> None:
    async def body(w: _World) -> None:
        s = w.seed
        # viewer: auch am eigenen Fall nicht.
        own = await w.report(w.viewer)
        await w.model_limit(own)
        with pytest.raises(ApiGateError) as gate:
            await w.svc.transition(w.viewer, own, CaseTransitionRequest(to=CaseStatus.triaged))
        assert gate.value.reason == "insufficient_role"

        # Agent ohne case_triage: am Fall ueber sich lesbar, aber nicht triagierbar.
        with pytest.raises(ApiGateError) as gate:
            await w.svc.transition(w.agent, own, CaseTransitionRequest(to=CaseStatus.triaged))
        assert gate.value.reason == "missing_capability"
        # ... an einem Fall ueber einen anderen Agenten gibt es ihn nicht.
        foreign = await w.report(agent=s.agent_a2)
        with pytest.raises(ApiError) as err:
            await w.svc.transition(w.agent, foreign, CaseTransitionRequest(to=CaseStatus.triaged))
        assert err.value.reason == "case_not_found"

        # Agent mit case_triage triagiert, Akteur ist der Agent.
        updated = await w.svc.transition(
            w.triage, own, CaseTransitionRequest(to=CaseStatus.triaged)
        )
        assert updated.status is CaseStatus.triaged
        last = (await w.svc.get_case(w.editor, own)).events[-1]
        assert (last.actor_kind, last.actor_id) == (CaseActorKind.agent, s.agent_a2)

        # Partei, nicht Richter: auch mit case_triage nie addressed/verified/
        # dismissed/reopened — unabhaengig von Status und Pflichtfeldern.
        version = await w.persona_version()
        for source in (CaseStatus.open, CaseStatus.triaged, CaseStatus.addressed):
            case_id = await w.case_in(source)
            for target in (
                CaseStatus.addressed,
                CaseStatus.verified,
                CaseStatus.dismissed,
                CaseStatus.reopened,
            ):
                for ctx in (w.triage, w.agent):
                    with pytest.raises(ApiGateError) as gate:
                        await w.svc.transition(ctx, case_id, w.request(target, version))
                    assert gate.value.reason == "case_transition_human_only", (source, target)
                    assert gate.value.status == 403
                assert await _status(w, case_id) is source

    _run(body)


# --- Zuordnung -------------------------------------------------------------


def test_elements_rights_and_existence() -> None:
    async def body(w: _World) -> None:
        s = w.seed
        case_id = await w.report(w.viewer)
        persona = await w.persona()
        lesson = await _insert_lesson(w.owner, s.ws_a, s.agent_a)

        elements = await w.svc.set_elements(
            w.editor,
            case_id,
            [
                CaseElementInput(target=CaseTarget.persona, entity_id=persona),
                CaseElementInput(target=CaseTarget.memory, entity_id=lesson),
                CaseElementInput(target=CaseTarget.tool_policy),
            ],
        )
        assert {e.target for e in elements} == {
            CaseTarget.persona,
            CaseTarget.memory,
            CaseTarget.tool_policy,
        }
        assert {e.assigned_by_kind for e in elements} == {CaseAssignedByKind.human}

        replaced = await w.svc.set_elements(
            w.triage, case_id, [CaseElementInput(target=CaseTarget.model_limit)]
        )
        assert [(e.target, e.assigned_by_kind, e.assigned_by) for e in replaced] == [
            (CaseTarget.model_limit, CaseAssignedByKind.agent, s.agent_a2)
        ]

        missing = [
            (CaseTarget.persona, uuid4(), "persona_not_found"),
            (CaseTarget.persona, await w.persona(s.ws_b), "persona_not_found"),
            (CaseTarget.playbook, uuid4(), "playbook_not_found"),
            (CaseTarget.resource, uuid4(), "resource_not_found"),
            (CaseTarget.external_tool, uuid4(), "external_tool_not_found"),
            (CaseTarget.system_prompt_template, uuid4(), "system_prompt_template_not_found"),
            (CaseTarget.memory, uuid4(), "memory_not_found"),
        ]
        for target, entity_id, reason in missing:
            with pytest.raises(ApiError) as err:
                await w.svc.set_elements(
                    w.editor, case_id, [CaseElementInput(target=target, entity_id=entity_id)]
                )
            assert err.value.reason == reason
        # Nichts ersetzt: die Zuordnung steht wie zuvor.
        detail = await w.svc.get_case(w.editor, case_id)
        assert [e.target for e in detail.elements] == [CaseTarget.model_limit]

        with pytest.raises(ApiGateError) as gate:
            await w.svc.set_elements(w.viewer, case_id, [])
        assert gate.value.reason == "insufficient_role"
        with pytest.raises(ApiGateError) as gate:
            await w.svc.set_elements(w.agent, case_id, [])
        assert gate.value.reason == "missing_capability"
        with pytest.raises(ApiError) as err:
            await w.svc.set_elements(w.viewer2, case_id, [])
        assert err.value.reason == "case_not_found"

    _run(body)


# --- Schilderung -----------------------------------------------------------


def test_statement_only_by_subject_append_only() -> None:
    async def body(w: _World) -> None:
        s = w.seed
        case_id = await w.report(agent=s.agent_a)
        text = CaseStatementCreate(
            followed_instruction="Playbook Kuendigung", missing_information="Frist", conflict=""
        )
        first = await w.svc.add_statement(w.agent, case_id, text)
        second = await w.svc.add_statement(w.agent, case_id, text)
        assert first.agent_id == s.agent_a
        detail = await w.svc.get_case(w.editor, case_id)
        assert [st.id for st in detail.statements] == [second.id, first.id]  # neueste zuerst
        assert sum(e.event is CaseEventKind.statement for e in detail.events) == 2

        # Fremder Agent (liest dank case_triage, ist aber nicht betroffen),
        # Mensch: nie.
        for ctx in (w.triage, w.editor, w.admin):
            with pytest.raises(ApiGateError) as gate:
                await w.svc.add_statement(ctx, case_id, text)
            assert gate.value.reason == "case_statement_not_subject"
        # Fremder Agent ohne case_triage sieht den Fall nicht.
        other = await w.report(agent=s.agent_a2)
        with pytest.raises(ApiError) as err:
            await w.svc.add_statement(w.agent, other, text)
        assert err.value.reason == "case_not_found"

    _run(body)


# --- Loeschen --------------------------------------------------------------


def test_delete_rights_reuses_d1b_purge() -> None:
    async def body(w: _World) -> None:
        s = w.seed
        case_id = await w.report()
        await _insert_lesson(w.owner, s.ws_a, s.agent_a, converted_case_id=case_id)

        with pytest.raises(ApiGateError) as gate:
            await w.svc.delete_case(w.viewer, case_id)
        assert gate.value.reason == "insufficient_role"
        for ctx in (w.agent, w.triage):
            with pytest.raises(ApiGateError) as gate:
                await w.svc.delete_case(ctx, case_id)
            assert (gate.value.reason, gate.value.actionable_by) == ("missing_capability", "none")

        await w.svc.delete_case(w.editor, case_id)  # trotz umgewandeltem Lernvorschlag
        assert await w.repo.get_case(s.ws_a, case_id) is None
        with pytest.raises(ApiError) as err:
            await w.svc.delete_case(w.editor, case_id)
        assert err.value.reason == "case_not_found"

    _run(body)


# --- Nebenlaeufigkeit ------------------------------------------------------


def test_append_transition_rechecks_under_lock() -> None:
    """Der Repo-Schritt prueft Ausgangsstatus und Zuordnung erneut (Check-then-act)."""

    async def body(w: _World) -> None:
        s = w.seed
        case_id = await w.report()
        triaged = CaseEventCreate(event=CaseEventKind.triaged)
        kwargs = {"actor_kind": CaseActorKind.human, "actor_id": w.editor.user_id}
        # Zuordnung fehlt -> nichts geschrieben.
        assert (
            await w.repo.append_transition(
                s.ws_a,
                case_id,
                triaged,
                expected_status=CaseStatus.open,
                require_element=True,
                **kwargs,  # type: ignore[arg-type]
            )
            is None
        )
        await w.model_limit(case_id)
        # Veralteter Ausgangsstatus -> nichts geschrieben.
        assert (
            await w.repo.append_transition(
                s.ws_a,
                case_id,
                triaged,
                expected_status=CaseStatus.reopened,
                require_element=True,
                **kwargs,  # type: ignore[arg-type]
            )
            is None
        )
        assert await _status(w, case_id) is CaseStatus.open
        assert (
            await w.repo.append_transition(
                s.ws_a,
                case_id,
                triaged,
                expected_status=CaseStatus.open,
                require_element=True,
                **kwargs,  # type: ignore[arg-type]
            )
            is not None
        )
        assert await _status(w, case_id) is CaseStatus.triaged
        assert (
            await w.repo.append_transition(
                s.ws_a,
                uuid4(),
                triaged,
                expected_status=CaseStatus.open,
                require_element=False,
                **kwargs,  # type: ignore[arg-type]
            )
            is None
        )

    _run(body)
