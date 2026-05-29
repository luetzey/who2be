"""Tool-Tests fuer die Resource-MCP-Tools (Phase 2.2) gegen eine gemockte API.

Spiegelt das Muster aus test_tools.py: ein `httpx.MockTransport` faengt die
HTTP-Calls ab, `build_client` wird auf eine Factory gepatcht. So decken die
Tests Tool-Logik UND Client-URL-Aufbau ab, ohne echten Server.
"""

from collections.abc import Callable
from uuid import uuid4

import httpx
import pytest

from who2be_mcp import server
from who2be_mcp.client import ApiClient
from who2be_mcp.server import (
    PlaybookWithResources,
    ResourceSummary,
    fetch_playbook,
    fetch_resource,
    list_resources,
)
from who2be_models import ResourceRead

_WORKSPACE_ID = uuid4()


def _client_with(handler: Callable[[httpx.Request], httpx.Response]) -> ApiClient:
    transport = httpx.MockTransport(handler)
    return ApiClient("http://test", "token", _WORKSPACE_ID, transport=transport)


def _patch_build_client(
    monkeypatch: pytest.MonkeyPatch, handler: Callable[[httpx.Request], httpx.Response]
) -> None:
    async def _factory() -> ApiClient:
        return _client_with(handler)

    monkeypatch.setattr(server, "build_client", _factory)


def _block(block_id: str, text: str) -> dict:
    return {
        "id": block_id,
        "type": "paragraph",
        "props": {},
        "content": [{"type": "text", "text": text, "styles": {}}],
        "children": [],
    }


def _resource_payload(name: str = "Doc", blocks: list[dict] | None = None) -> dict:
    return {
        "id": str(uuid4()),
        "workspace_id": str(_WORKSPACE_ID),
        "owner_id": str(uuid4()),
        "name": name,
        "current_version": 1,
        "current_status": "active",
        "has_pending_draft": False,
        "content": {
            "description": "",
            "blocks": blocks if blocks is not None else [_block("b1", "Hallo")],
        },
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }


def _playbook_payload(name: str = "Onboard") -> dict:
    return {
        "id": str(uuid4()),
        "workspace_id": str(_WORKSPACE_ID),
        "owner_id": str(uuid4()),
        "name": name,
        "current_version": 1,
        "current_status": "active",
        "has_pending_draft": False,
        "type": "workflow",
        "tags": [],
        "triggers": None,
        "content": {
            "description": "d",
            "body": "b",
            "type": "workflow",
            "tags": [],
            "triggers": None,
        },
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }


@pytest.mark.asyncio
async def test_list_resources_returns_summaries(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _resource_payload(blocks=[_block("b1", "a"), _block("b2", "b")])

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/resources")
        return httpx.Response(200, json=[payload])

    _patch_build_client(monkeypatch, handler)
    result = await list_resources()
    assert len(result) == 1
    assert isinstance(result[0], ResourceSummary)
    assert result[0].block_count == 2
    assert result[0].name == "Doc"


@pytest.mark.asyncio
async def test_fetch_resource_filters_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    rid = uuid4()
    payload = _resource_payload(
        blocks=[_block("b1", "a"), _block("b2", "b"), _block("b3", "c")]
    )
    payload["id"] = str(rid)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith(f"/resources/{rid}")
        return httpx.Response(200, json=payload)

    _patch_build_client(monkeypatch, handler)

    full = await fetch_resource(str(rid))
    assert isinstance(full, ResourceRead)
    assert [b.id for b in full.content.blocks] == ["b1", "b2", "b3"]

    filtered = await fetch_resource(str(rid), block_ids=["b3", "b1"])
    assert [b.id for b in filtered.content.blocks] == ["b3", "b1"]


@pytest.mark.asyncio
async def test_fetch_resource_validates_uuid(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_build_client(monkeypatch, lambda request: httpx.Response(200, json=_resource_payload()))
    with pytest.raises(Exception):
        await fetch_resource("not-a-uuid")


@pytest.mark.asyncio
async def test_fetch_playbook_includes_linked_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    pid = uuid4()
    playbook = _playbook_payload()
    playbook["id"] = str(pid)
    link = {
        "resource_id": str(uuid4()),
        "resource_name": "Doc",
        "block_id": "b1",
        "position": 0,
        "available": True,
        "preview": "Hallo",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith(f"/playbooks/{pid}/resource_links"):
            return httpx.Response(200, json=[link])
        if request.url.path.endswith(f"/playbooks/{pid}"):
            return httpx.Response(200, json=playbook)
        return httpx.Response(404)

    _patch_build_client(monkeypatch, handler)
    result = await fetch_playbook(str(pid))
    assert isinstance(result, PlaybookWithResources)
    assert len(result.linked_blocks) == 1
    assert result.linked_blocks[0].block_id == "b1"
    assert result.linked_blocks[0].available is True
