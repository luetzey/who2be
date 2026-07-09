"""Tests fuer das MCP-Tool `list_placeholders` + `ApiClient.list_placeholders` (WP-A).

Muster wie test_whoami_tool.py: kein pytest-asyncio, `build_client` per
monkeypatch, `httpx.MockTransport`. Deckt den Roundtrip (Tool → Client → API →
Model) und die Tool-Registrierung ab.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from uuid import uuid4

import httpx
import pytest
from fastmcp.exceptions import ToolError

from who2be_mcp import server
from who2be_mcp.client import ApiClient
from who2be_mcp.server import list_placeholders, mcp
from who2be_models import PlaceholderCatalog

_WORKSPACE_ID = uuid4()


def _factory(handler: Callable[[httpx.Request], httpx.Response]) -> Callable[[], object]:
    transport = httpx.MockTransport(handler)

    async def _build() -> ApiClient:
        return ApiClient("http://test", "token", _WORKSPACE_ID, transport=transport)

    return _build


_CATALOG_PAYLOAD: dict[str, object] = {
    "kinds": [
        {
            "kind": "persona-field",
            "description": "Bettet ein Persona-Feld ein.",
            "target_id_semantics": "Feldname der Persona.",
            "target_id_values": ["name", "description", "profile", "profile-body", "modes"],
            "example": {
                "type": "placeholder",
                "props": {
                    "kind": "persona-field",
                    "target_id": "profile",
                    "label": "Persona: Profil",
                },
            },
        }
    ]
}


def test_list_placeholders_returns_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        return httpx.Response(200, json=_CATALOG_PAYLOAD)

    monkeypatch.setattr(server, "build_client", _factory(handler))

    result = asyncio.run(list_placeholders())

    assert seen["method"] == "GET"
    assert seen["path"].endswith("/placeholders")
    assert isinstance(result, PlaceholderCatalog)
    assert result.kinds[0].kind == "persona-field"
    assert result.kinds[0].example.props.target_id == "profile"
    assert "profile" in result.kinds[0].target_id_values


def test_list_placeholders_propagates_unauthorized(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "nope"})

    monkeypatch.setattr(server, "build_client", _factory(handler))

    with pytest.raises(ToolError):
        asyncio.run(list_placeholders())


def test_server_exposes_list_placeholders_tool() -> None:
    tools = {tool.name: tool for tool in asyncio.run(mcp.list_tools())}
    assert "list_placeholders" in tools
    description = tools["list_placeholders"].description or ""
    # Der Docstring verweist auf das echte BlockNote-Inline-Format.
    assert '"type": "placeholder"' in description
    assert "create_system_prompt" in description
