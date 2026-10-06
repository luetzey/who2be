"""Tool-Tests fuer die Resource-MCP-Tools (Phase 2.2) gegen eine gemockte API.

Spiegelt das Muster aus test_server.py: die async Tools werden ueber
`asyncio.run` getrieben (kein pytest-asyncio im Stack), der HTTP-Verkehr laeuft
ueber `httpx.MockTransport`, `build_client` wird je Test auf eine Factory
gepatcht.
"""

import asyncio
import json
from collections.abc import Callable
from uuid import UUID, uuid4

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
        "slug": name.lower().replace(" ", "-"),
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


def test_list_resources_summary_carries_locale_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    """WP4 (Plan „Ein Element, eine Sprache"): jeder `ResourceSummary`-Eintrag
    traegt die Sprache der Resource im Top-Level-Feld `locale`."""
    payload = _resource_payload()
    payload["locale"] = "en"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[payload])

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(list_resources())
    assert result[0].locale == "en"


def test_list_resources_forwards_locale_as_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    """WP4: `list_resources(locale=...)` wirkt als optionaler Sprachfilter auf
    der REST-Query (`None`-Default = kein Filter, alle Sprachen)."""
    received_params: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        for key, value in request.url.params.items():
            received_params[key] = value
        return httpx.Response(200, json=[])

    monkeypatch.setattr(server, "build_client", _factory(handler))
    asyncio.run(list_resources(locale="en"))
    assert received_params.get("locale") == "en"


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


def test_fetch_resource_old_client_explicit_locale_still_works(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WP4: ein Alt-Client-Aufruf mit explizitem `locale='de'` funktioniert
    unveraendert — der Parameter wird akzeptiert (Backward-Compat), aber nicht
    mehr zur Aufloesung genutzt (die Resource ist bereits per UUID eindeutig).
    Die tatsaechliche Sprache traegt die Antwort selbst im `locale`-Feld."""
    rid = uuid4()
    payload = _resource_payload()
    payload["id"] = str(rid)
    payload["locale"] = "en"

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith(f"/resources/{rid}/sub_resources"):
            return httpx.Response(200, json=[])
        return httpx.Response(200, json=payload)

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(fetch_resource(str(rid), locale="de"))
    assert isinstance(result, ResourceRead)
    # Die Antwort traegt die tatsaechliche Resource-Sprache, NICHT den
    # (ignorierten) Alt-Client-Parameter.
    assert result.locale == "en"


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


def test_list_resource_blocks_ignores_locale(monkeypatch: pytest.MonkeyPatch) -> None:
    """Plan „Ein Element, eine Sprache" (2026-07-24): `locale` ist ein
    Backward-Compat-Parameter (frueher: Variantenwahl, WP-6/ADR-0027) und wird
    nicht mehr an die API weitergereicht — die Resource ist per UUID eindeutig."""
    rid = uuid4()
    received: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        for key, value in request.url.params.items():
            received[key] = value
        return httpx.Response(200, json=[])

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(list_resource_blocks(str(rid), locale="en"))
    assert result == []
    assert "locale" not in received


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
    result = asyncio.run(fetch_playbook(str(pid), format="full"))
    assert isinstance(result, PlaybookWithResources)
    assert len(result.linked_blocks) == 1
    assert result.linked_blocks[0].block_id == "b1"
    assert result.linked_blocks[0].available is True
    assert result.linked_blocks[0].link_scope == "block"
    # Block-Refs ziehen das Volldokument NICHT mit — Snippet via fetch_resource.
    assert result.linked_resources == []
    # Kein Composite → leere composed_playbooks.
    assert result.composed_playbooks == []


def test_fetch_playbook_carries_locale_metadata_and_ignores_alt_client_param(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WP4 (Plan „Ein Element, eine Sprache"): `fetch_playbook` liefert die
    Playbook-Sprache im Top-Level-Feld `locale`; ein Alt-Client-Aufruf mit
    explizitem `locale='de'` funktioniert unveraendert (der Parameter wird
    akzeptiert, aber ignoriert — die tatsaechliche Sprache kommt aus der
    Antwort, nicht dem Parameter)."""
    pid = uuid4()
    playbook = _playbook_payload()
    playbook["id"] = str(pid)
    playbook["locale"] = "en"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith(f"/playbooks/{pid}/resource_links"):
            return httpx.Response(200, json=[])
        if request.url.path.endswith(f"/playbooks/{pid}/composes"):
            return httpx.Response(200, json=[])
        if request.url.path.endswith(f"/playbooks/{pid}/rendered"):
            return httpx.Response(200, json={"body_rendered": "b", "unresolved": []})
        if request.url.path.endswith(f"/playbooks/{pid}"):
            return httpx.Response(200, json=playbook)
        return httpx.Response(404)

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(fetch_playbook(str(pid), locale="de", format="full"))
    assert isinstance(result, PlaybookWithResources)
    assert result.locale == "en"
    assert result.playbook.locale == "en"


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
    result = asyncio.run(fetch_playbook(str(pid), format="full"))
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
    result = asyncio.run(fetch_playbook(str(pid), format="full"))
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
    result = asyncio.run(fetch_playbook(str(pid), format="full"))
    assert isinstance(result, PlaybookWithResources)
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
    result = asyncio.run(fetch_playbook(str(pid), format="full"))
    assert isinstance(result, PlaybookWithResources)
    assert len(result.composed_playbooks) == 2
    assert result.composed_playbooks[0].id == child_a_id
    assert result.composed_playbooks[1].id == child_b_id
    assert result.composed_playbooks[0].name == "Child-A"
    assert result.composed_playbooks[1].name == "Child-B"


def test_fetch_playbook_default_is_markdown_with_children_and_inline_bodies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default `text` (ADR-0056, Option B): ein Markdown-Dokument, kein JSON.

    Geschlossene Luecken: die Bodies der Sub-Playbooks und der inline
    eingebetteten Resources stehen als Klartext im Dokument — nicht als
    Editor-JSON und nicht nur als Pointer.
    """
    pid = uuid4()
    rid = uuid4()
    playbook = _playbook_payload()
    playbook["id"] = str(pid)
    playbook["is_composite"] = True
    child = _playbook_payload("Child-A")
    child["id"] = str(uuid4())
    child["content"]["body"] = json.dumps(  # type: ignore[index]
        [_paragraph_block("c1", "Kind-Schritt eins")], ensure_ascii=False
    )
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
            return httpx.Response(200, json=[child])
        if path.endswith(f"/playbooks/{pid}/rendered"):
            return httpx.Response(
                200, json={"body_rendered": "Schritt 1\n\nSchritt 2", "unresolved": []}
            )
        if path.endswith(f"/playbooks/{pid}"):
            return httpx.Response(200, json=playbook)
        if path.endswith(f"/resources/{rid}"):
            return httpx.Response(200, json=resource)
        return httpx.Response(404)

    monkeypatch.setattr(server, "build_client", _factory(handler))
    text = asyncio.run(fetch_playbook(str(pid)))

    # Rot-Probe: liefert der Default wieder das Modell, faellt der Typ.
    assert isinstance(text, str)
    with pytest.raises(json.JSONDecodeError):
        json.loads(text)
    assert "\\n" not in text
    assert '"props"' not in text
    assert text.startswith(f"# Playbook: {playbook['name']}\n")
    assert f"- id: {pid}" in text
    assert "## Prozedur\n\nSchritt 1\n\nSchritt 2" in text
    assert f"### Child-A (`{child['id']}`)" in text
    assert "Kind-Schritt eins" in text
    assert f"### {resource['name']} (`{rid}`)" in text
    assert "Inline-Inhalt" in text


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
    result = asyncio.run(fetch_playbook(str(pid), format="full"))
    assert isinstance(result, PlaybookWithResources)
    assert result.body_rendered == "Schritt 1\n\nSub-Playbook-Inhalt"


# Obergrenze fuer den Text-Pfad. Das Ergebnisbudget der Laufzeit liegt bei
# 50_000 Zeichen; der Fixture-Body unten ist so bemessen, dass der
# Default-Pfad (`format="full"`) daran vorbeischrammt und der Text-Pfad
# deutlich darunter bleibt. Verhalten, nicht Feldname: gemessen wird die
# serialisierte Antwort, nicht ob ein Schluessel existiert.
_TEXT_PATH_CHAR_LIMIT = 50_000


def _fat_blocknote_body(paragraphs: int) -> str:
    """Realistisch fetter BlockNote-Body als String (wie ihn die API liefert).

    Ein Editor-Block traegt pro Absatz ~250 Zeichen Struktur-Overhead
    (props, styles, children) auf ~60 Zeichen Nutztext — genau das Verhaeltnis,
    das die Payload aufblaeht.
    """
    blocks = [
        {
            "id": f"p{index}",
            "type": "paragraph",
            "props": {
                "backgroundColor": "default",
                "textColor": "default",
                "textAlignment": "left",
            },
            "content": [
                {
                    "type": "text",
                    "text": f"Schritt {index}: Prozedurtext dieses Playbook-Absatzes.",
                    "styles": {},
                }
            ],
            "children": [],
        }
        for index in range(paragraphs)
    ]
    return json.dumps(blocks, ensure_ascii=False)


def _rendered_text(paragraphs: int) -> str:
    return "\n\n".join(
        f"Schritt {index}: Prozedurtext dieses Playbook-Absatzes." for index in range(paragraphs)
    )


def _payload_chars(result: PlaybookWithResources | str) -> int:
    """Groesse der Antwort so, wie sie beim Agenten ankommt (serialisiert).

    Der Markdown-Default (ADR-0056) IST bereits der Text, der ankommt.
    """
    if isinstance(result, str):
        return len(result)
    return len(result.model_dump_json())


def _fat_playbook_handler(
    pid: UUID, playbook: dict[str, object]
) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith(f"/playbooks/{pid}/resource_links"):
            return httpx.Response(200, json=[])
        if path.endswith(f"/playbooks/{pid}/composes"):
            return httpx.Response(200, json=[])
        if path.endswith(f"/playbooks/{pid}/rendered"):
            body = playbook["content"]["body"]  # type: ignore[index]
            paragraphs = body.count('"type": "paragraph"') or body.count('"type":"paragraph"')
            return httpx.Response(
                200,
                json={"body_rendered": _rendered_text(paragraphs), "unresolved": []},
            )
        if path.endswith(f"/playbooks/{pid}"):
            return httpx.Response(200, json=playbook)
        return httpx.Response(404)

    return handler


def test_fetch_playbook_text_format_stays_under_payload_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rot-Probe: der Text-Pfad haelt das Ergebnisbudget, der Default nicht.

    Gemessen wird die serialisierte Antwortgroesse, nicht ein Feldname. Ohne
    den `format="text"`-Pfad liefert `fetch_playbook` fuer beide Aufrufe
    dieselbe Payload und die Obergrenze reisst.
    """
    pid = uuid4()
    playbook = _playbook_payload()
    playbook["id"] = str(pid)
    playbook["content"]["body"] = _fat_blocknote_body(180)  # type: ignore[index]

    monkeypatch.setattr(server, "build_client", _factory(_fat_playbook_handler(pid, playbook)))

    full = asyncio.run(fetch_playbook(str(pid), format="full"))
    text = asyncio.run(fetch_playbook(str(pid), format="text"))

    full_chars = _payload_chars(full)
    text_chars = _payload_chars(text)

    # Regressionsanker: das Fixture ist gross genug, dass der Default das
    # Budget tatsaechlich reisst — sonst wuerde der Test unten nichts zeigen.
    assert full_chars > _TEXT_PATH_CHAR_LIMIT, (
        f"Fixture zu klein ({full_chars} Zeichen) — der Default muss die "
        "Obergrenze reissen, sonst beweist der Text-Pfad nichts."
    )
    assert text_chars <= _TEXT_PATH_CHAR_LIMIT, (
        f"Text-Pfad {text_chars} Zeichen > Obergrenze {_TEXT_PATH_CHAR_LIMIT}."
    )
    # Der Prozedurtext kommt vollstaendig an — gekuerzt wird das Editor-JSON,
    # nicht der Inhalt. Markdown statt JSON: kein Editor-JSON im Dokument.
    assert isinstance(text, str)
    assert "Schritt 179" in text
    assert '"props"' not in text


def test_fetch_playbook_full_format_keeps_editor_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`format="full"` liefert das Modell mit Editor-JSON (Vorlage fuer PUT).

    Der Default ist seit ADR-0056 das Markdown-Dokument; die Metadaten, die
    `full` traegt, stehen dort im Kopf.
    """
    pid = uuid4()
    playbook = _playbook_payload()
    playbook["id"] = str(pid)
    raw_body = _fat_blocknote_body(12)
    playbook["content"]["body"] = raw_body  # type: ignore[index]

    monkeypatch.setattr(server, "build_client", _factory(_fat_playbook_handler(pid, playbook)))

    explicit_full = asyncio.run(fetch_playbook(str(pid), format="full"))
    assert isinstance(explicit_full, PlaybookWithResources)
    assert explicit_full.playbook.content.body == raw_body

    # Default = Markdown: Metadaten im Kopf, kein Editor-Body.
    default = asyncio.run(fetch_playbook(str(pid)))
    text = asyncio.run(fetch_playbook(str(pid), format="text"))
    assert default == text
    assert isinstance(text, str)
    assert text.startswith(f"# Playbook: {explicit_full.playbook.name}\n")
    assert explicit_full.playbook.content.description in text
    assert f"- id: {explicit_full.playbook.id}" in text
    assert f"- locale: {explicit_full.locale}" in text
    assert raw_body not in text
    assert '"props"' not in text


def test_fetch_playbook_rejects_unknown_format(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ein Tippfehler im `format` faellt auf, statt still den Default zu liefern."""
    pid = uuid4()
    playbook = _playbook_payload()
    playbook["id"] = str(pid)

    monkeypatch.setattr(server, "build_client", _factory(_fat_playbook_handler(pid, playbook)))

    with pytest.raises(ToolError):
        asyncio.run(fetch_playbook(str(pid), format="plain"))


# --------------------------------------------------------------------------
# Blockselektion: Gliederung finden, dann nur den Abschnitt holen.
#
# Die API schneidet serverseitig (`?sections=`); der Fake-Handler unten bildet
# genau diesen Vertrag nach, damit die Messung unten die Groesse misst, die
# beim Agenten ankommt — nicht ein Feld, das zufaellig leer ist.
# --------------------------------------------------------------------------


def _heading_block(block_id: str, text: str, level: int = 1) -> dict[str, object]:
    return {
        "id": block_id,
        "type": "heading",
        "props": {"level": level},
        "content": [{"type": "text", "text": text, "styles": {}}],
        "children": [],
    }


def _paragraph_block(block_id: str, text: str) -> dict[str, object]:
    return {
        "id": block_id,
        "type": "paragraph",
        "props": {
            "backgroundColor": "default",
            "textColor": "default",
            "textAlignment": "left",
        },
        "content": [{"type": "text", "text": text, "styles": {}}],
        "children": [],
    }


def _sectioned_blocks(sections: int, paragraphs_each: int) -> list[dict[str, object]]:
    blocks: list[dict[str, object]] = []
    for s in range(sections):
        blocks.append(_heading_block(f"h{s}", f"Abschnitt {s}"))
        for p in range(paragraphs_each):
            blocks.append(
                _paragraph_block(
                    f"h{s}-p{p}",
                    f"Abschnitt {s}, Schritt {p}: Prozedurtext dieses Playbook-Absatzes.",
                )
            )
    return blocks


def _sectioned_playbook_handler(
    pid: UUID, playbook: dict[str, object], blocks: list[dict[str, object]]
) -> Callable[[httpx.Request], httpx.Response]:
    """Fake-API, die `?sections=` wie der echte Endpoint auswertet."""

    def _slice(selected: list[str]) -> list[dict[str, object]]:
        keep: list[dict[str, object]] = []
        taking = False
        for block in blocks:
            if block["type"] == "heading":
                taking = block["id"] in selected
            if taking:
                keep.append(block)
        return keep

    def _plain(chosen: list[dict[str, object]]) -> str:
        texts = []
        for block in chosen:
            inline = block["content"]
            assert isinstance(inline, list)
            texts.append(str(inline[0]["text"]))
        return "\n\n".join(texts)

    def _anchors() -> list[dict[str, object]]:
        return [
            {
                "block_id": block["id"],
                "level": block["props"]["level"],  # type: ignore[index]
                "text": block["content"][0]["text"],  # type: ignore[index]
            }
            for block in blocks
            if block["type"] == "heading"
        ]

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith(f"/playbooks/{pid}/resource_links"):
            return httpx.Response(200, json=[])
        if path.endswith(f"/playbooks/{pid}/composes"):
            return httpx.Response(200, json=[])
        if path.endswith(f"/playbooks/{pid}/rendered"):
            raw = request.url.params.get("sections")
            chosen = blocks if raw is None else _slice([p for p in raw.split(",") if p])
            return httpx.Response(
                200,
                json={
                    "body_rendered": _plain(chosen),
                    "unresolved": [],
                    "sections": _anchors(),
                },
            )
        if path.endswith(f"/playbooks/{pid}"):
            return httpx.Response(200, json=playbook)
        return httpx.Response(404)

    return handler


def _sectioned_fixture(
    monkeypatch: pytest.MonkeyPatch, sections: int = 12, paragraphs_each: int = 15
) -> UUID:
    pid = uuid4()
    blocks = _sectioned_blocks(sections, paragraphs_each)
    playbook = _playbook_payload()
    playbook["id"] = str(pid)
    playbook["content"]["body"] = json.dumps(blocks, ensure_ascii=False)  # type: ignore[index]
    monkeypatch.setattr(
        server, "build_client", _factory(_sectioned_playbook_handler(pid, playbook, blocks))
    )
    return pid


def test_fetch_playbook_block_selection_is_a_fraction_of_the_full_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rot-Probe: ein Abschnitt kostet einen Bruchteil des Volldokuments.

    Gemessen wird die serialisierte Antwortgroesse — nicht ob ein Feld
    existiert. Ohne echten Schnitt liefert die Auswahl dieselbe Payload wie
    der Vollabruf und der Faktor unten reisst.
    """
    pid = _sectioned_fixture(monkeypatch)

    full = asyncio.run(fetch_playbook(str(pid), format="full"))
    one = asyncio.run(fetch_playbook(str(pid), block_ids=["h3"], format="text"))

    full_chars = _payload_chars(full)
    one_chars = _payload_chars(one)

    assert full_chars > _TEXT_PATH_CHAR_LIMIT, (
        f"Fixture zu klein ({full_chars} Zeichen) — der Vollabruf muss das "
        "Budget reissen, sonst beweist die Auswahl nichts."
    )
    # Eine von zwoelf Sections: die Auswahl muss um Groessenordnungen kleiner
    # sein, nicht nur ein bisschen.
    assert one_chars * 10 < full_chars, (
        f"Blockauswahl {one_chars} Zeichen vs. Vollabruf {full_chars} — der Schnitt greift nicht."
    )
    # Und es ist der RICHTIGE Abschnitt.
    assert isinstance(one, str)
    assert "Abschnitt 3, Schritt 0" in one
    assert "Abschnitt 4," not in one


def test_fetch_playbook_outline_is_findable_without_full_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Die Gliederung ist ohne Vollabruf erreichbar — sonst waere sie nutzlos."""
    pid = _sectioned_fixture(monkeypatch)

    outline = asyncio.run(fetch_playbook(str(pid), format="outline"))

    assert isinstance(outline, PlaybookWithResources)
    assert [s.block_id for s in outline.sections][:3] == ["h0", "h1", "h2"]
    assert outline.sections[0].text == "Abschnitt 0"
    # Der Einstieg traegt KEINE Prozedur — sonst waere er kein Einstieg.
    assert outline.body_rendered == ""
    assert outline.playbook.content.body == ""
    assert _payload_chars(outline) < 5_000


def test_fetch_playbook_keeps_outline_after_slicing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nach dem Schnitt bleibt die Gliederung vollstaendig — Nachfassen ohne Neuabruf."""
    pid = _sectioned_fixture(monkeypatch)

    one = asyncio.run(fetch_playbook(str(pid), block_ids=["h3"], format="text"))

    # Die Gliederung im Markdown nennt alle zwoelf Anker, nicht nur den gewaehlten.
    assert isinstance(one, str)
    assert all(f"- Abschnitt {s} (`h{s}`)" in one for s in range(12))


def test_fetch_playbook_selection_forwards_anchors_to_the_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Der Schnitt MUSS serverseitig passieren — `body_rendered` hat keine Anker."""
    pid = uuid4()
    blocks = _sectioned_blocks(3, 2)
    playbook = _playbook_payload()
    playbook["id"] = str(pid)
    playbook["content"]["body"] = json.dumps(blocks, ensure_ascii=False)  # type: ignore[index]
    seen: list[str | None] = []
    inner = _sectioned_playbook_handler(pid, playbook, blocks)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/rendered"):
            seen.append(request.url.params.get("sections"))
        return inner(request)

    monkeypatch.setattr(server, "build_client", _factory(handler))

    asyncio.run(fetch_playbook(str(pid), block_ids=["h1", "h2"], format="text"))
    assert seen == ["h1,h2"]


def test_fetch_playbook_without_selection_is_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Additiv: ohne `block_ids` bleibt der Default-Abruf der alte."""
    pid = _sectioned_fixture(monkeypatch, sections=3, paragraphs_each=2)

    default = asyncio.run(fetch_playbook(str(pid), format="full"))

    assert isinstance(default, PlaybookWithResources)
    assert default.playbook.content.body != ""
    assert "Abschnitt 0" in default.body_rendered
    assert "Abschnitt 2" in default.body_rendered


def test_fetch_playbook_selection_drops_editor_json_even_under_full(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein Ausschnitt gibt es nicht als Editor-JSON — der Body bleibt leer."""
    pid = _sectioned_fixture(monkeypatch, sections=3, paragraphs_each=2)

    sliced = asyncio.run(fetch_playbook(str(pid), block_ids=["h1"], format="full"))

    assert isinstance(sliced, PlaybookWithResources)
    assert sliced.playbook.content.body == ""
    assert "Abschnitt 1" in sliced.body_rendered
