"""Tool-Tests fuer die ExternalTool-MCP-Tools (WP-3) gegen eine gemockte API.

Spiegelt das Muster aus test_resource_tools.py: die async Tools werden ueber
`asyncio.run` getrieben (kein pytest-asyncio im Stack), der HTTP-Verkehr laeuft
ueber `httpx.MockTransport`, `build_client` wird je Test auf eine Factory
gepatcht.
"""

import asyncio
import json
from collections.abc import Callable
from uuid import uuid4

import httpx
import pytest
from fastmcp.exceptions import ToolError

from who2be_mcp import server
from who2be_mcp.client import ApiClient
from who2be_mcp.server import (
    create_external_tool,
    diff_versions,
    get_external_tool,
    list_external_tools,
    restore_external_tool,
    transition_external_tool,
    update_external_tool,
)
from who2be_models import (
    ExternalToolContent,
    ExternalToolCreate,
    ExternalToolRead,
    ExternalToolUpdate,
    ExternalToolVersionRead,
    VersionStatus,
)

_WORKSPACE_ID = uuid4()


def _factory(handler: Callable[[httpx.Request], httpx.Response]) -> Callable[[], object]:
    transport = httpx.MockTransport(handler)

    async def _build() -> ApiClient:
        return ApiClient("http://test", "token", _WORKSPACE_ID, transport=transport)

    return _build


def _tool_payload(
    name: str = "Todoist",
    alias: str = "todo",
    tags: list[str] | None = None,
) -> dict[str, object]:
    return {
        "id": str(uuid4()),
        "workspace_id": str(_WORKSPACE_ID),
        "owner_id": str(uuid4()),
        "name": name,
        "alias": alias,
        "current_version": 1,
        "is_managed": False,
        "current_status": "active",
        "has_pending_draft": False,
        "locale": "de",
        "content": {
            "display_name": name,
            "mcp_server_name": f"{name} MCP",
            "tool_names": ["add_task", "list_tasks"],
            "usage_notes": "Fuer Aufgaben nutzen.",
            "fallback_note": None,
            "tags": tags if tags is not None else [],
        },
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }


def _workspace_json(content_locale: str = "de") -> dict[str, object]:
    return {
        "id": str(_WORKSPACE_ID),
        "org_id": str(uuid4()),
        "name": "WS",
        "slug": "ws",
        "content_locale": content_locale,
        "created_at": "2024-01-01T00:00:00Z",
    }


def _version_payload(version: int = 1, status: str = "active") -> dict[str, object]:
    return {
        "version": version,
        "status": status,
        "locale": "de",
        "content": {
            "display_name": "Todoist",
            "mcp_server_name": "Todoist MCP",
            "tool_names": ["add_task"],
            "usage_notes": "",
            "fallback_note": None,
            "tags": [],
        },
        "created_by": str(uuid4()),
        "created_at": "2024-01-01T00:00:00Z",
    }


def test_list_external_tools_returns_reads(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _tool_payload()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/external_tools")
        return httpx.Response(200, json=[payload])

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(list_external_tools())
    assert len(result) == 1
    assert isinstance(result[0], ExternalToolRead)
    assert result[0].alias == "todo"


def test_list_external_tools_filters_by_tag_client_side(monkeypatch: pytest.MonkeyPatch) -> None:
    """Kein REST-`?tag=`-Endpoint fuer ExternalTool — der Filter laeuft im Tool."""
    matching = _tool_payload(name="Todoist", alias="todo", tags=["produktivitaet"])
    other = _tool_payload(name="Kalender", alias="calendar", tags=["planung"])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[matching, other])

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(list_external_tools(tag="produktivitaet"))
    assert len(result) == 1
    assert result[0].alias == "todo"


def test_get_external_tool_resolves_uuid(monkeypatch: pytest.MonkeyPatch) -> None:
    tid = uuid4()
    payload = _tool_payload()
    payload["id"] = str(tid)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith(f"/external_tools/{tid}")
        return httpx.Response(200, json=payload)

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(get_external_tool(str(tid)))
    assert isinstance(result, ExternalToolRead)
    assert result.id == tid


def test_get_external_tool_resolves_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nicht-UUID-Identifier => Aliasnamen-Aufloesung ueber die Liste (spiegelt
    `get_persona`s UUID-oder-Name-Pfad)."""
    payload = _tool_payload(name="Todoist", alias="todo")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/external_tools")
        return httpx.Response(200, json=[payload])

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(get_external_tool("todo"))
    assert isinstance(result, ExternalToolRead)
    assert result.alias == "todo"


def test_get_external_tool_unknown_alias_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    empty_list_handler = _factory(lambda request: httpx.Response(200, json=[]))
    monkeypatch.setattr(server, "build_client", empty_list_handler)
    with pytest.raises(ToolError, match="todo"):
        asyncio.run(get_external_tool("todo"))


def test_create_external_tool_forwards_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    seen_names: list[object] = []

    def handler(request: httpx.Request) -> httpx.Response:
        # `create_external_tool` loest `data.locale=None` zuerst ueber ein
        # `GET .../workspaces/{id}` auf die Workspace-Content-Sprache auf
        # (WP4, Plan „Ein Element, eine Sprache").
        if request.method == "GET" and request.url.path == f"/v1/workspaces/{_WORKSPACE_ID}":
            return httpx.Response(200, json=_workspace_json())
        assert request.method == "POST"
        assert request.url.path.endswith("/external_tools")
        seen_names.append(json.loads(request.content)["name"])
        return httpx.Response(201, json=_tool_payload())

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(
        create_external_tool(
            ExternalToolCreate(name="Todoist", content=ExternalToolContent(display_name="Todoist"))
        )
    )
    assert isinstance(result, ExternalToolRead)
    assert seen_names == ["Todoist"]


def test_update_external_tool_sends_put(monkeypatch: pytest.MonkeyPatch) -> None:
    tid = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PUT"
        assert request.url.path.endswith(f"/external_tools/{tid}")
        return httpx.Response(200, json=_tool_payload())

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(
        update_external_tool(str(tid), ExternalToolUpdate(content=ExternalToolContent()))
    )
    assert isinstance(result, ExternalToolRead)


def test_transition_external_tool_posts_transition(monkeypatch: pytest.MonkeyPatch) -> None:
    tid = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path.endswith(f"/external_tools/{tid}/versions/1/transition")
        return httpx.Response(200, json=_version_payload(status="review"))

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(transition_external_tool(str(tid), 1, VersionStatus.review))
    assert isinstance(result, ExternalToolVersionRead)
    assert result.status == VersionStatus.review


def test_restore_external_tool_posts_restore(monkeypatch: pytest.MonkeyPatch) -> None:
    tid = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path.endswith(f"/external_tools/{tid}/versions/1/restore")
        return httpx.Response(201, json=_tool_payload())

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(restore_external_tool(str(tid), 1))
    assert isinstance(result, ExternalToolRead)


def test_get_external_tool_validates_uuid_shaped_but_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein UUID-parsbarer Identifier ohne Treffer wird als UUID behandelt (404),
    NICHT als Alias-Suche (Verhalten spiegelt get_persona)."""
    tid = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "nicht gefunden"})

    monkeypatch.setattr(server, "build_client", _factory(handler))
    with pytest.raises(ToolError):
        asyncio.run(get_external_tool(str(tid)))


def test_diff_versions_rejects_external_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    """Kein REST-Diff-Endpunkt fuer ExternalTool (WP-1) — sauberer ToolError
    statt eines generischen 404-Durchgriffs."""
    tid = uuid4()
    monkeypatch.setattr(
        server, "build_client", _factory(lambda request: httpx.Response(404, json={}))
    )
    with pytest.raises(ToolError, match="external_tool"):
        asyncio.run(diff_versions("external_tool", str(tid), 1))
