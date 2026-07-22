"""DB-freie Unit-Tests fuer das Read-Scoping der Sekundaer-Lesepfade.

Schliesst die HIGH-Findings des Security-Reviews zur „secure by default"-
Umstellung ab: Composition-, Link- und Usage-Endpoints liefen bisher am
`assigned`-Scope vorbei (nur Workspace-Check) und konnten so von einem
Agenten-Token zum Enumerieren des ganzen Workspaces missbraucht werden.

Geprueft wird pro Service:
- **Gate-per-ID** (usages, list_children, resource_links): ein nicht
  zugewiesenes Ziel → 404.
- **Filter-der-Liste** (`composed_by`/`used_by`-Parents, persona→playbooks):
  nicht zugewiesene Eintraege fallen aus dem Ergebnis.
- **No-Op** fuer ungebundene Tokens (Mensch, `tool_policy=None`) und Scope
  `all`; **403** fuer Scope `none`.

Der einzige DB-Zugriff (`agent_scope.assigned_*_ids` → `pool.fetch`) wird ueber
einen Fake-Pool gestubbt, der die zugewiesene ID-Menge zurueckgibt. Die
Fake-Repos sind absichtlich minimal; `cast` brueckt die Repo-Protokolle (die
gepruefte Logik liegt komplett im Service, nicht im Repo).
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import asyncpg
import pytest
from fastapi import HTTPException

from who2be_api.core.security import WorkspaceContext
from who2be_api.services.persona_playbook_service import PersonaPlaybookService
from who2be_api.services.playbook_composition_service import PlaybookCompositionService
from who2be_api.services.playbook_resource_link_service import PlaybookResourceLinkService
from who2be_api.services.resource_composition_service import ResourceCompositionService
from who2be_api.services.usage_service import UsageService
from who2be_models import (
    AgentToolPolicy,
    PlaybookRef,
    ReadScope,
    ResourceRef,
    WorkspaceRole,
)


class _FakePool:
    """Stubt `agent_scope.assigned_*_ids`: `fetch` liefert die assigned-Menge."""

    def __init__(self, assigned: list[UUID]) -> None:
        self._assigned = assigned

    async def fetch(self, _sql: str, *_args: object) -> list[dict[str, UUID]]:
        return [{"id": a} for a in self._assigned]


def _pool(assigned: list[UUID]) -> asyncpg.Pool:
    return cast("asyncpg.Pool", _FakePool(assigned))


def _agent_ctx(
    scope: ReadScope = ReadScope.assigned, *, persona_read: bool = True
) -> WorkspaceContext:
    return WorkspaceContext(
        workspace_id=uuid4(),
        user_id=uuid4(),
        role=WorkspaceRole.editor,
        is_api_token=True,
        agent_id=uuid4(),
        tool_policy=AgentToolPolicy(
            playbook_read=scope, resource_read=scope, persona_read=persona_read
        ),
    )


def _human_ctx() -> WorkspaceContext:
    # Ungebundener Token / Mensch: keine Policy → kein Scoping.
    return WorkspaceContext(
        workspace_id=uuid4(),
        user_id=uuid4(),
        role=WorkspaceRole.admin,
        is_api_token=False,
    )


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


# --- Fake-Repos (minimal; Protokoll via cast gebrueckt) ---------------------


class _FakeUsageRepo:
    def __init__(
        self, playbook_usages: list[Any] | None = None, resource_usages: list[Any] | None = None
    ) -> None:
        self._pu = (
            playbook_usages
            if playbook_usages is not None
            else [SimpleNamespace(persona_id=uuid4())]
        )
        self._ru = (
            resource_usages
            if resource_usages is not None
            else [SimpleNamespace(playbook_id=uuid4())]
        )

    async def playbook_belongs_to(self, _ws: UUID, _id: UUID) -> bool:
        return True

    async def resource_belongs_to(self, _ws: UUID, _id: UUID) -> bool:
        return True

    async def list_playbook_usages(self, _ws: UUID, _id: UUID) -> list[Any]:
        return self._pu

    async def list_resource_usages(self, _ws: UUID, _id: UUID) -> list[Any]:
        return self._ru


class _FakePbCompRepo:
    def __init__(self, parents: list[PlaybookRef]) -> None:
        self._parents = parents

    async def parent_belongs_to(self, _ws: UUID, _id: UUID) -> bool:
        return True

    async def list_children(self, _ws: UUID, _id: UUID, active_only: bool) -> list[Any]:
        return [SimpleNamespace(id=uuid4())]

    async def list_parents(self, _ws: UUID, _id: UUID) -> list[PlaybookRef]:
        return self._parents


class _FakeResCompRepo:
    def __init__(self, parents: list[ResourceRef]) -> None:
        self._parents = parents

    async def parent_belongs_to(self, _ws: UUID, _id: UUID) -> bool:
        return True

    async def list_children(self, _ws: UUID, _id: UUID, active_only: bool) -> list[Any]:
        return [SimpleNamespace(id=uuid4())]

    async def list_parents(self, _ws: UUID, _id: UUID) -> list[ResourceRef]:
        return self._parents


class _FakePersonaPbRepo:
    def __init__(self, linked: list[Any]) -> None:
        self._linked = linked

    async def persona_belongs_to(self, _ws: UUID, _id: UUID) -> bool:
        return True

    async def list_linked(self, _ws: UUID, _id: UUID, active_only: bool) -> list[Any]:
        return self._linked


class _FakeLinkRepo:
    async def list_links(self, _ws: UUID, _id: UUID) -> list[Any] | None:
        return [SimpleNamespace(resource_id=uuid4())]


# --- Service-Factories (zentralisieren den cast aufs Repo-Protokoll) --------


def _usage_svc(
    assigned: list[UUID],
    *,
    playbook_usages: list[Any] | None = None,
    resource_usages: list[Any] | None = None,
) -> UsageService:
    return UsageService(
        cast(Any, _FakeUsageRepo(playbook_usages, resource_usages)), _pool(assigned)
    )


def _pb_comp_svc(parents: list[PlaybookRef], assigned: list[UUID]) -> PlaybookCompositionService:
    return PlaybookCompositionService(cast(Any, _FakePbCompRepo(parents)), _pool(assigned))


def _res_comp_svc(parents: list[ResourceRef], assigned: list[UUID]) -> ResourceCompositionService:
    return ResourceCompositionService(cast(Any, _FakeResCompRepo(parents)), _pool(assigned))


def _persona_svc(linked: list[Any], assigned: list[UUID]) -> PersonaPlaybookService:
    return PersonaPlaybookService(cast(Any, _FakePersonaPbRepo(linked)), _pool(assigned))


def _link_svc(assigned: list[UUID]) -> PlaybookResourceLinkService:
    return PlaybookResourceLinkService(cast(Any, _FakeLinkRepo()), _pool(assigned))


# --- UsageService -----------------------------------------------------------


def test_usage_playbook_assigned_visible() -> None:
    pid = uuid4()
    assert _run(_usage_svc([pid]).list_playbook_usages(_agent_ctx(), pid))  # kein 404


def test_usage_playbook_unassigned_404() -> None:
    with pytest.raises(HTTPException) as exc:
        _run(_usage_svc([uuid4()]).list_playbook_usages(_agent_ctx(), uuid4()))
    assert exc.value.status_code == 404


def test_usage_resource_unassigned_404() -> None:
    with pytest.raises(HTTPException) as exc:
        _run(_usage_svc([uuid4()]).list_resource_usages(_agent_ctx(), uuid4()))
    assert exc.value.status_code == 404


def test_usage_human_token_not_scoped() -> None:
    # Ohne Policy darf der Mensch jeden Backlink sehen (kein 404, kein Pool-Hit).
    assert _run(_usage_svc([]).list_playbook_usages(_human_ctx(), uuid4()))


def test_usage_resource_items_filtered_to_visible_playbooks() -> None:
    resource_id, visible_pb, hidden_pb = uuid4(), uuid4(), uuid4()
    usages = [SimpleNamespace(playbook_id=visible_pb), SimpleNamespace(playbook_id=hidden_pb)]
    # Scope enthaelt die Resource (Gate) + das sichtbare Referenz-Playbook.
    svc = _usage_svc([resource_id, visible_pb], resource_usages=usages)
    result = _run(svc.list_resource_usages(_agent_ctx(), resource_id))
    assert [u.playbook_id for u in result] == [visible_pb]


def test_usage_playbook_items_hidden_without_persona_read() -> None:
    pid = uuid4()
    usages = [SimpleNamespace(persona_id=uuid4())]
    svc = _usage_svc([pid], playbook_usages=usages)
    # persona_read aus → keine Persona-Backlinks (auch nicht ueber den Umweg).
    result = _run(svc.list_playbook_usages(_agent_ctx(persona_read=False), pid))
    assert result == []


# --- PlaybookCompositionService --------------------------------------------


def test_pb_composition_children_gate_404() -> None:
    with pytest.raises(HTTPException) as exc:
        _run(_pb_comp_svc([], [uuid4()]).list_children(_agent_ctx(), uuid4()))
    assert exc.value.status_code == 404


def test_pb_composition_parents_filtered_to_scope() -> None:
    child = uuid4()
    visible = PlaybookRef(id=uuid4(), name="sichtbar")
    hidden = PlaybookRef(id=uuid4(), name="fremd")
    # Scope = Kind + sichtbarer Parent; fremder Parent faellt raus.
    svc = _pb_comp_svc([visible, hidden], [child, visible.id])
    result = _run(svc.list_parents(_agent_ctx(), child))
    assert [p.id for p in result] == [visible.id]


# --- ResourceCompositionService --------------------------------------------


def test_res_composition_children_gate_404() -> None:
    with pytest.raises(HTTPException) as exc:
        _run(_res_comp_svc([], [uuid4()]).list_children(_agent_ctx(), uuid4()))
    assert exc.value.status_code == 404


def test_res_composition_parents_filtered_to_scope() -> None:
    child = uuid4()
    visible = ResourceRef(id=uuid4(), name="sichtbar")
    hidden = ResourceRef(id=uuid4(), name="fremd")
    svc = _res_comp_svc([visible, hidden], [child, visible.id])
    result = _run(svc.list_parents(_agent_ctx(), child))
    assert [p.id for p in result] == [visible.id]


# --- PersonaPlaybookService -------------------------------------------------


def test_persona_playbooks_filtered_to_scope() -> None:
    visible = SimpleNamespace(id=uuid4(), name="sichtbar")
    hidden = SimpleNamespace(id=uuid4(), name="fremd")
    svc = _persona_svc([visible, hidden], [visible.id])
    result = _run(svc.list_links(_agent_ctx(), uuid4()))
    assert [p.id for p in result] == [visible.id]


def test_persona_playbooks_all_scope_unfiltered() -> None:
    visible = SimpleNamespace(id=uuid4(), name="a")
    hidden = SimpleNamespace(id=uuid4(), name="b")
    svc = _persona_svc([visible, hidden], [])
    result = _run(svc.list_links(_agent_ctx(ReadScope.all), uuid4()))
    assert {p.id for p in result} == {visible.id, hidden.id}


# --- PlaybookResourceLinkService -------------------------------------------


def test_resource_links_assigned_visible() -> None:
    pid = uuid4()
    assert _run(_link_svc([pid]).list_links(_agent_ctx(), pid))


def test_resource_links_unassigned_404() -> None:
    with pytest.raises(HTTPException) as exc:
        _run(_link_svc([uuid4()]).list_links(_agent_ctx(), uuid4()))
    assert exc.value.status_code == 404


def test_resource_links_scope_none_raises_403() -> None:
    with pytest.raises(HTTPException) as exc:
        _run(_link_svc([uuid4()]).list_links(_agent_ctx(ReadScope.none), uuid4()))
    assert exc.value.status_code == 403
