"""Tests fuer den Who2Be-MCP-Server: Tool-Registrierung und ein Tool-Pfad."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from who2be_mcp import server
from who2be_mcp.client import ApiClient
from who2be_mcp.server import mcp


def _playbook_json(name: str, workspace_id: str) -> dict[str, object]:
    now = datetime.now(UTC).isoformat()
    return {
        "id": str(uuid4()),
        "workspace_id": workspace_id,
        "owner_id": str(uuid4()),
        "name": name,
        "current_version": 1,
        "type": "workflow",
        "tags": ["t"],
        "triggers": None,
        "content": {
            "description": "d",
            "body": "b",
            "type": "workflow",
            "tags": ["t"],
            "triggers": None,
        },
        "created_at": now,
        "updated_at": now,
    }


def test_server_exposes_all_tools() -> None:
    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}
    assert {"ping", "get_persona", "list_playbooks", "fetch_playbook"} <= names


def test_fetch_playbook_rejects_invalid_uuid() -> None:
    async def _run() -> None:
        async with Client(mcp) as client:
            await client.call_tool("fetch_playbook", {"playbook_id": "not-a-uuid"})

    with pytest.raises(ToolError):
        asyncio.run(_run())


def test_list_playbooks_tool_returns_playbooks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[_playbook_json("PB", str(workspace_id))])

    api_client = ApiClient(
        "http://api.test",
        "tok",
        workspace_id,
        transport=httpx.MockTransport(handler),
    )

    async def _build() -> ApiClient:
        return api_client

    monkeypatch.setattr(server, "build_client", _build)

    async def _run() -> object:
        async with Client(mcp) as client:
            result = await client.call_tool("list_playbooks", {})
            return result.data

    data = asyncio.run(_run())
    assert isinstance(data, list)
    assert len(data) == 1
