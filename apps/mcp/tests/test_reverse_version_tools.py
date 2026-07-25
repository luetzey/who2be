"""Tool-Tests fuer die Read-only Reverse-Lookup- + Versions-MCP-Tools (Track 1).

`find_usages`, `list_versions`, `get_version`, `diff_versions` sind duenne
Adapter ueber bestehende REST-Endpunkte. Gleiches Muster wie test_resource_tools:
async Tools via `asyncio.run`, HTTP ueber `httpx.MockTransport`, `build_client`
je Test gepatcht.
"""

import asyncio
from collections.abc import Callable
from uuid import uuid4

import httpx
import pytest
from fastmcp.exceptions import ToolError

from who2be_mcp import server
from who2be_mcp.client import ApiClient
from who2be_mcp.server import diff_versions, find_usages, get_version, list_versions
from who2be_models import (
    PlaybookUsage,
    PlaybookVersionRead,
    ResourceUsage,
    ResourceVersionRead,
    VersionDiff,
)

_WORKSPACE_ID = uuid4()


def _factory(handler: Callable[[httpx.Request], httpx.Response]) -> Callable[[], object]:
    transport = httpx.MockTransport(handler)

    async def _build() -> ApiClient:
        return ApiClient("http://test", "token", _WORKSPACE_ID, transport=transport)

    return _build


def _playbook_version(version: int = 1, status: str = "active") -> dict[str, object]:
    return {
        "version": version,
        "status": status,
        "locale": "de",
        "content": {
            "description": "d",
            "body": "b",
            "type": "workflow",
            "tags": [],
            "triggers": None,
        },
        "created_by": str(uuid4()),
        "created_at": "2024-01-01T00:00:00Z",
    }


def _resource_version(version: int = 1, status: str = "draft") -> dict[str, object]:
    return {
        "version": version,
        "status": status,
        "locale": "de",
        "content": {"description": "", "blocks": []},
        "created_by": str(uuid4()),
        "created_at": "2024-01-01T00:00:00Z",
    }


# --- find_usages -----------------------------------------------------------


def test_find_usages_playbook_returns_persona_backlinks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pid = uuid4()
    persona_id = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith(f"/playbooks/{pid}/usages")
        return httpx.Response(200, json=[{"persona_id": str(persona_id), "persona_name": "Coder"}])

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(find_usages("playbook", str(pid)))
    assert len(result) == 1
    assert isinstance(result[0], PlaybookUsage)
    assert result[0].persona_id == persona_id
    assert result[0].persona_name == "Coder"


def test_find_usages_resource_returns_playbook_backlinks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rid = uuid4()
    pb_id = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith(f"/resources/{rid}/usages")
        return httpx.Response(
            200,
            json=[{"playbook_id": str(pb_id), "playbook_name": "Onboard", "block_count": 3}],
        )

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(find_usages("resource", str(rid)))
    assert len(result) == 1
    assert isinstance(result[0], ResourceUsage)
    assert result[0].playbook_id == pb_id
    assert result[0].block_count == 3


def test_find_usages_validates_uuid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        server, "build_client", _factory(lambda request: httpx.Response(200, json=[]))
    )
    with pytest.raises(ToolError):
        asyncio.run(find_usages("playbook", "not-a-uuid"))


# --- list_versions ---------------------------------------------------------


def test_list_versions_playbook_returns_snapshots(monkeypatch: pytest.MonkeyPatch) -> None:
    pid = uuid4()
    versions = [_playbook_version(1, "inactive"), _playbook_version(2, "active")]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith(f"/playbooks/{pid}/versions")
        return httpx.Response(200, json=versions)

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(list_versions("playbook", str(pid)))
    assert len(result) == 2
    assert all(isinstance(v, PlaybookVersionRead) for v in result)
    assert [v.version for v in result] == [1, 2]
    assert result[1].status == "active"


def test_list_versions_resource_dispatches_to_resource_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rid = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith(f"/resources/{rid}/versions")
        return httpx.Response(200, json=[_resource_version()])

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(list_versions("resource", str(rid)))
    assert len(result) == 1
    assert isinstance(result[0], ResourceVersionRead)


def test_list_versions_persona_dispatches_to_persona_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """entity_type='persona' trifft den /personas/-Pfad (leere Liste, kein Content-Parse)."""
    pid = uuid4()
    seen_path = ""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_path
        seen_path = request.url.path
        return httpx.Response(200, json=[])

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(list_versions("persona", str(pid)))
    assert result == []
    assert seen_path.endswith(f"/personas/{pid}/versions")


def test_list_versions_ignores_locale(monkeypatch: pytest.MonkeyPatch) -> None:
    """Plan „Ein Element, eine Sprache" (2026-07-24): `locale` ist ein
    Backward-Compat-Parameter (frueher: Variantenwahl) und wird nicht mehr an
    die API weitergereicht — die Historie gehoert zu genau EINEM Element."""
    pid = uuid4()
    received: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        for key, value in request.url.params.items():
            received[key] = value
        return httpx.Response(200, json=[])

    monkeypatch.setattr(server, "build_client", _factory(handler))
    asyncio.run(list_versions("playbook", str(pid), locale="en"))
    assert "locale" not in received


# --- get_version -----------------------------------------------------------


def test_get_version_returns_single_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    pid = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith(f"/playbooks/{pid}/versions/2")
        return httpx.Response(200, json=_playbook_version(2, "active"))

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(get_version("playbook", str(pid), 2))
    assert isinstance(result, PlaybookVersionRead)
    assert result.version == 2


def test_get_version_validates_uuid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        server, "build_client", _factory(lambda request: httpx.Response(200, json={}))
    )
    with pytest.raises(ToolError):
        asyncio.run(get_version("playbook", "not-a-uuid", 1))


# --- diff_versions ---------------------------------------------------------


def test_diff_versions_returns_structured_diff(monkeypatch: pytest.MonkeyPatch) -> None:
    rid = uuid4()
    diff = {
        "version": 2,
        "against": "active",
        "against_version": 1,
        "changes": [{"path": "tags", "op": "changed", "before": [], "after": ["x"]}],
        "identical": False,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith(f"/resources/{rid}/versions/2/diff")
        return httpx.Response(200, json=diff)

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(diff_versions("resource", str(rid), 2))
    assert isinstance(result, VersionDiff)
    assert result.identical is False
    assert len(result.changes) == 1
    assert result.changes[0].op == "changed"


def test_diff_versions_defaults_against_active(monkeypatch: pytest.MonkeyPatch) -> None:
    pid = uuid4()
    received: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        for key, value in request.url.params.items():
            received[key] = value
        return httpx.Response(
            200,
            json={"version": 1, "against": "active", "changes": [], "identical": True},
        )

    monkeypatch.setattr(server, "build_client", _factory(handler))
    asyncio.run(diff_versions("playbook", str(pid), 1))
    assert received.get("against") == "active"


def test_diff_versions_passes_explicit_against(monkeypatch: pytest.MonkeyPatch) -> None:
    pid = uuid4()
    received: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        for key, value in request.url.params.items():
            received[key] = value
        return httpx.Response(
            200,
            json={"version": 3, "against": "1", "changes": [], "identical": True},
        )

    monkeypatch.setattr(server, "build_client", _factory(handler))
    asyncio.run(diff_versions("persona", str(pid), 3, against="1"))
    assert received.get("against") == "1"
