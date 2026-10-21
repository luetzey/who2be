"""Tests der Gespraechs-MCP-Tools (ADR-0053 6.6/6.7, Paket E-MCP-1).

Muster wie `test_learning_tools.py`: direkter Funktionsaufruf mit
`httpx.MockTransport` (Pfad, Body, Fehler-Durchreichung) und der
In-Memory-`Client` fuer Sichtbarkeit und Call-Sperre. Die Rechte selbst
entscheidet die API (`require_triage_right`, `apps/api/tests/test_sessions_*`);
hier wird geprueft, dass die Werkzeuge die richtigen Routen rufen, vor dem
Netz validieren und die Problem-Gruende samt Hinweis weitergeben.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from who2be_mcp import policy_filter, server
from who2be_mcp.client import ApiClient
from who2be_mcp.clients.sessions import FollowUpReport, SessionSubmitResult
from who2be_mcp.config import Settings
from who2be_mcp.server import mcp
from who2be_mcp.tools.sessions import (
    dossier_text,
    get_dossier,
    get_follow_up,
    link_measure_draft,
    submit_session_protocol,
)
from who2be_models import (
    CaseSeverity,
    CaseStatus,
    MeasureCreate,
    MeasureEventRead,
    MeasureState,
    MeasureTarget,
    MeasureVerdict,
    SessionParticipant,
    SessionTrigger,
)
from who2be_models.session import (
    DOSSIER_ELEMENTS_LIMIT,
    DOSSIER_GENERATIONS_LIMIT,
    DOSSIER_MEASURES_LIMIT,
    DOSSIER_OPEN_CASES_LIMIT,
    DOSSIER_TEXT_MAX_LENGTH,
    DOSSIER_VERSIONS_PER_ELEMENT,
    Dossier,
)

_WORKSPACE_ID = uuid4()
_PREFIX = f"/v1/workspaces/{_WORKSPACE_ID}"
_OWN_AGENT = uuid4()
_NOW = "2026-10-14T00:00:00Z"
# Die Schwelle der Konsumenten-Laufzeit fuer eine einzelne Tool-Antwort
# (`test_tool_payload_budget._RESPONSE_CHAR_LIMIT`).
_RESPONSE_CHAR_LIMIT = 50_000
_SESSION_TOOLS = {"get_dossier", "submit_session_protocol", "link_measure_draft", "get_follow_up"}


def _factory(handler: Callable[[httpx.Request], httpx.Response]) -> Callable[[], object]:
    transport = httpx.MockTransport(handler)

    async def _build() -> ApiClient:
        return ApiClient("http://test", "w2b_test", _WORKSPACE_ID, transport=transport)

    return _build


def _problem(status: int, reason: str, detail: str) -> httpx.Response:
    return httpx.Response(
        status,
        json={"detail": detail, "reason": reason},
        headers={"content-type": "application/problem+json"},
    )


def _capture(monkeypatch: pytest.MonkeyPatch, response: httpx.Response) -> list[httpx.Request]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return response

    monkeypatch.setattr(server, "build_client", _factory(handler))
    return seen


def _no_network(monkeypatch: pytest.MonkeyPatch) -> list[httpx.Request]:
    return _capture(monkeypatch, httpx.Response(500, json={"detail": "darf nicht erreicht werden"}))


# --- Fixtures ------------------------------------------------------------------


def _event_payload(measure_id: UUID, version_id: UUID) -> dict[str, object]:
    return {
        "id": str(uuid4()),
        "measure_id": str(measure_id),
        "event": "draft_linked",
        "actor_kind": "agent",
        "actor_id": str(_OWN_AGENT),
        "version_entity_type": "playbook",
        "version_id": str(version_id),
        "verdict": None,
        "metrics": None,
        "note": None,
        "created_at": _NOW,
    }


def _submit_payload(agent_id: UUID, case_id: UUID) -> dict[str, object]:
    session_id = uuid4()
    return {
        "detail": {
            "session": {
                "id": str(session_id),
                "workspace_id": str(_WORKSPACE_ID),
                "agent_id": str(agent_id),
                "trigger": "manual",
                "participants": [],
                "summary": "Gespraech",
                "decisions": [],
                "dissent": [],
                "follow_up_at": "2026-11-01",
                "supersedes_id": None,
                "submitted_by_kind": "agent",
                "submitted_by": str(_OWN_AGENT),
                "case_ids": [str(case_id)],
                "created_at": _NOW,
            },
            "measures": [],
        },
        "cases_started": [str(case_id)],
        "cases_unchanged": [{"case_id": str(uuid4()), "status": "addressed"}],
    }


def _follow_up_payload(measure_id: UUID) -> dict[str, object]:
    version = {
        "version_id": str(uuid4()),
        "version": 2,
        "test_run": {
            "runs_total": 3,
            "runs_passed": 3,
            "verdict": "pass",
            "attestation": "client_self_report",
            "created_at": _NOW,
        },
        "uses": 40,
        "cases": 1,
    }
    return {
        "measure_id": str(measure_id),
        "state": "follow_up_prepared",
        "follow_up_at": "2026-10-10",
        "due": True,
        "reviewable": True,
        "before": {**version, "version": 1, "test_run": None, "cases": 4},
        "after": version,
        "recurrence": 0,
        "min_uses": 30,
        "insufficient": False,
    }


def _full_dossier(name_length: int = 200) -> Dossier:
    """Ein Dossier mit allen Listen am Deckel und allen Texten an der Kuerzung."""
    now = datetime.now(UTC)
    today = now.date()
    text = "x" * (DOSSIER_TEXT_MAX_LENGTH - 1) + "…"
    name = "N" * name_length
    payload: dict[str, Any] = {
        "agent_id": str(_OWN_AGENT),
        "agent_name": name,
        "generated_at": now.isoformat(),
        "min_uses": 30,
        "open_cases": {
            "counts": {s.value: 999 for s in CaseStatus},
            "total": 9_999,
            "items": [
                {
                    "id": str(uuid4()),
                    "status": CaseStatus.open.value,
                    "severity": CaseSeverity.high.value,
                    "situation": text,
                    "expected_behavior": text,
                    "created_at": now.isoformat(),
                }
                for _ in range(DOSSIER_OPEN_CASES_LIMIT)
            ],
        },
        "elements": [
            {
                "entity_type": "playbook",
                "entity_id": str(uuid4()),
                "name": name,
                "versions": [
                    {
                        "version": v,
                        "active": v == 1,
                        "activated_at": now.isoformat(),
                        "uses": 99_999,
                        "outcomes": {"applied": 999, "skipped": 999, "error": 999},
                        "signals": {"helpful": 99, "outdated": 99, "incorrect": 99, "unclear": 99},
                        "cases": 999,
                        "insufficient": False,
                    }
                    for v in range(1, DOSSIER_VERSIONS_PER_ELEMENT + 1)
                ],
            }
            for _ in range(DOSSIER_ELEMENTS_LIMIT)
        ],
        "elements_total": 999,
        "access": {
            "since": today.isoformat(),
            "window_days": 90,
            "total": 99_999,
            "rows": [
                {
                    "ref_kind": "artifact",
                    "operation": "read",
                    "sensitivity": "internal",
                    "entries": 999,
                    "refs": 999,
                    "last_on": today.isoformat(),
                }
                for _ in range(12)
            ],
        },
        "measures": [
            {
                "id": str(uuid4()),
                "session_id": str(uuid4()),
                "target": MeasureTarget.playbook.value,
                "entity_id": str(uuid4()),
                "change_summary": text,
                "state": MeasureState.effective.value,
                "verdict": MeasureVerdict.effective.value,
                "reviewed_at": now.isoformat(),
                "follow_up_at": today.isoformat(),
                "case_count": 99,
                "created_at": now.isoformat(),
            }
            for _ in range(DOSSIER_MEASURES_LIMIT)
        ],
        "measures_total": 999,
        "generations": [
            {
                "entity_type": "playbook",
                "entity_id": str(uuid4()),
                "name": name,
                "from_version": 1,
                "to_version": 2,
                "activated_at": now.isoformat(),
                "measure_ids": [str(uuid4()) for _ in range(5)],
                "verdict": MeasureVerdict.effective.value,
                "shared_agent_count": 99,
            }
            for _ in range(DOSSIER_GENERATIONS_LIMIT)
        ],
        "generations_next_cursor": "c" * 80,
    }
    return Dossier.model_validate(payload)


# --- get_dossier -----------------------------------------------------------------


def test_get_dossier_calls_route_with_cursor(monkeypatch: pytest.MonkeyPatch) -> None:
    dossier = _full_dossier(20)
    seen = _capture(monkeypatch, httpx.Response(200, json=dossier.model_dump(mode="json")))

    result = asyncio.run(get_dossier(str(_OWN_AGENT), cursor="abc", format="full"))

    assert isinstance(result, Dossier)
    assert result == dossier
    assert [r.method for r in seen] == ["GET"]
    assert seen[0].url.path == f"{_PREFIX}/agents/{_OWN_AGENT}/dossier"
    assert seen[0].url.params.get("cursor") == "abc"


def test_get_dossier_without_cursor_sends_no_param(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _capture(
        monkeypatch, httpx.Response(200, json=_full_dossier(20).model_dump(mode="json"))
    )
    asyncio.run(get_dossier(str(_OWN_AGENT)))
    assert "cursor" not in seen[0].url.params


def test_get_dossier_format_text_stays_under_response_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rot-Probe + Zusage: ein voll ausgereiztes Dossier reisst als JSON die Grenze.

    Alle Listen am Deckel des Servers, alle Texte an seiner Kuerzung, Namen am
    Feld-Maximum (200). Der Markdown-Pfad traegt dieselben Zahlen und Texte
    und bleibt darunter.
    """
    dossier = _full_dossier()
    monkeypatch.setattr(
        server,
        "build_client",
        _factory(lambda _r: httpx.Response(200, json=dossier.model_dump(mode="json"))),
    )

    full = asyncio.run(get_dossier(str(_OWN_AGENT), format="full"))
    text = asyncio.run(get_dossier(str(_OWN_AGENT)))

    assert isinstance(full, Dossier)
    assert isinstance(text, str)
    full_chars = len(full.model_dump_json())
    assert full_chars > _RESPONSE_CHAR_LIMIT, f"Fixture zu klein ({full_chars} Zeichen)"
    assert len(text) <= _RESPONSE_CHAR_LIMIT, f"text-Pfad {len(text)} Zeichen"
    with pytest.raises(json.JSONDecodeError):
        json.loads(text)
    # Nichts fehlt: jeder Fall, jeder Baustein, jede Massnahme, der Cursor.
    for case in dossier.open_cases.items:
        assert str(case.id) in text
    for element in dossier.elements:
        assert str(element.entity_id) in text
    for measure in dossier.measures:
        assert str(measure.id) in text
    assert f'cursor="{dossier.generations_next_cursor}"' in text
    assert "uses 99999" in text


def test_dossier_text_marks_direct_generations_and_missing_figures() -> None:
    dossier = _full_dossier(20)
    generation = dossier.generations[0].model_copy(
        update={"measure_ids": [], "from_version": None, "verdict": None}
    )
    version = (
        dossier.elements[0].versions[0].model_copy(update={"cases": None, "insufficient": True})
    )
    element = dossier.elements[0].model_copy(update={"versions": [version]})
    text = dossier_text(
        dossier.model_copy(
            update={
                "generations": [generation],
                "elements": [element],
                "generations_next_cursor": None,
            }
        )
    )
    assert "neu → v2 · Massnahmen: direkt, ohne Massnahme" in text
    assert "Faelle - · zu wenig Nutzung" in text
    assert "weitere Generationen" not in text


def test_get_dossier_rejects_unknown_format_before_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _no_network(monkeypatch)
    with pytest.raises(ToolError, match="Ungueltiges format"):
        asyncio.run(get_dossier(str(_OWN_AGENT), format="plain"))
    assert seen == []


def test_get_dossier_passes_agent_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    _capture(monkeypatch, _problem(404, "agent_not_found", "Agent nicht gefunden."))
    with pytest.raises(ToolError, match=r"reason=agent_not_found"):
        asyncio.run(get_dossier(str(uuid4())))


# --- submit_session_protocol -----------------------------------------------------


def _measure(case_id: UUID, test_case_id: UUID) -> MeasureCreate:
    return MeasureCreate(
        case_ids=[case_id],
        target=MeasureTarget.playbook,
        entity_id=uuid4(),
        change_summary="Schritt 3 praezisieren",
        test_case_id=test_case_id,
        success_criterion="Pruefall gruen",
        counterposition="Mehr Text kostet Tokens",
    )


def _submit(**overrides: Any) -> SessionSubmitResult:
    case_id = overrides.pop("case_id", uuid4())
    args: dict[str, Any] = {
        "agent_id": str(_OWN_AGENT),
        "trigger": SessionTrigger.manual,
        "participants": [
            SessionParticipant(kind="builder", id=_OWN_AGENT, role="Moderation")  # type: ignore[arg-type]
        ],
        "case_ids": [str(case_id)],
        "summary": "Gespraech",
        "decisions": [],
        "dissent": [],
        "follow_up_at": "2026-11-01",
        "measures": [_measure(case_id, uuid4())],
    }
    args.update(overrides)
    return asyncio.run(submit_session_protocol(**args))


def test_submit_posts_full_protocol(monkeypatch: pytest.MonkeyPatch) -> None:
    case_id = uuid4()
    seen = _capture(monkeypatch, httpx.Response(201, json=_submit_payload(_OWN_AGENT, case_id)))
    supersedes = uuid4()

    result = _submit(case_id=case_id, supersedes_id=str(supersedes))

    assert isinstance(result, SessionSubmitResult)
    assert result.cases_started == [case_id]
    assert result.cases_unchanged[0].status is CaseStatus.addressed
    assert [r.method for r in seen] == ["POST"]
    assert seen[0].url.path == f"{_PREFIX}/feedback-sessions"
    body = json.loads(seen[0].content)
    assert body["agent_id"] == str(_OWN_AGENT)
    assert body["follow_up_at"] == "2026-11-01"
    assert body["case_ids"] == [str(case_id)]
    assert body["supersedes_id"] == str(supersedes)
    assert body["measures"][0]["case_ids"] == [str(case_id)]
    assert body["participants"] == [
        {"kind": "builder", "id": str(_OWN_AGENT), "role": "Moderation"}
    ]
    # Den Einreicher setzt der Server; der Client schickt ihn nie mit.
    assert not {"submitted_by", "submitted_by_kind"} & set(body)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"follow_up_at": "naechste Woche"}, "Ungueltiges follow_up_at"),
        ({"agent_id": "kein-uuid"}, "Ungueltige Agent-UUID"),
        ({"case_ids": ["kein-uuid"]}, "Ungueltige Fall-UUID"),
        ({"supersedes_id": "kein-uuid"}, "Ungueltige Protokoll-UUID"),
        ({"summary": ""}, "Ungueltige Eingabe"),
    ],
)
def test_submit_validates_before_network(
    monkeypatch: pytest.MonkeyPatch, overrides: dict[str, Any], message: str
) -> None:
    seen = _no_network(monkeypatch)
    with pytest.raises(ToolError, match=message):
        _submit(**overrides)
    assert seen == []


@pytest.mark.parametrize(
    ("reason", "hint"),
    [
        ("session_cases_invalid", "`list_cases`"),
        ("measure_test_case_required", "`list_test_cases`"),
    ],
)
def test_submit_passes_reason_with_hint(
    monkeypatch: pytest.MonkeyPatch, reason: str, hint: str
) -> None:
    _capture(monkeypatch, _problem(422, reason, "Server sagt nein."))
    with pytest.raises(ToolError) as exc:
        _submit()
    message = str(exc.value)
    assert message.startswith("Server sagt nein.")
    assert f"reason={reason}" in message
    assert hint in message


@pytest.mark.parametrize(
    ("status", "reason"),
    [(403, "missing_capability"), (404, "agent_not_found"), (404, "session_not_found")],
)
def test_submit_passes_other_reasons_unchanged(
    monkeypatch: pytest.MonkeyPatch, status: int, reason: str
) -> None:
    _capture(monkeypatch, _problem(status, reason, "Abgelehnt."))
    with pytest.raises(ToolError) as exc:
        _submit()
    assert str(exc.value) == f"Abgelehnt. (reason={reason})"


# --- link_measure_draft ----------------------------------------------------------


def test_link_posts_version(monkeypatch: pytest.MonkeyPatch) -> None:
    measure_id, version_id = uuid4(), uuid4()
    seen = _capture(monkeypatch, httpx.Response(201, json=_event_payload(measure_id, version_id)))

    event = asyncio.run(link_measure_draft(str(measure_id), "playbook", str(version_id)))

    assert isinstance(event, MeasureEventRead)
    assert event.version_id == version_id
    assert seen[0].method == "POST"
    assert seen[0].url.path == f"{_PREFIX}/measures/{measure_id}/link-draft"
    assert json.loads(seen[0].content) == {
        "version_entity_type": "playbook",
        "version_id": str(version_id),
    }


def test_link_passes_version_not_found_with_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    _capture(monkeypatch, _problem(404, "test_subject_version_not_found", "Version passt nicht."))
    with pytest.raises(ToolError, match=r"reason=test_subject_version_not_found") as exc:
        asyncio.run(link_measure_draft(str(uuid4()), "playbook", str(uuid4())))
    assert "`list_versions`" in str(exc.value)


@pytest.mark.parametrize(
    ("status", "reason"),
    [(404, "measure_not_found"), (409, "measure_transition_forbidden")],
)
def test_link_passes_other_reasons_unchanged(
    monkeypatch: pytest.MonkeyPatch, status: int, reason: str
) -> None:
    _capture(monkeypatch, _problem(status, reason, "Nein."))
    with pytest.raises(ToolError) as exc:
        asyncio.run(link_measure_draft(str(uuid4()), "playbook", str(uuid4())))
    assert str(exc.value) == f"Nein. (reason={reason})"


def test_link_rejects_malformed_ids_before_network(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _no_network(monkeypatch)
    with pytest.raises(ToolError, match="Ungueltige Massnahme-UUID"):
        asyncio.run(link_measure_draft("x", "playbook", str(uuid4())))
    with pytest.raises(ToolError, match="Ungueltige Version-UUID"):
        asyncio.run(link_measure_draft(str(uuid4()), "playbook", "x"))
    assert seen == []


# --- get_follow_up ---------------------------------------------------------------


def test_follow_up_reads_report(monkeypatch: pytest.MonkeyPatch) -> None:
    measure_id = uuid4()
    seen = _capture(monkeypatch, httpx.Response(200, json=_follow_up_payload(measure_id)))

    report = asyncio.run(get_follow_up(str(measure_id)))

    assert isinstance(report, FollowUpReport)
    assert report.state is MeasureState.follow_up_prepared
    assert report.after is not None and report.after.test_run is not None
    assert report.after.test_run.runs_passed == 3
    assert report.before is not None and report.before.cases == 4
    assert seen[0].method == "GET"
    assert seen[0].url.path == f"{_PREFIX}/measures/{measure_id}/follow-up"


def test_follow_up_passes_measure_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    _capture(monkeypatch, _problem(404, "measure_not_found", "Massnahme nicht gefunden."))
    with pytest.raises(ToolError) as exc:
        asyncio.run(get_follow_up(str(uuid4())))
    assert str(exc.value) == "Massnahme nicht gefunden. (reason=measure_not_found)"


# --- Sichtbarkeit und Call-Sperre ------------------------------------------------


def _settings() -> Settings:
    return Settings(api_base_url="http://test", api_token="w2b_test", transport="stdio")


def _install_agent(monkeypatch: pytest.MonkeyPatch, capabilities: list[str]) -> dict[str, int]:
    policy_filter._whoami_cache.clear()
    calls = {"api": 0}
    whoami = {
        "user_id": str(uuid4()),
        "workspace_id": str(_WORKSPACE_ID),
        "role": "editor",
        "is_api_token": True,
        "agent_id": str(_OWN_AGENT),
        "unrestricted": False,
        "capabilities": capabilities,
        "read_scopes": {"persona": "all", "playbook": "all", "resource": "all", "agent": "all"},
        "memory_mode": None,
        "features": ["core"],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/whoami"):
            return httpx.Response(200, json=whoami)
        calls["api"] += 1
        return httpx.Response(200, json={})

    monkeypatch.setattr(policy_filter, "get_settings", _settings)
    monkeypatch.setattr(server, "build_client", _factory(handler))
    return calls


async def _tool_names() -> set[str]:
    async with Client(mcp) as client:
        return {tool.name for tool in await client.list_tools()}


@pytest.mark.parametrize(
    ("capabilities", "expected"),
    [
        (["feedback_write", "test_report"], set()),
        (["case_triage"], _SESSION_TOOLS),
    ],
)
def test_session_tools_visible_only_with_case_triage(
    monkeypatch: pytest.MonkeyPatch, capabilities: list[str], expected: set[str]
) -> None:
    """6.7: die vier Werkzeuge nur mit `case_triage` in `tools/list`."""
    _install_agent(monkeypatch, capabilities)
    assert asyncio.run(_tool_names()) & _SESSION_TOOLS == expected
    policy_filter._whoami_cache.clear()


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("get_dossier", {"agent_id": str(uuid4())}),
        ("get_follow_up", {"measure_id": str(uuid4())}),
        (
            "link_measure_draft",
            {
                "measure_id": str(uuid4()),
                "version_entity_type": "playbook",
                "version_id": str(uuid4()),
            },
        ),
        (
            "submit_session_protocol",
            {
                "agent_id": str(uuid4()),
                "trigger": "manual",
                "participants": [],
                "case_ids": [],
                "summary": "S",
                "decisions": [],
                "dissent": [],
                "follow_up_at": "2026-11-01",
                "measures": [],
            },
        ),
    ],
)
def test_session_tools_blocked_without_case_triage(
    monkeypatch: pytest.MonkeyPatch, tool: str, arguments: dict[str, Any]
) -> None:
    calls = _install_agent(monkeypatch, ["feedback_write"])

    async def _call() -> None:
        async with Client(mcp) as client:
            await client.call_tool(tool, arguments)

    with pytest.raises(ToolError, match="nicht freigeschaltet"):
        asyncio.run(_call())
    assert calls["api"] == 0
    policy_filter._whoami_cache.clear()


def test_no_tool_for_review_or_withdraw() -> None:
    """Einstufen und Zurueckziehen bleiben beim Menschen (6.6, F-W7)."""
    names = {tool.name for tool in asyncio.run(mcp.list_tools(run_middleware=False))}
    assert _SESSION_TOOLS <= names
    assert not {n for n in names if "review" in n or "withdraw" in n}
