"""DB-freie Unit-Tests fuer das Read-Scoping der DISTINCT-Tags-Endpunkte.

Schliesst LOW-1 aus dem MCP/Tenant-Isolation-Audit ab: `playbook_service.
list_tags` und `resource_service.list_tags` liefen am `assigned`-Scope vorbei
(nur Workspace-Filter) und leakten so einem an einen Agenten gebundenen Token
ueber den Tag-Picker die Tag-Namen NICHT zugewiesener Objekte des ganzen
Workspaces.

Geprueft wird je Service:
- **assigned** filtert die Tag-Menge auf die zugewiesenen Aggregate.
- **all** und **Mensch/JWT** (`tool_policy=None`) bleiben ungefiltert.
- **none** liefert eine leere Liste (kein 403 — Tags sind reine Metadaten,
  konsistent mit den Render-Pfaden).

Der einzige DB-Zugriff (`agent_scope.assigned_*_ids` → `pool.fetch`) wird ueber
einen Fake-Pool gestubbt; das Fake-Repo spiegelt die SQL-Semantik von
`list_distinct_tags` (NULL ⇒ alle, ID-Menge ⇒ gefiltert). `cast` brueckt die
Repo-Protokolle — die gepruefte Logik liegt im Service bzw. im restrict_ids-Pfad.
"""

from __future__ import annotations

import asyncio
from typing import Any, cast
from uuid import UUID, uuid4

import asyncpg

from who2be_api.core.security import WorkspaceContext
from who2be_api.services.playbook_service import PlaybookService
from who2be_api.services.resource_service import ResourceService
from who2be_models import AgentToolPolicy, ReadScope, WorkspaceRole


class _FakePool:
    """Stubt `agent_scope.assigned_*_ids`: `fetch` liefert die assigned-Menge."""

    def __init__(self, assigned: list[UUID]) -> None:
        self._assigned = assigned

    async def fetch(self, _sql: str, *_args: object) -> list[dict[str, UUID]]:
        return [{"id": a} for a in self._assigned]


def _pool(assigned: list[UUID]) -> asyncpg.Pool:
    return cast("asyncpg.Pool", _FakePool(assigned))


class _FakeTagRepo:
    """Spiegelt `list_distinct_tags`: Tags pro Entity-ID, gefiltert auf restrict_ids."""

    def __init__(self, tags_by_id: dict[UUID, list[str]]) -> None:
        self._by_id = tags_by_id

    async def list_distinct_tags(
        self,
        _workspace_id: UUID,
        _locale: str = "de",
        restrict_ids: list[UUID] | None = None,
    ) -> list[str]:
        allowed = None if restrict_ids is None else set(restrict_ids)
        tags: set[str] = set()
        for entity_id, entity_tags in self._by_id.items():
            if allowed is not None and entity_id not in allowed:
                continue
            tags.update(entity_tags)
        return sorted(tags)


def _agent_ctx(scope: ReadScope) -> WorkspaceContext:
    return WorkspaceContext(
        workspace_id=uuid4(),
        user_id=uuid4(),
        role=WorkspaceRole.editor,
        is_api_token=True,
        agent_id=uuid4(),
        tool_policy=AgentToolPolicy(playbook_read=scope, resource_read=scope),
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


def _pb_svc(tags_by_id: dict[UUID, list[str]], assigned: list[UUID]) -> PlaybookService:
    return PlaybookService(
        cast(Any, _FakeTagRepo(tags_by_id)),
        _pool(assigned),
        cast(Any, None),  # composition_service — von list_tags nicht benutzt
        cast(Any, None),  # resource_link_service — dito
    )


def _res_svc(tags_by_id: dict[UUID, list[str]], assigned: list[UUID]) -> ResourceService:
    return ResourceService(cast(Any, _FakeTagRepo(tags_by_id)), _pool(assigned))


# --- PlaybookService.list_tags ----------------------------------------------


def test_playbook_tags_assigned_filtered_to_scope() -> None:
    visible, hidden = uuid4(), uuid4()
    tags = {visible: ["alpha"], hidden: ["beta"]}
    # Scope = nur das sichtbare Playbook → fremder Tag faellt weg.
    result = _run(_pb_svc(tags, [visible]).list_tags(_agent_ctx(ReadScope.assigned)))
    assert result == ["alpha"]


def test_playbook_tags_all_scope_unfiltered() -> None:
    visible, hidden = uuid4(), uuid4()
    tags = {visible: ["alpha"], hidden: ["beta"]}
    # Scope `all` → restrict_ids=None → alle Tags des Workspaces.
    result = _run(_pb_svc(tags, []).list_tags(_agent_ctx(ReadScope.all)))
    assert result == ["alpha", "beta"]


def test_playbook_tags_human_unfiltered() -> None:
    visible, hidden = uuid4(), uuid4()
    tags = {visible: ["alpha"], hidden: ["beta"]}
    result = _run(_pb_svc(tags, []).list_tags(_human_ctx()))
    assert result == ["alpha", "beta"]


def test_playbook_tags_none_scope_empty() -> None:
    visible = uuid4()
    tags = {visible: ["alpha"]}
    # Scope `none` → leere Liste, KEIN 403.
    result = _run(_pb_svc(tags, [visible]).list_tags(_agent_ctx(ReadScope.none)))
    assert result == []


# --- ResourceService.list_tags ----------------------------------------------


def test_resource_tags_assigned_filtered_to_scope() -> None:
    visible, hidden = uuid4(), uuid4()
    tags = {visible: ["alpha"], hidden: ["beta"]}
    result = _run(_res_svc(tags, [visible]).list_tags(_agent_ctx(ReadScope.assigned)))
    assert result == ["alpha"]


def test_resource_tags_all_scope_unfiltered() -> None:
    visible, hidden = uuid4(), uuid4()
    tags = {visible: ["alpha"], hidden: ["beta"]}
    result = _run(_res_svc(tags, []).list_tags(_agent_ctx(ReadScope.all)))
    assert result == ["alpha", "beta"]


def test_resource_tags_human_unfiltered() -> None:
    visible, hidden = uuid4(), uuid4()
    tags = {visible: ["alpha"], hidden: ["beta"]}
    result = _run(_res_svc(tags, []).list_tags(_human_ctx()))
    assert result == ["alpha", "beta"]


def test_resource_tags_none_scope_empty() -> None:
    visible = uuid4()
    tags = {visible: ["alpha"]}
    result = _run(_res_svc(tags, [visible]).list_tags(_agent_ctx(ReadScope.none)))
    assert result == []
