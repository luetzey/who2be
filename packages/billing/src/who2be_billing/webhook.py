"""Cloud-Billing-Adapter: Webhook-Signatur + Event→Entitlement (Plan §3.5/§3.6).

Bewusst **nicht im Kern** (Guardrail §3.6 "Keine Billing-Logik im Anwendungskern"):
dieses Modul wird nur unter `is_cloud()` vom `billing`-Router aktiviert. Es uebersetzt
Provider-Ereignisse in ein `Entitlement` — der Zahlungsanbieter meldet nur, die App
entscheidet.

Signatur (Guardrail §3.6 "Webhooks ohne Signaturpruefung verarbeiten" verboten):
- **Stripe-Schema** ``t=<ts>,v1=<hex>`` ⇒ HMAC-SHA256 ueber ``"<ts>.<body>"`` mit
  Toleranz gegen Replays (Zeitstempel aus dem Header).
- **Generisches Schema** (Mollie u. a.): roher Hex-HMAC ueber den Body, optional mit
  ``sha256=``-Praefix, dieselbe Replay-Toleranz — mangels Header-Zeitbezug gegen
  das `created`-Feld im (HMAC-gedeckten) Payload.
Beide Pfade vergleichen **konstant-zeitlich**; leeres Secret ⇒ fail closed.

Feature-Mapping (Guardrail §3.6 "kein hartkodiertes Produkt→Feature-Mapping"):
die freigeschalteten Codes kommen aus den Provider-**Metadaten**
(`metadata.license_policy`), nicht aus einer Code-Tabelle.

Haertung (Issue #452): ein Grant-Event ohne auflösbares Periodenende wird
abgelehnt statt ein unbefristetes Entitlement zu erzeugen (`_parse_period_end`);
`extract_event_id` liefert die Envelope-ID fuer das Dedupe-Ledger im Router
(`router.py`, dasselbe `ProcessedEventRepository` wie der Mollie-Pfad).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from who2be_api.licensing.entitlement import Entitlement

# Toleranz fuer den Stripe-Zeitstempel (Replay-Schutz).
_SIGNATURE_TOLERANCE_SECONDS = 5 * 60


class WebhookError(Exception):
    """Webhook-Body ist unbrauchbar (Signatur, JSON oder Pflichtfelder)."""


def _parse_stripe_header(header: str) -> tuple[int, str] | None:
    timestamp: int | None = None
    signature: str | None = None
    for part in header.split(","):
        key, _, value = part.strip().partition("=")
        if key == "t" and value.isdigit():
            timestamp = int(value)
        elif key == "v1" and value:
            signature = value
    if timestamp is None or signature is None:
        return None
    return timestamp, signature


def _extract_event_timestamp(payload: bytes) -> int | None:
    """Liest den Ereignis-Zeitstempel (`created`, Stripe-Konvention) aus dem Body.

    Nur fuer das **generische** Signaturschema gebraucht: anders als beim
    Stripe-Schema (`t=…,v1=…`) traegt der Header hier keinen Zeitbezug. Statt
    das Header-Format zu erweitern (das waere ein Vertrag mit einem Anbieter,
    den es fuer dieses Schema nicht gibt), wird die Zeit aus dem Payload
    gelesen, den die HMAC ohnehin komplett deckt. Fehlt/ist unlesbar ⇒ `None`
    — der Aufrufer weist dann fail-closed ab, statt die Pruefung zu ueberspringen.
    """
    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    raw = data.get("created")
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int | float):
        return int(raw)
    if isinstance(raw, str) and raw.strip().lstrip("-").isdigit():
        return int(raw)
    return None


def verify_webhook_signature(
    payload: bytes,
    header: str | None,
    secret: str,
    *,
    now: float | None = None,
) -> bool:
    """True nur bei gueltiger Signatur. Leeres Secret oder fehlender Header ⇒ False."""
    if not secret or not header:
        return False
    secret_bytes = secret.encode("utf-8")

    stripe = _parse_stripe_header(header)
    if stripe is not None:
        timestamp, signature = stripe
        reference = now if now is not None else time.time()
        if abs(reference - timestamp) > _SIGNATURE_TOLERANCE_SECONDS:
            return False
        signed = f"{timestamp}.".encode() + payload
        expected = hmac.new(secret_bytes, signed, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    # Generisches Schema: optionaler `sha256=`-Praefix, sonst roher Hex-Digest.
    candidate = header.strip()
    if candidate.startswith("sha256="):
        candidate = candidate[len("sha256=") :]
    expected = hmac.new(secret_bytes, payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, candidate):
        return False

    # Replay-Toleranz auch im generischen Schema (Issue #452, Massnahme 3):
    # der Zeitstempel kommt mangels Header-Zeitbezug aus dem Event-Payload
    # selbst; fehlt er, wird fail-closed abgewiesen.
    created = _extract_event_timestamp(payload)
    if created is None:
        return False
    reference = now if now is not None else time.time()
    return abs(reference - created) <= _SIGNATURE_TOLERANCE_SECONDS


def parse_event(payload: bytes) -> dict[str, Any]:
    """Decodet den Webhook-Body zu JSON (nach erfolgreicher Signaturpruefung)."""
    try:
        event = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise WebhookError("Webhook-Body ist kein gueltiges JSON.") from exc
    if not isinstance(event, dict):
        raise WebhookError("Webhook-Body muss ein JSON-Objekt sein.")
    return event


# Event-Typen, die das Entitlement entziehen (Kuendigung/Fehlzahlung →
# sofort `inactive`, Guardrail §3.6 "Zugriff am Entitlement, nie am Zahlungsstatus").
_REVOKE_EVENTS = frozenset(
    {
        "customer.subscription.deleted",
        "customer.subscription.paused",
        "invoice.payment_failed",
    }
)
_GRANT_EVENTS = frozenset(
    {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.resumed",
        "checkout.session.completed",
        "invoice.paid",
    }
)


def _event_object(event: dict[str, Any]) -> dict[str, Any]:
    data = event.get("data")
    obj = data.get("object") if isinstance(data, dict) else None
    if not isinstance(obj, dict):
        raise WebhookError("Webhook-Event hat kein 'data.object'.")
    return obj


def _metadata(obj: dict[str, Any]) -> dict[str, Any]:
    meta = obj.get("metadata")
    return meta if isinstance(meta, dict) else {}


def _extract_org_id(obj: dict[str, Any], metadata: dict[str, Any]) -> UUID:
    raw = metadata.get("org_id") or obj.get("client_reference_id")
    if not isinstance(raw, str):
        raise WebhookError("Webhook-Event traegt keine 'org_id' (metadata/client_reference_id).")
    try:
        return UUID(raw)
    except ValueError as exc:
        raise WebhookError("Webhook-'org_id' ist keine gueltige UUID.") from exc


def _parse_policy_features(metadata: dict[str, Any]) -> frozenset[str]:
    """Liest die freigeschalteten Feature-Codes aus den Provider-Metadaten.

    `license_policy` ist eine Komma-/Whitespace-separierte Liste von Feature-Codes,
    die der Provider pro Produkt pflegt — **kein** hartkodiertes Mapping hier.
    """
    raw = metadata.get("license_policy") or metadata.get("short_code") or ""
    if not isinstance(raw, str):
        return frozenset()
    tokens = [tok.strip() for tok in raw.replace(",", " ").split()]
    return frozenset(tok for tok in tokens if tok)


def _parse_int_meta(metadata: dict[str, Any], key: str) -> int | None:
    raw = metadata.get(key)
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise WebhookError(f"Webhook-Metadatum '{key}' ist keine Ganzzahl.") from exc


def _parse_period_end(obj: dict[str, Any], metadata: dict[str, Any]) -> datetime:
    """Liest das Periodenende eines Grant-Events. **Pflicht**, keine Ausnahme.

    Issue #452, Massnahme 1: ein Grant-Event ohne auflösbares Periodenende darf
    niemals ein unbefristetes Entitlement erzeugen (das wuerde die
    Ablaufpruefung in `Entitlement.is_active()` folgenlos umgehen). Statt
    stillschweigend `None` zurueckzugeben, wird fail-closed abgelehnt — ein
    Entitlement ohne Ablauf bleibt exklusiv dem OSS-/On-Prem-Default vorbehalten
    (`licensing/entitlement.py:OSS_ENTITLEMENT`).
    """
    raw = obj.get("current_period_end") or metadata.get("expires_at")
    if raw is None:
        raise WebhookError(
            "Grant-Event ohne Periodenende ('current_period_end'/'expires_at') "
            "wird abgelehnt — ein Provider-Ereignis darf kein unbefristetes "
            "Entitlement erzeugen."
        )
    if isinstance(raw, int | float):
        return datetime.fromtimestamp(raw, tz=UTC)
    if isinstance(raw, str):
        if raw.isdigit():
            return datetime.fromtimestamp(int(raw), tz=UTC)
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError as exc:
            raise WebhookError("Webhook-'current_period_end' ist kein ISO-Datum.") from exc
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    raise WebhookError("Webhook-'current_period_end' hat einen unerwarteten Typ.")


@dataclass(frozen=True)
class EntitlementUpdate:
    """Ergebnis des Event-Mappings: was fuer welche Org persistiert wird."""

    org_id: UUID
    entitlement: Entitlement
    external_ref: str | None


def extract_event_id(event: dict[str, Any]) -> str:
    """Liest die Ereignis-Kennung des **Umschlags** (Dedupe-Schluessel).

    Issue #452, Massnahme 2: bewusst die Envelope-ID (top-level `id`, Stripe-
    Konvention z. B. `evt_...`) und **nicht** die Objekt-ID (`data.object.id`),
    die in mehreren Ereignissen wiederkehrt und darum als Dedupe-Schluessel
    ungeeignet waere. Fehlt sie, wird das Ereignis abgelehnt — ohne Schluessel
    kein Dedupe.
    """
    raw = event.get("id")
    if not isinstance(raw, str) or not raw:
        raise WebhookError("Webhook-Event hat keine Ereignis-Kennung ('id').")
    return raw


def map_event_to_entitlement(event: dict[str, Any]) -> EntitlementUpdate | None:
    """Bildet ein Provider-Event auf ein Org-Entitlement ab.

    `None` ⇒ Event ist fuer das Entitlement irrelevant (z. B. ein nicht
    abonnementbezogener Typ) und wird vom Router quittiert, aber ignoriert.
    Grant-Events setzen `active` + Features/Limits aus den Metadaten (das
    Periodenende ist Pflicht, siehe `_parse_period_end`); Revoke-Events setzen
    `inactive` (Zugriff sofort entzogen).
    """
    event_type = event.get("type")
    if not isinstance(event_type, str):
        raise WebhookError("Webhook-Event hat keinen 'type'.")
    if event_type not in _GRANT_EVENTS and event_type not in _REVOKE_EVENTS:
        return None

    obj = _event_object(event)
    metadata = _metadata(obj)
    org_id = _extract_org_id(obj, metadata)
    external_ref = obj.get("id") if isinstance(obj.get("id"), str) else None

    if event_type in _REVOKE_EVENTS:
        entitlement = Entitlement(status="inactive", features=frozenset())
        return EntitlementUpdate(org_id=org_id, entitlement=entitlement, external_ref=external_ref)

    entitlement = Entitlement(
        status="active",
        features=_parse_policy_features(metadata),
        expires_at=_parse_period_end(obj, metadata),
        mcp_monthly_quota=_parse_int_meta(metadata, "mcp_monthly_quota"),
        mcp_rate_per_min=_parse_int_meta(metadata, "mcp_rate_per_min"),
    )
    return EntitlementUpdate(org_id=org_id, entitlement=entitlement, external_ref=external_ref)
