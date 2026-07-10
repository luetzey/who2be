"""Tool-Tests fuer die Usage-/Feedback-Flywheel-MCP-Tools (ADR-0038).

`record_usage`/`submit_feedback`/`get_feedback` sind duenne Adapter ueber die
REST-Endpunkte. Muster wie test_resource_tools: async Tools via `asyncio.run`,
HTTP ueber `httpx.MockTransport`, `build_client` gepatcht.
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
    get_feedback,
    record_usage,
    report_problem,
    resolve_feedback,
    submit_feedback,
)
from who2be_models import (
    AgentFeedbackRead,
    FeedbackCreate,
    FeedbackResolution,
    FeedbackSummary,
    SystemFeedbackCreate,
    UsageEventCreate,
    UsageEventRead,
)

_WORKSPACE_ID = uuid4()


def _factory(handler: Callable[[httpx.Request], httpx.Response]) -> Callable[[], object]:
    transport = httpx.MockTransport(handler)

    async def _build() -> ApiClient:
        return ApiClient("http://test", "token", _WORKSPACE_ID, transport=transport)

    return _build


def test_record_usage_posts_event(monkeypatch: pytest.MonkeyPatch) -> None:
    pid = uuid4()
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        return httpx.Response(
            201,
            json={
                "id": str(uuid4()),
                "entity_type": "playbook",
                "entity_id": str(pid),
                "version": 2,
                "outcome": "applied",
                "agent_id": None,
                "created_at": "2024-01-01T00:00:00Z",
            },
        )

    monkeypatch.setattr(server, "build_client", _factory(handler))
    data = UsageEventCreate.model_validate(
        {"entity_type": "playbook", "entity_id": str(pid), "version": 2, "outcome": "applied"}
    )
    result = asyncio.run(record_usage(data))
    assert isinstance(result, UsageEventRead)
    assert result.outcome == "applied"
    assert seen["method"] == "POST"
    assert seen["path"].endswith("/usage-events")


def test_submit_feedback_posts_signal(monkeypatch: pytest.MonkeyPatch) -> None:
    rid = uuid4()
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        return httpx.Response(
            201,
            json={
                "id": str(uuid4()),
                "entity_type": "resource",
                "entity_id": str(rid),
                "version": None,
                "signal": "outdated",
                "note": "Link tot",
                "agent_id": None,
                "created_at": "2024-01-01T00:00:00Z",
            },
        )

    monkeypatch.setattr(server, "build_client", _factory(handler))
    data = FeedbackCreate.model_validate(
        {"entity_type": "resource", "entity_id": str(rid), "signal": "outdated", "note": "Link tot"}
    )
    result = asyncio.run(submit_feedback(data))
    assert isinstance(result, AgentFeedbackRead)
    assert result.signal == "outdated"
    assert seen["path"].endswith("/feedback")


def test_report_problem_posts_system_feedback(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        return httpx.Response(
            201,
            json={
                "id": str(uuid4()),
                "entity_type": "system",
                "entity_id": None,
                "version": None,
                "signal": "mcp",
                "note": "fetch_playbook 500",
                "agent_id": None,
                "created_at": "2024-01-01T00:00:00Z",
            },
        )

    monkeypatch.setattr(server, "build_client", _factory(handler))
    data = SystemFeedbackCreate.model_validate({"category": "mcp", "note": "fetch_playbook 500"})
    result = asyncio.run(report_problem(data))
    assert isinstance(result, AgentFeedbackRead)
    assert result.entity_type == "system"
    assert result.entity_id is None
    assert result.signal == "mcp"
    assert seen["method"] == "POST"
    assert seen["path"].endswith("/system-feedback")


def test_get_feedback_returns_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    pid = uuid4()
    fid = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith(f"/feedback/playbook/{pid}")
        return httpx.Response(
            200,
            json={
                "entity_type": "playbook",
                "entity_id": str(pid),
                "usage_count": 5,
                "by_outcome": {"applied": 4, "skipped": 1},
                "by_signal": {"helpful": 3, "outdated": 1},
                "recent_notes": ["super", "bitte aktualisieren"],
                "recent_feedback": [
                    {
                        "id": str(fid),
                        "signal": "outdated",
                        "note": "bitte aktualisieren",
                        "resolution": None,
                        "created_at": "2024-01-01T00:00:00Z",
                    },
                    {
                        "id": str(uuid4()),
                        "signal": "helpful",
                        "note": None,
                        "resolution": "addressed",
                        "created_at": "2023-12-31T00:00:00Z",
                    },
                ],
            },
        )

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(get_feedback("playbook", str(pid)))
    assert isinstance(result, FeedbackSummary)
    assert result.usage_count == 5
    assert result.by_outcome["applied"] == 4
    assert result.by_signal["helpful"] == 3
    assert len(result.recent_notes) == 2
    # Passthrough der Einzel-Feedbacks: id + Triage-Status kommen durch,
    # damit der Agent offene Signale (resolution None) triagieren kann.
    assert len(result.recent_feedback) == 2
    assert result.recent_feedback[0].id == fid
    assert result.recent_feedback[0].resolution is None
    assert result.recent_feedback[1].resolution == FeedbackResolution.addressed


def test_resolve_feedback_tool_registered() -> None:
    """Das Triage-Tool ist registriert (Durchsetzung der feedback_resolve-
    Capability liegt serverseitig in der API, wie bei allen Write-Tools)."""
    names = {tool.name for tool in asyncio.run(server.mcp.list_tools())}
    assert "resolve_feedback" in names


def test_get_feedback_validates_uuid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "build_client", _factory(lambda r: httpx.Response(200, json={})))
    with pytest.raises(ToolError):
        asyncio.run(get_feedback("playbook", "not-a-uuid"))


def test_resolve_feedback_posts_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    fid = uuid4()
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["body"] = request.read().decode()
        return httpx.Response(
            201,
            json={
                "id": str(fid),
                "entity_type": "playbook",
                "entity_id": str(uuid4()),
                "version": None,
                "signal": "outdated",
                "note": "Schritt 4 veraltet",
                "agent_id": None,
                "created_at": "2024-01-01T00:00:00Z",
                "resolution": "dismissed",
            },
        )

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(
        resolve_feedback(str(fid), FeedbackResolution.dismissed, note="Absichtlich so — Legacy.")
    )
    assert isinstance(result, AgentFeedbackRead)
    assert result.resolution == FeedbackResolution.dismissed
    assert seen["method"] == "POST"
    assert str(seen["path"]).endswith(f"/feedback/{fid}/resolution")
    assert "dismissed" in str(seen["body"])
    assert "Absichtlich so" in str(seen["body"])


def test_resolve_feedback_validates_uuid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "build_client", _factory(lambda r: httpx.Response(201, json={})))
    with pytest.raises(ToolError):
        asyncio.run(resolve_feedback("not-a-uuid", FeedbackResolution.addressed))


def test_resolve_feedback_propagates_403_as_toolerror(monkeypatch: pytest.MonkeyPatch) -> None:
    """Policy-Durchsetzung liegt serverseitig: fehlt dem agent-gebundenen Token
    die feedback_resolve-Capability, antwortet die API 403 → ToolError."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403, json={"detail": "Dieser Agent ist nicht berechtigt, Feedback zu schliessen."}
        )

    monkeypatch.setattr(server, "build_client", _factory(handler))
    with pytest.raises(ToolError):
        asyncio.run(resolve_feedback(str(uuid4()), FeedbackResolution.addressed))


def test_record_usage_propagates_404_as_toolerror(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fremde/unbekannte entity_id → 404 der API → ToolError."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "Element nicht gefunden."})

    monkeypatch.setattr(server, "build_client", _factory(handler))
    data = UsageEventCreate.model_validate({"entity_type": "playbook", "entity_id": str(uuid4())})
    with pytest.raises(ToolError):
        asyncio.run(record_usage(data))
