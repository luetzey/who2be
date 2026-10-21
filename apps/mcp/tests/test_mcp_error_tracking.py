"""Fehler-Tracking MCP-Server (Stabilitaet A2).

Ohne DSN bleibt das SDK aus. Mit DSN landen Werkzeug-Argumente, Ergebnisse,
Tokens und E-Mail-Adressen nicht im Event. Alle Werte sind synthetisch (W6);
der Test-Transport faengt Events im Prozess ab, ohne Netzwerk.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator
from typing import Any

import pytest
import sentry_sdk
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError
from sentry_sdk.envelope import Envelope
from sentry_sdk.integrations.mcp import MCPIntegration
from sentry_sdk.transport import Transport

from who2be_models.error_tracking import init_error_tracking

TOKEN = "w2b_synthmcptoken0123456789"
EMAIL = "max.synthetisch@example.org"
PROMPT = "PERSONA-INHALT-synthetisch-geheim"
SECRETS = (TOKEN, EMAIL, PROMPT)

SENT: list[dict[str, Any]] = []


class CapturingTransport(Transport):
    def capture_envelope(self, envelope: Envelope) -> None:
        for item in envelope.items:
            payload = item.payload.json
            if payload is not None:
                SENT.append(payload)


@pytest.fixture(autouse=True)
def _reset(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    from who2be_mcp import config

    monkeypatch.delenv("SENTRY_DSN", raising=False)
    config.get_settings.cache_clear()
    SENT.clear()
    yield
    sentry_sdk.get_client().close()
    sentry_sdk.get_global_scope().set_client(None)
    config.get_settings.cache_clear()
    SENT.clear()


def _stub_run(monkeypatch: pytest.MonkeyPatch) -> None:
    from who2be_mcp import server

    monkeypatch.setattr(server.mcp, "run", lambda **_kw: None)
    monkeypatch.setattr(server, "configure_logging", lambda _fmt: None)


def test_main_without_dsn_leaves_sdk_inactive(monkeypatch: pytest.MonkeyPatch) -> None:
    from who2be_mcp import server

    _stub_run(monkeypatch)
    server.main()
    assert not sentry_sdk.get_client().is_active()


def test_main_with_dsn_wires_mcp_integration_without_prompts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from who2be_mcp import server

    _stub_run(monkeypatch)
    calls: list[dict[str, Any]] = []

    def _fake_init(service: str, version: str, **kwargs: Any) -> bool:
        calls.append({"service": service, "version": version, **kwargs})
        return True

    monkeypatch.setattr(server, "init_error_tracking", _fake_init)
    server.main()

    assert len(calls) == 1
    assert calls[0]["service"] == "who2be-mcp"
    integrations = calls[0]["integrations"]
    mcp_integrations = [i for i in integrations if isinstance(i, MCPIntegration)]
    assert len(mcp_integrations) == 1
    assert mcp_integrations[0].include_prompts is False


def test_tool_error_event_has_no_arguments_tokens_or_email() -> None:
    env = {"SENTRY_DSN": "https://public@tracker.invalid/2"}
    assert init_error_tracking(
        "who2be-mcp",
        "0.0.0",
        environ=env,
        transport=CapturingTransport,
        integrations=[MCPIntegration(include_prompts=False)],
    )

    probe = FastMCP("probe")

    @probe.tool
    def explode(api_token: str, email: str, persona_prompt: str) -> str:
        raise RuntimeError(f"Fehler fuer {email} mit {api_token}")

    async def _run() -> None:
        async with Client(probe) as client:
            await client.call_tool(
                "explode", {"api_token": TOKEN, "email": EMAIL, "persona_prompt": PROMPT}
            )

    with pytest.raises(ToolError):
        asyncio.run(_run())
    sentry_sdk.flush(timeout=2)

    events = [e for e in SENT if e.get("exception")]
    assert events, "kein Fehler-Event fuer den Werkzeug-Fehler erfasst"
    assert events[0]["exception"]["values"][-1]["type"] == "RuntimeError"
    dumped = json.dumps(SENT)
    for secret in SECRETS:
        assert secret not in dumped, secret
