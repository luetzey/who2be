"""Mustererkennung (ADR-0053 3.7, Lernschleife Phase D, Paket D5a).

Echte DB unter der Laufzeitrolle `who2be_app` (RLS aktiv), Fixture
`_with_repo` aus `test_agent_case_schema`. Die Fixtures liegen jeweils
*zwischen* den Grenzen, damit eine verschobene Grenze rot wird:

- **Fall-Muster:** n-1 Faelle kein Muster, n Faelle ein Muster; ein Fall vor
  31 Tagen zaehlt nicht, einer vor 29 Tagen schon; abgeschlossene Faelle
  (`addressed`, `verified`, `dismissed`) zaehlen nicht, `triaged`,
  `in_progress` und `reopened` schon; anderer Agent oder anderes Element
  trennt; ein Fall mit zwei Zuordnungen zaehlt fuer beide.
- **Lernvorschlags-Muster:** Zaehler n-1 kein Muster, n ein Muster; zwei
  aehnliche Eintraege bilden ein Cluster, zwei unaehnliche nicht (Trigram-
  und Vektor-Zweig); `converted`/`rejected` zaehlen nicht als `pending`;
  andere Arten und das Nutzergedaechtnis fliessen nie ein.
- **Rechte:** Mensch ab `editor`, Agent-Token mit `case_triage` (6.5).

Ohne DB greift der zentrale Skip; mit `WHO2BE_REQUIRE_DB=1` schlaegt er hart fehl.
"""

from __future__ import annotations

import secrets
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest
from test_agent_case_schema import (  # type: ignore[import-not-found]
    _APP_PASSWORD,
    _insert_case,
    _insert_element,
    _insert_event,
    _with_repo,
)

from who2be_api.core.config import get_settings
from who2be_api.core.db import init_connection
from who2be_api.core.errors import ApiGateError
from who2be_api.core.security import WorkspaceContext
from who2be_api.core.tenancy import apply_tenant_settings
from who2be_api.repositories.case_repository import PgCaseRepository
from who2be_api.repositories.memory_repository import (
    MEMORY_DEDUP_SIMILARITY,
    PgMemoryRepository,
    reset_vector_support,
)
from who2be_api.services.pattern_service import PatternService
from who2be_models import AgentToolPolicy, CaseTarget, WorkspaceRole
from who2be_models.pattern import (
    PATTERN_CASE_WINDOW_DAYS,
    PATTERN_MIN_COUNT,
    Pattern,
    PatternElement,
    PatternSource,
)

pytestmark = pytest.mark.integration

_N = PATTERN_MIN_COUNT
_DIMS = 384

# Texte rund um die Schwelle der Dublettenpruefung (0,6). Gegen pg_trgm
# gemessen, im Test `test_texts_straddle_the_dedup_threshold` erneut belegt:
# _NEAR_HIT ~0,61 (knapp darueber), _NEAR_MISS ~0,48 (knapp darunter),
# _UNRELATED ~0,05.
_SIMILAR_A = "Nennt bei Kuendigungsfragen keine Frist aus dem Playbook"
_SIMILAR_B = "Nennt bei Kuendigungsfragen keine Frist aus dem Playbook Kuendigung"
_NEAR_HIT = "Nennt bei Kuendigungsfragen nie eine Frist"
_NEAR_MISS = "Nennt bei Widerrufsfragen keine Frist aus dem Handbuch"
_UNRELATED = "Antwortet auf Englisch, obwohl der Nutzer Deutsch schreibt"


class _World:
    def __init__(self, repo: PgCaseRepository, env: Any) -> None:
        self.seed = env.seed
        self.owner: asyncpg.Connection = env.owner
        self.memories = PgMemoryRepository(repo._pool)  # noqa: SLF001 — derselbe App-Pool
        self.svc = PatternService(repo, self.memories)
        ws = self.seed.ws_a
        self.editor = WorkspaceContext(ws, uuid4(), WorkspaceRole.editor)
        self.viewer = WorkspaceContext(ws, uuid4(), WorkspaceRole.viewer)
        self.agent = self._agent(AgentToolPolicy())
        self.triage = self._agent(AgentToolPolicy(case_triage=True))
        self.no_policy = WorkspaceContext(
            ws, uuid4(), WorkspaceRole.admin, is_api_token=True, agent_id=self.seed.agent_a
        )
        self.persona = uuid4()
        self.playbook = uuid4()

    def _agent(self, policy: AgentToolPolicy) -> WorkspaceContext:
        return WorkspaceContext(
            self.seed.ws_a,
            uuid4(),
            WorkspaceRole.admin,
            is_api_token=True,
            agent_id=self.seed.agent_a,
            tool_policy=policy,
        )

    async def case(
        self,
        *,
        agent_id: UUID | None = None,
        days_ago: float = 1,
        elements: tuple[tuple[CaseTarget, UUID | None], ...] | None = None,
        status_event: str | None = None,
        workspace_id: UUID | None = None,
    ) -> UUID:
        """Fall mit `reported`, Zuordnung und optional einem Status-Event."""
        ws = workspace_id or self.seed.ws_a
        agent = agent_id or self.seed.agent_a
        case_id: UUID = await _insert_case(
            self.owner,
            ws,
            agent,
            created_at=await self.owner.fetchval(
                "SELECT now() - make_interval(secs => $1)", days_ago * 86_400
            ),
        )
        await _insert_event(self.owner, ws, case_id, "reported", actor_kind="agent", actor_id=agent)
        if elements is None:
            elements = ((CaseTarget.persona, self.persona),)
        for target, entity_id in elements:
            await _insert_element(self.owner, ws, case_id, target.value, entity_id)
        if status_event is not None:
            extra: dict[str, object] = {}
            if status_event in ("dismissed", "reopened"):
                extra["note"] = "Begruendung"
            if status_event == "addressed":
                extra.update(version_entity_type="persona", version_id=uuid4())
            if status_event in ("in_progress", "verified"):
                extra["measure_id"] = uuid4()
            await _insert_event(self.owner, ws, case_id, status_event, **extra)
        return case_id

    async def lesson(
        self,
        fact: str,
        *,
        occurrences: int = 1,
        status: str = "pending",
        kind: str = "lesson",
        agent_id: UUID | None = None,
    ) -> UUID:
        converted: UUID | None = None
        agent = agent_id or self.seed.agent_a
        if status == "converted":
            converted = await self.case(agent_id=agent, elements=())
        memory_id: UUID = await self.owner.fetchval(
            "INSERT INTO agent_memory (workspace_id, agent_id, status, fact, kind, scope, "
            " created_by_agent_id, converted_case_id, origin, source, occurrence_count) "
            "VALUES ($1, $2, $3, $4, $5, 'agent', $2, $6, 'inferred', 'agent', $7) RETURNING id",
            self.seed.ws_a,
            agent,
            status,
            fact,
            kind,
            converted,
            occurrences,
        )
        return memory_id

    async def patterns(self, agent_id: UUID | None = None) -> list[Pattern]:
        return await self.svc.list_patterns(self.editor, agent_id=agent_id)

    async def case_patterns(self) -> list[Pattern]:
        return [p for p in await self.patterns() if p.source is PatternSource.case]

    async def lesson_patterns(self) -> list[Pattern]:
        return [p for p in await self.patterns() if p.source is PatternSource.lesson]


def _run(body: Callable[[_World], Awaitable[None]]) -> None:
    """Wie `_with_repo`, aber mit `public` im search_path.

    `pg_trgm` (`similarity`) und pgvector (`<=>`) liegen in `public`, nicht im
    isolierten Schema — dieselbe Loesung wie `test_memory_v2_schema`.
    """

    async def outer(_repo: PgCaseRepository, env: Any) -> None:
        reset_vector_support()
        await env.owner.execute(f'SET search_path TO "{env.seed.schema}", public')
        pool = await asyncpg.create_pool(
            get_settings().database_url,
            user="who2be_app",
            password=_APP_PASSWORD,
            min_size=1,
            max_size=2,
            init=init_connection,
            setup=apply_tenant_settings,
            server_settings={"search_path": f"{env.seed.schema},public"},
        )
        assert pool is not None
        try:
            await body(_World(PgCaseRepository(pool), env))
        finally:
            await pool.close()
            reset_vector_support()

    _with_repo(outer)


def _unit(axis: int) -> list[float]:
    vector = [0.0] * _DIMS
    vector[axis] = 1.0
    return vector


# --- Fall-Muster -----------------------------------------------------------------


def test_case_threshold_n_minus_one_none_n_one() -> None:
    async def body(w: _World) -> None:
        ids = [await w.case() for _ in range(_N - 1)]
        assert await w.case_patterns() == []

        ids.append(await w.case())
        [pattern] = await w.case_patterns()
        assert pattern.source is PatternSource.case
        assert pattern.agent_id == w.seed.agent_a
        assert pattern.element == PatternElement(target=CaseTarget.persona, entity_id=w.persona)
        assert pattern.count == _N
        assert pattern.evidence_ids == sorted(ids)
        assert pattern.first_seen <= pattern.last_seen

    _run(body)


def test_case_window_31_days_out_29_days_in() -> None:
    async def body(w: _World) -> None:
        assert PATTERN_CASE_WINDOW_DAYS == 30
        for _ in range(_N - 1):
            await w.case()
        old = await w.case(days_ago=31)
        assert await w.case_patterns() == []

        recent = await w.case(days_ago=29)
        [pattern] = await w.case_patterns()
        assert recent in pattern.evidence_ids
        assert old not in pattern.evidence_ids
        assert pattern.count == _N

    _run(body)


@pytest.mark.parametrize("closed", ["addressed", "verified", "dismissed"])
def test_closed_cases_do_not_count(closed: str) -> None:
    async def body(w: _World) -> None:
        for _ in range(_N - 1):
            await w.case()
        await w.case(status_event=closed)
        assert await w.case_patterns() == []

    _run(body)


@pytest.mark.parametrize("still_open", ["triaged", "in_progress", "reopened"])
def test_unfinished_cases_count_as_open(still_open: str) -> None:
    async def body(w: _World) -> None:
        for _ in range(_N - 1):
            await w.case()
        counted = await w.case(status_event=still_open)
        [pattern] = await w.case_patterns()
        assert counted in pattern.evidence_ids

    _run(body)


def test_case_groups_by_agent_and_by_element() -> None:
    async def body(w: _World) -> None:
        # Je Gruppe n-1: nur wer Agent ODER Element ignoriert, sieht ein Muster.
        for _ in range(_N - 1):
            await w.case()
        await w.case(agent_id=w.seed.agent_a2)
        await w.case(elements=((CaseTarget.playbook, w.playbook),))
        await w.case(elements=((CaseTarget.persona, uuid4()),))
        assert await w.case_patterns() == []

    _run(body)


def test_case_with_two_elements_counts_for_both_and_null_entity_groups() -> None:
    async def body(w: _World) -> None:
        both = ((CaseTarget.persona, w.persona), (CaseTarget.model_limit, None))
        for _ in range(_N):
            await w.case(elements=both)
        patterns = await w.case_patterns()
        assert [p.element for p in patterns] == [
            PatternElement(target=CaseTarget.model_limit, entity_id=None),
            PatternElement(target=CaseTarget.persona, entity_id=w.persona),
        ]
        assert all(p.count == _N for p in patterns)

        # Ohne Zuordnung kein Fall-Muster (3.7: „gleiche Element-Zuordnung“).
        for _ in range(_N):
            await w.case(agent_id=w.seed.agent_a2, elements=())
        assert len(await w.case_patterns()) == 2

    _run(body)


def test_case_patterns_stay_in_workspace_and_filter_by_agent() -> None:
    async def body(w: _World) -> None:
        for _ in range(_N):
            await w.case(workspace_id=w.seed.ws_b, agent_id=w.seed.agent_b)
        assert await w.case_patterns() == []

        for _ in range(_N):
            await w.case(agent_id=w.seed.agent_a2)
        assert len(await w.patterns(agent_id=w.seed.agent_a2)) == 1
        assert await w.patterns(agent_id=w.seed.agent_a) == []

    _run(body)


# --- Lernvorschlags-Muster -------------------------------------------------------


def test_texts_straddle_the_dedup_threshold() -> None:
    """Die Fixture-Texte liegen tatsaechlich auf beiden Seiten der Schwelle."""

    async def body(w: _World) -> None:
        async def sim(other: str) -> float:
            value: float = await w.owner.fetchval("SELECT similarity($1, $2)", _SIMILAR_A, other)
            return value

        assert await sim(_SIMILAR_B) >= MEMORY_DEDUP_SIMILARITY
        assert MEMORY_DEDUP_SIMILARITY <= await sim(_NEAR_HIT) < MEMORY_DEDUP_SIMILARITY + 0.05
        assert MEMORY_DEDUP_SIMILARITY - 0.15 < await sim(_NEAR_MISS) < MEMORY_DEDUP_SIMILARITY
        assert await sim(_UNRELATED) < MEMORY_DEDUP_SIMILARITY

    _run(body)


def test_lesson_threshold_n_minus_one_none_n_one() -> None:
    async def body(w: _World) -> None:
        below = await w.lesson(_SIMILAR_A, occurrences=_N - 1)
        assert await w.lesson_patterns() == []

        at = await w.lesson(_UNRELATED, occurrences=_N)
        [pattern] = await w.lesson_patterns()
        assert pattern.source is PatternSource.lesson
        assert pattern.agent_id == w.seed.agent_a
        assert pattern.element is None
        assert pattern.count == _N
        assert pattern.evidence_ids == [at]
        assert below not in pattern.evidence_ids

    _run(body)


def test_two_similar_lessons_form_a_cluster() -> None:
    async def body(w: _World) -> None:
        a = await w.lesson(_SIMILAR_A, occurrences=_N - 1)
        b = await w.lesson(_SIMILAR_B, occurrences=1)
        [pattern] = await w.lesson_patterns()
        assert pattern.count == _N
        assert pattern.evidence_ids == sorted([a, b])

    _run(body)


def test_lessons_just_above_the_threshold_cluster() -> None:
    async def body(w: _World) -> None:
        a = await w.lesson(_SIMILAR_A, occurrences=_N - 1)
        b = await w.lesson(_NEAR_HIT, occurrences=1)
        [pattern] = await w.lesson_patterns()
        assert pattern.evidence_ids == sorted([a, b])

    _run(body)


@pytest.mark.parametrize("other", [_NEAR_MISS, _UNRELATED])
def test_two_dissimilar_lessons_do_not_cluster(other: str) -> None:
    async def body(w: _World) -> None:
        await w.lesson(_SIMILAR_A, occurrences=_N - 1)
        await w.lesson(other, occurrences=1)
        assert await w.lesson_patterns() == []

    _run(body)


def test_vector_branch_clusters_paraphrases() -> None:
    """Gleicher Weg wie die Dublettenpruefung: Cosinus faengt Paraphrasen."""

    async def body(w: _World) -> None:
        a = await w.lesson(_SIMILAR_A, occurrences=_N - 1)
        b = await w.lesson(_UNRELATED, occurrences=1)
        assert await w.memories.vector_supported()
        await w.memories.set_vector(a, _unit(0))
        await w.memories.set_vector(b, _unit(1))
        assert await w.lesson_patterns() == []

        await w.memories.set_vector(b, _unit(0))
        [pattern] = await w.lesson_patterns()
        assert pattern.evidence_ids == sorted([a, b])

    _run(body)


@pytest.mark.parametrize("closed", ["converted", "rejected"])
def test_converted_and_rejected_are_not_pending(closed: str) -> None:
    async def body(w: _World) -> None:
        await w.lesson(_SIMILAR_A, occurrences=_N, status=closed)
        assert await w.lesson_patterns() == []

        # Auch als Cluster-Partner hebt ein abgeschlossener Eintrag nichts ueber n.
        await w.lesson(_SIMILAR_B, occurrences=_N - 1)
        assert await w.lesson_patterns() == []

    _run(body)


def test_other_kinds_never_become_lesson_patterns() -> None:
    async def body(w: _World) -> None:
        for kind in ("user_fact", "agent_note"):
            await w.lesson(f"{_SIMILAR_A} {kind}", occurrences=_N, kind=kind)
        assert await w.lesson_patterns() == []

    _run(body)


def test_user_memory_never_flows_into_patterns() -> None:
    async def body(w: _World) -> None:
        subject = uuid4()
        # Die DB laesst `lesson` im Nutzergedaechtnis gar nicht zu ...
        with pytest.raises(asyncpg.CheckViolationError):
            await w.owner.execute(
                "INSERT INTO agent_memory (workspace_id, agent_id, status, fact, kind, scope, "
                " subject_user_id, origin, source, occurrence_count) "
                "VALUES ($1, NULL, 'pending', $2, 'lesson', 'user', $3, 'inferred', 'agent', $4)",
                w.seed.ws_a,
                _SIMILAR_A,
                subject,
                _N,
            )
        # ... und ein aehnlicher offener Nutzerfakt zieht keinen Lernvorschlag ueber n.
        await w.owner.execute(
            "INSERT INTO agent_memory (workspace_id, agent_id, status, fact, kind, scope, "
            " subject_user_id, origin, source, occurrence_count) "
            "VALUES ($1, NULL, 'pending', $2, 'user_fact', 'user', $3, 'user_stated', 'agent', $4)",
            w.seed.ws_a,
            _SIMILAR_B,
            subject,
            _N,
        )
        await w.lesson(_SIMILAR_A, occurrences=_N - 1)
        assert await w.patterns() == []

    _run(body)


def test_user_scope_filter_holds_even_without_the_db_check() -> None:
    """Zweite Linie: faellt der CHECK weg, haelt der Filter `scope='agent'` allein.

    Nur im Wegwerf-Schema dieses Tests (Owner-Verbindung), nie in `public`.
    """

    async def body(w: _World) -> None:
        await w.owner.execute(
            "ALTER TABLE agent_memory DROP CONSTRAINT agent_memory_user_scope_check"
        )
        await w.owner.execute(
            "INSERT INTO agent_memory (workspace_id, agent_id, status, fact, kind, scope, "
            " subject_user_id, origin, source, occurrence_count) "
            "VALUES ($1, $2, 'pending', $3, 'lesson', 'user', $4, 'inferred', 'agent', $5)",
            w.seed.ws_a,
            w.seed.agent_a,
            _SIMILAR_A,
            uuid4(),
            _N,
        )
        assert await w.patterns() == []

    _run(body)


def test_lessons_cluster_only_within_one_agent() -> None:
    async def body(w: _World) -> None:
        await w.lesson(_SIMILAR_A, occurrences=_N - 1)
        await w.lesson(_SIMILAR_B, occurrences=1, agent_id=w.seed.agent_a2)
        assert await w.lesson_patterns() == []

    _run(body)


def test_lesson_cluster_is_transitive_and_period_follows_merges() -> None:
    async def body(w: _World) -> None:
        base = "Nennt bei Kuendigungsfragen keine Frist"
        a = await w.lesson(f"{base} aus dem Playbook")
        b = await w.lesson(f"{base} aus dem Playbook Kuendigung")
        c = await w.lesson(f"{base} aus dem Playbook Kuendigung und Widerruf")
        merged = await w.memories.merge_lesson(w.seed.ws_a, w.seed.agent_a, a)
        assert merged is not None
        [pattern] = await w.lesson_patterns()
        assert pattern.evidence_ids == sorted([a, b, c])
        assert pattern.count == 4
        merged_at = await w.owner.fetchval(
            "SELECT max(created_at) FROM agent_memory_event WHERE memory_id = $1 "
            "AND event = 'merged'",
            a,
        )
        created = await w.owner.fetchval(
            "SELECT min(created_at) FROM agent_memory WHERE id = ANY($1::uuid[])", [a, b, c]
        )
        assert (pattern.first_seen, pattern.last_seen) == (created, merged_at)

    _run(body)


def test_lesson_patterns_filter_by_agent() -> None:
    async def body(w: _World) -> None:
        await w.lesson(f"{_SIMILAR_A} {secrets.token_hex(2)}", occurrences=_N)
        assert len(await w.patterns(agent_id=w.seed.agent_a)) == 1
        assert await w.patterns(agent_id=w.seed.agent_a2) == []

    _run(body)


def test_patterns_activate_nothing() -> None:
    """Eine berechnete Sicht: keine neue Zeile, kein geaenderter Status."""

    async def body(w: _World) -> None:
        for _ in range(_N):
            await w.case()
        await w.lesson(_SIMILAR_A, occurrences=_N)
        snapshot = (
            "SELECT (SELECT count(*) FROM agent_case), (SELECT count(*) FROM agent_case_event), "
        )
        snapshot += (
            "(SELECT string_agg(status || occurrence_count, ',' ORDER BY id) FROM agent_memory)"
        )
        before = await w.owner.fetchrow(snapshot)
        assert len(await w.patterns()) == 2
        assert await w.owner.fetchrow(snapshot) == before

    _run(body)


# --- Rechte ----------------------------------------------------------------------


def test_editor_and_triage_agent_see_patterns() -> None:
    async def body(w: _World) -> None:
        for _ in range(_N):
            await w.case()
        assert len(await w.svc.list_patterns(w.editor)) == 1
        assert len(await w.svc.list_patterns(w.triage)) == 1

    _run(body)


def test_viewer_and_agents_without_triage_are_refused() -> None:
    async def body(w: _World) -> None:
        for ctx in (w.viewer, w.agent, w.no_policy):
            with pytest.raises(ApiGateError) as exc:
                await w.svc.list_patterns(ctx)
            assert exc.value.status == 403

    _run(body)
