"""Tests fuer das MCP-Tool `fetch_agent` (Welle 5).

Testet den Tool-Aufruf gegen eine gemockte API. Der Renderer laeuft in der
API — das MCP-Tool delegiert nur und vertraut dem API-Endpoint.

Muster aus test_server.py / test_resource_tools.py: kein pytest-asyncio,
`build_client` per monkeypatch, `httpx.MockTransport`.
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
from who2be_mcp.server import fetch_agent, mcp
from who2be_models import AgentWithRenderedPrompt

_WORKSPACE_ID = uuid4()


def _factory(handler: Callable[[httpx.Request], httpx.Response]) -> Callable[[], object]:
    transport = httpx.MockTransport(handler)

    async def _build() -> ApiClient:
        return ApiClient("http://test", "token", _WORKSPACE_ID, transport=transport)

    return _build


def _persona_payload(name: str = "Coach Carla") -> dict[str, object]:
    return {
        "id": str(uuid4()),
        "workspace_id": str(_WORKSPACE_ID),
        "owner_id": str(uuid4()),
        "name": name,
        "current_version": 1,
        "current_status": "active",
        "has_pending_draft": False,
        "content": {
            "description": "Senior Coach",
            "system_prompt": "",
            "traits": [],
            "tags": [],
            "content": {"description": "", "blocks": []},
        },
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }


def _agent_rendered_payload(
    agent_id: UUID,
    persona: dict[str, object],
    tpl_id: UUID,
    prompt: str,
) -> dict[str, object]:
    return {
        "id": str(agent_id),
        "name": "Carla Bot",
        "persona": persona,
        "system_prompt_rendered": prompt,
        "system_prompt_template_id": str(tpl_id),
    }


def test_fetch_agent_returns_agent_with_rendered_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent_id = uuid4()
    tpl_id = uuid4()
    persona = _persona_payload()
    rendered_prompt = "Du bist Coach Carla. Heute ist 31. Mai 2026."
    payload = _agent_rendered_payload(agent_id, persona, tpl_id, rendered_prompt)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith(f"/agents/{agent_id}/rendered")
        return httpx.Response(200, json=payload)

    monkeypatch.setattr(server, "build_client", _factory(handler))

    result = asyncio.run(fetch_agent(str(agent_id)))

    assert isinstance(result, AgentWithRenderedPrompt)
    assert result.id == agent_id
    assert result.name == "Carla Bot"
    assert result.system_prompt_rendered == rendered_prompt
    assert result.system_prompt_template_id == tpl_id
    assert result.persona.name == "Coach Carla"


def test_fetch_agent_rejects_invalid_uuid() -> None:
    with pytest.raises(ToolError, match="Ungueltige Agent-UUID"):
        asyncio.run(fetch_agent("not-a-uuid"))


def test_fetch_agent_propagates_tool_error_on_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent_id = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    monkeypatch.setattr(server, "build_client", _factory(handler))

    with pytest.raises(ToolError):
        asyncio.run(fetch_agent(str(agent_id)))


def test_server_exposes_fetch_agent_tool() -> None:
    """fetch_agent muss im Tool-Set des MCP-Servers registriert sein."""
    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}
    assert "fetch_agent" in names


def test_fetch_agent_via_mcp_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """End-to-End vom MCP-Client ueber den Tool-Dispatcher."""
    agent_id = uuid4()
    tpl_id = uuid4()
    persona = _persona_payload()
    rendered_prompt = "Fertiger Prompt ohne Placeholder."
    payload = _agent_rendered_payload(agent_id, persona, tpl_id, rendered_prompt)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    monkeypatch.setattr(server, "build_client", _factory(handler))

    async def _run() -> object:
        async with Client(mcp) as client:
            result = await client.call_tool("fetch_agent", {"agent_id": str(agent_id)})
            return result.data

    data = asyncio.run(_run())
    # FastMCP serialisiert das Ergebnis — wir pruefen ob es ein dict ist
    # (AgentWithRenderedPrompt wurde serialisiert) oder ein AgentWithRenderedPrompt.
    if isinstance(data, dict):
        assert data["system_prompt_rendered"] == rendered_prompt
    elif isinstance(data, AgentWithRenderedPrompt):
        assert data.system_prompt_rendered == rendered_prompt
    else:
        # Fallback: als String geparst pruefen.
        assert rendered_prompt in str(data)
