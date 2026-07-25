"""Unit-Tests des Read-Scopings der inhaltlichen Suche (ADR-0037 §47, ADR-0046).

Der `SearchService` war bis ADR-0046 komplett ungetestet, obwohl er der
sicherheitsrelevante Teil der Suche ist (er entscheidet, was ein Agent
ueberhaupt finden darf). Diese Tests laufen ohne Datenbank gegen ein
Fake-Repository und einen Fake-Pool.

Kern der Regression: das Scoping muss als Praedikat IN die Repo-Query gehen,
nicht hinterher filtern. Nachfiltern hinter dem `LIMIT` liefert `[]`, sobald die
globalen Top-k ausserhalb des zugewiesenen Sets liegen.
"""

import asyncio
from collections.abc import Mapping, Sequence
from typing import Any, cast
from uuid import UUID, uuid4

import asyncpg

from who2be_api.core.security import WorkspaceContext
from who2be_api.services.search_service import SearchService
from who2be_models import AgentToolPolicy, ReadScope, SearchHit, WorkspaceRole

_WS = uuid4()
_AGENT = uuid4()


def _hit(entity_type: str, name: str, score: float, hit_id: UUID) -> SearchHit:
    return SearchHit(type=entity_type, id=hit_id, name=name, score=score)  # type: ignore[arg-type]


class _FakeRepo:
    """Repo-Fake, der `restrict` ehrlich anwendet und die Aufrufe protokolliert."""

    def __init__(self, hits: list[SearchHit]) -> None:
        self._hits = hits
        self.last_restrict: Mapping[str, Sequence[UUID]] | None = None
        self.last_types: list[str] | None = None

    async def search(
        self,
        workspace_id: UUID,
        query: str,
        types: list[str],
        limit: int,
        restrict: Mapping[str, Sequence[UUID]] | None = None,
    ) -> list[SearchHit]:
        self.last_restrict = restrict
        self.last_types = list(types)
        rows = [h for h in self._hits if h.type in types]
        if restrict is not None:
            allowed = {k: set(v) for k, v in restrict.items()}
            rows = [h for h in rows if h.type not in allowed or h.id in allowed[h.type]]
        rows.sort(key=lambda h: (-h.score, h.name))
        return rows[:limit]


class _FakePool:
    """Minimal-Pool fuer `agent_scope`: liefert feste Zuweisungs-IDs."""

    def __init__(self, playbooks: list[UUID], resources: list[UUID]) -> None:
        self._playbooks = playbooks
        self._resources = resources

    async def fetch(self, sql: str, *args: Any) -> list[dict[str, UUID]]:
        ids = self._resources if "playbook_resource_link" in sql else self._playbooks
        return [{"id": i} for i in ids]


def _ctx(policy: AgentToolPolicy | None) -> WorkspaceContext:
    return WorkspaceContext(
        workspace_id=_WS,
        user_id=uuid4(),
        role=WorkspaceRole.viewer,
        is_api_token=policy is not None,
        agent_id=_AGENT if policy is not None else None,
        tool_policy=policy,
    )


def _service(repo: _FakeRepo, pool: _FakePool) -> SearchService:
    # `_FakeRepo` erfuellt das `SearchRepository`-Protocol strukturell; der Pool
    # ist ein Duck-Type auf `.fetch` und braucht daher den cast.
    return SearchService(repo, cast("asyncpg.Pool", pool))


def test_assigned_scope_survives_a_crowded_top_k() -> None:
    """Die eigentliche Regression (ADR-0037 §47).

    Der Agent hat genau ein zugewiesenes Playbook, das global auf Rang 4 liegt.
    Bei `limit=3` faellt es aus den globalen Top-k — mit Nachfiltern bekaeme der
    Agent `[]`. Mit dem Praedikat in der Query findet er sein Playbook.
    """
    mine = uuid4()
    hits = [
        _hit("playbook", "Fremd A", 0.9, uuid4()),
        _hit("playbook", "Fremd B", 0.8, uuid4()),
        _hit("playbook", "Fremd C", 0.7, uuid4()),
        _hit("playbook", "Meins", 0.6, mine),
    ]
    repo = _FakeRepo(hits)
    service = _service(repo, _FakePool(playbooks=[mine], resources=[]))

    result = asyncio.run(
        service.search(
            _ctx(AgentToolPolicy(playbook_read=ReadScope.assigned)), "q", ["playbook"], 3
        )
    )

    assert [h.id for h in result] == [mine]
    assert repo.last_restrict is not None
    assert list(repo.last_restrict["playbook"]) == [mine]


def test_assigned_scope_without_assignments_finds_nothing() -> None:
    """Leere Zuweisungsmenge heisst „nichts sichtbar", nicht „keine Einschraenkung"."""
    repo = _FakeRepo([_hit("playbook", "Fremd", 0.9, uuid4())])
    service = _service(repo, _FakePool([], []))

    result = asyncio.run(
        service.search(
            _ctx(AgentToolPolicy(playbook_read=ReadScope.assigned)), "q", ["playbook"], 10
        )
    )

    assert result == []
    assert repo.last_restrict is not None
    assert list(repo.last_restrict["playbook"]) == []


def test_scope_all_passes_no_restriction() -> None:
    """`ReadScope.all` darf kein `restrict` setzen (sonst unnoetiges Praedikat)."""
    other = uuid4()
    repo = _FakeRepo([_hit("playbook", "Fremd", 0.9, other)])
    service = _service(repo, _FakePool([], []))

    result = asyncio.run(
        service.search(_ctx(AgentToolPolicy(playbook_read=ReadScope.all)), "q", ["playbook"], 10)
    )

    assert [h.id for h in result] == [other]
    assert repo.last_restrict is None


def test_none_scope_on_other_type_does_not_break_the_search() -> None:
    """Zweiter Fehler, mit ADR-0046 behoben.

    Der Scope wurde frueher fuer ALLE Typen berechnet — auch fuer solche, die
    schon aus der Anfrage gefallen waren. Da `playbook_read_restrict` bei Scope
    `none` ein 403 wirft, bekam ein Agent mit `playbook_read=none` auf eine
    reine Persona-Suche eine 403 statt seiner Treffer.
    """
    persona_id = uuid4()
    repo = _FakeRepo([_hit("persona", "Support", 0.9, persona_id)])
    service = _service(repo, _FakePool([], []))

    result = asyncio.run(
        service.search(
            _ctx(AgentToolPolicy(playbook_read=ReadScope.none, resource_read=ReadScope.none)),
            "q",
            ["persona"],
            10,
        )
    )

    assert [h.id for h in result] == [persona_id]


def test_excluded_types_never_reach_the_repository() -> None:
    """`none`-Typen werden vor dem Repo-Aufruf entfernt, nicht danach gefiltert."""
    repo = _FakeRepo([])
    service = _service(repo, _FakePool([], []))

    asyncio.run(
        service.search(
            _ctx(AgentToolPolicy(playbook_read=ReadScope.none, persona_read=False)),
            "q",
            ["persona", "playbook", "external_tool"],
            10,
        )
    )

    assert repo.last_types == ["external_tool"]


def test_unbound_token_is_unrestricted() -> None:
    """Ohne Policy (Mensch/JWT) kein Scoping."""
    pid = uuid4()
    repo = _FakeRepo([_hit("playbook", "Irgendwas", 0.5, pid)])
    service = _service(repo, _FakePool([], []))

    result = asyncio.run(service.search(_ctx(None), "q", None, 10))

    assert [h.id for h in result] == [pid]
    assert repo.last_restrict is None


def test_blank_query_short_circuits() -> None:
    repo = _FakeRepo([_hit("playbook", "X", 1.0, uuid4())])
    service = _service(repo, _FakePool([], []))

    assert asyncio.run(service.search(_ctx(None), "   ", None, 10)) == []
    assert repo.last_types is None
