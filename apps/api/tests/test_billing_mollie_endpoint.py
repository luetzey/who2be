"""Endpoint-Tests fuer den Mollie-Webhook + Checkout (`routers/billing.py`).

Die meisten Pfade brauchen keine DB: On-Prem ⇒ 404 (Mollie nur Cloud), das
optionale Token-Gate sowie die Rollen-/Plan-Validierung greifen ohne DB-Zugriff.
Der Webhook-Service wird ueber `app.dependency_overrides` durch einen Fake ersetzt
(kein echter Mollie-Call).
"""

from __future__ import annotations

from collections.abc import Iterator
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_licensing_mollie_adapter import (  # type: ignore[import-not-found]
    FakeEntitlementRepository,
    FakeMollieGateway,
)

from who2be_api.core.config import get_settings
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.licensing.adapters.mollie import MollieBillingService
from who2be_api.main import create_app
from who2be_api.routers.billing import get_mollie_service
from who2be_models import WorkspaceRole


def _admin_ctx() -> WorkspaceContext:
    return WorkspaceContext(
        workspace_id=uuid4(),
        user_id=uuid4(),
        role=WorkspaceRole.admin,
        is_api_token=False,
    )


def _viewer_ctx() -> WorkspaceContext:
    return WorkspaceContext(
        workspace_id=uuid4(),
        user_id=uuid4(),
        role=WorkspaceRole.viewer,
        is_api_token=False,
    )


@pytest.fixture
def cloud_app(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[FastAPI, FakeMollieGateway]]:
    monkeypatch.setenv("WHO2BE_EDITION", "cloud")
    monkeypatch.setenv("MOLLIE_API_KEY", "test_dummy")
    get_settings.cache_clear()
    app = create_app()
    gateway = FakeMollieGateway()
    repo = FakeEntitlementRepository()
    app.dependency_overrides[get_mollie_service] = lambda: MollieBillingService(gateway, repo)
    yield app, gateway
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def test_mollie_webhook_404_on_onprem(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WHO2BE_EDITION", "onprem")
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            resp = client.post("/v1/billing/mollie/webhook", data={"id": "tr_1"})
    finally:
        get_settings.cache_clear()
    assert resp.status_code == 404


def test_mollie_webhook_requires_form_id(cloud_app: tuple[FastAPI, FakeMollieGateway]) -> None:
    app, _ = cloud_app
    with TestClient(app) as client:
        resp = client.post("/v1/billing/mollie/webhook", data={})
    # Fehlendes Pflicht-Form-Feld ⇒ 422 (FastAPI-Validierung).
    assert resp.status_code == 422


def test_mollie_webhook_unknown_payment_acknowledged(
    cloud_app: tuple[FastAPI, FakeMollieGateway],
) -> None:
    app, gateway = cloud_app
    gateway.payment = None  # Pull liefert nichts
    with TestClient(app) as client:
        resp = client.post("/v1/billing/mollie/webhook", data={"id": "tr_missing"})
    assert resp.status_code == 200
    assert resp.json() == {"received": False}


def test_mollie_webhook_token_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WHO2BE_EDITION", "cloud")
    monkeypatch.setenv("MOLLIE_API_KEY", "test_dummy")
    monkeypatch.setenv("MOLLIE_WEBHOOK_SECRET", "s3cret")
    get_settings.cache_clear()
    app = create_app()
    gateway = FakeMollieGateway()
    app.dependency_overrides[get_mollie_service] = lambda: MollieBillingService(
        gateway, FakeEntitlementRepository()
    )
    try:
        with TestClient(app) as client:
            bad = client.post("/v1/billing/mollie/webhook?token=wrong", data={"id": "tr_1"})
            good = client.post("/v1/billing/mollie/webhook?token=s3cret", data={"id": "tr_1"})
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()
    assert bad.status_code == 403
    assert good.status_code == 200


def test_checkout_rejects_non_admin(cloud_app: tuple[FastAPI, FakeMollieGateway]) -> None:
    app, _ = cloud_app
    app.dependency_overrides[get_current_workspace] = _viewer_ctx
    with TestClient(app) as client:
        resp = client.post(
            f"/v1/workspaces/{uuid4()}/billing/checkout",
            json={"plan": "pro"},
            headers={"Authorization": "Bearer w2b_dummy"},
        )
    assert resp.status_code == 403


def test_checkout_rejects_unknown_plan(cloud_app: tuple[FastAPI, FakeMollieGateway]) -> None:
    app, _ = cloud_app
    app.dependency_overrides[get_current_workspace] = _admin_ctx
    with TestClient(app) as client:
        resp = client.post(
            f"/v1/workspaces/{uuid4()}/billing/checkout",
            json={"plan": "enterprise"},
            headers={"Authorization": "Bearer w2b_dummy"},
        )
    assert resp.status_code == 422


def test_checkout_404_on_onprem(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WHO2BE_EDITION", "onprem")
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_current_workspace] = _admin_ctx
    try:
        with TestClient(app) as client:
            resp = client.post(
                f"/v1/workspaces/{uuid4()}/billing/checkout",
                json={"plan": "pro"},
                headers={"Authorization": "Bearer w2b_dummy"},
            )
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()
    assert resp.status_code == 404
