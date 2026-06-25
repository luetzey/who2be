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
    list_resource_blocks,
    list_resources,
)
from who2be_models import ResourceBlockAnchor, ResourceRead

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
        path = request.url.path
        if path.endswith(f"/resources/{rid}/sub_resources"):
            return httpx.Response(200, json=[])
        assert path.endswith(f"/resources/{rid}")
        return httpx.Response(200, json=payload)

    monkeypatch.setattr(server, "build_client", _factory(handler))

    full = asyncio.run(fetch_resource(str(rid)))
    assert isinstance(full, ResourceRead)
    assert [b.id for b in full.content.blocks] == ["b1", "b2", "b3"]
    assert full.sub_resources == []

    filtered = asyncio.run(fetch_resource(str(rid), block_ids=["b3", "b1"]))
    assert [b.id for b in filtered.content.blocks] == ["b3", "b1"]


def test_fetch_resource_attaches_direct_sub_resources(monkeypatch: pytest.MonkeyPatch) -> None:
    """§3.3: fetch_resource liefert eigenen Body + direkte Sub-Resource-Tabelle.

    Die Kinder werden NICHT expandiert — jeder Eintrag traegt nur Pointer-Daten
    plus die fertige `fetch_call`-Anweisung.
    """
    rid = uuid4()
    child_id = uuid4()
    payload = _resource_payload(blocks=[_block("b1", "Eigener Body")])
    payload["id"] = str(rid)
    sub = {
        "id": str(child_id),
        "name": "Kind-Doc",
        "link_scope": "resource",
        "block_id": None,
        "position": 0,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith(f"/resources/{rid}/sub_resources"):
            return httpx.Response(200, json=[sub])
        if path.endswith(f"/resources/{rid}"):
            return httpx.Response(200, json=payload)
        return httpx.Response(404)

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(fetch_resource(str(rid)))
    assert isinstance(result, ResourceRead)
    # Eigener Body bleibt inline.
    assert [b.id for b in result.content.blocks] == ["b1"]
    # Direkte Sub-Resources als Pointer mit fetch_call, nicht expandiert.
    assert len(result.sub_resources) == 1
    assert result.sub_resources[0].id == child_id
    assert result.sub_resources[0].name == "Kind-Doc"
    assert result.sub_resources[0].fetch_call == f"fetch_resource('{child_id}')"
    # Default 'lazy' → kein Inline-Dokument.
    assert result.sub_resources[0].embedding_mode == "lazy"
    assert result.inline_sub_resources == []


def test_fetch_resource_inlines_inline_mode_sub_resource(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """embedding_mode='inline': das Kind-Volldokument haengt zusaetzlich an.

    Lazy-Kinder bleiben reine Pointer; nur 'inline' (link_scope='resource')
    zieht das Volldokument in `inline_sub_resources` (eine Ebene).
    """
    rid = uuid4()
    inline_child = uuid4()
    lazy_child = uuid4()
    parent = _resource_payload(blocks=[_block("b1", "Eigener Body")])
    parent["id"] = str(rid)
    child_payload = _resource_payload(name="Inline-Kind", blocks=[_block("c1", "Kind-Body")])
    child_payload["id"] = str(inline_child)
    subs = [
        {
            "id": str(inline_child),
            "name": "Inline-Kind",
            "link_scope": "resource",
            "block_id": None,
            "position": 0,
            "embedding_mode": "inline",
        },
        {
            "id": str(lazy_child),
            "name": "Lazy-Kind",
            "link_scope": "resource",
            "block_id": None,
            "position": 1,
            "embedding_mode": "lazy",
        },
    ]
    child_fetches = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal child_fetches
        path = request.url.path
        if path.endswith(f"/resources/{rid}/sub_resources"):
            return httpx.Response(200, json=subs)
        if path.endswith(f"/resources/{rid}"):
            return httpx.Response(200, json=parent)
        if path.endswith(f"/resources/{inline_child}"):
            child_fetches += 1
            return httpx.Response(200, json=child_payload)
        return httpx.Response(404)

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(fetch_resource(str(rid)))
    assert isinstance(result, ResourceRead)
    # Beide Kinder bleiben in der Pointer-Tabelle.
    assert len(result.sub_resources) == 2
    # Nur das 'inline'-Kind wird als Volldokument expandiert.
    assert len(result.inline_sub_resources) == 1
    assert result.inline_sub_resources[0].id == inline_child
    assert [b.id for b in result.inline_sub_resources[0].content.blocks] == ["c1"]
    # Das Lazy-Kind wird NICHT nachgeladen.
    assert child_fetches == 1


def test_list_resource_blocks_returns_anchors(monkeypatch: pytest.MonkeyPatch) -> None:
    """WP-6: list_resource_blocks reicht die Heading-Anker der API durch."""
    rid = uuid4()
    anchors = [
        {"block_id": "h1", "level": 1, "text": "Erster Block"},
        {"block_id": "h2", "level": 2, "text": "Zweiter"},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith(f"/resources/{rid}/blocks")
        return httpx.Response(200, json=anchors)

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(list_resource_blocks(str(rid)))
    assert len(result) == 2
    assert all(isinstance(a, ResourceBlockAnchor) for a in result)
    assert [a.block_id for a in result] == ["h1", "h2"]
    assert result[0].level == 1
    assert result[0].text == "Erster Block"
    assert result[1].level == 2


def test_list_resource_blocks_passes_locale(monkeypatch: pytest.MonkeyPatch) -> None:
    """WP-6: list_resource_blocks reicht den locale-Parameter an die API durch."""
    rid = uuid4()
    received: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        for key, value in request.url.params.items():
            received[key] = value
        return httpx.Response(200, json=[])

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(list_resource_blocks(str(rid), locale="en"))
    assert result == []
    assert received.get("locale") == "en"


def test_list_resource_blocks_validates_uuid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        server,
        "build_client",
        _factory(lambda request: httpx.Response(200, json=[])),
    )
    with pytest.raises(ToolError):
        asyncio.run(list_resource_blocks("not-a-uuid"))


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
        "embedding_mode": "inline",
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
    # Volldokument ist mit ausgeliefert (embedding_mode='inline').
    assert len(result.linked_resources) == 1
    assert result.linked_resources[0].id == rid
    assert [b.id for b in result.linked_resources[0].content.blocks] == ["b1"]


def test_fetch_playbook_lazy_resource_scope_link_not_inlined(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default 'lazy': ein 'resource'-scope-Link bleibt reiner Pointer.

    Bewusst breaking gegenueber dem Alt-Verhalten (immer inline) — der Agent
    laedt das Dokument bei Bedarf via fetch_resource nach.
    """
    pid = uuid4()
    rid = uuid4()
    playbook = _playbook_payload()
    playbook["id"] = str(pid)
    resource = _resource_payload(blocks=[_block("b1", "Lazy-Inhalt")])
    resource["id"] = str(rid)
    # Kein embedding_mode im Payload → Wire-Default 'lazy'.
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
    resource_fetches = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal resource_fetches
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
            resource_fetches += 1
            return httpx.Response(200, json=resource)
        return httpx.Response(404)

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(fetch_playbook(str(pid)))
    assert isinstance(result, PlaybookWithResources)
    # Link bleibt als Pointer sichtbar, aber NICHT inline.
    assert len(result.linked_blocks) == 1
    assert result.linked_blocks[0].embedding_mode == "lazy"
    assert result.linked_resources == []
    # Lazy-Link wird gar nicht erst nachgeladen.
    assert resource_fetches == 0


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
            "embedding_mode": "inline",
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
