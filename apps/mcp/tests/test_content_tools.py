"""Markdown-Schreibweg der MCP-Werkzeuge (ADR-0058 §6.2, §7, Paket P3).

Gegen eine gemockte API (`httpx.MockTransport`), Muster wie
`test_resource_tools.py`: die async Werkzeuge laufen ueber `asyncio.run`,
`build_client` wird je Test gepatcht.

Abgedeckt:
- `format="source"` an den lesenden Werkzeugen mit Schreibvorlage (der
  Budget-Nachweis M6 steht in `test_tool_payload_budget.py`);
- `edit_content` (Route, Body, Ziel-Pruefung, 409 als Fehler);
- der Waechter gegen Editor-JSON in Markdown-Feldern (§7) samt Gegenprobe;
- die Normalisierung des `content` nach Elementart im Client.
"""

import asyncio
import json
from collections.abc import Callable
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from pydantic import ValidationError

from who2be_mcp import server
from who2be_mcp.client import ApiClient
from who2be_mcp.server import (
    fetch_playbook,
    fetch_resource,
    get_persona,
    get_system_prompt,
    get_version,
    mcp,
    update_playbook,
    update_resource,
)
from who2be_mcp.text_view import SOURCE_HINT
from who2be_mcp.tools.content import (
    PlaybookMarkdownUpdate,
    ResourceMarkdownUpdate,
    edit_content,
    reject_editor_json,
)
from who2be_models.content_markdown import (
    MarkdownWriteResult,
    PlaybookMarkdownContent,
    ResourceMarkdownContent,
)
from who2be_models.playbook import PlaybookType

_WORKSPACE_ID = uuid4()


def _factory(handler: Callable[[httpx.Request], httpx.Response]) -> Callable[[], object]:
    transport = httpx.MockTransport(handler)

    async def _build() -> ApiClient:
        return ApiClient("http://test", "token", _WORKSPACE_ID, transport=transport)

    return _build


def _source(
    entity_type: str,
    content: dict[str, Any],
    *,
    entity_id: UUID | None = None,
    base_rev: str | None = "rev-7",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "entity_type": entity_type,
        "id": str(entity_id or uuid4()),
        "name": "Element",
        "locale": "de",
        "version": 3,
        "status": "draft",
        "base_rev": base_rev,
        "content": content,
    }
    return payload


def _editor_blocks(count: int) -> list[dict[str, object]]:
    """Editor-JSON (BlockNote) in der Form, die der Waechter abweisen muss."""
    return [
        {"id": f"b{i}", "type": "paragraph", "props": {}, "content": [], "children": []}
        for i in range(count)
    ]


# --- format="source": Route und Dokument ---------------------------------------


def test_fetch_playbook_source_format_reads_markdown_route_with_base_rev(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pid = uuid4()
    seen: list[str] = []
    body = "## Ablauf [#h-ablauf]\n\nErst lesen, dann schreiben.\n\n```py\nx = 1\n```"

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(f"{request.url.path}?{request.url.query.decode()}")
        content = {"description": "d", "body": body, "type": "workflow", "tags": ["a"]}
        return httpx.Response(200, json=_source("playbooks", content, entity_id=pid))

    monkeypatch.setattr(server, "build_client", _factory(handler))
    text = asyncio.run(fetch_playbook(str(pid), format="source"))

    assert seen == [f"/v1/workspaces/{_WORKSPACE_ID}/playbooks/{pid}/markdown?format=source"]
    assert isinstance(text, str)
    assert text.startswith("# Element\n")
    assert SOURCE_HINT in text
    assert "- base_rev: rev-7" in text
    # Der Body steht verlustfrei in einem Fence, der laenger ist als jeder
    # Zaun im Inhalt; Anker bleiben stehen.
    assert f"## body\n\n````markdown\n{body}\n````" in text
    # Strukturfelder kommen als JSON, das sich 1:1 in `data.content` uebernehmen laesst.
    assert '"type": "workflow"' in text
    assert '"body"' not in text.split("## body")[0]


def test_get_persona_source_format_splits_mode_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    pid = uuid4()
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        content = {
            "description": "d",
            "tags": [],
            "profile": "# Rolle [#h-rolle]\n\nDu bist **Coder**.",
            "modes": [
                {
                    "name": "Refiner",
                    "trigger": "issue veredeln",
                    "is_default": False,
                    "identity_add": "Veredeln statt umsetzen.",
                    "output_style_override": "",
                    "anti_patterns": "",
                }
            ],
            "skills": [],
        }
        return httpx.Response(200, json=_source("personas", content, entity_id=pid))

    monkeypatch.setattr(server, "build_client", _factory(handler))
    text = asyncio.run(get_persona(str(pid), format="source"))

    # Per UUID kein Vorab-GET auf die Persona: genau ein Request.
    assert calls == [f"/v1/workspaces/{_WORKSPACE_ID}/personas/{pid}/markdown"]
    assert isinstance(text, str)
    assert "## profile\n\n````markdown\n# Rolle [#h-rolle]" in text
    # Jedes Modus-Feld steht unter dem `field`-Namen, den `edit_content` erwartet.
    assert "## modes[Refiner].identity_add\n\n````markdown\nVeredeln statt umsetzen.\n````" in text
    # Im Strukturblock bleibt der Modus-Kopf, die Markdown-Felder nicht doppelt.
    structure = text.split("## Strukturfelder")[1].split("## profile")[0]
    assert '"trigger": "issue veredeln"' in structure
    assert "identity_add" not in structure


def test_get_persona_source_format_resolves_name_first(monkeypatch: pytest.MonkeyPatch) -> None:
    pid = uuid4()
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path.endswith("/markdown"):
            content = {"description": "", "tags": [], "profile": "", "modes": [], "skills": []}
            return httpx.Response(200, json=_source("personas", content, entity_id=pid))
        return httpx.Response(
            200,
            json=[
                {
                    "id": str(pid),
                    "workspace_id": str(_WORKSPACE_ID),
                    "owner_id": str(uuid4()),
                    "name": "Coder",
                    "current_version": 1,
                    "current_status": "active",
                    "has_pending_draft": False,
                    "locale": "de",
                    "content": {"description": "", "traits": [], "tags": []},
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                }
            ],
        )

    monkeypatch.setattr(server, "build_client", _factory(handler))
    text = asyncio.run(get_persona("Coder", format="source"))
    assert calls[-1] == f"/v1/workspaces/{_WORKSPACE_ID}/personas/{pid}/markdown"
    assert "- base_rev: rev-7" in str(text)


def test_get_version_source_format_has_no_base_rev(monkeypatch: pytest.MonkeyPatch) -> None:
    rid = uuid4()
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        content = {"description": "", "body": "Alt.", "tags": []}
        return httpx.Response(200, json=_source("resources", content, entity_id=rid, base_rev=None))

    monkeypatch.setattr(server, "build_client", _factory(handler))
    text = asyncio.run(get_version("resource", str(rid), 2, format="source"))
    assert seen == [f"/v1/workspaces/{_WORKSPACE_ID}/resources/{rid}/versions/2/markdown"]
    assert "- base_rev: keiner (nicht das Schreibziel, nur Vorlage)" in str(text)


def test_source_document_fence_outgrows_backticks_in_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = "`````text\nfuenf Backticks\n`````"
    payload = _source("system-prompts", {"description": "", "body": body})
    monkeypatch.setattr(
        server, "build_client", _factory(lambda _r: httpx.Response(200, json=payload))
    )
    text = str(asyncio.run(get_system_prompt(str(uuid4()), format="source")))
    assert f"``````markdown\n{body}\n``````" in text


def test_source_content_keeps_resource_shape_not_playbook(monkeypatch: pytest.MonkeyPatch) -> None:
    """Die `content`-Union hat keinen Diskriminator: ein Resource-Inhalt passt auch
    aufs Playbook-Modell. Ohne Normalisierung kaemen `type`/`triggers` in die
    Vorlage, und `update_resource` (extra=forbid) lehnte sie ab."""
    payload = _source("resources", {"description": "", "body": "x", "tags": []})
    monkeypatch.setattr(
        server, "build_client", _factory(lambda _r: httpx.Response(200, json=payload))
    )
    text = str(asyncio.run(fetch_resource(str(uuid4()), format="source")))
    structure = json.loads(text.split("```json\n")[1].split("\n```")[0])
    assert set(structure) == {"description", "tags"}
    # Gegenprobe: genau diese Struktur plus `body` nimmt das Resource-Modell an.
    ResourceMarkdownContent.model_validate({**structure, "body": "x"})


# M6 (Budget-Nachweis je Werkzeug mit `source`) steht in
# `test_tool_payload_budget.py`, neben den `text`-Nachweisen derselben Fixtures.


def test_source_format_rejected_by_tools_without_template(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nur die sechs Werkzeuge mit Schreibvorlage kennen `source`; Listen nicht."""
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(500)

    monkeypatch.setattr(server, "build_client", _factory(handler))
    with pytest.raises(ToolError, match="Ungueltiges format"):
        asyncio.run(server.list_system_prompts(format="source"))
    assert calls == []


# --- Schreibwerkzeuge -------------------------------------------------------------


def test_update_playbook_puts_markdown_with_base_rev(monkeypatch: pytest.MonkeyPatch) -> None:
    pid = uuid4()
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200, json=_source("playbooks", seen["body"]["content"], entity_id=pid)
        )

    monkeypatch.setattr(server, "build_client", _factory(handler))
    data = PlaybookMarkdownUpdate(
        base_rev="rev-7",
        content=PlaybookMarkdownContent(
            body="## Neu [#h-neu]\n\nText.", type=PlaybookType.workflow
        ),
    )
    result = asyncio.run(update_playbook(str(pid), data))

    assert seen["method"] == "PUT"
    assert seen["path"] == f"/v1/workspaces/{_WORKSPACE_ID}/playbooks/{pid}/markdown"
    assert seen["body"]["base_rev"] == "rev-7"
    assert seen["body"]["content"]["body"] == "## Neu [#h-neu]\n\nText."
    assert isinstance(result, MarkdownWriteResult)
    assert isinstance(result.content, PlaybookMarkdownContent)


def test_update_resource_write_result_keeps_resource_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rid = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        return httpx.Response(200, json=_source("resources", body["content"], entity_id=rid))

    monkeypatch.setattr(server, "build_client", _factory(handler))
    data = ResourceMarkdownUpdate(content=ResourceMarkdownContent(body="| a |\n| --- |\n| 1 |"))
    result = asyncio.run(update_resource(str(rid), data))
    assert isinstance(result.content, ResourceMarkdownContent)


def test_update_tool_rejects_blocknote_list_via_schema() -> None:
    """Eine Block-Liste scheitert an der Schema-Validierung (String erwartet)."""
    with pytest.raises(ValidationError):
        PlaybookMarkdownUpdate.model_validate(
            {"content": {"body": [{"id": "b1", "type": "paragraph", "content": []}]}}
        )


def test_update_tool_rejects_stringified_editor_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ein serialisiertes BlockNote-Array im Markdown-String wird laut abgewiesen,
    bevor die API gefragt wird (ADR-0058 §7)."""
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(500)

    monkeypatch.setattr(server, "build_client", _factory(handler))
    stringified = json.dumps(_editor_blocks(2))
    data = PlaybookMarkdownUpdate(content=PlaybookMarkdownContent(body=stringified))
    with pytest.raises(ToolError, match="body: Editor-JSON"):
        asyncio.run(update_playbook(str(uuid4()), data))
    assert calls == []


def test_create_tool_rejects_editor_json_in_mode_field(monkeypatch: pytest.MonkeyPatch) -> None:
    """Der Waechter greift auch in Persona-Modi, mit Feldnamen in der Meldung."""
    monkeypatch.setattr(server, "build_client", _factory(lambda _r: httpx.Response(500)))

    async def _run() -> None:
        async with Client(mcp) as client:
            await client.call_tool(
                "create_persona",
                {
                    "data": {
                        "name": "P",
                        "locale": "de",
                        "content": {
                            "modes": [
                                {"name": "M", "identity_add": json.dumps({"type": "paragraph"})}
                            ]
                        },
                    }
                },
            )

    with pytest.raises(ToolError, match=r"modes\[M\]\.identity_add: Editor-JSON"):
        asyncio.run(_run())


@pytest.mark.parametrize(
    "value",
    [
        "[Link](https://example.org) am Absatzanfang",
        "[1, 2, 3]",
        '{"kein": "block"}',
        "[]",
        "Normaler Text mit {{resource:abc#h1}}",
    ],
)
def test_editor_json_guard_lets_markdown_through(value: str) -> None:
    """Gegenprobe: Markdown, das mit `[` oder `{` beginnt, ist kein Editor-JSON."""
    reject_editor_json([("body", value)])


# --- edit_content ----------------------------------------------------------------


def test_edit_content_patches_markdown_route(monkeypatch: pytest.MonkeyPatch) -> None:
    pid = uuid4()
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        content = {"description": "", "body": "neu", "type": "", "tags": []}
        return httpx.Response(
            200, json=_source("playbooks", content, entity_id=pid, base_rev="rev-8")
        )

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(
        edit_content(
            "playbook", str(pid), "rev-7", "replace", anchor="h-ablauf", markdown="## Ablauf\n\nneu"
        )
    )
    assert seen["method"] == "PATCH"
    assert seen["path"] == f"/v1/workspaces/{_WORKSPACE_ID}/playbooks/{pid}/markdown"
    assert seen["body"] == {
        "base_rev": "rev-7",
        "op": "replace",
        "anchor": "h-ablauf",
        "field": None,
        "markdown": "## Ablauf\n\nneu",
    }
    assert result.base_rev == "rev-8"


@pytest.mark.parametrize(
    ("entity_type", "path"),
    [
        ("persona", "personas"),
        ("resource", "resources"),
        ("system_prompt", "system-prompts"),
        ("external_tool", "external_tools"),
    ],
)
def test_edit_content_maps_entity_type_to_route(
    entity_type: str, path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    eid = uuid4()
    seen: list[str] = []
    contents: dict[str, dict[str, Any]] = {
        "personas": {"description": "", "tags": [], "profile": "", "modes": [], "skills": []},
        "resources": {"description": "", "body": "", "tags": []},
        "system-prompts": {"description": "", "body": "x"},
        "external_tools": {"display_name": "", "usage_notes": ""},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        return httpx.Response(200, json=_source(path, contents[path], entity_id=eid))

    monkeypatch.setattr(server, "build_client", _factory(handler))
    asyncio.run(edit_content(entity_type, str(eid), "r", "delete", field="body"))  # type: ignore[arg-type]
    assert seen == [f"/v1/workspaces/{_WORKSPACE_ID}/{path}/{eid}/markdown"]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"op": "replace", "markdown": "x"},  # weder anchor noch field
        {"op": "replace", "anchor": "a", "field": "body", "markdown": "x"},  # beides
        {"op": "replace", "anchor": "a"},  # replace ohne markdown
        {"op": "delete", "anchor": "a", "markdown": "x"},  # delete mit markdown
    ],
)
def test_edit_content_rejects_invalid_target_before_api(
    kwargs: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(500)

    monkeypatch.setattr(server, "build_client", _factory(handler))
    with pytest.raises(ToolError):
        asyncio.run(edit_content("playbook", str(uuid4()), "r", **kwargs))  # type: ignore[arg-type]
    assert calls == []


def test_edit_content_surfaces_version_conflict(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            409,
            json={
                "type": "about:blank",
                "title": "Conflict",
                "status": 409,
                "detail": "version_conflict: base_rev veraltet, neu lesen.",
            },
        )

    monkeypatch.setattr(server, "build_client", _factory(handler))
    with pytest.raises(ToolError, match="version_conflict"):
        asyncio.run(edit_content("resource", str(uuid4()), "alt", "delete", anchor="h1"))


def test_edit_content_rejects_editor_json_markdown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "build_client", _factory(lambda _r: httpx.Response(500)))
    with pytest.raises(ToolError, match="Editor-JSON"):
        asyncio.run(
            edit_content(
                "playbook",
                str(uuid4()),
                "r",
                "insert_after",
                anchor="h1",
                markdown=json.dumps(_editor_blocks(1)),
            )
        )


def test_edit_content_is_registered_on_the_server() -> None:
    tools = {tool.name: tool for tool in asyncio.run(mcp.list_tools(run_middleware=False))}
    assert "edit_content" in tools
    params = (tools["edit_content"].parameters or {}).get("properties") or {}
    assert {"entity_type", "entity_id", "base_rev", "op", "anchor", "field", "markdown"} <= set(
        params
    )
