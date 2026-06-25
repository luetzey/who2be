"""Tests fuer die strukturierte API-Fehler-Taxonomie (WP-2 / #254).

Zwei Ebenen, beide ohne DB:

1. **Gate-Unit-Tests** — rufen die zentralen Gates direkt auf und pruefen, dass
   sie `ApiGateError` mit dem gezurrten `(status, reason, actionable_by)`-Tupel
   werfen (D1/D3). Je ein Fall pro reason/actionable_by-Kategorie.
2. **Handler-Test** — registriert `_on_api_gate_error` auf einer Minimal-App und
   verifiziert das `application/problem+json`-Shape (RFC 7807 + Who2Be-Felder)
   inkl. Statuscode und `request_id`-Mirror aus `X-Request-ID`.
"""

from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from who2be_api.core.errors import ApiGateError
from who2be_api.core.middleware import RequestIDMiddleware
from who2be_api.core.security import (
    WorkspaceContext,
    require_aal2,
    require_capability,
    require_role,
)
from who2be_api.main import _on_api_gate_error
from who2be_api.services.version_status import (
    _forbidden_transition,
    _invariant_violation,
    _require_transition_capability,
)
from who2be_models import AgentCapability, AgentToolPolicy, VersionStatus, WorkspaceRole


def _ctx(
    role: WorkspaceRole = WorkspaceRole.editor,
    *,
    aal: str | None = None,
    is_api_token: bool = False,
    tool_policy: AgentToolPolicy | None = None,
) -> WorkspaceContext:
    return WorkspaceContext(
        workspace_id=uuid4(),
        user_id=uuid4(),
        role=role,
        is_api_token=is_api_token,
        aal=aal,
        tool_policy=tool_policy,
    )


# --- Gate-Unit-Tests: ein Fall je reason/actionable_by-Kategorie ------------


def test_require_capability_missing_capability_human() -> None:
    ctx = _ctx(tool_policy=AgentToolPolicy())
    with pytest.raises(ApiGateError) as exc:
        require_capability(ctx, AgentCapability.playbook_write)
    assert exc.value.status == 403
    assert exc.value.reason == "missing_capability"
    assert exc.value.actionable_by == "human"


def test_require_role_insufficient_role_human() -> None:
    with pytest.raises(ApiGateError) as exc:
        require_role(_ctx(WorkspaceRole.editor, aal="aal2"), WorkspaceRole.admin)
    assert exc.value.status == 403
    assert exc.value.reason == "insufficient_role"
    assert exc.value.actionable_by == "human"
    assert "Rolle" in exc.value.detail


def test_require_aal2_mfa_required_human() -> None:
    with pytest.raises(ApiGateError) as exc:
        require_aal2(_ctx(WorkspaceRole.admin, aal="aal1"))
    assert exc.value.status == 403
    assert exc.value.reason == "mfa_required"
    assert exc.value.actionable_by == "human"
    assert "MFA" in exc.value.detail


def test_forbidden_transition_none() -> None:
    err = _forbidden_transition(VersionStatus.draft, VersionStatus.active)
    assert err.status == 409
    assert err.reason == "forbidden_transition"
    assert err.actionable_by == "none"


def test_invariant_violation_concurrent_conflict_agent() -> None:
    err = _invariant_violation()
    assert err.status == 409
    assert err.reason == "concurrent_conflict"
    assert err.actionable_by == "agent"


def test_template_lock_missing_capability_none() -> None:
    # Agent-gebundener Token darf System-Prompt-Templates nicht transitionieren.
    ctx = _ctx(tool_policy=AgentToolPolicy())
    with pytest.raises(ApiGateError) as exc:
        _require_transition_capability(ctx, "system_prompt_template", VersionStatus.review)
    assert exc.value.status == 403
    assert exc.value.reason == "missing_capability"
    assert exc.value.actionable_by == "none"


# --- Handler-Test: problem+json-Shape ---------------------------------------


def test_handler_emits_problem_json_with_request_id() -> None:
    app = FastAPI()
    app.add_exception_handler(ApiGateError, _on_api_gate_error)
    app.add_middleware(RequestIDMiddleware)

    @app.get("/boom")
    def boom() -> None:
        raise ApiGateError(
            status=403,
            reason="insufficient_role",
            actionable_by="human",
            detail="Diese Aktion erfordert mindestens die Rolle 'admin'.",
        )

    with TestClient(app) as client:
        resp = client.get("/boom", headers={"X-Request-ID": "req-test-123"})

    assert resp.status_code == 403
    assert resp.headers["content-type"].startswith("application/problem+json")
    body = resp.json()
    assert body["status"] == 403
    assert body["reason"] == "insufficient_role"
    assert body["actionable_by"] == "human"
    assert body["detail"] == "Diese Aktion erfordert mindestens die Rolle 'admin'."
    # type/title werden zentral gesetzt:
    assert body["type"].startswith("https://who2be.dev/errors/")
    assert isinstance(body["title"], str) and body["title"]
    # request_id wird aus X-Request-ID gespiegelt:
    assert body["request_id"] == "req-test-123"


def test_handler_request_id_none_without_header() -> None:
    # Ohne gebundene Request-ID (kein Middleware) ist request_id null.
    app = FastAPI()
    app.add_exception_handler(ApiGateError, _on_api_gate_error)

    @app.get("/boom")
    def boom() -> None:
        raise ApiGateError(
            status=409,
            reason="concurrent_conflict",
            actionable_by="agent",
            detail="Konfliktierende Status-Aenderung (parallele Transition).",
        )

    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/boom")

    assert resp.status_code == 409
    body = resp.json()
    assert body["reason"] == "concurrent_conflict"
    assert body["request_id"] is None
