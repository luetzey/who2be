"""Unit-Tests fuer den API-Client des MCP-Servers.

Ohne laufende API: `httpx.MockTransport` simuliert die Who2Be-REST-API.
"""

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
import pytest
from fastmcp.exceptions import ToolError

from who2be_mcp.client import ApiClient
from who2be_models import PersonaRead, PlaybookRead

_WORKSPACE = uuid4()
_WS_PREFIX = f"/v1/workspaces/{_WORKSPACE}"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _persona_json(persona_id: str, name: str) -> dict[str, object]:
    return {
        "id": persona_id,
        "workspace_id": str(_WORKSPACE),
        "owner_id": str(uuid4()),
        "name": name,
        "current_version": 1,
        "content": {"description": "d", "system_prompt": "s", "traits": []},
        "created_at": _now(),
        "updated_at": _now(),
    }


def _playbook_json(playbook_id: str, name: str) -> dict[str, object]:
    return {
        "id": playbook_id,
        "workspace_id": str(_WORKSPACE),
        "owner_id": str(uuid4()),
        "name": name,
        "current_version": 1,
        "type": "workflow",
        "tags": ["t"],
        "triggers": None,
        "content": {
            "description": "d",
            "body": "b",
            "type": "workflow",
            "tags": ["t"],
            "triggers": None,
        },
        "created_at": _now(),
        "updated_at": _now(),
    }


def _client(handler: object) -> ApiClient:
    transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
    return ApiClient("http://api.test", "tok", _WORKSPACE, transport=transport)


def test_get_persona_by_uuid_sends_token_and_returns_model() -> None:
    pid = str(uuid4())

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer tok"
        assert request.url.path == f"{_WS_PREFIX}/personas/{pid}"
        return httpx.Response(200, json=_persona_json(pid, "QA"))

    persona = asyncio.run(_client(handler).get_persona(pid))
    assert isinstance(persona, PersonaRead)
    assert persona.name == "QA"


def test_get_persona_by_uuid_ignores_locale() -> None:
    """Plan „Ein Element, eine Sprache" (2026-07-24): bei UUID-Aufloesung wird
    `locale` gar nicht erst mitgesendet — die Persona traegt ihre Sprache
    selbst (Backward-Compat-Parameter, frueher: Variantenwahl ADR-0027)."""
    pid = str(uuid4())
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(dict(request.url.params))
        return httpx.Response(200, json=_persona_json(pid, "QA"))

    asyncio.run(_client(handler).get_persona(pid, "en"))
    assert "locale" not in seen


def test_get_persona_by_uuid_defaults_locale_to_none() -> None:
    pid = str(uuid4())
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(dict(request.url.params))
        return httpx.Response(200, json=_persona_json(pid, "QA"))

    asyncio.run(_client(handler).get_persona(pid))
    assert "locale" not in seen


def test_get_persona_by_name_forwards_locale_as_filter() -> None:
    """Namens-Aufloesung laeuft ueber die Liste — `locale` wirkt dort als
    optionaler Sprachfilter."""
    pid = str(uuid4())
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(dict(request.url.params))
        return httpx.Response(200, json=[_persona_json(pid, "QA")])

    asyncio.run(_client(handler).get_persona("QA", "en"))
    assert seen["locale"] == "en"


def test_get_persona_by_name_omits_locale_by_default() -> None:
    pid = str(uuid4())
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(dict(request.url.params))
        return httpx.Response(200, json=[_persona_json(pid, "QA")])

    asyncio.run(_client(handler).get_persona("QA"))
    assert "locale" not in seen


def test_get_persona_by_name_resolves_via_list() -> None:
    pid = str(uuid4())

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"{_WS_PREFIX}/personas"
        return httpx.Response(
            200,
            json=[_persona_json(str(uuid4()), "Other"), _persona_json(pid, "QA")],
        )

    persona = asyncio.run(_client(handler).get_persona("QA"))
    assert persona.name == "QA"


def test_get_persona_unknown_name_raises_toolerror() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    with pytest.raises(ToolError):
        asyncio.run(_client(handler).get_persona("Ghost"))


def test_get_persona_not_found_raises_toolerror() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "weg"})

    with pytest.raises(ToolError):
        asyncio.run(_client(handler).get_persona(str(uuid4())))


def test_get_persona_playbooks_returns_list() -> None:
    persona_id = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"{_WS_PREFIX}/personas/{persona_id}/playbooks"
        return httpx.Response(200, json=[_playbook_json(str(uuid4()), "PB")])

    playbooks = asyncio.run(_client(handler).get_persona_playbooks(persona_id))
    assert len(playbooks) == 1
    assert isinstance(playbooks[0], PlaybookRead)


def test_get_persona_rendered_returns_body_string() -> None:
    persona_id = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"{_WS_PREFIX}/personas/{persona_id}/rendered"
        # Ohne Modus-Anfrage wird kein `mode`-Query-Param gesendet (additiv).
        assert "mode" not in request.url.params
        return httpx.Response(
            200,
            json={"body_rendered": "Profil\n\n## Skills\n...", "unresolved": []},
        )

    body, applied = asyncio.run(_client(handler).get_persona_rendered(persona_id))
    assert body.startswith("Profil")
    assert "## Skills" in body
    assert applied is None


def test_get_persona_rendered_tolerates_missing_field() -> None:
    persona_id = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unresolved": []})

    body, applied = asyncio.run(_client(handler).get_persona_rendered(persona_id))
    assert body == ""
    assert applied is None


def test_get_persona_rendered_forwards_mode_and_returns_applied_name() -> None:
    """WP-F: `mode` wandert als Query-Param zur API; der kanonische Name kommt zurueck."""
    persona_id = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"{_WS_PREFIX}/personas/{persona_id}/rendered"
        assert request.url.params["mode"] == "sparring"
        return httpx.Response(
            200,
            json={
                "body_rendered": "Profil\n\n## Aktiver Modus: Sparring",
                "unresolved": [],
                "mode": "Sparring",
            },
        )

    body, applied = asyncio.run(_client(handler).get_persona_rendered(persona_id, mode="sparring"))
    assert "## Aktiver Modus: Sparring" in body
    assert applied == "Sparring"


def test_get_persona_rendered_unknown_mode_raises_toolerror_with_detail() -> None:
    """WP-F: das 422-`detail` (Liste verfuegbarer Modi) landet im ToolError."""
    persona_id = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422,
            json={"detail": "Unbekannter Modus 'Ghost'. Verfuegbare Modi: Sparring, Kurzform."},
        )

    with pytest.raises(ToolError, match="Verfuegbare Modi: Sparring, Kurzform"):
        asyncio.run(_client(handler).get_persona_rendered(persona_id, mode="Ghost"))


def test_list_playbooks_forwards_filters() -> None:
    seen: dict[str, dict[str, str]] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"{_WS_PREFIX}/playbooks"
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json=[_playbook_json(str(uuid4()), "PB")])

    result = asyncio.run(_client(handler).list_playbooks("onboarding", "new user", "de"))
    assert seen["params"] == {"tag": "onboarding", "trigger": "new user", "locale": "de"}
    assert len(result) == 1


def test_list_playbooks_omits_unset_filters() -> None:
    """Plan „Ein Element, eine Sprache" (2026-07-24): `locale=None` (Default)
    sendet KEINEN Sprachfilter mehr — ein Alt-Client, der keinen `locale`
    uebergibt, sieht weiterhin Playbooks aller Sprachen (statt sie auf 'de'
    zu verengen)."""
    seen: dict[str, dict[str, str]] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json=[])

    asyncio.run(_client(handler).list_playbooks(None, None))
    assert seen["params"] == {}


def test_get_playbook_returns_model() -> None:
    pid = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"{_WS_PREFIX}/playbooks/{pid}"
        return httpx.Response(200, json=_playbook_json(str(pid), "PB"))

    playbook = asyncio.run(_client(handler).get_playbook(pid))
    assert isinstance(playbook, PlaybookRead)
    assert playbook.name == "PB"


def test_unauthorized_raises_toolerror() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401)

    with pytest.raises(ToolError):
        asyncio.run(_client(handler).get_playbook(uuid4()))


def test_server_error_raises_toolerror() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    with pytest.raises(ToolError):
        asyncio.run(_client(handler).get_playbook(uuid4()))


def test_network_error_raises_toolerror() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Verbindung fehlgeschlagen")

    with pytest.raises(ToolError):
        asyncio.run(_client(handler).get_playbook(UUID(int=0)))


def test_network_error_log_does_not_leak_token(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Verbindung fehlgeschlagen")

    import logging

    with caplog.at_level(logging.WARNING, logger="who2be_mcp.client"):
        with pytest.raises(ToolError):
            asyncio.run(_client(handler).get_playbook(UUID(int=0)))
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "tok" not in messages
    assert "Bearer" not in messages
