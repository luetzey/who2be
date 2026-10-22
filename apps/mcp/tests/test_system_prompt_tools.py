"""Tool-Tests fuer die System-Prompt-Template-MCP-Tools (ADR-0040).

Reads (`list_system_prompts`/`get_system_prompt`) + Writes (`create`/`update`/
`restore`/`transition_system_prompt`) sind duenne Adapter ueber die REST-
Endpunkte `/system-prompts`. Gleiches Muster wie test_resource_tools: async Tools
via `asyncio.run`, HTTP ueber `httpx.MockTransport`, `build_client` gepatcht.
"""

import asyncio
import json
from collections.abc import Callable
from typing import Any
from uuid import uuid4

import httpx
import pytest
from fastmcp.exceptions import ToolError

from who2be_mcp import server
from who2be_mcp.client import ApiClient
from who2be_mcp.server import (
    create_system_prompt,
    get_system_prompt,
    list_system_prompts,
    list_versions,
    transition_system_prompt,
    update_system_prompt,
)
from who2be_mcp.tools.content import SystemPromptMarkdownCreate, SystemPromptMarkdownUpdate
from who2be_models import (
    SystemPromptTemplateRead,
    SystemPromptTemplateVersionRead,
    VersionTransitionRequest,
)
from who2be_models.content_markdown import MarkdownWriteResult

_WORKSPACE_ID = uuid4()


def _md_result(
    entity_type: str, content: dict[str, object], name: str = "Neu", locale: str = "de"
) -> dict[str, object]:
    """Antwort der `/markdown`-Schreibrouten (`MarkdownWriteResult`, ADR-0058 P2)."""
    return {
        "entity_type": entity_type,
        "id": str(uuid4()),
        "name": name,
        "locale": locale,
        "version": 1,
        "status": "draft",
        "base_rev": "rev-1",
        "content": content,
        "dangling_refs": [],
    }


def _factory(handler: Callable[[httpx.Request], httpx.Response]) -> Callable[[], object]:
    transport = httpx.MockTransport(handler)

    async def _build() -> ApiClient:
        return ApiClient("http://test", "token", _WORKSPACE_ID, transport=transport)

    return _build


def _template_payload(
    name: str = "Agent-Builder", body: str = "{{persona:profile}}"
) -> dict[str, object]:
    return {
        "id": str(uuid4()),
        "workspace_id": str(_WORKSPACE_ID),
        "owner_id": str(uuid4()),
        "name": name,
        "slug": "agent-builder",
        "current_version": 1,
        "current_status": "active",
        "has_pending_draft": False,
        "locale": "de",
        "content": {"description": "d", "body": body},
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


def _template_version(version: int = 1, status: str = "draft") -> dict[str, object]:
    return {
        "id": str(uuid4()),
        "version": version,
        "status": status,
        "locale": "de",
        "content": {"description": "d", "body": "{{persona:profile}}"},
        "created_by": str(uuid4()),
        "created_at": "2024-01-01T00:00:00Z",
    }


# --- Reads -----------------------------------------------------------------


def test_list_system_prompts_returns_templates(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/system-prompts")
        return httpx.Response(200, json=[_template_payload()])

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(list_system_prompts(format="full"))
    assert len(result) == 1
    assert isinstance(result[0], SystemPromptTemplateRead)
    assert result[0].slug == "agent-builder"
    assert result[0].locale == "de"


def test_list_system_prompts_forwards_locale_as_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    """WP4 (Plan „Ein Element, eine Sprache"): `locale` ist ein neuer,
    optionaler Sprachfilter (`None` = alle Sprachen, Default) — spiegelt
    `list_playbooks`/`list_resources`/`list_external_tools`."""
    received_params: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        for key, value in request.url.params.items():
            received_params[key] = value
        return httpx.Response(200, json=[])

    monkeypatch.setattr(server, "build_client", _factory(handler))
    asyncio.run(list_system_prompts(locale="en"))
    assert received_params.get("locale") == "en"


def test_list_system_prompts_without_locale_sends_no_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received_params: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        for key, value in request.url.params.items():
            received_params[key] = value
        return httpx.Response(200, json=[])

    monkeypatch.setattr(server, "build_client", _factory(handler))
    asyncio.run(list_system_prompts())
    assert "locale" not in received_params


def test_get_system_prompt_returns_template(monkeypatch: pytest.MonkeyPatch) -> None:
    tid = uuid4()
    payload = _template_payload()
    payload["id"] = str(tid)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith(f"/system-prompts/{tid}")
        return httpx.Response(200, json=payload)

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(get_system_prompt(str(tid), format="full"))
    assert isinstance(result, SystemPromptTemplateRead)
    assert result.id == tid


def test_get_system_prompt_validates_uuid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        server, "build_client", _factory(lambda r: httpx.Response(200, json=_template_payload()))
    )
    with pytest.raises(ToolError):
        asyncio.run(get_system_prompt("not-a-uuid"))


def test_list_versions_supports_system_prompt_entity(monkeypatch: pytest.MonkeyPatch) -> None:
    """Track-1-Tool list_versions deckt entity_type='system_prompt' mit ab."""
    tid = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith(f"/system-prompts/{tid}/versions")
        return httpx.Response(200, json=[_template_version(1, "active")])

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(list_versions("system_prompt", str(tid), format="full"))
    assert len(result) == 1
    assert isinstance(result[0], SystemPromptTemplateVersionRead)


# --- Writes ----------------------------------------------------------------


def test_create_system_prompt_posts_template(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        # `create_system_prompt` loest `data.locale=None` zuerst ueber ein
        # `GET .../workspaces/{id}` auf die Workspace-Content-Sprache auf
        # (WP4, Plan „Ein Element, eine Sprache").
        if request.method == "GET" and request.url.path == f"/v1/workspaces/{_WORKSPACE_ID}":
            return httpx.Response(200, json=_workspace_json())
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_md_result("system-prompts", seen["body"]["content"]))

    monkeypatch.setattr(server, "build_client", _factory(handler))
    data = SystemPromptMarkdownCreate.model_validate(
        {"name": "Neu", "content": {"description": "d", "body": "Du bist {{persona-field:name}}."}}
    )
    result = asyncio.run(create_system_prompt(data))
    assert isinstance(result, MarkdownWriteResult)
    assert seen["method"] == "POST"
    assert seen["path"].endswith("/system-prompts/markdown")
    # Der Markdown-Body geht unveraendert an die API; umwandeln macht sie.
    assert seen["body"]["content"]["body"] == "Du bist {{persona-field:name}}."
    assert seen["body"]["locale"] == "de"


def test_create_system_prompt_with_explicit_locale_skips_workspace_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein explizit gesetztes `data.locale` laeuft unveraendert durch — keine
    zusaetzliche Workspace-Query noetig."""
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        body = json.loads(request.content)
        return httpx.Response(200, json=_md_result("system-prompts", body["content"], locale="en"))

    monkeypatch.setattr(server, "build_client", _factory(handler))
    data = SystemPromptMarkdownCreate.model_validate(
        {
            "name": "Neu",
            "locale": "en",
            "content": {"description": "d", "body": "{{persona:profile}}"},
        }
    )
    result = asyncio.run(create_system_prompt(data))
    assert isinstance(result, MarkdownWriteResult)
    assert calls == [f"POST /v1/workspaces/{_WORKSPACE_ID}/system-prompts/markdown"]


def test_update_system_prompt_puts_template(monkeypatch: pytest.MonkeyPatch) -> None:
    tid = uuid4()
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_md_result("system-prompts", seen["body"]["content"]))

    monkeypatch.setattr(server, "build_client", _factory(handler))
    data = SystemPromptMarkdownUpdate.model_validate(
        {"name": None, "base_rev": "rev-0", "content": {"description": "d", "body": "v2"}}
    )
    asyncio.run(update_system_prompt(str(tid), data))
    assert seen["method"] == "PUT"
    assert seen["path"].endswith(f"/system-prompts/{tid}/markdown")
    assert seen["body"]["base_rev"] == "rev-0"


def test_transition_to_review_passes_through(monkeypatch: pytest.MonkeyPatch) -> None:
    """draft→review ist erlaubt — das Tool reicht den Transition-Call durch."""
    tid = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith(f"/system-prompts/{tid}/versions/1/transition")
        return httpx.Response(200, json=_template_version(1, "review"))

    monkeypatch.setattr(server, "build_client", _factory(handler))
    data = VersionTransitionRequest.model_validate({"to": "review"})
    result = asyncio.run(transition_system_prompt(str(tid), 1, data))
    assert isinstance(result, SystemPromptTemplateVersionRead)
    assert result.status == "review"


def test_transition_to_active_propagates_403_as_toolerror(monkeypatch: pytest.MonkeyPatch) -> None:
    """→active wird serverseitig fuer Agent-Token abgelehnt (ADR-0040) → ToolError."""
    tid = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={
                "detail": "Agent-gebundene Tokens duerfen System-Prompt-Templates "
                "nicht aktivieren oder zurueckziehen — das uebernimmt ein Mensch/Admin."
            },
        )

    monkeypatch.setattr(server, "build_client", _factory(handler))
    data = VersionTransitionRequest.model_validate({"to": "active"})
    with pytest.raises(ToolError):
        asyncio.run(transition_system_prompt(str(tid), 1, data))
