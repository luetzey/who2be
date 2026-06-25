"""Tests fuer das MCP-Tool `whoami` + `ApiClient.whoami` (#253).

Muster wie test_agent_read_tools.py: kein pytest-asyncio, `build_client` per
monkeypatch, `httpx.MockTransport`. Deckt den Roundtrip (Tool → Client → API →
Model) fuer beide Identitaets-Faelle ab (unrestricted Mensch, agent-gebunden).
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
from who2be_mcp.server import mcp, whoami
from who2be_models import WhoAmIRead

_WORKSPACE_ID = uuid4()


def _factory(handler: Callable[[httpx.Request], httpx.Response]) -> Callable[[], object]:
    transport = httpx.MockTransport(handler)

    async def _build() -> ApiClient:
        return ApiClient("http://test", "token", _WORKSPACE_ID, transport=transport)

    return _build


def _unrestricted_payload(user_id: UUID) -> dict[str, object]:
    return {
        "user_id": str(user_id),
        "workspace_id": str(_WORKSPACE_ID),
        "role": "admin",
        "is_api_token": False,
        "agent_id": None,
        "unrestricted": True,
        "capabilities": None,
        "read_scopes": None,
        "features": ["core", "agents"],
    }


def _agent_payload(user_id: UUID, agent_id: UUID) -> dict[str, object]:
    return {
        "user_id": str(user_id),
        "workspace_id": str(_WORKSPACE_ID),
        "role": "admin",
        "is_api_token": True,
        "agent_id": str(agent_id),
        "unrestricted": False,
        "capabilities": ["resource_write", "promote_retire"],
        "read_scopes": {
            "persona": "all",
            "playbook": "all",
            "resource": "all",
            "agent": "assigned",
        },
        "features": ["core"],
    }


def test_whoami_returns_unrestricted_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = uuid4()
    payload = _unrestricted_payload(user_id)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/whoami")
        return httpx.Response(200, json=payload)

    monkeypatch.setattr(server, "build_client", _factory(handler))

    result = asyncio.run(whoami())

    assert isinstance(result, WhoAmIRead)
    assert result.user_id == user_id
    assert result.is_api_token is False
    assert result.agent_id is None
    # KRITISCH: unrestricted ≠ "nichts erlaubt".
    assert result.unrestricted is True
    assert result.capabilities is None
    assert result.read_scopes is None


def test_whoami_returns_agent_capabilities(monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = uuid4()
    agent_id = uuid4()
    payload = _agent_payload(user_id, agent_id)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    monkeypatch.setattr(server, "build_client", _factory(handler))

    result = asyncio.run(whoami())

    assert result.unrestricted is False
    assert result.agent_id == agent_id
    assert result.capabilities is not None
    assert {c.value for c in result.capabilities} == {"resource_write", "promote_retire"}
    assert result.read_scopes is not None
    assert result.read_scopes["agent"].value == "assigned"


def test_whoami_propagates_unauthorized(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "nope"})

    monkeypatch.setattr(server, "build_client", _factory(handler))

    with pytest.raises(ToolError):
        asyncio.run(whoami())


def test_server_exposes_whoami_tool() -> None:
    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}
    assert "whoami" in names
    # ping bleibt erhalten und auth-frei.
    assert "ping" in names


def test_whoami_via_mcp_client(monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = uuid4()
    payload = _unrestricted_payload(user_id)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    monkeypatch.setattr(server, "build_client", _factory(handler))

    async def _run() -> object:
        async with Client(mcp) as client:
            result = await client.call_tool("whoami", {})
            return result.data

    data = asyncio.run(_run())
    if isinstance(data, dict):
        assert data["unrestricted"] is True
    elif isinstance(data, WhoAmIRead):
        assert data.unrestricted is True
    else:
        assert "unrestricted" in str(data)
