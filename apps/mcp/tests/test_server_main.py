"""Tests fuer die `main()`-Dispatch-Logik des MCP-Servers (ADR-0034)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    """`get_settings()` ist `lru_cache`d — pro Test resetten, sonst leakt Env."""
    from who2be_mcp import config

    config.get_settings.cache_clear()
    yield
    config.get_settings.cache_clear()


def test_main_defaults_to_stdio_when_transport_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ohne `WHO2BE_TRANSPORT` (oder mit `stdio`) ruft `main()` `mcp.run()`
    ohne Transport-Kwargs auf — das ist der FastMCP-Stdio-Default."""
    monkeypatch.delenv("WHO2BE_TRANSPORT", raising=False)

    from who2be_mcp import server

    run_calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        server.mcp,
        "run",
        MagicMock(side_effect=lambda **kw: run_calls.append(kw)),
    )
    monkeypatch.setattr(server, "configure_logging", lambda _fmt: None)

    server.main()

    assert run_calls == [{}]


def test_main_uses_http_transport_when_env_says_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mit `WHO2BE_TRANSPORT=http` ruft `main()` `mcp.run(transport='http', ...)`
    mit Host/Port/Path aus den Settings auf."""
    monkeypatch.setenv("WHO2BE_TRANSPORT", "http")
    monkeypatch.setenv("WHO2BE_HTTP_HOST", "1.2.3.4")
    monkeypatch.setenv("WHO2BE_HTTP_PORT", "9999")
    monkeypatch.setenv("WHO2BE_HTTP_PATH", "/custom-mcp")

    from who2be_mcp import server

    run_calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        server.mcp,
        "run",
        MagicMock(side_effect=lambda **kw: run_calls.append(kw)),
    )
    monkeypatch.setattr(server, "configure_logging", lambda _fmt: None)

    server.main()

    assert run_calls == [
        {
            "transport": "http",
            "host": "1.2.3.4",
            "port": 9999,
            "path": "/custom-mcp",
        }
    ]


def test_settings_default_transport_is_stdio() -> None:
    """Settings-Default sichert die Migration: bestehende Deployments ohne
    `WHO2BE_TRANSPORT` bleiben auf stdio."""
    from who2be_mcp.config import Settings

    settings = Settings()
    assert settings.transport == "stdio"
    assert settings.http_host == "0.0.0.0"
    assert settings.http_port == 8765
    assert settings.http_path == "/mcp"
