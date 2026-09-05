"""Endpoint-Tests fuer den Mollie-Webhook + Checkout (`routers/billing.py`).

Die meisten Pfade brauchen keine DB: On-Prem ⇒ 404 (Mollie nur Cloud), das
optionale Token-Gate sowie die Rollen-/Plan-Validierung greifen ohne DB-Zugriff.
Der Webhook-Service wird ueber `app.dependency_overrides` durch einen Fake ersetzt
(kein echter Mollie-Call).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_mollie_adapter import (  # type: ignore[import-not-found]
    FakeEntitlementRepository,
    FakeMollieGateway,
    FakeProcessedEventRepository,
)

import who2be_billing.router as billing_router
from who2be_api.core.config import get_settings
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.main import create_app
from who2be_billing.mollie import (
    MollieBillingService,
    MolliePayment,
    MollieSubscription,
)
from who2be_billing.plans import PRO_PLAN
from who2be_billing.router import get_mollie_service
from who2be_models import WorkspaceRole


def _admin_ctx() -> WorkspaceContext:
    return WorkspaceContext(
        workspace_id=uuid4(),
        user_id=uuid4(),
        role=WorkspaceRole.admin,
        is_api_token=False,
        aal="aal2",
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


def test_mollie_webhook_replay_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Zwei identische Pings ueber den Endpoint ⇒ nur ein Entitlement-Upsert.

    Der Service (inkl. Dedupe-Ledger) wird als **eine** Instanz ueber alle
    Requests injiziert, damit der Claim ueber Pings hinweg greift.
    """
    monkeypatch.setenv("WHO2BE_EDITION", "cloud")
    monkeypatch.setenv("MOLLIE_API_KEY", "test_dummy")
    get_settings.cache_clear()
    app = create_app()
    org_id = uuid4()
    repo = FakeEntitlementRepository()
    gateway = FakeMollieGateway(
        payment=MolliePayment("tr_1", True, "cst_1", "sub_1", "mdt_1", {}),
        subscription=MollieSubscription("sub_1", "active", dict(PRO_PLAN.metadata(org_id))),
    )
    service = MollieBillingService(gateway, repo, FakeProcessedEventRepository())
    app.dependency_overrides[get_mollie_service] = lambda: service
    try:
        with TestClient(app) as client:
            first = client.post("/v1/billing/mollie/webhook", data={"id": "tr_1"})
            second = client.post("/v1/billing/mollie/webhook", data={"id": "tr_1"})
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()
    assert first.json() == {"received": True}
    assert second.json() == {"received": False}
    assert len(repo.calls) == 1


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


class _CheckoutPool:
    """Minimaler `asyncpg.Pool`-Stub fuer `resolve_org_id` + `_fetch_billing_identity`.

    `create_checkout` holt den Pool per `get_pool()` direkt (keine FastAPI-
    Dependency, siehe `router.py:249`) — `app.dependency_overrides` greift hier
    also nicht; stattdessen wird `billing_router.get_pool` gepatcht (AC3).
    """

    def __init__(self, *, workspace_id: UUID, org_id: UUID, org_name: str) -> None:
        self._workspace_id = workspace_id
        self._org_id = org_id
        self._org_name = org_name

    async def fetchval(self, query: str, *args: Any) -> Any:
        normalized = " ".join(query.split())
        if "FROM workspace WHERE id" in normalized:
            assert args[0] == self._workspace_id
            return self._org_id
        if "FROM organization WHERE id" in normalized:
            return self._org_name
        if "FROM auth.users WHERE id" in normalized:
            return None  # Email ist fuer Mollie optional (siehe router.py:143).
        raise AssertionError(f"_CheckoutPool.fetchval: unerwartete Query: {query!r}")


def test_checkout_success_returns_201_with_mollie_metadata(
    cloud_app: tuple[FastAPI, FakeMollieGateway],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Checkout-Erfolgspfad einmal ueber HTTP (AC3): 201 + die an Mollie
    uebergebene Metadata (Vorlage: `test_start_checkout_creates_customer_and_payment`
    in `test_mollie_adapter.py`, dort nur am Service, nicht ueber den Endpoint)."""
    app, gateway = cloud_app
    workspace_id = uuid4()
    org_id = uuid4()
    admin_ctx = WorkspaceContext(
        workspace_id=workspace_id,
        user_id=uuid4(),
        role=WorkspaceRole.admin,
        is_api_token=False,
        aal="aal2",
    )
    app.dependency_overrides[get_current_workspace] = lambda: admin_ctx
    monkeypatch.setattr(
        billing_router,
        "get_pool",
        lambda: _CheckoutPool(workspace_id=workspace_id, org_id=org_id, org_name="Acme GmbH"),
    )
    with TestClient(app) as client:
        resp = client.post(
            f"/v1/workspaces/{workspace_id}/billing/checkout",
            json={"plan": "pro"},
            headers={"Authorization": "Bearer w2b_dummy"},
        )
    assert resp.status_code == 201
    assert resp.json() == {"checkout_url": gateway.checkout_url}
    # Metadata, die tatsaechlich an das (Fake-)Mollie-Gateway ging.
    assert gateway.created_customer_metadata["org_id"] == str(org_id)
    assert gateway.first_payment_metadata["org_id"] == str(org_id)
    assert gateway.first_payment_metadata["plan_code"] == "pro"
    assert gateway.first_payment_metadata["license_policy"] == " ".join(sorted(PRO_PLAN.features))
    assert gateway.first_payment_metadata["mcp_monthly_quota"] == str(PRO_PLAN.mcp_monthly_quota)


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
