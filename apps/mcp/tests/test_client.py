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


def test_get_persona_by_name_sends_server_side_name_filter() -> None:
    """Issue #415: der Name geht als Query mit, statt im Client verglichen zu werden.

    Vorher lud dieser Pfad die GANZE Persona-Liste — inklusive der vollen
    Bodies jeder Persona — nur um einen String zu vergleichen.
    """
    pid = str(uuid4())
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(dict(request.url.params))
        return httpx.Response(200, json=[_persona_json(pid, "QA")])

    persona = asyncio.run(_client(handler).get_persona("QA"))

    assert seen["name"] == "QA"
    assert persona.name == "QA"


def test_get_persona_by_name_still_matches_when_server_ignores_filter() -> None:
    """Sicherheitsnetz gegen Versions-Versatz MCP ↔ API.

    Eine aeltere API kennt `?name=` nicht und ignoriert den Parameter — die
    Antwort ist dann die volle Liste. Ohne den gebliebenen Client-Vergleich
    kaeme die erstbeste Persona als Treffer zurueck, hier also die falsche.
    """
    wanted = str(uuid4())

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[_persona_json(str(uuid4()), "Other"), _persona_json(wanted, "QA")],
        )

    persona = asyncio.run(_client(handler).get_persona("QA"))

    assert str(persona.id) == wanted


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


# --------------------------------------------------- Reason-Codes (Befund C)


def _problem(status: int, reason: str, detail: str, actionable_by: str) -> httpx.Response:
    """`application/problem+json`, wie die API-Gates es liefern."""
    return httpx.Response(
        status,
        json={
            "type": "about:blank",
            "title": "Fehler",
            "status": status,
            "detail": detail,
            "reason": reason,
            "actionable_by": actionable_by,
            "request_id": "req-1",
        },
    )


def test_reason_und_actionable_by_landen_im_toolerror() -> None:
    """Der Schluessel, auf den ein Agent verzweigen soll, muss ihn erreichen.

    `reason` ist ein geschlossenes Vokabular und ausdruecklich dafuer gebaut,
    dass ein Agent NICHT den `detail`-Freitext parsen muss
    (`models/errors.py`). Der MCP-Server hat ihn bis 2026-08-17 verworfen.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return _problem(
            422,
            "convention_missing",
            "Die Quelle 'n26' hat keine hinterlegte Konvention.",
            "agent",
        )

    with pytest.raises(ToolError) as excinfo:
        asyncio.run(_client(handler).get_playbook(uuid4()))
    message = str(excinfo.value)
    # Die Prosa bleibt vorne — danach handelt das Modell.
    assert message.startswith("Die Quelle 'n26' hat keine hinterlegte Konvention.")
    assert "reason=convention_missing" in message
    assert "actionable_by=agent" in message


@pytest.mark.parametrize(
    ("status", "reason", "actionable_by"),
    [
        (503, "tablestore_unavailable", "human"),
        (413, "ingest_too_large", "agent"),
        (403, "area_forbidden", "agent"),
        (409, "rev_conflict", "agent"),
    ],
)
def test_reason_kommt_bei_jedem_status_durch(status: int, reason: str, actionable_by: str) -> None:
    """Auch die Statuses, die vorher NUR den nackten Code lieferten.

    `Who2Be-API-Fehler (503)` liess einen Agenten im Dunkeln: er konnte weder
    sehen, dass ein Retry sinnlos ist (`actionable_by=human`), noch warum.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return _problem(status, reason, "Sprechende Begruendung.", actionable_by)

    with pytest.raises(ToolError) as excinfo:
        asyncio.run(_client(handler).get_playbook(uuid4()))
    message = str(excinfo.value)
    assert "Sprechende Begruendung." in message
    assert f"reason={reason}" in message
    assert f"actionable_by={actionable_by}" in message
    # Und nicht mehr die generische Huelle, die vorher alles verdeckt hat.
    assert "Who2Be-API-Fehler" not in message


def test_ohne_reason_bleibt_die_meldung_unveraendert() -> None:
    """Antworten ohne Taxonomie (FastAPI-`HTTPException`) erfinden nichts.

    Sonst stuende an einer 422-Validierungsantwort ploetzlich ein
    `reason=`-Schluessel, auf den kein Agent verzweigen kann.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"detail": "Zeile 0: 'occurred_at' fehlt."})

    with pytest.raises(ToolError) as excinfo:
        asyncio.run(_client(handler).get_playbook(uuid4()))
    message = str(excinfo.value)
    assert message == "Zeile 0: 'occurred_at' fehlt."
    assert "reason=" not in message


def test_ohne_body_bleibt_der_fallback() -> None:
    """Kein JSON (Proxy-Fehlerseite, leerer Body) → generische Meldung."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text="<html>bad gateway</html>")

    with pytest.raises(ToolError, match=r"Who2Be-API-Fehler \(502\)"):
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
