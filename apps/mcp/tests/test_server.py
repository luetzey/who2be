"""Tests fuer den Who2Be-MCP-Server: Tool-Registrierung und ein Tool-Pfad."""

import asyncio
import json
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


def test_server_exposes_write_tools() -> None:
    """ADR-0012: die Mutations-Tools fuer alle vier Kernelemente sind registriert."""
    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}
    assert {
        "create_persona",
        "update_persona",
        "transition_persona",
        "restore_persona",
        "set_persona_playbooks",
        "create_playbook",
        "update_playbook",
        "transition_playbook",
        "restore_playbook",
        "set_playbook_resource_links",
        "set_playbook_composes",
        "create_resource",
        "update_resource",
        "transition_resource",
        "restore_resource",
        "set_resource_sub_resources",
        "create_agent",
        "update_agent",
        "copy_agent",
    } <= names


def test_transition_tools_share_state_machine_doc() -> None:
    """WP-5 (#257): alle drei transition_*-Tools tragen dieselbe State-Machine-
    Doku (SSoT `TRANSITION_RULE_DOC`) inkl. des review-Zwischenstopp-Hinweises."""
    tools = {tool.name: tool for tool in asyncio.run(mcp.list_tools())}
    for name in ("transition_persona", "transition_playbook", "transition_resource"):
        description = tools[name].description or ""
        assert "review" in description, name
        assert "draft->active geht NICHT direkt" in description, name
        assert "admin-Rolle" in description, name


def test_create_persona_tool_posts_and_returns_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    persona_id = uuid4()
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        return httpx.Response(201, json=_persona_json(str(persona_id), "Neu", str(workspace_id)))

    api_client = ApiClient(
        "http://api.test", "tok", workspace_id, transport=httpx.MockTransport(handler)
    )

    async def _build() -> ApiClient:
        return api_client

    monkeypatch.setattr(server, "build_client", _build)

    async def _run() -> object:
        async with Client(mcp) as client:
            result = await client.call_tool("create_persona", {"data": {"name": "Neu"}})
            # Ohne outputSchema (bewusst abgeschaltet, Claude-Chat-Tool-Budget)
            # liefert der Client das strukturierte Ergebnis als dict.
            return result.structured_content

    data = asyncio.run(_run())
    assert seen["method"] == "POST"
    assert str(seen["path"]).endswith("/personas")
    assert isinstance(data, dict)
    assert data["name"] == "Neu"


def test_transition_persona_tool_rejects_invalid_uuid() -> None:
    async def _run() -> None:
        async with Client(mcp) as client:
            await client.call_tool(
                "transition_persona",
                {"persona_id": "not-a-uuid", "version": 1, "to": "review"},
            )

    with pytest.raises(ToolError):
        asyncio.run(_run())


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
            return result.structured_content

    data = asyncio.run(_run())
    assert isinstance(data, dict)
    assert data["body_rendered"] == "Profil-Briefing\n\n## Skills"
    assert data["persona"]["name"] == "QA"


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
            # Ohne outputSchema liefern Listen-Ergebnisse kein structured_content —
            # der Client bekommt das JSON als Text-Content (so parst es auch Claude).
            assert result.content and result.content[0].type == "text"
            return json.loads(result.content[0].text)

    data = asyncio.run(_run())
    assert isinstance(data, list)
    assert len(data) == 1
