"""Tool-Test fuer das Discovery-/Search-MCP-Tool (ADR-0037).

`search` ist ein duenner Adapter ueber `GET /search`. Muster wie
test_resource_tools: async Tool via `asyncio.run`, HTTP ueber `MockTransport`.
"""

import asyncio
from collections.abc import Callable
from uuid import uuid4

import httpx
import pytest

from who2be_mcp import server
from who2be_mcp.client import ApiClient
from who2be_mcp.server import search
from who2be_models import SearchHit

_WORKSPACE_ID = uuid4()


def _factory(handler: Callable[[httpx.Request], httpx.Response]) -> Callable[[], object]:
    transport = httpx.MockTransport(handler)

    async def _build() -> ApiClient:
        return ApiClient("http://test", "token", _WORKSPACE_ID, transport=transport)

    return _build


def test_search_returns_ranked_hits(monkeypatch: pytest.MonkeyPatch) -> None:
    pid = uuid4()
    rid = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/search")
        assert request.url.params.get("q") == "reklamation"
        return httpx.Response(
            200,
            json=[
                {
                    "type": "playbook",
                    "id": str(pid),
                    "name": "Reklamation",
                    "snippet": "x",
                    "score": 0.9,
                },
                {"type": "resource", "id": str(rid), "name": "Doc", "snippet": "y", "score": 0.3},
            ],
        )

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(search("reklamation"))
    assert len(result) == 2
    assert all(isinstance(h, SearchHit) for h in result)
    assert result[0].type == "playbook"
    assert result[0].score == 0.9


def test_search_passes_types_and_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        for key, value in request.url.params.items():
            seen[key] = value
        return httpx.Response(200, json=[])

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(search("x", types=["playbook", "resource"], limit=5))
    assert result == []
    assert seen.get("types") == "playbook,resource"
    assert seen.get("limit") == "5"
