"""Unit-Tests fuer Webhook-Signatur + Event→Entitlement-Mapping (`licensing/billing.py`).

Deckt die Guardrails ab: keine Verarbeitung ohne gueltige Signatur, fail-closed bei
leerem Secret, Replay-Toleranz, metadaten-getriebenes Feature-Mapping (kein
hartkodiertes Produkt-Mapping), Entzug bei Kuendigung/Fehlzahlung.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any
from uuid import uuid4

import pytest

from who2be_billing.webhook import (
    WebhookError,
    map_event_to_entitlement,
    parse_event,
    verify_webhook_signature,
)

_SECRET = "whsec_test_secret"


def _generic_sig(payload: bytes, secret: str = _SECRET) -> str:
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def _stripe_sig(payload: bytes, timestamp: int, secret: str = _SECRET) -> str:
    signed = f"{timestamp}.".encode() + payload
    digest = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


def test_generic_signature_valid() -> None:
    payload = b'{"hello":"world"}'
    assert verify_webhook_signature(payload, _generic_sig(payload), _SECRET)
    assert verify_webhook_signature(payload, f"sha256={_generic_sig(payload)}", _SECRET)


def test_generic_signature_invalid() -> None:
    payload = b'{"hello":"world"}'
    assert not verify_webhook_signature(payload, "deadbeef", _SECRET)
    assert not verify_webhook_signature(payload, _generic_sig(payload, "wrong-secret"), _SECRET)


def test_empty_secret_fails_closed() -> None:
    payload = b"{}"
    assert not verify_webhook_signature(payload, _generic_sig(payload), "")
    assert not verify_webhook_signature(payload, None, _SECRET)


def test_stripe_signature_valid_and_replay_window() -> None:
    payload = b'{"type":"x"}'
    now = time.time()
    header = _stripe_sig(payload, int(now))
    assert verify_webhook_signature(payload, header, _SECRET, now=now)
    # Zu alter Zeitstempel ⇒ Replay-Schutz greift.
    old_header = _stripe_sig(payload, int(now) - 10_000)
    assert not verify_webhook_signature(payload, old_header, _SECRET, now=now)


def _subscription_event(event_type: str, **meta: Any) -> dict[str, Any]:
    return {
        "type": event_type,
        "data": {
            "object": {
                "id": "sub_123",
                "metadata": meta,
            }
        },
    }


def test_grant_event_maps_features_from_metadata() -> None:
    org_id = uuid4()
    event = _subscription_event(
        "customer.subscription.updated",
        org_id=str(org_id),
        license_policy="core, sso audit_export",
        mcp_monthly_quota="20000",
        mcp_rate_per_min="120",
    )
    update = map_event_to_entitlement(event)
    assert update is not None
    assert update.org_id == org_id
    assert update.entitlement.status == "active"
    assert update.entitlement.features == frozenset({"core", "sso", "audit_export"})
    assert update.entitlement.mcp_monthly_quota == 20000
    assert update.entitlement.mcp_rate_per_min == 120
    assert update.external_ref == "sub_123"


def test_revoke_event_sets_inactive() -> None:
    org_id = uuid4()
    event = _subscription_event("customer.subscription.deleted", org_id=str(org_id))
    update = map_event_to_entitlement(event)
    assert update is not None
    assert update.entitlement.status == "inactive"
    assert update.entitlement.features == frozenset()


def test_irrelevant_event_returns_none() -> None:
    assert map_event_to_entitlement(_subscription_event("ping", org_id=str(uuid4()))) is None


def test_missing_org_id_raises() -> None:
    with pytest.raises(WebhookError):
        map_event_to_entitlement(_subscription_event("customer.subscription.updated"))


def test_parse_event_rejects_non_json() -> None:
    with pytest.raises(WebhookError):
        parse_event(b"not-json")
    # Gueltiges JSON, aber kein Objekt.
    with pytest.raises(WebhookError):
        parse_event(json.dumps([1, 2, 3]).encode())
