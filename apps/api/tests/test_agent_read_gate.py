"""DB-freie Unit-Tests fuer das `agent_read`-Gate auf den Agent-Read-Pfaden.

`AgentService.list_all`/`get` gaten ueber `require_read_flag(ctx, "agent_read")`:
- ungebundener Token / Mensch (`tool_policy is None`) -> No-Op (UI unberuehrt),
- agent-gebundener Token mit `agent_read=True` -> darf lesen,
- agent-gebundener Token mit `agent_read=False` -> 403.

Zusaetzlich gesichert: die Liste filtert NICHT auf `enabled` — ein frisch
angelegter (=`disabled`) Agent muss fuer einen verwaltenden Builder sichtbar
bleiben (sonst kaeme das urspruengliche „404 nach dem Anlegen" zurueck).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from who2be_api.core.security import WorkspaceContext
from who2be_api.services.agent_service import AgentService
from who2be_models import AgentRead, AgentStatus, AgentToolPolicy, WorkspaceRole

_WS = uuid4()
_OWNER = uuid4()


def _agent(name: str, status: AgentStatus) -> AgentRead:
    now = datetime(2026, 6, 22, tzinfo=UTC)
    return AgentRead(
        id=uuid4(),
        workspace_id=_WS,
        owner_id=_OWNER,
        name=name,
        description="",
        persona_id=None,
        system_prompt_template_id=None,
        status=status,
        created_at=now,
        updated_at=now,
    )


class _FakeAgentRepo:
    """Minimaler Fake — nur die von list/get genutzten Methoden."""

    def __init__(self, agents: list[AgentRead]) -> None:
        self._agents = agents

    async def list_by_workspace(
        self, workspace_id: UUID, limit: int, cursor: object
    ) -> list[AgentRead]:
        return self._agents[:limit]

    async def fetch(self, workspace_id: UUID, agent_id: UUID) -> AgentRead | None:
        return next((a for a in self._agents if a.id == agent_id), None)


def _ctx(tool_policy: AgentToolPolicy | None) -> WorkspaceContext:
    return WorkspaceContext(
        workspace_id=_WS,
        user_id=_OWNER,
        role=WorkspaceRole.editor,
        is_api_token=tool_policy is not None,
        agent_id=uuid4() if tool_policy is not None else None,
        tool_policy=tool_policy,
    )


def _service() -> tuple[AgentService, AgentRead]:
    disabled = _agent("Frisch angelegt", AgentStatus.disabled)
    enabled = _agent("Aktiv", AgentStatus.enabled)
    return AgentService(_FakeAgentRepo([disabled, enabled])), disabled  # type: ignore[arg-type]


def test_human_token_may_read_agents() -> None:
    service, _ = _service()
    items, _cursor = asyncio.run(service.list_all(_ctx(None), limit=50, cursor=None))
    assert len(items) == 2


def test_agent_read_true_may_list_and_get() -> None:
    service, disabled = _service()
    ctx = _ctx(AgentToolPolicy(agent_read=True))
    items, _cursor = asyncio.run(service.list_all(ctx, limit=50, cursor=None))
    # Disabled-Agent ist enthalten: kein enabled-only-Filter.
    assert disabled.id in {a.id for a in items}
    got = asyncio.run(service.get(ctx, disabled.id))
    assert got.id == disabled.id


def test_agent_read_false_blocks_list_with_403() -> None:
    service, _ = _service()
    ctx = _ctx(AgentToolPolicy(agent_read=False))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.list_all(ctx, limit=50, cursor=None))
    assert exc.value.status_code == 403


def test_agent_read_false_blocks_get_with_403() -> None:
    service, disabled = _service()
    ctx = _ctx(AgentToolPolicy(agent_read=False))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.get(ctx, disabled.id))
    assert exc.value.status_code == 403
