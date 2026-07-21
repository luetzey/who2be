"""Endpoint-Tests fuer den Cloud-Manual-Override (`who2be_billing/router.py`).

Geprueft werden die DB-freien Pfade: On-Prem ⇒ 404 (Billing-Paket nicht
registriert), Nicht-Admin ⇒ 403, unbekannter Plan ⇒ 422 und die Pflicht-Befristung
(`days`) + Pflicht-`reason` ⇒ 422 (Pydantic).

**Bewusste Erwartungs-Aenderung (LIC-1, Standards-Review 2026-07-20):** Die
fruehere Erwartung „Workspace-Admin reicht" ist falsch — ADR-0028 definiert den
`manual_override`-Writer als **Cloud-OPS-Override**, nicht als Kunden-Self-Service.
Ein Workspace-Admin (Kunden-Kontext) ohne Eintrag in der Operator-Allowlist
(`WHO2BE_BILLING_OVERRIDE_OPERATORS`) bekommt jetzt 403; leere Allowlist ⇒ immer
403 (fail-closed). Der Erfolgs-Pfad wird hier DB-frei ueber gefakte Pool-/Repo-/
Org-Resolver-Objekte verifiziert.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from who2be_api.core.config import get_settings
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.main import create_app
from who2be_models import WorkspaceRole

_OPERATORS_ENV = "WHO2BE_BILLING_OVERRIDE_OPERATORS"

# Fester Operator-User fuer die Allowlist-Tests (deterministisch, keine Kollision
# mit den per `uuid4()` erzeugten Nicht-Operator-Kontexten).
OPERATOR_ID = UUID("00000000-0000-4000-8000-000000000001")


def _ctx(
    role: WorkspaceRole = WorkspaceRole.admin,
    *,
    user_id: UUID | None = None,
    aal: str | None = "aal2",
    is_api_token: bool = False,
) -> WorkspaceContext:
    return WorkspaceContext(
        workspace_id=uuid4(),
        user_id=user_id if user_id is not None else uuid4(),
        role=role,
        is_api_token=is_api_token,
        aal=aal,
    )


@pytest.fixture
def cloud_app(monkeypatch: pytest.MonkeyPatch) -> Iterator[FastAPI]:
    monkeypatch.setenv("WHO2BE_EDITION", "cloud")
    # Default fuer jeden Test: leere Allowlist — einzelne Tests setzen sie explizit.
    monkeypatch.delenv(_OPERATORS_ENV, raising=False)
    get_settings.cache_clear()
    app = create_app()
    yield app
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def _post(app: FastAPI, body: dict[str, object]) -> httpx.Response:
    with TestClient(app) as client:
        resp: httpx.Response = client.post(
            f"/v1/workspaces/{uuid4()}/billing/override",
            json=body,
            headers={"Authorization": "Bearer w2b_dummy"},
        )
    return resp


_VALID_BODY: dict[str, object] = {"plan": "pro", "days": 30, "reason": "Kulanz"}


def test_override_rejects_non_admin(cloud_app: FastAPI) -> None:
    cloud_app.dependency_overrides[get_current_workspace] = lambda: _ctx(WorkspaceRole.viewer)
    assert _post(cloud_app, _VALID_BODY).status_code == 403


def test_override_rejects_admin_not_in_allowlist(
    cloud_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """LIC-1-Repro: Workspace-Admin (Kunden-Kontext) darf sich KEIN Entitlement
    schreiben — `manual_override` ist Betreiber-only (ADR-0028). Die Allowlist
    enthaelt einen anderen User, der Admin faellt durch."""
    monkeypatch.setenv(_OPERATORS_ENV, str(OPERATOR_ID))
    cloud_app.dependency_overrides[get_current_workspace] = lambda: _ctx()
    resp = _post(cloud_app, _VALID_BODY)
    assert resp.status_code == 403
    assert "ADR-0028" in resp.json()["detail"]


def test_override_rejects_everyone_on_empty_allowlist(cloud_app: FastAPI) -> None:
    """Leere/fehlende Allowlist ⇒ immer 403 (fail-closed, ADR-0028)."""
    cloud_app.dependency_overrides[get_current_workspace] = lambda: _ctx()
    assert _post(cloud_app, _VALID_BODY).status_code == 403


def test_override_rejects_operator_without_aal2(
    cloud_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auch der gelistete Operator braucht eine MFA-Session (`require_aal2`)."""
    monkeypatch.setenv(_OPERATORS_ENV, str(OPERATOR_ID))
    cloud_app.dependency_overrides[get_current_workspace] = lambda: _ctx(
        user_id=OPERATOR_ID, aal="aal1"
    )
    assert _post(cloud_app, _VALID_BODY).status_code == 403


def test_override_rejects_api_token_caller(
    cloud_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Maschinen-Tokens sind kategorisch ausgeschlossen — `require_aal2`
    exempted API-Tokens, der Betreiber-Pfad hat aber keinen legitimen
    Maschinen-Aufrufer (ADR-0028)."""
    monkeypatch.setenv(_OPERATORS_ENV, str(OPERATOR_ID))
    cloud_app.dependency_overrides[get_current_workspace] = lambda: _ctx(
        user_id=OPERATOR_ID, aal=None, is_api_token=True
    )
    assert _post(cloud_app, _VALID_BODY).status_code == 403


def test_override_ignores_unparsable_allowlist_entries(
    cloud_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unparsbare Eintraege oeffnen die Liste nicht (fail-closed)."""
    monkeypatch.setenv(_OPERATORS_ENV, "not-a-uuid, ,also-broken")
    cloud_app.dependency_overrides[get_current_workspace] = lambda: _ctx()
    assert _post(cloud_app, _VALID_BODY).status_code == 403


def test_override_rejects_unknown_plan(cloud_app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(_OPERATORS_ENV, str(OPERATOR_ID))
    cloud_app.dependency_overrides[get_current_workspace] = lambda: _ctx(user_id=OPERATOR_ID)
    body = {"plan": "unobtanium", "days": 30, "reason": "Kulanz"}
    assert _post(cloud_app, body).status_code == 422


def test_override_requires_bounded_duration(cloud_app: FastAPI) -> None:
    cloud_app.dependency_overrides[get_current_workspace] = lambda: _ctx()
    # days=0 (nicht > 0) und days=999 (> 365) sind beide unzulaessig (Pydantic,
    # greift vor dem Operator-Gate).
    assert _post(cloud_app, {"plan": "pro", "days": 0, "reason": "x"}).status_code == 422
    assert _post(cloud_app, {"plan": "pro", "days": 999, "reason": "Kulanz"}).status_code == 422


def test_override_requires_reason(cloud_app: FastAPI) -> None:
    cloud_app.dependency_overrides[get_current_workspace] = lambda: _ctx()
    assert _post(cloud_app, {"plan": "pro", "days": 30}).status_code == 422


class _FakeEntitlementRepo:
    """Zeichnet den Upsert auf, damit der Erfolgs-Pfad DB-frei pruefbar ist."""

    calls: list[dict[str, Any]] = []

    def __init__(self, pool: object) -> None:
        self._pool = pool

    async def upsert(self, org_id: UUID, entitlement: object, **kwargs: Any) -> None:
        _FakeEntitlementRepo.calls.append({"org_id": org_id, **kwargs})


def test_override_succeeds_for_listed_operator_with_aal2(
    cloud_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Operator in der Allowlist + aal2 ⇒ weiterhin 201 (ADR-0028-konformer
    Betreiber-Pfad). DB-Kontakt ist ueber Fakes ersetzt."""
    monkeypatch.setenv(_OPERATORS_ENV, f" {OPERATOR_ID} ,{uuid4()}")
    cloud_app.dependency_overrides[get_current_workspace] = lambda: _ctx(user_id=OPERATOR_ID)

    org_id = uuid4()

    async def _fake_resolve_org_id(pool: object, workspace_id: UUID) -> UUID:
        return org_id

    _FakeEntitlementRepo.calls = []
    monkeypatch.setattr("who2be_billing.router.get_pool", lambda: object())
    monkeypatch.setattr("who2be_billing.router.resolve_org_id", _fake_resolve_org_id)
    monkeypatch.setattr("who2be_billing.router.PgEntitlementRepository", _FakeEntitlementRepo)

    resp = _post(cloud_app, _VALID_BODY)
    assert resp.status_code == 201
    assert resp.json()["plan"] == "pro"
    assert len(_FakeEntitlementRepo.calls) == 1
    call = _FakeEntitlementRepo.calls[0]
    assert call["org_id"] == org_id
    assert call["source"] == "manual_override"
    assert call["created_by"] == OPERATOR_ID


def test_override_404_on_onprem(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WHO2BE_EDITION", "onprem")
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_current_workspace] = lambda: _ctx()
    try:
        status_code = _post(app, dict(_VALID_BODY)).status_code
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()
    # On-Prem ist das Billing-Paket nicht registriert ⇒ Route existiert nicht.
    assert status_code == 404
