"""Tool-Tests fuer die WorkArea-MCP-Tools (ADR-0047, WP8) gegen eine gemockte API.

Test-Muster A (wie test_resource_tools.py): die modulweiten async
Tool-Funktionen aus `who2be_mcp.tools.workarea` werden direkt ueber
`asyncio.run` getrieben (kein pytest-asyncio im Stack), der HTTP-Verkehr
laeuft ueber `httpx.MockTransport`, `server.build_client` wird je Test auf
eine Factory gepatcht — die Tools loesen den Client zur Laufzeit ueber das
`server`-Modul auf, der Patch greift also unveraendert.

Abgedeckt: je Tool ein Roundtrip (Methode + Pfad + Body), die
Private-Area-Pfade (`area_id=None`), die Anker-Normalisierung
(`<artifact_id>#<block_id>` -> `block_id`), die 409-`rev_conflict`-
Durchreichung bei `patch_artifact` und `ingest` mit url vs. file_b64.
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
from who2be_mcp.tools.workarea import (
    append_artifact,
    create_artifact,
    delete_artifact,
    ingest,
    list_artifacts,
    patch_artifact,
    read_artifact,
    search_workarea,
)
from who2be_models import ArtifactMarkdown, ArtifactRead, IngestResult, WorkAreaSearchHit

_WORKSPACE_ID = uuid4()
_PREFIX = f"/v1/workspaces/{_WORKSPACE_ID}"
_OCCURRED = datetime(2026, 8, 12, 9, 30, tzinfo=UTC)


def _factory(handler: Callable[[httpx.Request], httpx.Response]) -> Callable[[], object]:
    transport = httpx.MockTransport(handler)

    async def _build() -> ApiClient:
        return ApiClient("http://test", "token", _WORKSPACE_ID, transport=transport)

    return _build


def _body(request: httpx.Request) -> dict[str, object]:
    parsed = json.loads(request.content)
    assert isinstance(parsed, dict)
    return parsed


def _artifact_payload(
    artifact_id: UUID | None = None,
    area_id: UUID | None = None,
    rev: int = 1,
    blocks: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "id": str(artifact_id or uuid4()),
        "area_id": str(area_id or uuid4()),
        "workspace_id": str(_WORKSPACE_ID),
        "type": "doc",
        "title": "Meeting-Notiz",
        "rev": rev,
        "occurred_at": "2026-08-12T09:30:00Z",
        "occurred_precision": "minute",
        "sensitivity": "general",
        "created_at": "2026-08-12T09:31:00Z",
        "updated_at": "2026-08-12T09:31:00Z",
        "updated_by": "agent:00000000-0000-0000-0000-000000000001",
        "blocks": blocks
        if blocks is not None
        else [{"block_id": "abc12345", "kind": "paragraph", "md": "Hallo"}],
    }


def _area_payload(area_id: UUID, scope: str = "shared", name: str = "Team") -> dict[str, object]:
    return {
        "id": str(area_id),
        "workspace_id": str(_WORKSPACE_ID),
        "scope": scope,
        "owner_agent_id": str(uuid4()) if scope == "private" else None,
        "name": name,
        "retention_days": None,
        "created_at": "2026-08-12T09:00:00Z",
        "updated_at": "2026-08-12T09:00:00Z",
    }


# --- create_artifact ---------------------------------------------------------


def test_create_artifact_posts_into_area(monkeypatch: pytest.MonkeyPatch) -> None:
    area_id = uuid4()
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["body"] = _body(request)
        return httpx.Response(201, json=_artifact_payload(area_id=area_id))

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(
        create_artifact(
            title="Meeting-Notiz",
            content_md="# Thema\n\nInhalt.",
            occurred_at=_OCCURRED,
            area_id=str(area_id),
        )
    )
    assert isinstance(result, ArtifactRead)
    assert result.blocks is not None and result.blocks[0].block_id == "abc12345"
    assert seen["method"] == "POST"
    assert seen["path"] == f"{_PREFIX}/work-areas/{area_id}/artifacts"
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["title"] == "Meeting-Notiz"
    assert body["content_md"] == "# Thema\n\nInhalt."
    occurred = body["occurred_at"]
    assert isinstance(occurred, str) and occurred.startswith("2026-08-12T09:30")
    assert body["occurred_precision"] == "minute"
    assert body["sensitivity"] == "general"


def test_create_artifact_without_area_uses_private_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        return httpx.Response(201, json=_artifact_payload())

    monkeypatch.setattr(server, "build_client", _factory(handler))
    asyncio.run(create_artifact(title="Privat", content_md="x", occurred_at=_OCCURRED))
    # Ohne Area geht der Post auf den Private-Area-Endpunkt, NICHT auf
    # /work-areas/... — die Aufloesung uebernimmt der Server.
    assert seen["path"] == f"{_PREFIX}/artifacts"


def test_create_artifact_validates_area_uuid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        server, "build_client", _factory(lambda request: httpx.Response(201, json={}))
    )
    with pytest.raises(ToolError, match="Area-UUID"):
        asyncio.run(
            create_artifact(title="x", content_md="y", occurred_at=_OCCURRED, area_id="not-a-uuid")
        )


def test_create_artifact_source_system_requires_fetched_at(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Schatten-System-Schutz (Spec §3) — Modell-Validator, kein API-Roundtrip.
    monkeypatch.setattr(
        server, "build_client", _factory(lambda request: httpx.Response(201, json={}))
    )
    with pytest.raises(ToolError, match="fetched_at"):
        asyncio.run(
            create_artifact(
                title="x",
                content_md="y",
                occurred_at=_OCCURRED,
                source_system="banking-api",
            )
        )


# --- append_artifact ---------------------------------------------------------


def test_append_artifact_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    artifact_id = uuid4()
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["body"] = _body(request)
        return httpx.Response(200, json=_artifact_payload(artifact_id=artifact_id, rev=2))

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(append_artifact(str(artifact_id), "Neuer Absatz."))
    assert isinstance(result, ArtifactRead)
    assert result.rev == 2
    assert seen["method"] == "POST"
    assert seen["path"] == f"{_PREFIX}/wa-artifacts/{artifact_id}/append"
    assert seen["body"] == {"content_md": "Neuer Absatz."}


# --- patch_artifact ----------------------------------------------------------


def test_patch_artifact_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    artifact_id = uuid4()
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["body"] = _body(request)
        return httpx.Response(200, json=_artifact_payload(artifact_id=artifact_id, rev=4))

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(
        patch_artifact(
            str(artifact_id), anchor="abc12345", op="replace", expected_rev=3, content_md="Neu."
        )
    )
    assert isinstance(result, ArtifactRead)
    assert seen["method"] == "PATCH"
    assert seen["path"] == f"{_PREFIX}/wa-artifacts/{artifact_id}"
    assert seen["body"] == {
        "anchor": "abc12345",
        "op": "replace",
        "content_md": "Neu.",
        "expected_rev": 3,
    }


def test_patch_artifact_accepts_full_search_anchor(monkeypatch: pytest.MonkeyPatch) -> None:
    """Der volle Suchtreffer-Anker `<artifact_id>#<block_id>` wird auf die
    reine `block_id` normalisiert — Agenten reichen Treffer 1:1 weiter."""
    artifact_id = uuid4()
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = _body(request)
        return httpx.Response(200, json=_artifact_payload(artifact_id=artifact_id))

    monkeypatch.setattr(server, "build_client", _factory(handler))
    asyncio.run(
        patch_artifact(
            str(artifact_id),
            anchor=f"{artifact_id}#zz11yy22",
            op="delete",
            expected_rev=1,
        )
    )
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["anchor"] == "zz11yy22"
    assert body["content_md"] is None


def test_patch_artifact_409_surfaces_current_rev_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Der 409-`rev_conflict` traegt die aktuelle rev im Detail — genau dieser
    Text muss beim Agenten ankommen (neu lesen, dann mit aktueller rev patchen)."""
    artifact_id = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            409,
            json={"detail": "rev_conflict: erwartete rev 3, aktuelle rev ist 7."},
        )

    monkeypatch.setattr(server, "build_client", _factory(handler))
    with pytest.raises(ToolError, match="aktuelle rev ist 7"):
        asyncio.run(
            patch_artifact(
                str(artifact_id), anchor="abc12345", op="replace", expected_rev=3, content_md="x"
            )
        )


def test_patch_artifact_replace_requires_content(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        server, "build_client", _factory(lambda request: httpx.Response(200, json={}))
    )
    with pytest.raises(ToolError, match="content_md"):
        asyncio.run(patch_artifact(str(uuid4()), anchor="abc12345", op="replace", expected_rev=1))


# --- read_artifact -----------------------------------------------------------


def test_read_artifact_returns_markdown_with_anchors(monkeypatch: pytest.MonkeyPatch) -> None:
    artifact_id = uuid4()
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["params"] = dict(request.url.params)
        return httpx.Response(
            200,
            json={
                "artifact_id": str(artifact_id),
                "title": "Meeting-Notiz",
                "rev": 3,
                "markdown": "# Thema [#abc12345]\n\nInhalt. [#def67890]",
            },
        )

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(read_artifact(str(artifact_id)))
    assert isinstance(result, ArtifactMarkdown)
    assert result.rev == 3
    assert "[#abc12345]" in result.markdown
    assert seen["method"] == "GET"
    assert seen["path"] == f"{_PREFIX}/wa-artifacts/{artifact_id}"
    assert seen["params"] == {}


def test_read_artifact_normalizes_full_anchor_to_block_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_id = uuid4()
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["params"] = dict(request.url.params)
        return httpx.Response(
            200,
            json={
                "artifact_id": str(artifact_id),
                "title": "t",
                "rev": 1,
                "markdown": "Inhalt. [#def67890]",
            },
        )

    monkeypatch.setattr(server, "build_client", _factory(handler))
    asyncio.run(read_artifact(str(artifact_id), anchor=f"{artifact_id}#def67890"))
    assert seen["params"] == {"anchor": "def67890"}


# --- list_artifacts ----------------------------------------------------------


def test_list_artifacts_for_area(monkeypatch: pytest.MonkeyPatch) -> None:
    area_id = uuid4()
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        return httpx.Response(200, json=[_artifact_payload(area_id=area_id)])

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(list_artifacts(str(area_id)))
    assert len(result) == 1
    assert isinstance(result[0], ArtifactRead)
    assert result[0].area_id == area_id
    assert seen["path"] == f"{_PREFIX}/work-areas/{area_id}/artifacts"


def test_list_artifacts_without_area_resolves_private(monkeypatch: pytest.MonkeyPatch) -> None:
    """`area_id=None` loest die private Area ueber `GET /work-areas` auf (die
    Route legt sie fuer agent-gebundene Tokens beim ersten Zugriff an)."""
    private_id = uuid4()
    shared_id = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == f"{_PREFIX}/work-areas":
            return httpx.Response(
                200,
                json=[
                    _area_payload(shared_id, scope="shared", name="Team"),
                    _area_payload(private_id, scope="private", name="privat"),
                ],
            )
        assert path == f"{_PREFIX}/work-areas/{private_id}/artifacts"
        return httpx.Response(200, json=[_artifact_payload(area_id=private_id)])

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(list_artifacts())
    assert len(result) == 1
    assert result[0].area_id == private_id


def test_list_artifacts_without_area_and_without_private_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"{_PREFIX}/work-areas"
        return httpx.Response(200, json=[_area_payload(uuid4(), scope="shared")])

    monkeypatch.setattr(server, "build_client", _factory(handler))
    with pytest.raises(ToolError, match="private Area"):
        asyncio.run(list_artifacts())


# --- delete_artifact ---------------------------------------------------------


def test_delete_artifact_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    artifact_id = uuid4()
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        return httpx.Response(204)

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(delete_artifact(str(artifact_id)))
    assert seen["method"] == "DELETE"
    assert seen["path"] == f"{_PREFIX}/wa-artifacts/{artifact_id}"
    assert str(artifact_id) in result and "geloescht" in result


# --- ingest ------------------------------------------------------------------


def _ingest_result_payload() -> dict[str, object]:
    return {
        "blob_artifact_id": str(uuid4()),
        "doc_artifact_id": str(uuid4()),
        "sha256": "ab" * 32,
        "deduplicated": False,
        "block_count": 5,
    }


def test_ingest_url_posts_into_area(monkeypatch: pytest.MonkeyPatch) -> None:
    area_id = uuid4()
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["body"] = _body(request)
        return httpx.Response(201, json=_ingest_result_payload())

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(ingest(url="https://example.org/doc.pdf", area_id=str(area_id)))
    assert isinstance(result, IngestResult)
    assert result.block_count == 5
    assert seen["method"] == "POST"
    assert seen["path"] == f"{_PREFIX}/work-areas/{area_id}/ingest"
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["url"] == "https://example.org/doc.pdf"
    assert body["file_b64"] is None


def test_ingest_file_b64_into_private_area(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = _body(request)
        return httpx.Response(201, json=_ingest_result_payload())

    monkeypatch.setattr(server, "build_client", _factory(handler))
    asyncio.run(ingest(file_b64="aGFsbG8=", filename="notiz.md"))
    # Ohne Area: Private-Area-Endpunkt, nicht /work-areas/....
    assert seen["path"] == f"{_PREFIX}/ingest"
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["file_b64"] == "aGFsbG8="
    assert body["filename"] == "notiz.md"
    assert body["url"] is None


def test_ingest_requires_exactly_one_source(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        server, "build_client", _factory(lambda request: httpx.Response(201, json={}))
    )
    with pytest.raises(ToolError, match="Genau eine Quelle"):
        asyncio.run(ingest())
    with pytest.raises(ToolError, match="Genau eine Quelle"):
        asyncio.run(ingest(url="https://example.org", file_b64="aGFsbG8="))


# --- search_workarea ---------------------------------------------------------


def _search_hit_payload(artifact_id: UUID, area_id: UUID) -> dict[str, object]:
    return {
        "anchor": f"{artifact_id}#abc12345",
        "artifact_id": str(artifact_id),
        "block_id": "abc12345",
        "title": "Meeting-Notiz",
        "snippet": "… das Budget-Thema …",
        "score": 0.42,
        "area_id": str(area_id),
    }


def test_search_workarea_sends_query_and_area(monkeypatch: pytest.MonkeyPatch) -> None:
    artifact_id = uuid4()
    area_id = uuid4()
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json=[_search_hit_payload(artifact_id, area_id)])

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(search_workarea("Budget", area_id=str(area_id)))
    assert len(result) == 1
    assert isinstance(result[0], WorkAreaSearchHit)
    # Der Treffer-Anker ist direkt `read_artifact(artifact_id, anchor)`-faehig.
    assert result[0].anchor == f"{artifact_id}#abc12345"
    assert seen["path"] == f"{_PREFIX}/workarea-search"
    assert seen["params"] == {"q": "Budget", "area_id": str(area_id)}


def test_search_workarea_without_area_omits_param(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json=[])

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(search_workarea("Budget"))
    assert result == []
    assert seen["params"] == {"q": "Budget"}
