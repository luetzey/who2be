"""Tool-Tests fuer die Resource-MCP-Tools (Phase 2.2) gegen eine gemockte API.

Spiegelt das Muster aus test_server.py: die async Tools werden ueber
`asyncio.run` getrieben (kein pytest-asyncio im Stack), der HTTP-Verkehr laeuft
ueber `httpx.MockTransport`, `build_client` wird je Test auf eine Factory
gepatcht.
"""

import asyncio
from collections.abc import Callable
from uuid import uuid4

import httpx
import pytest
from fastmcp.exceptions import ToolError

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


def _factory(handler: Callable[[httpx.Request], httpx.Response]) -> Callable[[], object]:
    transport = httpx.MockTransport(handler)

    async def _build() -> ApiClient:
        return ApiClient("http://test", "token", _WORKSPACE_ID, transport=transport)

    return _build


def _block(block_id: str, text: str) -> dict[str, object]:
    return {
        "id": block_id,
        "type": "paragraph",
        "props": {},
        "content": [{"type": "text", "text": text, "styles": {}}],
        "children": [],
    }


def _resource_payload(
    name: str = "Doc", blocks: list[dict[str, object]] | None = None
) -> dict[str, object]:
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


def _playbook_payload(name: str = "Onboard") -> dict[str, object]:
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


def test_list_resources_returns_summaries(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _resource_payload(blocks=[_block("b1", "a"), _block("b2", "b")])

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/resources")
        return httpx.Response(200, json=[payload])

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(list_resources())
    assert len(result) == 1
    assert isinstance(result[0], ResourceSummary)
    assert result[0].block_count == 2
    assert result[0].name == "Doc"


def test_list_resources_summary_includes_tags(monkeypatch: pytest.MonkeyPatch) -> None:
    """E3: ResourceSummary.tags spiegelt content.tags der Resource."""
    payload = _resource_payload(blocks=[_block("b1", "x")])
    payload["content"]["tags"] = ["wissen", "onboarding"]  # type: ignore[index]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[payload])

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(list_resources())
    assert len(result) == 1
    assert result[0].tags == ["wissen", "onboarding"]


def test_list_resources_summary_empty_tags_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """E3: Resource ohne Tags liefert leere Tags-Liste (Backward-Compat)."""
    payload = _resource_payload()  # kein 'tags' im content

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[payload])

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(list_resources())
    assert result[0].tags == []


def test_list_resources_passes_tag_filter_to_api(monkeypatch: pytest.MonkeyPatch) -> None:
    """E3: list_resources(tag='x') reicht den tag-Parameter an den API-Client durch."""
    received_params: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        # Anfrage-Query-String auf tag pruefen
        for key, value in request.url.params.items():
            received_params[key] = value
        return httpx.Response(200, json=[])

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(list_resources(tag="wissen"))
    assert result == []
    assert received_params.get("tag") == "wissen"


def test_list_resources_without_tag_sends_no_tag_param(monkeypatch: pytest.MonkeyPatch) -> None:
    """E3: list_resources() ohne tag sendet keinen tag-Parameter (kein ?tag=None)."""
    received_params: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        for key, value in request.url.params.items():
            received_params[key] = value
        return httpx.Response(200, json=[])

    monkeypatch.setattr(server, "build_client", _factory(handler))
    asyncio.run(list_resources())
    assert "tag" not in received_params


def test_fetch_resource_filters_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    rid = uuid4()
    payload = _resource_payload(blocks=[_block("b1", "a"), _block("b2", "b"), _block("b3", "c")])
    payload["id"] = str(rid)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith(f"/resources/{rid}")
        return httpx.Response(200, json=payload)

    monkeypatch.setattr(server, "build_client", _factory(handler))

    full = asyncio.run(fetch_resource(str(rid)))
    assert isinstance(full, ResourceRead)
    assert [b.id for b in full.content.blocks] == ["b1", "b2", "b3"]

    filtered = asyncio.run(fetch_resource(str(rid), block_ids=["b3", "b1"]))
    assert [b.id for b in filtered.content.blocks] == ["b3", "b1"]


def test_fetch_resource_validates_uuid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        server,
        "build_client",
        _factory(lambda request: httpx.Response(200, json=_resource_payload())),
    )
    with pytest.raises(ToolError):
        asyncio.run(fetch_resource("not-a-uuid"))


def test_fetch_playbook_includes_linked_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
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
        "link_scope": "block",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith(f"/playbooks/{pid}/resource_links"):
            return httpx.Response(200, json=[link])
        if request.url.path.endswith(f"/playbooks/{pid}/composes"):
            return httpx.Response(200, json=[])
        if request.url.path.endswith(f"/playbooks/{pid}/rendered"):
            return httpx.Response(200, json={"body_rendered": "b", "unresolved": []})
        if request.url.path.endswith(f"/playbooks/{pid}"):
            return httpx.Response(200, json=playbook)
        return httpx.Response(404)

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(fetch_playbook(str(pid)))
    assert isinstance(result, PlaybookWithResources)
    assert len(result.linked_blocks) == 1
    assert result.linked_blocks[0].block_id == "b1"
    assert result.linked_blocks[0].available is True
    assert result.linked_blocks[0].link_scope == "block"
    # Block-Refs ziehen das Volldokument NICHT mit — Snippet via fetch_resource.
    assert result.linked_resources == []
    # Kein Composite → leere composed_playbooks.
    assert result.composed_playbooks == []


def test_fetch_playbook_inlines_resource_for_resource_scope_links(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pid = uuid4()
    rid = uuid4()
    playbook = _playbook_payload()
    playbook["id"] = str(pid)
    resource = _resource_payload(blocks=[_block("b1", "Inline-Inhalt")])
    resource["id"] = str(rid)
    link = {
        "resource_id": str(rid),
        "resource_name": resource["name"],
        "block_id": None,
        "position": 0,
        "available": True,
        "available_in": "active",
        "preview": None,
        "link_scope": "resource",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith(f"/playbooks/{pid}/resource_links"):
            return httpx.Response(200, json=[link])
        if path.endswith(f"/playbooks/{pid}/composes"):
            return httpx.Response(200, json=[])
        if path.endswith(f"/playbooks/{pid}/rendered"):
            return httpx.Response(200, json={"body_rendered": "b", "unresolved": []})
        if path.endswith(f"/playbooks/{pid}"):
            return httpx.Response(200, json=playbook)
        if path.endswith(f"/resources/{rid}"):
            return httpx.Response(200, json=resource)
        return httpx.Response(404)

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(fetch_playbook(str(pid)))
    assert isinstance(result, PlaybookWithResources)
    assert len(result.linked_blocks) == 1
    assert result.linked_blocks[0].link_scope == "resource"
    assert result.linked_blocks[0].block_id is None
    # Volldokument ist mit ausgeliefert.
    assert len(result.linked_resources) == 1
    assert result.linked_resources[0].id == rid
    assert [b.id for b in result.linked_resources[0].content.blocks] == ["b1"]


def test_fetch_playbook_deduplicates_resource_scope_inline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pid = uuid4()
    rid = uuid4()
    playbook = _playbook_payload()
    playbook["id"] = str(pid)
    resource = _resource_payload(blocks=[_block("b1", "x")])
    resource["id"] = str(rid)
    # Zweimal derselbe 'resource'-Link (Service-Dedup haette das eigentlich
    # weggeraeumt; der MCP-Server muss aber idempotent bleiben).
    links = [
        {
            "resource_id": str(rid),
            "resource_name": resource["name"],
            "block_id": None,
            "position": idx,
            "available": True,
            "available_in": "active",
            "preview": None,
            "link_scope": "resource",
        }
        for idx in range(2)
    ]
    resource_fetches = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal resource_fetches
        path = request.url.path
        if path.endswith(f"/playbooks/{pid}/resource_links"):
            return httpx.Response(200, json=links)
        if path.endswith(f"/playbooks/{pid}/composes"):
            return httpx.Response(200, json=[])
        if path.endswith(f"/playbooks/{pid}/rendered"):
            return httpx.Response(200, json={"body_rendered": "b", "unresolved": []})
        if path.endswith(f"/playbooks/{pid}"):
            return httpx.Response(200, json=playbook)
        if path.endswith(f"/resources/{rid}"):
            resource_fetches += 1
            return httpx.Response(200, json=resource)
        return httpx.Response(404)

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(fetch_playbook(str(pid)))
    assert len(result.linked_resources) == 1
    assert resource_fetches == 1


def test_fetch_playbook_includes_composed_playbooks_ordered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Composite-Playbook: composed_playbooks enthaelt geordnete aktive Kinder."""
    pid = uuid4()
    child_a_id = uuid4()
    child_b_id = uuid4()
    playbook = _playbook_payload()
    playbook["id"] = str(pid)
    playbook["is_composite"] = True
    child_a = _playbook_payload("Child-A")
    child_a["id"] = str(child_a_id)
    child_b = _playbook_payload("Child-B")
    child_b["id"] = str(child_b_id)

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith(f"/playbooks/{pid}/resource_links"):
            return httpx.Response(200, json=[])
        if path.endswith(f"/playbooks/{pid}/composes"):
            # Geordnet: child_a an Position 0, child_b an Position 1
            return httpx.Response(200, json=[child_a, child_b])
        if path.endswith(f"/playbooks/{pid}/rendered"):
            return httpx.Response(200, json={"body_rendered": "b", "unresolved": []})
        if path.endswith(f"/playbooks/{pid}"):
            return httpx.Response(200, json=playbook)
        return httpx.Response(404)

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(fetch_playbook(str(pid)))
    assert isinstance(result, PlaybookWithResources)
    assert len(result.composed_playbooks) == 2
    assert result.composed_playbooks[0].id == child_a_id
    assert result.composed_playbooks[1].id == child_b_id
    assert result.composed_playbooks[0].name == "Child-A"
    assert result.composed_playbooks[1].name == "Child-B"


def test_fetch_playbook_returns_rendered_body(monkeypatch: pytest.MonkeyPatch) -> None:
    """B5: fetch_playbook liefert den serverseitig expandierten Body.

    Der MCP-Server holt den Body ueber `GET .../playbooks/{id}/rendered`; bei
    BlockNote-Bodies haben ihre Inline-Pills bereits zu Plain-Text
    aufgeloest. Hier mocken wir die API-Antwort mit dem expandierten Text.
    """
    pid = uuid4()
    playbook = _playbook_payload()
    playbook["id"] = str(pid)

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith(f"/playbooks/{pid}/resource_links"):
            return httpx.Response(200, json=[])
        if path.endswith(f"/playbooks/{pid}/composes"):
            return httpx.Response(200, json=[])
        if path.endswith(f"/playbooks/{pid}/rendered"):
            return httpx.Response(
                200,
                json={"body_rendered": "Schritt 1\n\nSub-Playbook-Inhalt", "unresolved": []},
            )
        if path.endswith(f"/playbooks/{pid}"):
            return httpx.Response(200, json=playbook)
        return httpx.Response(404)

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(fetch_playbook(str(pid)))
    assert isinstance(result, PlaybookWithResources)
    assert result.body_rendered == "Schritt 1\n\nSub-Playbook-Inhalt"
