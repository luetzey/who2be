"""Tests fuer die Per-Request-Token-Aufloesung (ADR-0034 Multi-Tenant).

HTTP-Transport: der eingehende `Authorization: Bearer`-Header bestimmt den
Token (jede Session ihr eigener, serverseitig gescopter Agent) — fehlt er, wird
hart abgelehnt (kein Rueckfall auf den Env-Token). stdio: der statische
`WHO2BE_API_TOKEN`. Die Workspace-Resolution wird pro Token (gehasht) gecacht.

Der Fake fuer `get_http_headers` spiegelt die echte FastMCP-Semantik: `authorization`
wird nur zurueckgegeben, wenn es explizit via `include` angefordert wird (sonst
gefiltert). Damit faellt ein Regress auf, der das `include` weglaesst.
"""

import asyncio
import time
from collections.abc import Callable, Iterable
from uuid import UUID, uuid4

import pytest
from fastmcp.exceptions import ToolError

from who2be_mcp import server
from who2be_mcp.config import Settings


def _settings(
    api_token: str = "w2b_env",
    workspace_id: str = "",
    transport: str = "http",
) -> Settings:
    return Settings(
        api_base_url="http://api.test",
        api_token=api_token,
        workspace_id=workspace_id,
        transport=transport,  # type: ignore[arg-type]
    )


def _headers_fake(raw: dict[str, str]) -> Callable[..., dict[str, str]]:
    """Spiegelt FastMCP `get_http_headers`: `authorization` nur bei `include`."""

    def _fake(include_all: bool = False, include: Iterable[str] | None = None) -> dict[str, str]:
        if include_all:
            return dict(raw)
        result = {k: v for k, v in raw.items() if k != "authorization"}
        for name in include or ():
            if name in raw:
                result[name] = raw[name]
        return result

    return _fake


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    server._workspace_cache.clear()


# --- _request_token --------------------------------------------------------


def test_http_uses_incoming_bearer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        server, "get_http_headers", _headers_fake({"authorization": "Bearer w2b_caller"})
    )
    assert server._request_token(_settings(transport="http")) == "w2b_caller"


def test_http_rejects_missing_bearer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "get_http_headers", _headers_fake({}))
    with pytest.raises(ToolError):
        server._request_token(_settings(transport="http"))


def test_http_rejects_non_bearer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "get_http_headers", _headers_fake({"authorization": "Basic abc"}))
    with pytest.raises(ToolError):
        server._request_token(_settings(transport="http"))


def test_http_rejects_empty_bearer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "get_http_headers", _headers_fake({"authorization": "Bearer   "}))
    with pytest.raises(ToolError):
        server._request_token(_settings(transport="http"))


def test_stdio_uses_env_token(monkeypatch: pytest.MonkeyPatch) -> None:
    # stdio konsultiert die Header gar nicht — Env-Token gilt.
    monkeypatch.setattr(server, "get_http_headers", _headers_fake({"authorization": "Bearer x"}))
    assert server._request_token(_settings(api_token="w2b_env", transport="stdio")) == "w2b_env"


# --- Workspace-Cache -------------------------------------------------------


def test_resolve_honours_explicit_pin() -> None:
    ws = uuid4()
    resolved = asyncio.run(
        server._resolve_workspace_id(_settings(workspace_id=str(ws)), "w2b_x")
    )
    assert resolved == ws


def test_cache_hit_avoids_resolution() -> None:
    ws = uuid4()
    server._ws_cache_put("w2b_cached", ws)
    resolved = asyncio.run(server._resolve_workspace_id(_settings(), "w2b_cached"))
    assert resolved == ws


def test_cache_evicts_oldest_over_max(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "_WS_CACHE_MAX", 2)
    server._ws_cache_put("a", uuid4())
    server._ws_cache_put("b", uuid4())
    server._ws_cache_put("c", uuid4())  # verdraengt "a"
    assert server._ws_cache_get("a") is None
    assert server._ws_cache_get("c") is not None


def test_cache_respects_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = {"t": 1000.0}
    # `time` ist ein Singleton-Modul — server.py sieht den Patch.
    monkeypatch.setattr(time, "monotonic", lambda: clock["t"])
    server._ws_cache_put("a", uuid4())
    clock["t"] += server._WS_CACHE_TTL_SECONDS + 1
    assert server._ws_cache_get("a") is None


# --- build_client ----------------------------------------------------------


def test_build_client_uses_request_token(monkeypatch: pytest.MonkeyPatch) -> None:
    ws = uuid4()
    monkeypatch.setattr(server, "get_settings", lambda: _settings(transport="http"))
    monkeypatch.setattr(
        server, "get_http_headers", _headers_fake({"authorization": "Bearer w2b_caller"})
    )

    async def _fake_resolve(_settings: Settings, _token: str) -> UUID:
        return ws

    monkeypatch.setattr(server, "_resolve_workspace_id", _fake_resolve)
    client = asyncio.run(server.build_client())
    assert client._headers["Authorization"] == "Bearer w2b_caller"


def test_build_client_stdio_empty_token_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "get_settings", lambda: _settings(api_token="", transport="stdio"))
    with pytest.raises(ToolError):
        asyncio.run(server.build_client())
