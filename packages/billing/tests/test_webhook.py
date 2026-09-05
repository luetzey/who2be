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
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from who2be_billing.webhook import (
    WebhookError,
    extract_event_id,
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
    # Das generische Schema hat keinen Header-Zeitbezug (anders als Stripe) —
    # die Replay-Toleranz liest `created` aus dem Payload (Issue #452 AC4),
    # daher braucht ein gueltiges Beispiel dieses Feld.
    payload = json.dumps({"hello": "world", "created": int(time.time())}).encode()
    assert verify_webhook_signature(payload, _generic_sig(payload), _SECRET)
    assert verify_webhook_signature(payload, f"sha256={_generic_sig(payload)}", _SECRET)


def test_generic_signature_invalid() -> None:
    payload = json.dumps({"hello": "world", "created": int(time.time())}).encode()
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


def test_generic_signature_rejects_stale_timestamp() -> None:
    """Issue #452 AC4: die Signatur allein reicht im generischen Format nicht —
    ein `created` ausserhalb der Toleranz wird trotz korrekter HMAC abgewiesen."""
    now = time.time()
    payload = json.dumps({"hello": "world", "created": int(now) - 10_000}).encode()
    assert not verify_webhook_signature(payload, _generic_sig(payload), _SECRET, now=now)


def test_generic_signature_rejects_missing_timestamp() -> None:
    """Fehlt `created` im generischen Payload, wird fail-closed abgewiesen statt
    die Toleranzpruefung stillschweigend zu ueberspringen."""
    payload = json.dumps({"hello": "world"}).encode()
    assert not verify_webhook_signature(payload, _generic_sig(payload), _SECRET)


def _subscription_event(
    event_type: str,
    *,
    event_id: str | None = None,
    current_period_end: int | None = None,
    **meta: Any,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "type": event_type,
        "data": {
            "object": {
                "id": "sub_123",
                "metadata": meta,
            }
        },
    }
    if event_id is not None:
        event["id"] = event_id
    if current_period_end is not None:
        event["data"]["object"]["current_period_end"] = current_period_end
    return event


def test_grant_event_maps_features_from_metadata() -> None:
    org_id = uuid4()
    period_end = int(time.time()) + 30 * 24 * 3600
    event = _subscription_event(
        "customer.subscription.updated",
        event_id="evt_1",
        current_period_end=period_end,
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
    assert update.entitlement.expires_at == datetime.fromtimestamp(period_end, tz=UTC)
    assert update.external_ref == "sub_123"


def test_grant_event_without_period_is_rejected() -> None:
    """Issue #452 AC1: ein Grant-Event ohne Periodenangabe erzeugt kein
    unbefristetes Entitlement — es wird stattdessen fail-closed abgelehnt
    (weder `current_period_end` noch `metadata.expires_at` gesetzt)."""
    event = _subscription_event(
        "customer.subscription.updated",
        event_id="evt_2",
        org_id=str(uuid4()),
        license_policy="core",
    )
    with pytest.raises(WebhookError):
        map_event_to_entitlement(event)


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


def test_extract_event_id_returns_envelope_id() -> None:
    """Issue #452 AC2: der Dedupe-Schluessel ist die Envelope-ID, nicht die
    Objekt-ID (`data.object.id`, hier bewusst mit einem anderen Wert)."""
    event = _subscription_event(
        "customer.subscription.updated",
        event_id="evt_abc",
        current_period_end=int(time.time()) + 3600,
        org_id=str(uuid4()),
    )
    assert extract_event_id(event) == "evt_abc"
    assert event["data"]["object"]["id"] == "sub_123"  # Objekt-ID bleibt unberuehrt


def test_extract_event_id_missing_raises() -> None:
    event = _subscription_event(
        "customer.subscription.updated",
        current_period_end=int(time.time()) + 3600,
        org_id=str(uuid4()),
    )
    with pytest.raises(WebhookError):
        extract_event_id(event)
