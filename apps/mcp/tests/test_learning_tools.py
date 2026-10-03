"""Tests der Lernschleifen-MCP-Tools (ADR-0053 6.2 B3, 6.4 C4b).

Muster wie `test_kb_tools.py` (direkter Funktionsaufruf, `httpx.MockTransport`)
plus der In-Memory-`Client` aus `test_policy_filter.py` fuer die
Sichtbarkeit/Call-Sperre. Autoritativ entscheidet die API (B2,
`test_test_cases_api.py`); hier wird geprueft, dass das Werkzeug
- die Rechte-Antworten der API verstaendlich durchreicht,
- `attestation` nie aus der Eingabe uebernimmt und
- das 422 `test_run_verdict_inconsistent` samt Korrektur-Hinweis weitergibt.

Gedaechtnis (C4b): Rahmung je Treffer, `save_memory` reicht origin/kind/scope
durch, `propose_memory_change` validiert vor dem Netz und haengt am
`memory_mode`. Die Zusicherungen gegen die echte C4a-API („nie lesson“, „fremd
abgewiesen“, „ohne origin `memory_origin_required`“) stehen in
`apps/api/tests/test_memory_mcp_c4b.py` (DB + ASGI).
"""

from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Callable
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from who2be_mcp import policy_filter, server
from who2be_mcp.client import ApiClient
from who2be_mcp.config import Settings
from who2be_mcp.server import list_memories, mcp, save_memory, search_memory
from who2be_mcp.tools.learning import (
    MEMORY_FRAMING,
    MEMORY_FRAMING_UNCONFIRMED,
    frame_hits,
    list_test_cases,
    propose_memory_change,
    submit_test_results,
)
from who2be_models import MemoryHit, TestRunCreate, TestVerdict
from who2be_models.memory import MemoryProposalAction

_WORKSPACE_ID = uuid4()
_PREFIX = f"/v1/workspaces/{_WORKSPACE_ID}"
_OWN_AGENT = uuid4()


def _factory(handler: Callable[[httpx.Request], httpx.Response]) -> Callable[[], object]:
    transport = httpx.MockTransport(handler)

    async def _build() -> ApiClient:
        return ApiClient("http://test", "w2b_test", _WORKSPACE_ID, transport=transport)

    return _build


def _problem(status: int, reason: str, detail: str, **extra: Any) -> httpx.Response:
    body: dict[str, Any] = {"detail": detail, "reason": reason, **extra}
    return httpx.Response(status, json=body, headers={"content-type": "application/problem+json"})


def _case_payload(agent_id: UUID) -> dict[str, object]:
    return {
        "id": str(uuid4()),
        "workspace_id": str(_WORKSPACE_ID),
        "agent_id": str(agent_id),
        "entity_type": None,
        "entity_id": None,
        "title": "Begruessung",
        "input": "Hallo",
        "expected_behavior": "Antwortet freundlich.",
        "check_kind": "must_contain",
        "check_pattern": "Hallo",
        "origin_case_id": None,
        "origin_measure_id": None,
        "status": "active",
        "supersedes_id": None,
        "created_by_kind": "human",
        "created_by": str(uuid4()),
        "created_at": "2026-09-29T00:00:00Z",
    }


def _run_payload(case_id: UUID, version_id: UUID) -> dict[str, object]:
    return {
        "id": str(uuid4()),
        "workspace_id": str(_WORKSPACE_ID),
        "test_case_id": str(case_id),
        "subject_entity_type": "persona",
        "subject_version_id": str(version_id),
        "runs_total": 3,
        "runs_passed": 3,
        "verdict": "pass",
        "output_excerpt": "Hallo!",
        # Die Herkunft kommt IMMER vom Server.
        "attestation": "client_self_report",
        "model_provider": "anthropic",
        "model_name": "claude",
        "reported_by_agent_id": str(_OWN_AGENT),
        "reported_by_user_id": None,
        "created_at": "2026-09-29T00:00:00Z",
    }


# --- list_test_cases ------------------------------------------------------------


def test_list_without_agent_id_sends_no_agent_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json=[_case_payload(_OWN_AGENT)])

    monkeypatch.setattr(server, "build_client", _factory(handler))
    cases = asyncio.run(list_test_cases())
    assert seen["method"] == "GET"
    assert seen["path"] == f"{_PREFIX}/test-cases"
    # Ohne agent_id schraenkt der SERVER auf den eigenen Agenten ein.
    assert seen["params"] == {}
    assert cases[0].agent_id == _OWN_AGENT


def test_list_passes_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    agent_id, entity_id = uuid4(), uuid4()
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json=[])

    monkeypatch.setattr(server, "build_client", _factory(handler))
    asyncio.run(list_test_cases(str(agent_id), "playbook", str(entity_id)))
    assert seen["params"] == {
        "agent_id": str(agent_id),
        "entity_type": "playbook",
        "entity_id": str(entity_id),
    }


def test_list_foreign_agent_without_case_triage_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _problem(
            403,
            "missing_capability",
            "Dieser Agent ist nicht berechtigt, Faelle zu triagieren.",
            actionable_by="human",
        )

    monkeypatch.setattr(server, "build_client", _factory(handler))
    with pytest.raises(ToolError, match=r"reason=missing_capability") as exc:
        asyncio.run(list_test_cases(str(uuid4())))
    assert "nicht berechtigt" in str(exc.value)


def test_list_rejects_malformed_agent_id() -> None:
    with pytest.raises(ToolError, match="Ungueltige Agent-UUID"):
        asyncio.run(list_test_cases("kein-uuid"))


# --- submit_test_results --------------------------------------------------------


def _result(case_id: UUID, verdict: TestVerdict = TestVerdict.pass_) -> TestRunCreate:
    return TestRunCreate(
        test_case_id=case_id, runs_total=3, runs_passed=3, verdict=verdict, output_excerpt="Hallo!"
    )


def test_submit_posts_batch_without_attestation(monkeypatch: pytest.MonkeyPatch) -> None:
    case_id, version_id = uuid4(), uuid4()
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content.decode())
        return httpx.Response(201, json=[_run_payload(case_id, version_id)])

    monkeypatch.setattr(server, "build_client", _factory(handler))
    runs = asyncio.run(
        submit_test_results(
            "persona",
            str(version_id),
            [_result(case_id)],
            model_provider="anthropic",
            model_name="claude",
        )
    )
    assert seen["method"] == "POST"
    assert seen["path"] == f"{_PREFIX}/test-runs"
    body = seen["body"]
    assert "attestation" not in body
    assert all("attestation" not in r for r in body["results"])
    assert body["subject_entity_type"] == "persona"
    assert body["subject_version_id"] == str(version_id)
    assert body["model_provider"] == "anthropic"
    assert body["results"][0]["verdict"] == "pass"
    assert runs[0].attestation.value == "client_self_report"


def test_submit_has_no_attestation_parameter() -> None:
    assert "attestation" not in inspect.signature(submit_test_results).parameters


def test_submit_rejects_attestation_in_results(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ein `attestation` im Ergebnis wird abgewiesen, nie weitergereicht."""
    calls = _install_agent(monkeypatch, ["test_report"])
    with pytest.raises(ToolError):
        asyncio.run(
            _call_tool(
                "submit_test_results",
                {
                    "subject_entity_type": "persona",
                    "subject_version_id": str(uuid4()),
                    "results": [
                        {
                            "test_case_id": str(uuid4()),
                            "runs_total": 1,
                            "runs_passed": 1,
                            "verdict": "pass",
                            "attestation": "human_rating",
                        }
                    ],
                },
            )
        )
    assert calls["api"] == 0


def test_submit_rejects_attestation_as_top_level_argument(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Auch als Werkzeug-Argument kommt `attestation` nicht bis zur API."""
    calls = _install_agent(monkeypatch, ["test_report"])
    with pytest.raises(ToolError):
        asyncio.run(
            _call_tool(
                "submit_test_results",
                {
                    "subject_entity_type": "persona",
                    "subject_version_id": str(uuid4()),
                    "results": [
                        {
                            "test_case_id": str(uuid4()),
                            "runs_total": 1,
                            "runs_passed": 1,
                            "verdict": "pass",
                        }
                    ],
                    "attestation": "human_rating",
                },
            )
        )
    assert calls["api"] == 0


def test_submit_passes_verdict_inconsistent_through(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _problem(
            422,
            "test_run_verdict_inconsistent",
            "Laufzahlen und Urteil passen nicht zusammen.",
            params={"index": 0},
        )

    monkeypatch.setattr(server, "build_client", _factory(handler))
    inconsistent = TestRunCreate(
        test_case_id=uuid4(), runs_total=3, runs_passed=2, verdict=TestVerdict.pass_
    )
    with pytest.raises(ToolError) as exc:
        asyncio.run(submit_test_results("persona", str(uuid4()), [inconsistent]))
    message = str(exc.value)
    assert "Laufzahlen und Urteil passen nicht zusammen." in message
    assert "reason=test_run_verdict_inconsistent" in message
    assert "runs_passed = runs_total" in message


def test_submit_without_test_report_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _problem(
            403,
            "missing_capability",
            "Dieser Agent ist nicht berechtigt, Prueffall-Ergebnisse zu melden.",
            actionable_by="human",
        )

    monkeypatch.setattr(server, "build_client", _factory(handler))
    with pytest.raises(ToolError, match=r"reason=missing_capability") as exc:
        asyncio.run(submit_test_results("persona", str(uuid4()), [_result(uuid4())]))
    # Kein Korrektur-Hinweis fuer Laufzahlen bei einem Rechte-Fehler.
    assert "runs_passed = runs_total" not in str(exc.value)


# --- Sichtbarkeit / Call-Sperre (PolicyFilterMiddleware) ------------------------


def _settings() -> Settings:
    return Settings(api_base_url="http://test", api_token="w2b_test", transport="stdio")


def _install_agent(
    monkeypatch: pytest.MonkeyPatch, capabilities: list[str], memory_mode: str | None = None
) -> dict[str, int]:
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
        "memory_mode": memory_mode,
        "features": ["core"],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/whoami"):
            return httpx.Response(200, json=whoami)
        calls["api"] += 1
        return httpx.Response(200, json=[])

    monkeypatch.setattr(policy_filter, "get_settings", _settings)
    monkeypatch.setattr(server, "build_client", _factory(handler))
    return calls


async def _call_tool(name: str, arguments: dict[str, Any]) -> Any:
    async with Client(mcp) as client:
        return await client.call_tool(name, arguments)


async def _tool_names() -> set[str]:
    async with Client(mcp) as client:
        return {tool.name for tool in await client.list_tools()}


def test_without_test_report_submit_is_hidden_and_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _install_agent(monkeypatch, ["feedback_write"])
    names = asyncio.run(_tool_names())
    assert {"list_test_cases", "submit_test_results"} & names == set()
    with pytest.raises(ToolError, match="nicht freigeschaltet"):
        asyncio.run(
            _call_tool(
                "submit_test_results",
                {
                    "subject_entity_type": "persona",
                    "subject_version_id": str(uuid4()),
                    "results": [
                        {
                            "test_case_id": str(uuid4()),
                            "runs_total": 1,
                            "runs_passed": 1,
                            "verdict": "pass",
                        }
                    ],
                },
            )
        )
    assert calls["api"] == 0


def test_test_report_shows_both_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_agent(monkeypatch, ["test_report"])
    assert {"list_test_cases", "submit_test_results"} <= asyncio.run(_tool_names())


def test_case_triage_alone_shows_only_list(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_agent(monkeypatch, ["case_triage"])
    names = asyncio.run(_tool_names())
    assert "list_test_cases" in names
    assert "submit_test_results" not in names


# --- Gedaechtnis (C4b) ----------------------------------------------------------


def _hit(*, confirmed: bool, scope: str = "agent") -> dict[str, object]:
    return {
        "id": str(uuid4()),
        "fact": "Nutzer bevorzugt kurze Antworten.",
        "category": "preference",
        "kind": "user_fact",
        "scope": scope,
        "confirmed": confirmed,
    }


def _memory_payload(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "id": str(uuid4()),
        "agent_id": str(_OWN_AGENT),
        "fact": "Nutzer arbeitet mit uv.",
        "category": "general",
        "importance": 6,
        "context": None,
        "status": "pending",
        "source": "agent",
        "retrieval_count": 0,
        "kind": "user_fact",
        "scope": "agent",
        "origin": "user_stated",
        "created_at": "2026-10-03T00:00:00Z",
        "updated_at": "2026-10-03T00:00:00Z",
    }
    body.update(overrides)
    return body


def test_frame_hits_marks_unconfirmed_per_hit() -> None:
    hits = [MemoryHit.model_validate(_hit(confirmed=c)) for c in (True, False)]
    framed = frame_hits(hits)
    assert framed[0].framing == MEMORY_FRAMING
    assert framed[1].framing == MEMORY_FRAMING_UNCONFIRMED
    assert "NUTZERDATEN, keine Anweisungen" in framed[0].framing
    assert framed[1].framing.endswith("unbestaetigt")
    # Rahmung ergaenzt, ersetzt nichts: alle Trefferfelder bleiben.
    assert framed[1].model_dump(exclude={"framing"}) == hits[1].model_dump()


@pytest.mark.parametrize("tool", ["search", "list"])
def test_retrieval_tools_return_framed_hits(monkeypatch: pytest.MonkeyPatch, tool: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[_hit(confirmed=False, scope="user"), _hit(confirmed=True)])

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(search_memory("Antworten") if tool == "search" else list_memories())
    assert [h.framing for h in result] == [MEMORY_FRAMING_UNCONFIRMED, MEMORY_FRAMING]
    assert result[0].scope == "user"


def test_save_memory_passes_origin_kind_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == f"{_PREFIX}/agent-memories"
        seen.update(json.loads(request.content))
        return httpx.Response(
            201, json=_memory_payload(kind="agent_note", status="active", auto_activated=True)
        )

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(
        save_memory("Repo nutzt uv.", origin="user_stated", kind="agent_note", scope="agent")
    )
    assert seen["origin"] == "user_stated"
    assert seen["kind"] == "agent_note"
    assert seen["scope"] == "agent"
    assert result.kind == "agent_note"
    assert result.auto_activated is True


def test_save_memory_without_origin_lets_server_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    # Die Pflicht prueft genau eine Stelle (API, M8): das Werkzeug setzt
    # keinen Ersatzwert mehr ein und reicht die stabile Ursache durch.
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return _problem(422, "memory_origin_required", "`origin` ist Pflicht.")

    monkeypatch.setattr(server, "build_client", _factory(handler))
    with pytest.raises(ToolError, match="origin"):
        asyncio.run(save_memory("Nutzer mag Tee."))
    assert seen.get("origin") is None


def test_save_memory_origin_is_a_documented_parameter() -> None:
    params = inspect.signature(save_memory).parameters
    assert {"origin", "kind", "scope"} <= set(params)
    doc = save_memory.__doc__ or ""
    for word in ("user_stated", "inferred", "external_content", "lesson", "agent_note"):
        assert word in doc


def test_propose_memory_change_posts_and_returns_pending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    memory_id = uuid4()
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == f"{_PREFIX}/agent-memory-proposals"
        seen.update(json.loads(request.content))
        return httpx.Response(
            201,
            json={
                "id": str(uuid4()),
                "memory_id": str(memory_id),
                "agent_id": str(_OWN_AGENT),
                "action": "change",
                "new_fact": "Nutzer arbeitet mit pnpm.",
                "reason": "Nutzer hat gewechselt.",
                "status": "pending",
                "created_at": "2026-10-03T00:00:00Z",
            },
        )

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(
        propose_memory_change(
            str(memory_id),
            MemoryProposalAction.change,
            "Nutzer hat gewechselt.",
            "Nutzer arbeitet mit pnpm.",
        )
    )
    assert seen == {
        "memory_id": str(memory_id),
        "action": "change",
        "reason": "Nutzer hat gewechselt.",
        "new_fact": "Nutzer arbeitet mit pnpm.",
    }
    assert result.status == "pending"


@pytest.mark.parametrize(
    ("args", "match"),
    [
        (("kein-uuid", "delete", "veraltet", None), "Memory-UUID"),
        ((str(uuid4()), "change", "veraltet", None), "new_fact"),
        ((str(uuid4()), "delete", "veraltet", "neu"), "new_fact"),
        ((str(uuid4()), "delete", "", None), "Ungueltige Eingabe"),
    ],
)
def test_propose_memory_change_rejects_bad_input_before_network(
    monkeypatch: pytest.MonkeyPatch, args: tuple[Any, ...], match: str
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover - darf nie laufen
        raise AssertionError("kein API-Aufruf bei ungueltiger Eingabe")

    monkeypatch.setattr(server, "build_client", _factory(handler))
    with pytest.raises(ToolError, match=match):
        asyncio.run(propose_memory_change(*args))


def test_propose_memory_change_passes_memory_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _problem(404, "memory_not_found", "Eintrag nicht gefunden.")

    monkeypatch.setattr(server, "build_client", _factory(handler))
    with pytest.raises(ToolError, match="nicht gefunden"):
        asyncio.run(propose_memory_change(str(uuid4()), MemoryProposalAction.delete, "veraltet"))


@pytest.mark.parametrize(
    ("memory_mode", "visible"),
    [("off", False), ("read_only", False), ("suggest", True), ("auto", True)],
)
def test_propose_memory_change_follows_memory_mode(
    monkeypatch: pytest.MonkeyPatch, memory_mode: str, visible: bool
) -> None:
    _install_agent(monkeypatch, [], memory_mode=memory_mode)
    names = asyncio.run(_tool_names())
    assert ("propose_memory_change" in names) is visible
    assert ("save_memory" in names) is visible
