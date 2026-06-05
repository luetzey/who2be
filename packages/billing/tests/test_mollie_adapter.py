"""Unit-Tests fuer den Mollie-Pull-Adapter (`licensing/adapters/mollie.py`).

Ohne Netz: ein Fake-`MollieGateway` simuliert die Mollie-API, ein Fake-Repository
faengt die Entitlement-Upserts ab. Deckt das Pull-Modell ab — Checkout,
Erstzahlung→Subscription, Folgezahlung-Status, Kuendigung→Free, fremde Metadata.

Die Codebasis nutzt kein pytest-asyncio; async-Pfade werden ueber `asyncio.run`
getrieben (konsistent zu `test_licensing_onprem_adapter.py`).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest

from who2be_api.licensing.entitlement import CLOUD_FREE_ENTITLEMENT, Entitlement, Feature
from who2be_billing.mollie import (
    MollieBillingService,
    MollieError,
    MolliePayment,
    MollieSubscription,
    metadata_org_id,
    metadata_to_entitlement,
    subscription_to_update,
)
from who2be_billing.plans import PRO_PLAN


@dataclass
class _UpsertCall:
    org_id: UUID
    entitlement: Entitlement
    source: str
    external_ref: str | None


class FakeEntitlementRepository:
    """Faengt `upsert` ab; `fetch` ist fuer den Service irrelevant."""

    def __init__(self) -> None:
        self.calls: list[_UpsertCall] = []

    async def fetch(self, org_id: UUID) -> Entitlement | None:
        return None

    async def upsert(
        self,
        org_id: UUID,
        entitlement: Entitlement,
        source: str,
        external_ref: str | None,
        created_by: UUID | None = None,
        reason: str | None = None,
    ) -> None:
        self.calls.append(_UpsertCall(org_id, entitlement, source, external_ref))


class FakeProcessedEventRepository:
    """In-Memory-Dedupe-Ledger: `claim` ist beim ersten (provider, id) True."""

    def __init__(self) -> None:
        self.claimed: set[tuple[str, str]] = set()

    async def claim(self, provider: str, event_id: str) -> bool:
        key = (provider, event_id)
        if key in self.claimed:
            return False
        self.claimed.add(key)
        return True

    async def release(self, provider: str, event_id: str) -> None:
        self.claimed.discard((provider, event_id))


@dataclass
class FakeMollieGateway:
    """Konfigurierbarer Fake der Mollie-API-Grenze."""

    payment: MolliePayment | None = None
    subscription: MollieSubscription | None = None
    new_customer_id: str = "cst_fake"
    new_subscription_id: str = "sub_new"
    checkout_url: str = "https://www.mollie.com/checkout/fake"
    created_customer_metadata: dict[str, str] = field(default_factory=dict)
    first_payment_metadata: dict[str, str] = field(default_factory=dict)
    created_subscription_metadata: dict[str, str] = field(default_factory=dict)
    subscription_create_count: int = 0

    async def create_customer(
        self, *, name: str, email: str | None, metadata: dict[str, str]
    ) -> str:
        self.created_customer_metadata = metadata
        return self.new_customer_id

    async def create_first_payment(
        self,
        *,
        customer_id: str,
        amount_eur: str,
        description: str,
        redirect_url: str,
        webhook_url: str | None,
        metadata: dict[str, str],
    ) -> str:
        self.first_payment_metadata = metadata
        return self.checkout_url

    async def get_payment(self, payment_id: str) -> MolliePayment | None:
        return self.payment

    async def create_subscription(
        self,
        *,
        customer_id: str,
        amount_eur: str,
        interval: str,
        description: str,
        webhook_url: str | None,
        metadata: dict[str, str],
    ) -> str:
        self.created_subscription_metadata = metadata
        self.subscription_create_count += 1
        return self.new_subscription_id

    async def get_subscription(
        self, customer_id: str, subscription_id: str
    ) -> MollieSubscription | None:
        return self.subscription


def _pro_metadata(org_id: UUID) -> dict[str, Any]:
    return dict(PRO_PLAN.metadata(org_id))


# --- reine Mapping-Funktionen ----------------------------------------------------


def test_metadata_to_entitlement_parses_features_and_limits() -> None:
    org_id = uuid4()
    ent = metadata_to_entitlement(_pro_metadata(org_id))
    assert ent.status == "active"
    assert Feature.AGENTS in ent.features
    assert ent.mcp_monthly_quota == 100_000
    assert ent.mcp_rate_per_min == 240


def test_metadata_org_id_missing_raises() -> None:
    with pytest.raises(MollieError):
        metadata_org_id({})


def test_subscription_to_update_active_maps_tier() -> None:
    org_id = uuid4()
    sub = MollieSubscription("sub_1", "active", _pro_metadata(org_id))
    update = subscription_to_update(sub)
    assert update.org_id == org_id
    assert update.external_ref == "sub_1"
    assert update.entitlement.status == "active"
    assert Feature.COMPOSITE_PLAYBOOKS in update.entitlement.features


def test_subscription_to_update_canceled_falls_back_to_free() -> None:
    org_id = uuid4()
    sub = MollieSubscription("sub_1", "canceled", {"org_id": str(org_id)})
    update = subscription_to_update(sub)
    assert update.entitlement == CLOUD_FREE_ENTITLEMENT
    assert update.external_ref == "sub_1"


# --- Service-Orchestrierung ------------------------------------------------------


def test_start_checkout_creates_customer_and_payment() -> None:
    org_id = uuid4()
    gateway = FakeMollieGateway()
    service = MollieBillingService(gateway, FakeEntitlementRepository())
    url = asyncio.run(
        service.start_checkout(
            org_id=org_id,
            plan=PRO_PLAN,
            customer_name="Acme",
            customer_email="a@example.com",
            redirect_url="https://app/settings/billing",
            webhook_url="https://api/v1/billing/mollie/webhook",
        )
    )
    assert url == gateway.checkout_url
    assert gateway.created_customer_metadata["org_id"] == str(org_id)
    # Erstzahlung traegt die volle Plan-Metadata (license_policy etc.).
    assert gateway.first_payment_metadata["license_policy"] == " ".join(sorted(PRO_PLAN.features))
    assert gateway.first_payment_metadata["plan_code"] == "pro"


def test_handle_webhook_recurring_active_upserts_tier() -> None:
    org_id = uuid4()
    repo = FakeEntitlementRepository()
    gateway = FakeMollieGateway(
        payment=MolliePayment(
            id="tr_1",
            is_paid=True,
            customer_id="cst_1",
            subscription_id="sub_1",
            mandate_id="mdt_1",
            metadata={},
        ),
        subscription=MollieSubscription("sub_1", "active", _pro_metadata(org_id)),
    )
    service = MollieBillingService(gateway, repo)
    applied = asyncio.run(service.handle_webhook("tr_1", webhook_url=None))
    assert applied is True
    assert len(repo.calls) == 1
    call = repo.calls[0]
    assert call.org_id == org_id
    assert call.source == "mollie"
    assert call.external_ref == "sub_1"
    assert call.entitlement.status == "active"


def test_handle_webhook_recurring_canceled_downgrades_to_free() -> None:
    org_id = uuid4()
    repo = FakeEntitlementRepository()
    gateway = FakeMollieGateway(
        payment=MolliePayment("tr_1", True, "cst_1", "sub_1", "mdt_1", {}),
        subscription=MollieSubscription("sub_1", "canceled", {"org_id": str(org_id)}),
    )
    service = MollieBillingService(gateway, repo)
    applied = asyncio.run(service.handle_webhook("tr_1", webhook_url=None))
    assert applied is True
    assert repo.calls[0].entitlement == CLOUD_FREE_ENTITLEMENT


def test_handle_webhook_first_payment_creates_subscription() -> None:
    org_id = uuid4()
    repo = FakeEntitlementRepository()
    gateway = FakeMollieGateway(
        payment=MolliePayment(
            id="tr_first",
            is_paid=True,
            customer_id="cst_1",
            subscription_id=None,  # Erstzahlung gehoert noch zu keiner Subscription
            mandate_id="mdt_1",
            metadata=_pro_metadata(org_id),
        ),
    )
    service = MollieBillingService(gateway, repo)
    applied = asyncio.run(service.handle_webhook("tr_first", webhook_url="https://api/hook"))
    assert applied is True
    # Subscription wurde angelegt + Entitlement aktiv gesetzt (external_ref = neue Sub-ID).
    assert gateway.created_subscription_metadata["org_id"] == str(org_id)
    assert repo.calls[0].external_ref == gateway.new_subscription_id
    assert repo.calls[0].entitlement.status == "active"


def test_handle_webhook_unpaid_first_payment_is_noop() -> None:
    repo = FakeEntitlementRepository()
    gateway = FakeMollieGateway(
        payment=MolliePayment("tr_1", False, "cst_1", None, None, {}),
    )
    service = MollieBillingService(gateway, repo)
    applied = asyncio.run(service.handle_webhook("tr_1", webhook_url=None))
    assert applied is False
    assert repo.calls == []


def test_handle_webhook_unknown_payment_is_noop() -> None:
    repo = FakeEntitlementRepository()
    service = MollieBillingService(FakeMollieGateway(payment=None), repo)
    assert asyncio.run(service.handle_webhook("tr_missing", webhook_url=None)) is False
    assert repo.calls == []


# --- Dunning / Grace (Plan §3.2) -------------------------------------------------


def test_subscription_to_update_failed_recurring_enters_grace() -> None:
    """Aktive Subscription, aber die Folgezahlung ist fehlgeschlagen ⇒ Grace."""
    org_id = uuid4()
    now = datetime(2026, 6, 3, tzinfo=UTC)
    sub = MollieSubscription("sub_1", "active", _pro_metadata(org_id))
    update = subscription_to_update(sub, payment_paid=False, now=now, grace_days=7)
    ent = update.entitlement
    # Tier bleibt aktiv (Features/Limits aus Metadata) — nur befristet.
    assert ent.status == "active"
    assert Feature.AGENTS in ent.features
    assert ent.grace_until == now + timedelta(days=7)
    assert ent.expires_at == now + timedelta(days=7)
    # Innerhalb der Grace aktiv, danach abgelaufen (Sperre via expires_at).
    assert ent.is_active(now=now) is True
    assert ent.is_active(now=now + timedelta(days=8)) is False


def test_subscription_to_update_suspended_enters_grace() -> None:
    """Mollie-`suspended` (Retries erschoepft) ⇒ ebenfalls Grace, kein Hard-Cut."""
    org_id = uuid4()
    now = datetime(2026, 6, 3, tzinfo=UTC)
    sub = MollieSubscription("sub_1", "suspended", _pro_metadata(org_id))
    update = subscription_to_update(sub, payment_paid=False, now=now, grace_days=3)
    assert update.entitlement.status == "active"
    assert update.entitlement.grace_until == now + timedelta(days=3)


def test_subscription_to_update_active_paid_clears_grace() -> None:
    """Erfolgreiche Folgezahlung ⇒ voller Tier ohne grace_until (Grace geraeumt)."""
    org_id = uuid4()
    sub = MollieSubscription("sub_1", "active", _pro_metadata(org_id))
    update = subscription_to_update(sub, payment_paid=True, now=datetime(2026, 6, 3, tzinfo=UTC))
    assert update.entitlement.grace_until is None
    assert update.entitlement.expires_at is None


def test_subscription_to_update_canceled_keeps_tier_until_period_end() -> None:
    """Kuendigung am Periodenende: Tier laeuft bis next_payment_date weiter."""
    org_id = uuid4()
    now = datetime(2026, 6, 3, tzinfo=UTC)
    period_end = now + timedelta(days=12)
    sub = MollieSubscription(
        "sub_1", "canceled", _pro_metadata(org_id), next_payment_date=period_end
    )
    update = subscription_to_update(sub, now=now)
    assert update.entitlement.expires_at == period_end
    assert update.entitlement.grace_until is None  # Kuendigung ist kein Dunning-Fall
    assert Feature.AGENTS in update.entitlement.features
    assert update.entitlement.is_active(now=now) is True
    assert update.entitlement.is_active(now=period_end + timedelta(days=1)) is False


def test_subscription_to_update_canceled_without_period_end_falls_back_to_free() -> None:
    org_id = uuid4()
    sub = MollieSubscription("sub_1", "canceled", _pro_metadata(org_id))
    update = subscription_to_update(sub, now=datetime(2026, 6, 3, tzinfo=UTC))
    assert update.entitlement == CLOUD_FREE_ENTITLEMENT


def test_handle_webhook_failed_recurring_persists_grace() -> None:
    """End-to-end ueber den Service: fehlgeschlagene Folgezahlung ⇒ Grace im Upsert."""
    org_id = uuid4()
    now = datetime(2026, 6, 3, tzinfo=UTC)
    repo = FakeEntitlementRepository()
    gateway = FakeMollieGateway(
        payment=MolliePayment("tr_fail", False, "cst_1", "sub_1", "mdt_1", {}),
        subscription=MollieSubscription("sub_1", "active", _pro_metadata(org_id)),
    )
    service = MollieBillingService(gateway, repo, grace_days=5)
    applied = asyncio.run(service.handle_webhook("tr_fail", webhook_url=None, now=now))
    assert applied is True
    assert repo.calls[0].entitlement.grace_until == now + timedelta(days=5)


# --- Idempotenz / Dedupe (Plan §3.2) ---------------------------------------------


def test_handle_webhook_replay_recurring_is_noop() -> None:
    """Derselbe Folgezahlungs-Ping zweimal ⇒ nur ein Upsert (Replay = No-Op)."""
    org_id = uuid4()
    repo = FakeEntitlementRepository()
    gateway = FakeMollieGateway(
        payment=MolliePayment("tr_1", True, "cst_1", "sub_1", "mdt_1", {}),
        subscription=MollieSubscription("sub_1", "active", _pro_metadata(org_id)),
    )
    service = MollieBillingService(gateway, repo, FakeProcessedEventRepository())
    first = asyncio.run(service.handle_webhook("tr_1", webhook_url=None))
    second = asyncio.run(service.handle_webhook("tr_1", webhook_url=None))
    assert first is True
    assert second is False
    assert len(repo.calls) == 1


def test_handle_webhook_replay_first_payment_creates_one_subscription() -> None:
    """Wiederholter Erstzahlungs-Ping darf keine zweite Subscription anlegen."""
    org_id = uuid4()
    repo = FakeEntitlementRepository()
    gateway = FakeMollieGateway(
        payment=MolliePayment("tr_first", True, "cst_1", None, "mdt_1", _pro_metadata(org_id)),
    )
    service = MollieBillingService(gateway, repo, FakeProcessedEventRepository())
    first = asyncio.run(service.handle_webhook("tr_first", webhook_url=None))
    second = asyncio.run(service.handle_webhook("tr_first", webhook_url=None))
    assert first is True
    assert second is False
    assert gateway.subscription_create_count == 1
    assert len(repo.calls) == 1


def test_handle_webhook_distinct_payments_are_processed() -> None:
    """Verschiedene Payment-IDs sind unabhaengig — der Dedupe blockt nur Replays."""
    org_id = uuid4()
    repo = FakeEntitlementRepository()
    processed = FakeProcessedEventRepository()

    def _run(payment_id: str) -> bool:
        gateway = FakeMollieGateway(
            payment=MolliePayment(payment_id, True, "cst_1", "sub_1", "mdt_1", {}),
            subscription=MollieSubscription("sub_1", "active", _pro_metadata(org_id)),
        )
        service = MollieBillingService(gateway, repo, processed)
        return asyncio.run(service.handle_webhook(payment_id, webhook_url=None))

    assert _run("tr_a") is True
    assert _run("tr_b") is True
    assert len(repo.calls) == 2


def test_handle_webhook_releases_claim_on_failure() -> None:
    """Faellt der Upsert nach dem Claim aus, wird der Claim freigegeben — ein
    Retry desselben Pings verarbeitet erneut (kein verlorenes bezahltes Event)."""
    org_id = uuid4()
    gateway = FakeMollieGateway(
        payment=MolliePayment("tr_1", True, "cst_1", "sub_1", "mdt_1", {}),
        subscription=MollieSubscription("sub_1", "active", _pro_metadata(org_id)),
    )
    processed = FakeProcessedEventRepository()

    class _FlakyRepo(FakeEntitlementRepository):
        def __init__(self) -> None:
            super().__init__()
            self._failed = False

        async def upsert(
            self,
            org_id: UUID,
            entitlement: Entitlement,
            source: str,
            external_ref: str | None,
            created_by: UUID | None = None,
            reason: str | None = None,
        ) -> None:
            if not self._failed:
                self._failed = True
                raise RuntimeError("transienter DB-Fehler")
            await super().upsert(org_id, entitlement, source, external_ref)

    repo = _FlakyRepo()
    service = MollieBillingService(gateway, repo, processed)

    # Erster Ping: Upsert wirft ⇒ Claim wieder frei, Exception propagiert.
    with pytest.raises(RuntimeError):
        asyncio.run(service.handle_webhook("tr_1", webhook_url=None))
    assert ("mollie", "tr_1") not in processed.claimed
    assert repo.calls == []

    # Mollie-Retry desselben Pings verarbeitet jetzt erfolgreich.
    assert asyncio.run(service.handle_webhook("tr_1", webhook_url=None)) is True
    assert len(repo.calls) == 1
