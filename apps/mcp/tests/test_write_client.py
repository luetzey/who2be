"""Unit-Tests fuer den Write-Pfad des MCP-API-Clients (ADR-0012).

Ohne laufende API: `httpx.MockTransport` simuliert die Who2Be-REST-API und
prueft Methode, Pfad und gesendeten Body der Mutationen.
"""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
from fastmcp.exceptions import ToolError

from who2be_mcp.client import ApiClient
from who2be_models import (
    AgentCopy,
    AgentCreate,
    AgentRead,
    AgentUpdate,
    PersonaCreate,
    PersonaPlaybookLinkSet,
    PersonaRead,
    PersonaUpdate,
    PersonaVersionContent,
    PersonaVersionRead,
    PlaybookCompositionLinkSet,
    PlaybookCreate,
    PlaybookRead,
    ResourceCreate,
    ResourceLinkItem,
    ResourceLinkRead,
    ResourceLinkSet,
    ResourceRead,
    SubResourceLinkItem,
    SubResourceLinkSet,
    SubResourceRead,
    VersionStatus,
    VersionTransitionRequest,
)

_WORKSPACE = uuid4()
_WS_PREFIX = f"/v1/workspaces/{_WORKSPACE}"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _client(handler: object) -> ApiClient:
    transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
    return ApiClient("http://api.test", "tok", _WORKSPACE, transport=transport)


def _persona_json(name: str = "QA") -> dict[str, object]:
    return {
        "id": str(uuid4()),
        "workspace_id": str(_WORKSPACE),
        "owner_id": str(uuid4()),
        "name": name,
        "current_version": 1,
        "content": {"description": "d"},
        "created_at": _now(),
        "updated_at": _now(),
    }


def _playbook_json(name: str = "PB") -> dict[str, object]:
    return {
        "id": str(uuid4()),
        "workspace_id": str(_WORKSPACE),
        "owner_id": str(uuid4()),
        "name": name,
        "current_version": 1,
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
        "created_at": _now(),
        "updated_at": _now(),
    }


def _resource_json(name: str = "R") -> dict[str, object]:
    return {
        "id": str(uuid4()),
        "workspace_id": str(_WORKSPACE),
        "owner_id": str(uuid4()),
        "name": name,
        "slug": name.lower(),
        "current_version": 1,
        "content": {"description": "d", "blocks": [], "tags": []},
        "created_at": _now(),
        "updated_at": _now(),
    }


def _agent_json(name: str = "A") -> dict[str, object]:
    return {
        "id": str(uuid4()),
        "workspace_id": str(_WORKSPACE),
        "owner_id": str(uuid4()),
        "name": name,
        "description": "",
        "persona_id": None,
        "system_prompt_template_id": None,
        "status": "disabled",
        "created_at": _now(),
        "updated_at": _now(),
    }


def _version_json(version: int = 2) -> dict[str, object]:
    return {
        "version": version,
        "content": {"description": "d"},
        "created_by": str(uuid4()),
        "created_at": _now(),
    }


# --- Create -----------------------------------------------------------------


def test_create_persona_posts_body_and_returns_model() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["body"] = request.read().decode()
        return httpx.Response(201, json=_persona_json("Neu"))

    persona = asyncio.run(_client(handler).create_persona(PersonaCreate(name="Neu")))
    assert isinstance(persona, PersonaRead)
    assert seen["method"] == "POST"
    assert seen["path"] == f"{_WS_PREFIX}/personas"
    assert '"name":"Neu"' in str(seen["body"]).replace(" ", "")


def test_create_playbook_posts_to_playbooks() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == f"{_WS_PREFIX}/playbooks"
        return httpx.Response(201, json=_playbook_json())

    result = asyncio.run(_client(handler).create_playbook(PlaybookCreate(name="PB")))
    assert isinstance(result, PlaybookRead)


def test_create_resource_posts_to_resources() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == f"{_WS_PREFIX}/resources"
        return httpx.Response(201, json=_resource_json())

    result = asyncio.run(_client(handler).create_resource(ResourceCreate(name="R")))
    assert isinstance(result, ResourceRead)


def test_create_agent_posts_to_agents() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == f"{_WS_PREFIX}/agents"
        return httpx.Response(201, json=_agent_json())

    result = asyncio.run(_client(handler).create_agent(AgentCreate(name="A")))
    assert isinstance(result, AgentRead)


# --- Update -----------------------------------------------------------------


def test_update_persona_puts_language_switch_in_body() -> None:
    """Plan „Ein Element, eine Sprache": ein Sprachwechsel laeuft ueber
    `data.locale` (Entity-Metadatum im Body) — kein `?locale=`-Query-Param mehr
    (fruehere Variantenwahl, ADR-0027)."""
    pid = uuid4()
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["query_locale"] = dict(request.url.params).get("locale")
        seen["body"] = request.read().decode()
        return httpx.Response(200, json=_persona_json())

    asyncio.run(
        _client(handler).update_persona(
            pid,
            PersonaUpdate(content=PersonaVersionContent(description="x"), locale="en"),
        )
    )
    assert seen["method"] == "PUT"
    assert seen["path"] == f"{_WS_PREFIX}/personas/{pid}"
    # Kein Variantenselektor mehr auf der Query.
    assert seen["query_locale"] is None
    assert '"locale":"en"' in str(seen["body"]).replace(" ", "")


def test_update_agent_puts_to_agent() -> None:
    aid = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PUT"
        assert request.url.path == f"{_WS_PREFIX}/agents/{aid}"
        return httpx.Response(200, json=_agent_json())

    result = asyncio.run(_client(handler).update_agent(aid, AgentUpdate(name="A2")))
    assert isinstance(result, AgentRead)


# --- Versioning -------------------------------------------------------------


def test_transition_persona_posts_to_transition_with_body() -> None:
    pid = uuid4()
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = request.read().decode()
        return httpx.Response(200, json=_version_json())

    result = asyncio.run(
        _client(handler).transition_persona_version(
            pid, 2, VersionTransitionRequest(to=VersionStatus.review, note="go")
        )
    )
    assert isinstance(result, PersonaVersionRead)
    assert seen["path"] == f"{_WS_PREFIX}/personas/{pid}/versions/2/transition"
    body = str(seen["body"]).replace(" ", "")
    assert '"to":"review"' in body
    assert '"note":"go"' in body


def test_restore_persona_posts_to_restore_without_body() -> None:
    pid = uuid4()
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = request.read().decode()
        return httpx.Response(201, json=_persona_json())

    asyncio.run(_client(handler).restore_persona_version(pid, 1))
    assert seen["path"] == f"{_WS_PREFIX}/personas/{pid}/versions/1/restore"
    # Restore traegt keinen Body (null → "null").
    assert seen["body"] in ("", "null")


# --- Links ------------------------------------------------------------------


def test_set_persona_playbooks_puts_id_list() -> None:
    pid = uuid4()
    target = uuid4()
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = request.read().decode()
        return httpx.Response(200, json=[_playbook_json()])

    result = asyncio.run(
        _client(handler).set_persona_playbooks(pid, PersonaPlaybookLinkSet(playbook_ids=[target]))
    )
    assert len(result) == 1
    assert seen["path"] == f"{_WS_PREFIX}/personas/{pid}/playbooks"
    assert str(target) in str(seen["body"])


def test_set_playbook_resource_links_puts_links() -> None:
    pbid = uuid4()
    rid = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"{_WS_PREFIX}/playbooks/{pbid}/resource_links"
        return httpx.Response(
            200,
            json=[
                {
                    "resource_id": str(rid),
                    "resource_name": "R",
                    "position": 0,
                    "available": True,
                }
            ],
        )

    links = ResourceLinkSet(
        links=[ResourceLinkItem(resource_id=rid, position=0, link_scope="resource")]
    )
    result = asyncio.run(_client(handler).set_playbook_resource_links(pbid, links))
    assert isinstance(result[0], ResourceLinkRead)


def test_set_playbook_composes_puts_child_ids() -> None:
    pbid = uuid4()
    child = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"{_WS_PREFIX}/playbooks/{pbid}/composes"
        assert str(child) in request.read().decode()
        return httpx.Response(200, json=[_playbook_json()])

    result = asyncio.run(
        _client(handler).set_playbook_composes(pbid, PlaybookCompositionLinkSet(child_ids=[child]))
    )
    assert len(result) == 1


def test_set_resource_sub_resources_puts_links() -> None:
    rid = uuid4()
    child = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"{_WS_PREFIX}/resources/{rid}/sub_resources"
        return httpx.Response(200, json=[{"id": str(child), "name": "Child"}])

    links = SubResourceLinkSet(links=[SubResourceLinkItem(child_id=child, position=0)])
    result = asyncio.run(_client(handler).set_resource_sub_resources(rid, links))
    assert isinstance(result[0], SubResourceRead)


def test_copy_agent_posts_to_copy() -> None:
    aid = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"{_WS_PREFIX}/agents/{aid}/copy"
        return httpx.Response(201, json=_agent_json("A (Kopie)"))

    result = asyncio.run(_client(handler).copy_agent(aid, AgentCopy(name=None)))
    assert isinstance(result, AgentRead)


# --- Fehler-Mapping ---------------------------------------------------------


def test_forbidden_write_raises_toolerror_with_role_hint() -> None:
    # Rollen-Gate: das API-`detail` traegt den Hinweis und wird durchgereicht.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={"detail": "Diese Aktion erfordert mindestens die Rolle 'editor'."},
        )

    with pytest.raises(ToolError, match="editor"):
        asyncio.run(_client(handler).create_persona(PersonaCreate(name="X")))


def test_forbidden_write_surfaces_agent_policy_reason() -> None:
    # Pro-Agent-Policy-Gate: der spezifische Grund erreicht den Agenten.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={"detail": "Dieser Agent ist nicht berechtigt, Playbooks zu erstellen."},
        )

    with pytest.raises(ToolError, match="nicht berechtigt"):
        asyncio.run(_client(handler).create_persona(PersonaCreate(name="X")))


def test_conflict_surfaces_api_detail() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"detail": "Es existiert bereits ein Draft."})

    with pytest.raises(ToolError, match="bereits ein Draft"):
        asyncio.run(
            _client(handler).update_persona(
                uuid4(), PersonaUpdate(content=PersonaVersionContent(description="x"))
            )
        )


def test_validation_error_falls_back_to_generic_message() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        # 422 traegt oft eine Listen-`detail` — die bleibt generisch.
        return httpx.Response(422, json={"detail": [{"loc": ["name"], "msg": "too long"}]})

    with pytest.raises(ToolError, match="Ungueltige Eingabe"):
        asyncio.run(_client(handler).create_persona(PersonaCreate(name="X")))
