"""Tests fuer den Who2Be-MCP-Server: Tool-Registrierung und ein Tool-Pfad."""

import asyncio
from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

import httpx
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from who2be_mcp import server
from who2be_mcp.client import ApiClient
from who2be_mcp.server import PersonaWithPlaybooks, mcp


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


def _persona_json(persona_id: str, name: str, workspace_id: str) -> dict[str, object]:
    now = datetime.now(UTC).isoformat()
    return {
        "id": persona_id,
        "workspace_id": workspace_id,
        "owner_id": str(uuid4()),
        "name": name,
        "current_version": 1,
        "content": {"description": "d", "system_prompt": "", "traits": []},
        "created_at": now,
        "updated_at": now,
    }


def test_get_persona_tool_includes_body_rendered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    persona_id = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith(f"/personas/{persona_id}/rendered"):
            return httpx.Response(
                200, json={"body_rendered": "Profil-Briefing\n\n## Skills", "unresolved": []}
            )
        if path.endswith(f"/personas/{persona_id}/playbooks"):
            return httpx.Response(200, json=[_playbook_json("PB", str(workspace_id))])
        if path.endswith(f"/personas/{persona_id}"):
            return httpx.Response(200, json=_persona_json(str(persona_id), "QA", str(workspace_id)))
        return httpx.Response(404, json={"detail": "weg"})

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
            result = await client.call_tool("get_persona", {"identifier": str(persona_id)})
            return result.data

    # fastmcp deserialisiert in ein dynamisch generiertes Modell mit denselben
    # Feldern; `cast` ist ein Runtime-No-Op und stillt nur den Typecheck.
    data = cast(PersonaWithPlaybooks, asyncio.run(_run()))
    assert data.body_rendered == "Profil-Briefing\n\n## Skills"
    assert data.persona.name == "QA"


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
