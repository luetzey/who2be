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
    _parse_stripe_header,
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


def test_generic_signature_accepts_delayed_retry_within_plausibility_window() -> None:
    """Nachtrag-Befund 1: der generische Zweig muss einen legitimen, um Stunden
    verspaeteten Retry weiterhin annehmen — `created` steckt im HMAC-gedeckten
    Body und kann bei einem Retry NICHT aufgefrischt werden. Ein `created` von
    vor 3 Stunden (weit ausserhalb der 5-Minuten-Toleranz des Stripe-Zweigs)
    ist im generischen Plausibilitaetsfenster (Tage) weiterhin gueltig."""
    now = time.time()
    payload = json.dumps({"hello": "world", "created": int(now) - 3 * 60 * 60}).encode()
    assert verify_webhook_signature(payload, _generic_sig(payload), _SECRET, now=now)


def test_generic_signature_rejects_stale_timestamp() -> None:
    """Nachtrag-Befund 1: das Plausibilitaetsfenster ist weit, aber nicht
    unendlich — ein `created` von vor 8 Tagen (ausserhalb der 7-Tage-Grenze)
    wird trotz korrekter HMAC abgewiesen."""
    now = time.time()
    payload = json.dumps({"hello": "world", "created": int(now) - 8 * 24 * 60 * 60}).encode()
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


# --- Nachtrag zu Issue #452: Security-Review-Befunde 1-4 -------------------


def test_grant_event_period_in_past_is_rejected() -> None:
    """Nachtrag-Befund 2 (untere Grenze): ein Periodenende, das bereits
    vergangen ist, wuerde ein formal aktives, faktisch totes Entitlement
    erzeugen — abgelehnt statt geschrieben."""
    event = _subscription_event(
        "customer.subscription.updated",
        event_id="evt_past",
        current_period_end=int(time.time()) - 3600,
        org_id=str(uuid4()),
        license_policy="core",
    )
    with pytest.raises(WebhookError):
        map_event_to_entitlement(event)


def test_grant_event_period_too_far_in_future_is_rejected() -> None:
    """Nachtrag-Befund 2 (obere Grenze): `current_period_end: 253402300799`
    (Jahr 9999) waere inhaltlich wieder ein unbefristetes Entitlement, nur
    anders geschrieben — abgelehnt jenseits des Maximalhorizonts (~13 Monate)."""
    event = _subscription_event(
        "customer.subscription.updated",
        event_id="evt_far_future",
        current_period_end=253_402_300_799,
        org_id=str(uuid4()),
        license_policy="core",
    )
    with pytest.raises(WebhookError):
        map_event_to_entitlement(event)


def test_grant_event_period_just_within_horizon_is_accepted() -> None:
    """Gegenprobe zur Obergrenze: knapp innerhalb von ~13 Monaten bleibt gueltig
    (verhindert, dass die Grenze versehentlich zu eng gezogen wird)."""
    period_end = int(time.time()) + 390 * 24 * 3600  # ~12,8 Monate
    event = _subscription_event(
        "customer.subscription.updated",
        event_id="evt_within_horizon",
        current_period_end=period_end,
        org_id=str(uuid4()),
        license_policy="core",
    )
    update = map_event_to_entitlement(event)
    assert update is not None
    assert update.entitlement.expires_at == datetime.fromtimestamp(period_end, tz=UTC)


@pytest.mark.parametrize(
    "bad_created",
    [
        pytest.param("--12", id="double-minus-string"),
        pytest.param("²²²²", id="unicode-superscript-digits"),
        pytest.param("9" * 5000, id="overlong-digit-string"),
        pytest.param(float("inf"), id="infinity"),
        pytest.param(float("nan"), id="nan"),
    ],
)
def test_generic_signature_rejects_malformed_created_without_crashing(bad_created: Any) -> None:
    """Nachtrag-Befund 3: die eigene Zusicherung "unlesbar ⇒ None" darf nicht
    an Unicode-Ziffern, mehrfachen Vorzeichen, ueberlangen Ziffernstrings oder
    NaN/Infinity zerbrechen — `verify_webhook_signature` liefert `False`
    statt eine Exception durchzulassen (fail closed bleibt fail closed, nicht
    ein unauthentifizierter 500)."""
    payload = json.dumps({"hello": "world", "created": bad_created}).encode()
    assert verify_webhook_signature(payload, _generic_sig(payload), _SECRET) is False


def test_generic_signature_rejects_oversized_numeric_literal_without_crashing() -> None:
    """Nachtrag-Befund 3, `webhook.py:71-74`: ein *unquotiertes* Zahlen-Literal
    mit mehr als 4300 Stellen laesst `json.loads` selbst mit einem nackten
    `ValueError` scheitern (CPythons Integer-String-Konvertierungslimit) —
    keiner `json.JSONDecodeError`. Das alte, engere `except` haette das nicht
    abgefangen; hier direkt als Rohbytes gebaut, weil schon `str()` auf einem
    so grossen Python-`int` an derselben Grenze scheitern wuerde."""
    huge_literal = "9" * 5000
    payload = ('{"hello": "world", "created": ' + huge_literal + "}").encode()
    assert verify_webhook_signature(payload, _generic_sig(payload), _SECRET) is False


def test_int_metadata_rejects_non_finite_value() -> None:
    """Nachtrag-Befund 3: derselbe Schutz gilt fuer `_parse_int_meta` — ein
    `Infinity`-Metadatum bricht sonst mit `OverflowError` statt `WebhookError`."""
    event = _subscription_event(
        "customer.subscription.updated",
        event_id="evt_inf_quota",
        current_period_end=int(time.time()) + 3600,
        org_id=str(uuid4()),
        license_policy="core",
        mcp_monthly_quota=float("inf"),
    )
    with pytest.raises(WebhookError):
        map_event_to_entitlement(event)


def test_generic_signature_rejects_non_ascii_header_without_crashing() -> None:
    """Nachtrag-Befund 4: `hmac.compare_digest` wirft `TypeError` bei
    Nicht-ASCII-`str`-Operanden — ein Header, den Starlette latin-1-dekodiert
    haben koennte (0x80-0xFF), darf hoechstens `False` ausloesen, nie eine
    durchschlagende Exception."""
    payload = json.dumps({"hello": "world", "created": int(time.time())}).encode()
    assert verify_webhook_signature(payload, "é" * 64, _SECRET) is False
    assert verify_webhook_signature(payload, "sha256=" + "é" * 64, _SECRET) is False


def test_stripe_signature_rejects_non_ascii_v1_without_crashing() -> None:
    """Nachtrag-Befund 4, Stripe-Zweig: derselbe Schutz fuer den `v1=`-Wert."""
    payload = b'{"type":"x"}'
    now = time.time()
    header = f"t={int(now)},v1={'é' * 64}"
    assert verify_webhook_signature(payload, header, _SECRET, now=now) is False


# ---------------------------------------------------------------------------
# Issue #463 Punkt 5: `_parse_stripe_header` wandelt den `t=`-Wert ueber
# `_coerce_int`. Der alte `value.isdigit()`-Test war zu freundlich UND zu naiv.
# ---------------------------------------------------------------------------
def test_parse_stripe_header_survives_unicode_digit() -> None:
    """`"²".isdigit()` ist True, `int("²")` wirft aber ValueError — der alte
    Pfad liess die Exception durchschlagen."""
    assert "²".isdigit() is True  # die Falle, schwarz auf weiss

    assert _parse_stripe_header("t=²,v1=abc") is None


def test_parse_stripe_header_survives_integer_conversion_limit() -> None:
    """Ein sehr langer Ziffernstring reisst CPythons Konversionslimit
    (~4300 Stellen, ValueError) — auch das schlug bisher durch."""
    assert _parse_stripe_header(f"t={'1' * 5000},v1=abc") is None


def test_parse_stripe_header_still_accepts_a_valid_timestamp() -> None:
    """Gegenprobe: das bestehende Verhalten aendert sich nicht."""
    assert _parse_stripe_header("t=1700000000,v1=abc") == (1700000000, "abc")


def test_parse_stripe_header_still_rejects_negative_timestamp() -> None:
    """`isdigit()` liess ein Minus nie zu; `_coerce_int` wuerde es akzeptieren.
    Die zusaetzliche Bereichspruefung haelt das aeussere Verhalten gleich."""
    assert _parse_stripe_header("t=-1700000000,v1=abc") is None
