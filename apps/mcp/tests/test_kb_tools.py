"""Tests der MCP-KB-Tools (WP9, ADR-0047) — Muster A: DB-los.

Jedes Tool wird direkt als Funktion aufgerufen; die REST-Seite simuliert
`httpx.MockTransport`, `server.build_client` wird je Test auf eine Factory
mit diesem Transport gepatcht. Geprueft werden Methode, Pfad und Body der
Requests (der Fehlerkontrakt kommt ueber `_raise_for_status` gratis) sowie
die Modell-Validierungen, die als `ToolError` an den Agenten gehen.
"""

import asyncio
import json
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
import pytest
from fastmcp.exceptions import ToolError

from who2be_mcp import server
from who2be_mcp.client import ApiClient
from who2be_mcp.tools.kb import (
    create_edge,
    create_node,
    neighbors,
    search_kb,
    update_node,
)
from who2be_models import EdgeType, NodeTier

_WORKSPACE_ID = uuid4()
_PREFIX = f"/v1/workspaces/{_WORKSPACE_ID}"
_OCCURRED = datetime(2026, 8, 1, tzinfo=UTC)


def _factory(handler: Callable[[httpx.Request], httpx.Response]) -> Callable[[], object]:
    transport = httpx.MockTransport(handler)

    async def _build() -> ApiClient:
        return ApiClient("http://test", "token", _WORKSPACE_ID, transport=transport)

    return _build


def _body(request: httpx.Request) -> dict[str, object]:
    return dict(json.loads(request.content.decode()))


def _node_payload(node_id: UUID, tier: str = "hypothesis") -> dict[str, object]:
    return {
        "id": str(node_id),
        "workspace_id": str(_WORKSPACE_ID),
        "tier": tier,
        "content": "Kunde Alpha bevorzugt Indigo.",
        "content_ref": None,
        "source_ref": "url:https://example.com",
        "source_ref_kind": "url",
        "ttl_expires_at": None,
        "status": "live",
        "derivation_depth": 0,
        "sensitivity": "general",
        "occurred_at": "2026-08-01T00:00:00Z",
        "occurred_precision": "day",
        "created_by": None,
        "created_at": "2026-08-01T00:00:00Z",
        "updated_at": "2026-08-01T00:00:00Z",
    }


def test_search_kb_hits_kb_search_route(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["params"] = dict(request.url.params)
        return httpx.Response(
            200,
            json=[
                {
                    "node_id": str(uuid4()),
                    "anchor": "node:abc",
                    "snippet": "…Indigo…",
                    "tier": "derived",
                    "status": "live",
                    "score": 0.7,
                }
            ],
        )

    monkeypatch.setattr(server, "build_client", _factory(handler))
    hits = asyncio.run(search_kb("indigo", 5))
    assert seen["method"] == "GET"
    assert seen["path"] == f"{_PREFIX}/kb-search"
    assert seen["params"] == {"q": "indigo", "limit": "5"}
    assert hits[0].anchor == "node:abc"


def test_create_node_posts_body(monkeypatch: pytest.MonkeyPatch) -> None:
    node_id = uuid4()
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["body"] = _body(request)
        return httpx.Response(201, json=_node_payload(node_id))

    monkeypatch.setattr(server, "build_client", _factory(handler))
    node = asyncio.run(
        create_node(
            content="Kunde Alpha bevorzugt Indigo.",
            tier=NodeTier.hypothesis,
            source_ref="url:https://example.com",
            occurred_at=_OCCURRED,
        )
    )
    assert seen["method"] == "POST"
    assert seen["path"] == f"{_PREFIX}/kb/nodes"
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["tier"] == "hypothesis"
    assert body["source_ref"] == "url:https://example.com"
    assert body["occurred_precision"] == "day"
    assert str(node.id) == str(node_id)


def test_update_node_patches_by_id(monkeypatch: pytest.MonkeyPatch) -> None:
    node_id = uuid4()
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["body"] = _body(request)
        return httpx.Response(200, json=_node_payload(node_id, tier="derived"))

    monkeypatch.setattr(server, "build_client", _factory(handler))
    asyncio.run(
        update_node(
            str(node_id), tier=NodeTier.derived, additional_source_ref="sha256:" + "ab" * 32
        )
    )
    assert seen["method"] == "PATCH"
    assert seen["path"] == f"{_PREFIX}/kb/nodes/{node_id}"
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["tier"] == "derived"


def test_update_node_requires_a_field(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "build_client", _factory(lambda _r: httpx.Response(500)))
    with pytest.raises(ToolError):
        asyncio.run(update_node(str(uuid4())))


def test_update_node_rejects_bad_uuid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "build_client", _factory(lambda _r: httpx.Response(500)))
    with pytest.raises(ToolError):
        asyncio.run(update_node("keine-uuid", content="x"))


def test_create_edge_posts_co_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}
    edge_id = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = _body(request)
        return httpx.Response(
            201,
            json={
                "id": str(edge_id),
                "workspace_id": str(_WORKSPACE_ID),
                "type": "co_occurs_with",
                "from_anchor": "node:a",
                "to_anchor": "node:b",
                "from_node_id": None,
                "to_node_id": None,
                "evidence_from": ["url:https://example.com/q"],
                "evidence_to": ["url:https://example.com/q"],
                "co_query": "SELECT 1",
                "co_n": 34,
                "co_from": "2026-07-01T00:00:00Z",
                "co_to": "2026-08-01T00:00:00Z",
                "created_by": None,
                "created_at": "2026-08-01T00:00:00Z",
            },
        )

    monkeypatch.setattr(server, "build_client", _factory(handler))
    asyncio.run(
        create_edge(
            from_anchor="node:" + str(uuid4()),
            to_anchor="node:" + str(uuid4()),
            type=EdgeType.co_occurs_with,
            evidence_from=["url:https://example.com/q"],
            evidence_to=["url:https://example.com/q"],
            co_query="SELECT 1",
            co_n=34,
            co_from=datetime(2026, 7, 1, tzinfo=UTC),
            co_to=_OCCURRED,
        )
    )
    assert seen["path"] == f"{_PREFIX}/kb/edges"
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["co_n"] == 34
    assert body["type"] == "co_occurs_with"


def test_create_edge_without_co_fields_is_tool_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """co_occurs_with ohne Statistik-Felder scheitert am MODELL (kein Request)."""
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(500)

    monkeypatch.setattr(server, "build_client", _factory(handler))
    with pytest.raises(ToolError):
        asyncio.run(
            create_edge(
                from_anchor="node:" + str(uuid4()),
                to_anchor="node:" + str(uuid4()),
                type=EdgeType.co_occurs_with,
                evidence_from=["url:https://example.com"],
                evidence_to=["url:https://example.com"],
            )
        )
    assert calls == []


def test_neighbors_returns_co_n(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["params"] = dict(request.url.params)
        return httpx.Response(
            200,
            json=[
                {
                    "node": _node_payload(uuid4()),
                    "edge_type": "co_occurs_with",
                    "direction": "out",
                    "co_n": 34,
                }
            ],
        )

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(neighbors("node:" + str(uuid4()), EdgeType.co_occurs_with, 2))
    assert seen["path"] == f"{_PREFIX}/kb/neighbors"
    params = seen["params"]
    assert isinstance(params, dict)
    assert params["type"] == "co_occurs_with"
    assert params["depth"] == "2"
    assert result[0].co_n == 34
