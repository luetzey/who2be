"""Endpoint-Tests fuer den Billing-Webhook (`routers/billing.py`).

Die hier geprueften Pfade brauchen keine DB: On-Prem liefert 404 (Webhook nur
Cloud), und eine fehlende/ungueltige Signatur wird vor jedem DB-Zugriff mit 400
abgewiesen (fail closed). Der erfolgreiche Upsert-Pfad ist integration-gated.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from who2be_api.core.config import get_settings
from who2be_api.main import create_app

_SECRET = "whsec_endpoint_secret"


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
    payload = json.dumps({"type": "ping", "data": {"object": {}}}).encode()
    signature = hmac.new(_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    resp = cloud_client.post(
        "/v1/billing/webhook",
        content=payload,
        headers={"X-Webhook-Signature": signature},
    )
    assert resp.status_code == 200
    assert resp.json() == {"received": True}
