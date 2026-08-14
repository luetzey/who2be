"""Tests fuer die Per-Request-Policy-Filterung von tools/list (ADR-0042).

Muster wie test_whoami_tool.py: kein pytest-asyncio, in-memory `Client` gegen
die echte `mcp`-Instanz (Middleware laeuft mit), `server.build_client` per
monkeypatch auf einen `httpx.MockTransport`-Client — die whoami-Aufloesung der
Middleware nutzt denselben Pfad. `policy_filter.get_settings` wird gepatcht,
damit der stdio-Token deterministisch ist (kein Env-Leak).

Abgedeckt: Filter-Matrix (Default-/Voll-Policy, `resource_read=none`,
unrestricted admin/viewer), Drift-Guard Registrierung↔Mapping, fail-open bei
Aufloesungsfehler, Call-Sperre + Durchlass, whoami-Cache pro Token.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any
from uuid import uuid4

import httpx
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from who2be_mcp import policy_filter, server
from who2be_mcp.client import ApiClient
from who2be_mcp.config import Settings
from who2be_mcp.server import mcp
from who2be_models import MCP_TOOL_REQUIREMENTS

_WORKSPACE_ID = uuid4()

# Erwartete Sichtbarkeit fuer die Default-Policy eines Konsum-Agenten
# (unrestricted=False, role=editor, capabilities=[feedback_write],
# read_scopes: persona=all, playbook/resource/agent=assigned) — exakt diese
# Menge, nichts weiter.
_DEFAULT_POLICY_TOOLS = {
    "ping",
    "whoami",
    "get_persona",
    "search",
    "search_content",
    "list_triggers",
    "list_playbooks",
    "fetch_playbook",
    "list_resources",
    "fetch_resource",
    "list_resource_blocks",
    "list_agents",
    "get_agent",
    "fetch_agent",
    "find_usages",
    "list_versions",
    "get_version",
    "diff_versions",
    "record_usage",
    "submit_feedback",
    "report_problem",
    "get_feedback",
    # WP-3: external_tool_read faellt fail-open auf `all` (fehlender Key im
    # whoami-Payload unten), also sind die ExternalTool-Reads Default sichtbar.
    "list_external_tools",
    "get_external_tool",
    # WP8 (ADR-0047): die WorkArea-Reads haengen an dynamischen Area-Grants
    # (Domain "workarea", kein ReadScope) und sind damit Default sichtbar;
    # die Write-Tools (create/append/patch/delete/ingest) bleiben ohne
    # `workarea_write` unsichtbar.
    "read_artifact",
    "list_artifacts",
    "search_workarea",
    # KB-Reads (WP9, Domain "kb"): sichtbar wie die WorkArea-Reads; die
    # Write-Tools (create_node/update_node/create_edge) bleiben ohne
    # `kb_write`/`kb_edge_write` unsichtbar.
    "search_kb",
    "neighbors",
}

_ALL_CAPABILITIES = [
    "persona_write",
    "playbook_write",
    "resource_write",
    "agent_write",
    "system_prompt_write",
    "feedback_write",
    "feedback_resolve",
    "promote_retire",
    "external_tool_write",
    "workarea_write",
    "kb_write",
    "kb_edge_write",
]


@pytest.fixture(autouse=True)
def _clear_whoami_cache() -> None:
    policy_filter._whoami_cache.clear()


def _settings(api_token: str = "w2b_test") -> Settings:
    return Settings(api_base_url="http://test", api_token=api_token, transport="stdio")


def _whoami_payload(
    *,
    unrestricted: bool,
    role: str,
    capabilities: list[str] | None,
    read_scopes: dict[str, str] | None,
    memory_mode: str | None = None,
) -> dict[str, object]:
    return {
        "user_id": str(uuid4()),
        "workspace_id": str(_WORKSPACE_ID),
        "role": role,
        "is_api_token": not unrestricted,
        "agent_id": None if unrestricted else str(uuid4()),
        "unrestricted": unrestricted,
        "capabilities": capabilities,
        "read_scopes": read_scopes,
        "memory_mode": memory_mode,
        "features": ["core"],
    }


def _default_policy_payload() -> dict[str, object]:
    return _whoami_payload(
        unrestricted=False,
        role="editor",
        capabilities=["feedback_write"],
        read_scopes={
            "persona": "all",
            "playbook": "assigned",
            "resource": "assigned",
            "agent": "assigned",
        },
    )


def _install_identity(
    monkeypatch: pytest.MonkeyPatch,
    handler: Callable[[httpx.Request], httpx.Response],
    token: str = "w2b_test",
) -> None:
    """Patcht Settings (stdio-Token) + `server.build_client` auf den Mock.

    Die Middleware loest `whoami` ueber denselben `build_client`-Pfad auf wie
    die Tools selbst — ein Handler bedient beides.
    """
    monkeypatch.setattr(policy_filter, "get_settings", lambda: _settings(api_token=token))
    transport = httpx.MockTransport(handler)

    async def _build() -> ApiClient:
        return ApiClient("http://test", token, _WORKSPACE_ID, transport=transport)

    monkeypatch.setattr(server, "build_client", _build)


def _whoami_handler(payload: dict[str, object]) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/whoami"):
            return httpx.Response(200, json=payload)
        return httpx.Response(404, json={"detail": "nicht gemockt"})

    return handler


def _list_tool_names() -> set[str]:
    async def _run() -> set[str]:
        async with Client(mcp) as client:
            tools = await client.list_tools()
            return {tool.name for tool in tools}

    return asyncio.run(_run())


def _call_tool(name: str, arguments: dict[str, Any]) -> Any:
    async def _run() -> Any:
        async with Client(mcp) as client:
            result = await client.call_tool(name, arguments)
            # `output_schema=None` (server.py) → kein structured content;
            # der Rueckgabewert steht als Text im ersten Content-Block.
            return result.content[0].text if result.content else None

    return asyncio.run(_run())


# --- Filter-Matrix -----------------------------------------------------------


def test_default_policy_agent_sees_exact_consumer_set(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_identity(monkeypatch, _whoami_handler(_default_policy_payload()))
    assert _list_tool_names() == _DEFAULT_POLICY_TOOLS


def test_full_policy_agent_sees_all_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _whoami_payload(
        unrestricted=False,
        role="editor",
        capabilities=_ALL_CAPABILITIES,
        read_scopes={"persona": "all", "playbook": "all", "resource": "all", "agent": "all"},
        memory_mode="auto",
    )
    _install_identity(monkeypatch, _whoami_handler(payload))
    names = _list_tool_names()
    assert names == set(MCP_TOOL_REQUIREMENTS)
    # 58 server.py-Tools + 8 WorkArea-Tools (WP8) + 5 KB-Tools (WP9).
    assert len(names) == 71


def test_resource_read_none_hides_resource_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _whoami_payload(
        unrestricted=False,
        role="editor",
        capabilities=[],
        read_scopes={"persona": "all", "playbook": "all", "resource": "none", "agent": "all"},
    )
    _install_identity(monkeypatch, _whoami_handler(payload))
    names = _list_tool_names()
    assert {"list_resources", "fetch_resource", "list_resource_blocks"} & names == set()
    # Multi-Domain-Discovery bleibt: persona/playbook sind weiterhin lesbar.
    assert {"search", "find_usages", "list_versions", "get_version", "diff_versions"} <= names


def test_memory_mode_gates_memory_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    # ADR-0044: read_only zeigt nur die Lese-Tools; suggest/auto auch save_memory;
    # ohne memory_mode (Bestands-whoami/off) fehlen alle drei.
    scopes = {"persona": "all", "playbook": "all", "resource": "all", "agent": "all"}
    payload = _whoami_payload(
        unrestricted=False,
        role="editor",
        capabilities=[],
        read_scopes=scopes,
        memory_mode="read_only",
    )
    _install_identity(monkeypatch, _whoami_handler(payload))
    names = _list_tool_names()
    assert {"search_memory", "list_memories"} <= names
    assert "save_memory" not in names

    payload_off = _whoami_payload(
        unrestricted=False, role="editor", capabilities=[], read_scopes=scopes
    )
    policy_filter._whoami_cache.clear()  # gleicher Token, neue Identitaet
    _install_identity(monkeypatch, _whoami_handler(payload_off))
    assert {"search_memory", "list_memories", "save_memory"} & _list_tool_names() == set()

    payload_suggest = _whoami_payload(
        unrestricted=False,
        role="editor",
        capabilities=[],
        read_scopes=scopes,
        memory_mode="suggest",
    )
    policy_filter._whoami_cache.clear()
    _install_identity(monkeypatch, _whoami_handler(payload_suggest))
    assert {"search_memory", "list_memories", "save_memory"} <= _list_tool_names()


def test_unrestricted_admin_sees_all_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    # Ausser den Memory-Tools (ADR-0044): ohne Agent-Bindung kein
    # Memory-Namespace — sie bleiben fuer Unrestricted unsichtbar.
    payload = _whoami_payload(unrestricted=True, role="admin", capabilities=None, read_scopes=None)
    _install_identity(monkeypatch, _whoami_handler(payload))
    names = _list_tool_names()
    memory_tools = {name for name, req in MCP_TOOL_REQUIREMENTS.items() if req.memory is not None}
    assert names == set(MCP_TOOL_REQUIREMENTS) - memory_tools
    # 71 Tools minus die 3 Memory-Tools (ohne Agent-Bindung kein Namespace).
    assert len(names) == 68


def test_unrestricted_viewer_sees_no_write_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _whoami_payload(unrestricted=True, role="viewer", capabilities=None, read_scopes=None)
    _install_identity(monkeypatch, _whoami_handler(payload))
    names = _list_tool_names()
    write_tools = {name for name, req in MCP_TOOL_REQUIREMENTS.items() if req.capabilities}
    memory_tools = {name for name, req in MCP_TOOL_REQUIREMENTS.items() if req.memory is not None}
    assert names & write_tools == set()
    # Alle Reads + always-Tools bleiben sichtbar (Rollen-Gate betrifft nur
    # Writes); Memory-Tools fehlen fuer Unrestricted grundsaetzlich (ADR-0044).
    assert names == set(MCP_TOOL_REQUIREMENTS) - write_tools - memory_tools


# --- Drift-Guard -------------------------------------------------------------


def test_registered_tools_match_requirements_mapping() -> None:
    # Ein NEUES Tool in server.py MUSS in MCP_TOOL_REQUIREMENTS eingetragen
    # werden (packages/models/src/who2be_models/tool_requirements.py) — zur
    # Laufzeit bliebe es fail-open sichtbar, aber dieser Test macht das CI-rot.
    tools = asyncio.run(mcp.list_tools(run_middleware=False))
    assert {tool.name for tool in tools} == set(MCP_TOOL_REQUIREMENTS)


# --- Fail-open ----------------------------------------------------------------


def test_whoami_failure_falls_open_to_full_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(policy_filter, "get_settings", lambda: _settings())

    async def _build_raises() -> ApiClient:
        raise RuntimeError("API nicht erreichbar")

    monkeypatch.setattr(server, "build_client", _build_raises)
    names = _list_tool_names()
    assert names == set(MCP_TOOL_REQUIREMENTS)


def test_ping_works_without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    # Kein Token (stdio, leerer WHO2BE_API_TOKEN) → Identity unaufloesbar →
    # fail-open: ping bleibt sichtbar UND aufrufbar (auth-freier Liveness-Pfad).
    monkeypatch.setattr(policy_filter, "get_settings", lambda: _settings(api_token=""))
    assert "ping" in _list_tool_names()
    assert _call_tool("ping", {}) == "pong"


# --- Call-Sperre ---------------------------------------------------------------


def test_call_blocked_for_hidden_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_identity(monkeypatch, _whoami_handler(_default_policy_payload()))
    with pytest.raises(ToolError, match="nicht freigeschaltet"):
        _call_tool("create_playbook", {"data": {"name": "x", "content": {"body": ""}}})


def test_call_allowed_tool_passes_through(monkeypatch: pytest.MonkeyPatch) -> None:
    pid = uuid4()
    seen: dict[str, int] = {"usage": 0}
    payload = _default_policy_payload()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/whoami"):
            return httpx.Response(200, json=payload)
        if request.url.path.endswith("/usage-events"):
            seen["usage"] += 1
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
        return httpx.Response(404, json={"detail": "nicht gemockt"})

    _install_identity(monkeypatch, handler)
    data = _call_tool(
        "record_usage",
        {
            "data": {
                "entity_type": "playbook",
                "entity_id": str(pid),
                "version": 2,
                "outcome": "applied",
            }
        },
    )
    assert seen["usage"] == 1
    assert data is not None


# --- whoami-Cache --------------------------------------------------------------


def test_whoami_resolved_once_per_token(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"whoami": 0}
    payload = _default_policy_payload()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/whoami"):
            calls["whoami"] += 1
            return httpx.Response(200, json=payload)
        return httpx.Response(404, json={"detail": "nicht gemockt"})

    _install_identity(monkeypatch, handler)
    first = _list_tool_names()
    second = _list_tool_names()
    assert first == second == _DEFAULT_POLICY_TOOLS
    assert calls["whoami"] == 1
