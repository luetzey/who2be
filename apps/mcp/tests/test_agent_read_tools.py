"""Tests fuer die MCP-Tools `list_agents` und `get_agent` (Metadaten-Read).

Beide liefern reine `AgentRead`-Konfig (kein gerenderter Prompt) und sind der
Pfad, mit dem ein verwaltender Agent (Builder) bestehende/neue Agenten findet
und vor dem Editieren prueft. Muster wie test_fetch_agent_tool.py: kein
pytest-asyncio, `build_client` per monkeypatch, `httpx.MockTransport`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from uuid import UUID, uuid4

import httpx
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from who2be_mcp import server
from who2be_mcp.client import ApiClient
from who2be_mcp.server import get_agent, list_agents, mcp
from who2be_models import AgentRead

_WORKSPACE_ID = uuid4()


def _factory(handler: Callable[[httpx.Request], httpx.Response]) -> Callable[[], object]:
    transport = httpx.MockTransport(handler)

    async def _build() -> ApiClient:
        return ApiClient("http://test", "token", _WORKSPACE_ID, transport=transport)

    return _build


def _agent_payload(agent_id: UUID, name: str, status: str = "disabled") -> dict[str, object]:
    return {
        "id": str(agent_id),
        "workspace_id": str(_WORKSPACE_ID),
        "owner_id": str(uuid4()),
        "name": name,
        "description": "",
        "persona_id": None,
        "system_prompt_template_id": None,
        "status": status,
        "created_at": "2026-06-22T00:00:00Z",
        "updated_at": "2026-06-22T00:00:00Z",
    }


def test_list_agents_returns_metadata_list(monkeypatch: pytest.MonkeyPatch) -> None:
    a1 = _agent_payload(uuid4(), "Frisch angelegt", status="disabled")
    a2 = _agent_payload(uuid4(), "Aktiv", status="enabled")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/agents")
        return httpx.Response(200, json=[a1, a2])

    monkeypatch.setattr(server, "build_client", _factory(handler))

    result = asyncio.run(list_agents())

    assert len(result) == 2
    assert all(isinstance(a, AgentRead) for a in result)
    # Disabled-Agent ist enthalten — kein enabled-only-Filter.
    assert {"Frisch angelegt", "Aktiv"} == {a.name for a in result}


def test_get_agent_returns_single_config(monkeypatch: pytest.MonkeyPatch) -> None:
    agent_id = uuid4()
    payload = _agent_payload(agent_id, "Neuer Agent", status="disabled")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith(f"/agents/{agent_id}")
        return httpx.Response(200, json=payload)

    monkeypatch.setattr(server, "build_client", _factory(handler))

    result = asyncio.run(get_agent(str(agent_id)))

    assert isinstance(result, AgentRead)
    assert result.id == agent_id
    assert result.name == "Neuer Agent"
    # Frisch angelegte Huelle ohne Persona/Template ist nicht aktivierbar.
    assert result.activatable is False


def test_get_agent_rejects_invalid_uuid() -> None:
    with pytest.raises(ToolError, match="Ungueltige Agent-UUID"):
        asyncio.run(get_agent("not-a-uuid"))


def test_server_exposes_agent_read_tools() -> None:
    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}
    assert {"list_agents", "get_agent"} <= names


def test_get_agent_via_mcp_client(monkeypatch: pytest.MonkeyPatch) -> None:
    agent_id = uuid4()
    payload = _agent_payload(agent_id, "Dispatcher-Agent")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    monkeypatch.setattr(server, "build_client", _factory(handler))

    async def _run() -> object:
        async with Client(mcp) as client:
            result = await client.call_tool("get_agent", {"agent_id": str(agent_id)})
            return result.data

    data = asyncio.run(_run())
    if isinstance(data, dict):
        assert data["name"] == "Dispatcher-Agent"
    elif isinstance(data, AgentRead):
        assert data.name == "Dispatcher-Agent"
    else:
        assert "Dispatcher-Agent" in str(data)
