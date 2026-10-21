"""Fehler-Tracking API (Stabilitaet A2): ohne DSN aus, mit DSN PII-frei.

Alle Werte sind synthetisch (Weiche W6). Der Test-Transport faengt Events im
Prozess ab, es gibt nie einen echten Netzwerk-Aufruf.
"""

from __future__ import annotations

import json
import socket
from collections.abc import Iterator
from typing import Any

import pytest
import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sentry_sdk.envelope import Envelope
from sentry_sdk.transport import Transport

from who2be_models import error_tracking
from who2be_models.error_tracking import init_error_tracking, scrub_text

# Synthetische Geheimnisse; keines davon darf im Event auftauchen. Der JWT wird
# erst zur Laufzeit zusammengesetzt, damit der Secret-Scan (Gitleaks-Regel jwt)
# keinen Literal-Treffer im Repo findet; der Wert signiert nichts.
TOKEN = "w2b_synthetictoken0123456789abcdef"
JWT = ".".join(("eyJhbGciOiJIUzI1NiJ9", "eyJzdWIiOiJzeW50aGV0aWMifQ", "c2lnbmF0dXJlc3ludGg"))
COOKIE = "sb-session=synthcookievalue42"
EMAIL = "erika.synthetisch@example.org"
BODY = "GEHEIMER-PLAYBOOK-INHALT-synth"
QUERY_CODE = "oauthcodesynth987"
SECRETS = (TOKEN, JWT, "synthcookievalue42", EMAIL, BODY, QUERY_CODE)

SENT: list[dict[str, Any]] = []


class CapturingTransport(Transport):
    """Haelt Events im Speicher fest statt sie zu senden."""

    def capture_envelope(self, envelope: Envelope) -> None:
        for item in envelope.items:
            payload = item.payload.json
            if payload is not None:
                SENT.append(payload)


@pytest.fixture(autouse=True)
def _reset_sentry(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for name in ("SENTRY_DSN", "SENTRY_ENVIRONMENT", "SENTRY_RELEASE"):
        monkeypatch.delenv(name, raising=False)
    SENT.clear()
    yield
    sentry_sdk.get_client().close()
    sentry_sdk.get_global_scope().set_client(None)
    SENT.clear()


def test_without_dsn_no_init_and_no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ohne DSN wird `sentry_sdk.init` nie aufgerufen und kein Socket geoeffnet."""
    init_calls: list[dict[str, Any]] = []
    monkeypatch.setattr(sentry_sdk, "init", lambda **kw: init_calls.append(kw))
    connects: list[object] = []

    def _no_connect(*args: object, **kwargs: object) -> None:
        connects.append(args)
        raise AssertionError("Netzwerk-Aufruf ohne DSN")

    monkeypatch.setattr(socket.socket, "connect", _no_connect)
    monkeypatch.setattr(socket, "create_connection", _no_connect)

    assert init_error_tracking("who2be-api", "0.0.0", environ={"SENTRY_DSN": "  "}) is False
    assert init_error_tracking("who2be-api", "0.0.0") is False
    sentry_sdk.capture_exception(RuntimeError("ohne DSN"))
    sentry_sdk.flush(timeout=0.5)

    assert init_calls == []
    assert connects == []
    assert not sentry_sdk.get_client().is_active()


def test_api_module_import_leaves_sdk_inactive_without_dsn() -> None:
    from who2be_api import main

    assert main.app is not None
    assert not sentry_sdk.get_client().is_active()


def test_with_dsn_sets_safe_options_and_tags() -> None:
    env = {
        "SENTRY_DSN": "https://public@tracker.invalid/1",
        "SENTRY_ENVIRONMENT": "staging",
    }
    assert init_error_tracking("who2be-api", "1.2.3", environ=env, transport=CapturingTransport)
    options = sentry_sdk.get_client().options
    assert sentry_sdk.get_client().should_send_default_pii() is False
    assert options["include_local_variables"] is False
    assert options["max_request_body_size"] == "never"
    assert options["environment"] == "staging"
    assert options["release"] == "who2be-api@1.2.3"
    assert options["traces_sample_rate"] == 0.0


def test_release_override_and_bad_sample_rate() -> None:
    env = {
        "SENTRY_DSN": "https://public@tracker.invalid/1",
        "SENTRY_RELEASE": "who2be@abc123",
        "SENTRY_TRACES_SAMPLE_RATE": "nonsense",
    }
    assert init_error_tracking("who2be-api", "1.2.3", environ=env, transport=CapturingTransport)
    options = sentry_sdk.get_client().options
    assert options["release"] == "who2be@abc123"
    assert options["environment"] == "production"
    assert options["traces_sample_rate"] == 0.0


def test_scrub_text_masks_tokens_jwt_bearer_email() -> None:
    raw = f"t={TOKEN} j={JWT} h=Bearer abc.def-123 m={EMAIL} u=/cb?code={QUERY_CODE}"
    out = scrub_text(raw)
    for secret in (TOKEN, JWT, "abc.def-123", EMAIL, QUERY_CODE):
        assert secret not in out
    assert out.count("[Filtered]") == 5
    assert "/cb" in out


def test_drop_content_keys_removes_mcp_arguments_everywhere() -> None:
    """Die MCPIntegration setzt Argumente ohne PII-Pruefung in die Trace-Daten."""
    event: dict[str, Any] = {
        "contexts": {"trace": {"data": {"mcp.request.argument.x": BODY, "mcp.tool.name": "t"}}},
        "spans": [{"data": {"mcp.tool.result.content": BODY, "gen_ai.prompt": BODY}}],
    }
    out = error_tracking.before_send(event, {})
    assert BODY not in json.dumps(out)
    assert out["contexts"]["trace"]["data"] == {"mcp.tool.name": "t"}


def test_unhandled_request_error_event_is_scrubbed() -> None:
    """Authorization, Cookies, Tokens, E-Mail, Query und Body fehlen im Event."""
    env = {"SENTRY_DSN": "https://public@tracker.invalid/1"}
    assert init_error_tracking("who2be-api", "0.0.0", environ=env, transport=CapturingTransport)

    app = FastAPI()

    @app.post("/boom")
    async def boom(request: Request) -> None:
        payload = await request.json()
        # Fehlermeldung mit Nutzerdaten: before_send muss sie maskieren.
        raise RuntimeError(f"kaputt fuer {payload['email']} mit {TOKEN} und {JWT}")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        f"/boom?code={QUERY_CODE}&token={TOKEN}",
        headers={"Authorization": f"Bearer {JWT}", "Cookie": COOKIE, "X-Api-Key": TOKEN},
        json={"email": EMAIL, "content": BODY, "markdown": BODY},
    )
    assert response.status_code == 500
    sentry_sdk.flush(timeout=2)

    events = [e for e in SENT if e.get("exception")]
    assert events, "kein Fehler-Event erfasst"
    dumped = json.dumps(events)
    for secret in SECRETS:
        assert secret not in dumped, secret
    request = events[0].get("request", {})
    for key in ("headers", "cookies", "data", "query_string"):
        assert key not in request
    assert "user" not in events[0]
    assert "?" not in request.get("url", "")


def test_breadcrumbs_and_extra_are_scrubbed() -> None:
    env = {"SENTRY_DSN": "https://public@tracker.invalid/1"}
    assert init_error_tracking("who2be-api", "0.0.0", environ=env, transport=CapturingTransport)

    sentry_sdk.add_breadcrumb(
        category="httpx",
        message=f"GET mit {TOKEN}",
        data={
            "url": f"https://example.invalid/x?token={TOKEN}",
            "http.query": f"code={QUERY_CODE}",
        },
    )
    with sentry_sdk.new_scope() as scope:
        scope.set_user({"id": "synth-user-42", "username": "synthnutzer"})
        scope.set_extra("payload", {"email": EMAIL, "nested": {"content": BODY}})
        scope.set_extra("note", f"Absender {EMAIL}")
        sentry_sdk.capture_message("synthetischer Fehler")
    sentry_sdk.flush(timeout=2)

    dumped = json.dumps(SENT)
    assert SENT
    for secret in (*SECRETS, "synth-user-42", "synthnutzer"):
        assert secret not in dumped, secret
    assert all("user" not in event for event in SENT)
