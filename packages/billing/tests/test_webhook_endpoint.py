"""Endpoint-Tests fuer den Billing-Webhook (`routers/billing.py`).

Die hier geprueften Pfade brauchen keine DB: On-Prem liefert 404 (Webhook nur
Cloud), und eine fehlende/ungueltige Signatur wird vor jedem DB-Zugriff mit 400
abgewiesen (fail closed). Der erfolgreiche Upsert-Pfad ist integration-gated.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from test_mollie_adapter import (  # type: ignore[import-not-found]
    FakeEntitlementRepository,
    FakeProcessedEventRepository,
)

import who2be_billing.router as billing_router
from who2be_api.core.config import get_settings
from who2be_api.licensing.entitlement import Entitlement
from who2be_api.main import create_app

_SECRET = "whsec_endpoint_secret"


@dataclass
class _UpsertCall:
    org_id: UUID
    entitlement: Entitlement
    source: str
    external_ref: str | None


@dataclass
class _FlakyEntitlementRepository:
    """Wie `FakeEntitlementRepository` (`test_mollie_adapter`), aber der erste
    `upsert` schlaegt fehl (Issue #452 AC3).

    Eigenstaendig statt Unterklasse: `FakeEntitlementRepository` wird per
    `type: ignore[import-not-found]` importiert (Testmodul, kein Package) und
    ist fuer mypy daher `Any` — davon zu erben waere ein `[misc]`-Fehler.
    """

    calls: list[_UpsertCall] = field(default_factory=list)
    _failed: bool = False

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
        if not self._failed:
            self._failed = True
            raise RuntimeError("transienter DB-Fehler")
        self.calls.append(_UpsertCall(org_id, entitlement, source, external_ref))


@pytest.fixture
def cloud_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    # Edition + Secret werden zur Laufzeit ueber `get_settings()` gelesen (wie im
    # restlichen Code) — daher per Env setzen und den lru_cache leeren.
    monkeypatch.setenv("WHO2BE_EDITION", "cloud")
    monkeypatch.setenv("WHO2BE_BILLING_WEBHOOK_SECRET", _SECRET)
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        yield client
    get_settings.cache_clear()


def test_webhook_404_on_onprem(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WHO2BE_EDITION", "onprem")
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            resp = client.post("/v1/billing/webhook", content=b"{}")
    finally:
        get_settings.cache_clear()
    assert resp.status_code == 404


def test_webhook_rejects_missing_signature(cloud_client: TestClient) -> None:
    resp = cloud_client.post("/v1/billing/webhook", content=b"{}")
    assert resp.status_code == 400


def test_webhook_rejects_invalid_signature(cloud_client: TestClient) -> None:
    resp = cloud_client.post(
        "/v1/billing/webhook",
        content=b'{"type":"x"}',
        headers={"X-Webhook-Signature": "deadbeef"},
    )
    assert resp.status_code == 400


def test_webhook_irrelevant_event_acknowledged(cloud_client: TestClient) -> None:
    # Gueltige Signatur, aber ein Event-Typ, der das Entitlement nicht beruehrt:
    # quittiert mit 200, ohne DB-Zugriff (map_event_to_entitlement ⇒ None).
    # `created` ist noetig, weil das generische Format die Replay-Toleranz
    # gegen das Payload-Feld prueft (Issue #452 AC4), nicht gegen einen Header.
    payload = json.dumps(
        {"type": "ping", "data": {"object": {}}, "created": int(time.time())}
    ).encode()
    signature = hmac.new(_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    resp = cloud_client.post(
        "/v1/billing/webhook",
        content=payload,
        headers={"X-Webhook-Signature": signature},
    )
    assert resp.status_code == 200
    assert resp.json() == {"received": True}


def test_webhook_404_when_secret_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """Issue #452 AC6: ohne `billing_webhook_secret` ist die Route in der Cloud-
    Edition gar nicht erst gemountet (404), statt fail-closed mit 400 zu antworten.
    `test_webhook_404_on_onprem` deckt die zweite Konfiguration (On-Prem) ab."""
    monkeypatch.setenv("WHO2BE_EDITION", "cloud")
    monkeypatch.delenv("WHO2BE_BILLING_WEBHOOK_SECRET", raising=False)
    monkeypatch.setenv("WHO2BE_BILLING_WEBHOOK_SECRET", "")
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            resp = client.post("/v1/billing/webhook", content=b"{}")
    finally:
        get_settings.cache_clear()
    assert resp.status_code == 404


def _grant_event(*, event_id: str, org_id: str, period_end: int) -> bytes:
    return json.dumps(
        {
            "id": event_id,
            "type": "customer.subscription.updated",
            "created": int(time.time()),
            "data": {
                "object": {
                    "id": "sub_dedupe",
                    "current_period_end": period_end,
                    "metadata": {"org_id": org_id, "license_policy": "core"},
                }
            },
        }
    ).encode()


def _sign(payload: bytes) -> str:
    return hmac.new(_SECRET.encode(), payload, hashlib.sha256).hexdigest()


def test_webhook_duplicate_event_applied_once(
    cloud_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Issue #452 AC2: dieselbe Envelope-ID zweimal zugestellt ⇒ der Upsert
    laeuft nur einmal, die zweite Zustellung wird trotzdem mit Erfolg quittiert
    (kein Fehler, sonst haengt sich der Provider in eine Retry-Schleife)."""
    entitlement_repo = FakeEntitlementRepository()
    processed_repo = FakeProcessedEventRepository()
    monkeypatch.setattr(billing_router, "get_pool", lambda: object())
    monkeypatch.setattr(billing_router, "PgEntitlementRepository", lambda pool: entitlement_repo)
    monkeypatch.setattr(billing_router, "PgProcessedEventRepository", lambda pool: processed_repo)

    payload = _grant_event(
        event_id="evt_dup_1", org_id=str(uuid4()), period_end=int(time.time()) + 3600
    )
    signature = _sign(payload)

    first = cloud_client.post(
        "/v1/billing/webhook", content=payload, headers={"X-Webhook-Signature": signature}
    )
    second = cloud_client.post(
        "/v1/billing/webhook", content=payload, headers={"X-Webhook-Signature": signature}
    )

    assert first.status_code == 200
    assert first.json() == {"received": True}
    assert second.status_code == 200
    assert second.json() == {"received": True}
    assert len(entitlement_repo.calls) == 1


def test_webhook_release_dedupe_claim_on_failure(
    cloud_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Issue #452 AC3: schlaegt der Upsert nach dem Dedupe-Claim fehl, wird der
    Claim wieder freigegeben — ein Retry desselben Events verarbeitet danach
    erfolgreich (analog `test_handle_webhook_releases_claim_on_failure` fuer
    den Mollie-Pfad)."""
    processed_repo = FakeProcessedEventRepository()
    entitlement_repo = _FlakyEntitlementRepository()
    monkeypatch.setattr(billing_router, "get_pool", lambda: object())
    monkeypatch.setattr(billing_router, "PgEntitlementRepository", lambda pool: entitlement_repo)
    monkeypatch.setattr(billing_router, "PgProcessedEventRepository", lambda pool: processed_repo)

    payload = _grant_event(
        event_id="evt_fail_1", org_id=str(uuid4()), period_end=int(time.time()) + 3600
    )
    signature = _sign(payload)

    with pytest.raises(RuntimeError, match="transienter DB-Fehler"):
        cloud_client.post(
            "/v1/billing/webhook", content=payload, headers={"X-Webhook-Signature": signature}
        )
    assert ("cloud", "evt_fail_1") not in processed_repo.claimed
    assert entitlement_repo.calls == []

    # Retry desselben Events verarbeitet jetzt erfolgreich.
    retry = cloud_client.post(
        "/v1/billing/webhook", content=payload, headers={"X-Webhook-Signature": signature}
    )
    assert retry.status_code == 200
    assert retry.json() == {"received": True}
    assert len(entitlement_repo.calls) == 1
