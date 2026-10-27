"""Endpoint-Tests fuer den Mollie-Webhook + Checkout (`routers/billing.py`).

Die meisten Pfade brauchen keine DB: On-Prem ⇒ 404 (Mollie nur Cloud), das
optionale Token-Gate sowie die Rollen-/Plan-Validierung greifen ohne DB-Zugriff.
Der Webhook-Service wird ueber `app.dependency_overrides` durch einen Fake ersetzt
(kein echter Mollie-Call).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
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
from who2be_billing.billing_profile import BillingProfile
from who2be_billing.mollie import (
    CheckoutPricing,
    MollieBillingService,
    MolliePayment,
    MollieSubscription,
)
from who2be_billing.plans import PRO_PLAN
from who2be_billing.router import get_mollie_service
from who2be_billing.tax import PriceBasis, TaxMode, VatStatus
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


# --- Checkout-Betrag je Steuerfall + 409/503 (ADR-0061 §5, §6; R2c) ---------------
#
# Nur Platzhalter: keine echten Adressen, keine echten USt-IdNr. (oeffentliches Repo).


@dataclass
class _AmountGateway:
    """Fake-Gateway, das Betraege und Customer-Anlagen mitschreibt.

    Eigenstaendig statt von `FakeMollieGateway` abgeleitet: dessen Import ist
    fuer mypy `Any`, eine Unterklasse verloere damit jede Typpruefung.
    """

    payment: MolliePayment | None = None
    checkout_url: str = "https://www.mollie.com/checkout/fake"
    customer_count: int = 0
    first_payment_amounts: list[str] = field(default_factory=list)
    subscription_amounts: list[str] = field(default_factory=list)

    async def create_customer(
        self, *, name: str, email: str | None, metadata: dict[str, str]
    ) -> str:
        self.customer_count += 1
        return "cst_fake"

    async def create_first_payment(self, *, amount_eur: str, **_: Any) -> str:
        self.first_payment_amounts.append(amount_eur)
        return self.checkout_url

    async def get_payment(self, payment_id: str) -> MolliePayment | None:
        return self.payment

    async def create_subscription(self, *, amount_eur: str, **_: Any) -> str:
        self.subscription_amounts.append(amount_eur)
        return "sub_new"

    async def get_subscription(
        self, customer_id: str, subscription_id: str
    ) -> MollieSubscription | None:
        return None


@dataclass
class _FakeProfiles:
    """Rechnungsdaten einer Org im Speicher, mit Protokoll der VIES-Rueckschreibungen."""

    profile: BillingProfile | None
    vat_updates: list[tuple[UUID, str, VatStatus]] = field(default_factory=list)

    async def get(self, org_id: UUID) -> BillingProfile | None:
        return self.profile

    async def update_vat_status(
        self, org_id: UUID, vat_id: str, status: VatStatus, checked_at: datetime
    ) -> None:
        self.vat_updates.append((org_id, vat_id, status))


@dataclass
class _FakeVies:
    status: VatStatus = "unchecked"
    calls: int = 0

    async def check(self, vat_id: str) -> VatStatus:
        self.calls += 1
        return self.status


def _profile(
    country: str,
    customer_type: str,
    *,
    vat_id: str | None = None,
    vat_status: VatStatus | None = None,
) -> BillingProfile:
    names: dict[str, Any] = (
        {"given_name": "Erika", "family_name": "Beispiel"}
        if customer_type == "consumer"
        else {"company_name": "Beispiel GmbH"}
    )
    return BillingProfile(
        customer_type=customer_type,  # type: ignore[arg-type]
        street="Musterstrasse 1",
        postal_code="12345",
        city="Musterstadt",
        country=country,
        vat_id=vat_id,
        vat_status=vat_status,
        **names,
    )


def _post_checkout(
    monkeypatch: pytest.MonkeyPatch,
    service: MollieBillingService | None,
) -> Any:
    """Checkout ueber HTTP; `service=None` nutzt die echte `get_mollie_service`."""
    workspace_id = uuid4()
    app = create_app()
    if service is not None:
        app.dependency_overrides[get_mollie_service] = lambda: service
    app.dependency_overrides[get_current_workspace] = lambda: WorkspaceContext(
        workspace_id=workspace_id,
        user_id=uuid4(),
        role=WorkspaceRole.admin,
        is_api_token=False,
        aal="aal2",
    )
    monkeypatch.setattr(
        billing_router,
        "get_pool",
        lambda: _CheckoutPool(workspace_id=workspace_id, org_id=uuid4(), org_name="Beispiel"),
    )
    try:
        with TestClient(app) as client:
            return client.post(
                f"/v1/workspaces/{workspace_id}/billing/checkout",
                json={"plan": "pro"},
                headers={"Authorization": "Bearer w2b_dummy"},
            )
    finally:
        app.dependency_overrides.clear()


def _priced_service(
    profiles: _FakeProfiles,
    *,
    tax_mode: TaxMode | None = "regular",
    price_basis: PriceBasis = "net",
    vies: _FakeVies | None = None,
) -> tuple[MollieBillingService, _AmountGateway]:
    gateway = _AmountGateway()
    pricing = CheckoutPricing(
        profiles, vies or _FakeVies(), tax_mode=tax_mode, price_basis=price_basis
    )
    service = MollieBillingService(gateway, FakeEntitlementRepository(), pricing=pricing)
    return service, gateway


@pytest.fixture
def cloud_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("WHO2BE_EDITION", "cloud")
    monkeypatch.setenv("MOLLIE_API_KEY", "test_dummy")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.usefixtures("cloud_env")
@pytest.mark.parametrize(
    ("case", "profile", "vies_status", "expected"),
    [
        ("DE B2C", _profile("DE", "consumer"), "unchecked", "11.89"),
        ("DE B2B", _profile("DE", "business", vat_id="DE000000000"), "unchecked", "11.89"),
        (
            "EU B2B geprueft",
            _profile("AT", "business", vat_id="ATU00000000", vat_status="valid"),
            "unchecked",
            "9.99",
        ),
        (
            "EU B2B ungeprueft, VIES stumm (W-R2c-1 A: 19 %)",
            _profile("AT", "business", vat_id="ATU00000000", vat_status="unchecked"),
            "unchecked",
            "11.89",
        ),
        (
            "EU B2B ungeprueft, VIES jetzt gueltig",
            _profile("AT", "business", vat_id="ATU00000000", vat_status="unchecked"),
            "valid",
            "9.99",
        ),
        (
            "EU B2B ungeprueft, VIES jetzt ungueltig",
            _profile("AT", "business", vat_id="ATU00000000", vat_status="unchecked"),
            "invalid",
            "11.89",
        ),
        ("EU B2C", _profile("AT", "consumer"), "unchecked", "11.89"),
        ("Drittland B2B", _profile("US", "business"), "unchecked", "9.99"),
        ("Drittland B2C", _profile("US", "consumer"), "unchecked", "9.99"),
    ],
    ids=lambda value: value if isinstance(value, str) else "",
)
def test_checkout_amount_per_tax_case(
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    profile: BillingProfile,
    vies_status: VatStatus,
    expected: str,
) -> None:
    """Regelbesteuerung, Preisbasis netto (Default): Betrag = `expected_total`."""
    service, gateway = _priced_service(_FakeProfiles(profile), vies=_FakeVies(vies_status))
    resp = _post_checkout(monkeypatch, service)
    assert resp.status_code == 201, case
    assert gateway.first_payment_amounts == [expected], case


@pytest.mark.usefixtures("cloud_env")
@pytest.mark.parametrize(
    ("tax_mode", "price_basis", "profile", "expected"),
    [
        ("regular", "gross", _profile("DE", "consumer"), "9.99"),
        ("regular", "gross", _profile("US", "business"), "9.99"),
        ("small_business", "net", _profile("DE", "consumer"), "9.99"),
    ],
)
def test_checkout_amount_follows_switches(
    monkeypatch: pytest.MonkeyPatch,
    tax_mode: TaxMode,
    price_basis: PriceBasis,
    profile: BillingProfile,
    expected: str,
) -> None:
    """Brutto-Basis (W61-2 A): Planpreis enthaelt die Steuer. Kleinunternehmer: 0 %."""
    service, gateway = _priced_service(
        _FakeProfiles(profile), tax_mode=tax_mode, price_basis=price_basis
    )
    resp = _post_checkout(monkeypatch, service)
    assert resp.status_code == 201
    assert gateway.first_payment_amounts == [expected]


@pytest.mark.usefixtures("cloud_env")
def test_checkout_unchecked_vat_rechecks_vies_and_stores_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """W-R2c-1 A: VIES einmal neu fragen, ein Ergebnis landet in den Rechnungsdaten."""
    profiles = _FakeProfiles(
        _profile("AT", "business", vat_id="ATU00000000", vat_status="unchecked")
    )
    vies = _FakeVies("valid")
    service, _ = _priced_service(profiles, vies=vies)
    resp = _post_checkout(monkeypatch, service)
    assert resp.status_code == 201
    assert vies.calls == 1
    assert [(vat_id, status) for _, vat_id, status in profiles.vat_updates] == [
        ("ATU00000000", "valid")
    ]


@pytest.mark.usefixtures("cloud_env")
def test_checkout_silent_vies_keeps_profile_unchecked(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bleibt VIES stumm, wird nichts zurueckgeschrieben: die 19 % gelten nur fuer den Betrag."""
    profiles = _FakeProfiles(
        _profile("AT", "business", vat_id="ATU00000000", vat_status="unchecked")
    )
    vies = _FakeVies("unchecked")
    service, _ = _priced_service(profiles, vies=vies)
    resp = _post_checkout(monkeypatch, service)
    assert resp.status_code == 201
    assert vies.calls == 1
    assert profiles.vat_updates == []


@pytest.mark.usefixtures("cloud_env")
def test_checkout_without_billing_profile_is_409(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ohne Rechnungsdaten 409, und bei Mollie entsteht nichts (kein Customer, keine Zahlung)."""
    service, gateway = _priced_service(_FakeProfiles(None))
    resp = _post_checkout(monkeypatch, service)
    assert resp.status_code == 409
    assert "Rechnungsdaten" in resp.json()["detail"]
    assert gateway.customer_count == 0
    assert gateway.first_payment_amounts == []


@pytest.mark.usefixtures("cloud_env")
def test_checkout_without_tax_mode_is_503(monkeypatch: pytest.MonkeyPatch) -> None:
    """W-R2c-2 A: ohne Steuermodus fail closed, auch wenn Rechnungsdaten vorliegen."""
    service, gateway = _priced_service(_FakeProfiles(_profile("DE", "consumer")), tax_mode=None)
    resp = _post_checkout(monkeypatch, service)
    assert resp.status_code == 503
    assert resp.json()["detail"] == "Rechnungsstellung nicht konfiguriert."
    assert gateway.customer_count == 0
    assert gateway.first_payment_amounts == []


@pytest.mark.usefixtures("cloud_env")
def test_router_wires_pricing_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Echte `get_mollie_service` ohne `WHO2BE_INVOICE_TAX_MODE` ⇒ 503 vor jedem Mollie-Aufruf.

    Faellt die Verdrahtung von `CheckoutPricing` im Router weg, ginge der Checkout
    mit dem Plan-Preis an das (echte) SDK-Gateway und der Test waere rot.
    """
    monkeypatch.delenv("WHO2BE_INVOICE_TAX_MODE", raising=False)
    get_settings.cache_clear()
    resp = _post_checkout(monkeypatch, None)
    assert resp.status_code == 503
    assert resp.json()["detail"] == "Rechnungsstellung nicht konfiguriert."


@pytest.mark.usefixtures("cloud_env")
def test_subscription_uses_paid_first_amount() -> None:
    """Die Subscription traegt den bezahlten Erstbetrag, nicht den Planpreis (R2c).

    Sonst laeuft ab der zweiten Zahlung jede Rechnung in `amount_mismatch`.
    """
    app = create_app()
    org_id = uuid4()
    gateway = _AmountGateway(
        payment=MolliePayment(
            "tr_first",
            True,
            "cst_1",
            None,
            "mdt_1",
            dict(PRO_PLAN.metadata(org_id)),
            amount_value=Decimal("11.89"),
        ),
    )
    app.dependency_overrides[get_mollie_service] = lambda: MollieBillingService(
        gateway, FakeEntitlementRepository()
    )
    try:
        with TestClient(app) as client:
            resp = client.post("/v1/billing/mollie/webhook", data={"id": "tr_first"})
    finally:
        app.dependency_overrides.clear()
    assert resp.json() == {"received": True}
    assert gateway.subscription_amounts == ["11.89"]
