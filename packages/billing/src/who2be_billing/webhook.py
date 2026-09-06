"""Cloud-Billing-Adapter: Webhook-Signatur + Event→Entitlement (Plan §3.5/§3.6).

Bewusst **nicht im Kern** (Guardrail §3.6 "Keine Billing-Logik im Anwendungskern"):
dieses Modul wird nur unter `is_cloud()` vom `billing`-Router aktiviert. Es uebersetzt
Provider-Ereignisse in ein `Entitlement` — der Zahlungsanbieter meldet nur, die App
entscheidet.

Signatur (Guardrail §3.6 "Webhooks ohne Signaturpruefung verarbeiten" verboten):
- **Stripe-Schema** ``t=<ts>,v1=<hex>`` ⇒ HMAC-SHA256 ueber ``"<ts>.<body>"``. Der
  Zeitstempel steht im **Header** und wird vom Absender bei jeder Zustellung neu
  gestempelt/signiert (auch bei einem Retry) — ein enges Toleranzfenster
  (Minuten, `_SIGNATURE_TOLERANCE_SECONDS`) schuetzt hier nur vor der
  Verzoegerung einer einzelnen HTTP-Zustellung.
- **Generisches Schema** (Mollie u. a.): roher Hex-HMAC ueber den Body, optional
  mit ``sha256=``-Praefix. Der Zeitstempel (`created`) steckt hier im
  HMAC-**gedeckten Body** — ein Retry muss byte-identisch bleiben, kann `created`
  also NICHT auffrischen. Das Fenster ist deshalb bewusst weit
  (`_GENERIC_EVENT_MAX_AGE_SECONDS`, Groessenordnung Tage): es weist nur uralte
  Bodies ab, nicht legitime Retries nach einem Ausfall. Der wirksame
  Replay-Schutz ist hier der Dedupe-Ledger (`router.py`,
  `ProcessedEventRepository`), nicht dieses Fenster.
Beide Pfade vergleichen **konstant-zeitlich** und validieren den Kandidaten
zuvor als reinen Hex-String (ASCII) — `hmac.compare_digest` wirft sonst
`TypeError` bei Nicht-ASCII-Zeichen; leeres Secret ⇒ fail closed.

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
import math
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from who2be_api.licensing.entitlement import Entitlement

# Toleranz fuer den Stripe-Zeitstempel (Replay-Schutz). Der Wert steht im
# HEADER (`t=…`) und wird vom Absender bei JEDER Zustellung — auch einem Retry
# — neu gestempelt und neu signiert. Die Pruefung schuetzt also nur vor der
# Verzoegerung EINER HTTP-Zustellung, nicht vor dem Alter des Ereignisses
# selbst; ein enges Fenster (Minuten) ist hier richtig.
_SIGNATURE_TOLERANCE_SECONDS = 5 * 60

# Plausibilitaets-Fenster fuer das GENERISCHE Schema (Issue #452, Befund 1 aus
# dem Nachtrag). Hier steckt der Zeitstempel (`created`) im HMAC-**gedeckten
# Body**, nicht im Header — der Absender kann ihn bei einem Retry NICHT neu
# stempeln, ohne die Signatur zu brechen (er muesste exakt denselben Body
# erneut senden). Ein Retry Stunden oder Tage nach dem urspruenglichen
# Ereignis ist normal (Ausfall, Backoff) und traegt weiterhin den alten
# `created`-Wert. Ein enges Fenster wie beim Stripe-Zweig wuerde solche
# legitimen Retries dauerhaft abweisen — besonders gefaehrlich bei einem
# Revoke-Event (Kuendigung), das dann nie mehr ankommt und den Zugriff
# faelschlich aktiv liesse.
#
# Der wirksame Replay-Schutz ist deshalb NICHT dieses Fenster, sondern der
# Dedupe-Ledger (`ProcessedEventRepository`, Massnahme 2 in `router.py`): ein
# einmal beanspruchtes Ereignis kann nie ein zweites Mal wirken, unabhaengig
# vom Alter. Dieses Fenster ist nur eine Plausibilitaetsgrenze gegen uralte,
# irgendwo aufgezeichnete Bodies — GROESSENORDNUNG TAGE, nicht Minuten.
_GENERIC_EVENT_MAX_AGE_SECONDS = 7 * 24 * 60 * 60  # 7 Tage

# Maximaler Horizont fuer ein Grant-Periodenende (Issue #452, Befund 2 aus dem
# Nachtrag): Massnahme 1 verlangt nicht nur IRGENDein Periodenende, sondern ein
# PLAUSIBLES — ohne Obergrenze waere z. B. `current_period_end: 253402300799`
# (Jahr 9999) inhaltlich dasselbe unbefristete Entitlement, nur anders
# geschrieben. ~13 Monate deckt ein Jahresabo (12 Monate) plus einen
# Erneuerungs-Puffer ab; aktuell verkauft die App nur ein Monatsabo
# (`plans.py:PRO_PLAN.interval == "1 month"`), aber das generische Format ist
# anbieteragnostisch und soll nicht an das aktuelle Plan-Sortiment gekoppelt
# sein.
_MAX_PERIOD_HORIZON = timedelta(days=396)  # ~13 Monate

# Reiner Hex-Digest (SHA-256 ⇒ 64 Zeichen). Vor jedem `hmac.compare_digest`
# geprueft (Issue #452, Befund 4 aus dem Nachtrag): `compare_digest` akzeptiert
# bei `str`-Operanden nur ASCII und wirft sonst `TypeError` — ein
# Nicht-ASCII-Header (Starlette dekodiert Header als latin-1, h11 erlaubt
# 0x80–0xFF im Wert) wuerde sonst einen unauthentifizierten 500 statt eines
# regulaeren `False` ausloesen.
_HEX64_RE = re.compile(r"[0-9a-fA-F]{64}")

# Ganzzahl-Zeitstempel als String: nur ASCII-Ziffern, optional ein
# Minuszeichen, hart laengenbegrenzt (Issue #452, Befund 3 aus dem Nachtrag).
# `str.isdigit()` akzeptiert Unicode-Ziffern (z. B. Hochzahlen) sowie — nach
# einem `lstrip("-")` — mehrere Minuszeichen; beides bricht an `int(...)` mit
# `ValueError`. Eine harte Laengengrenze verhindert zusaetzlich, dass ein sehr
# langer Ziffernstring an CPythons Integer-String-Konvertierungslimit stoesst
# (ebenfalls `ValueError`, ab ca. 4300 Stellen).
_TIMESTAMP_STR_RE = re.compile(r"-?[0-9]{1,18}")


def _coerce_int(raw: Any) -> int | None:
    """Wandelt einen Rohwert sicher in `int`, ohne je eine Exception zu werfen.

    Deckt Issue #452 Befund 3 ab: `NaN`/`Infinity` (von `json.loads` per
    Default akzeptiert) brechen bei `int(float(...))` mit `OverflowError`;
    ein `bool` ist in Python ein `int` (`isinstance(True, int)` ⇒ `True`) und
    soll trotzdem nie als Zeitstempel durchgehen. Alle unbrauchbaren Faelle
    liefern `None` statt eine Exception durchzulassen — der Aufrufer behandelt
    das wie "unlesbar" (fail closed).
    """
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        if not math.isfinite(raw):
            return None
        try:
            return int(raw)
        except (OverflowError, ValueError):
            return None
    if isinstance(raw, str):
        candidate = raw.strip()
        if not _TIMESTAMP_STR_RE.fullmatch(candidate):
            return None
        try:
            return int(candidate)
        except (ValueError, OverflowError):
            return None
    return None


def _safe_fromtimestamp(ts: int) -> datetime:
    """`datetime.fromtimestamp` ohne durchschlagende Exception (Befund 3).

    Ein extremer, aber laut `_coerce_int`/`_TIMESTAMP_STR_RE` formal gueltiger
    Wert (z. B. nahe der `int64`-Grenze) kann `OverflowError` oder
    plattformabhaengig `OSError`/`ValueError` ausloesen.
    """
    try:
        return datetime.fromtimestamp(ts, tz=UTC)
    except (OverflowError, OSError, ValueError) as exc:
        raise WebhookError(
            "Webhook-Zeitstempel liegt ausserhalb des darstellbaren Bereichs."
        ) from exc


class WebhookError(Exception):
    """Webhook-Body ist unbrauchbar (Signatur, JSON oder Pflichtfelder)."""


def _parse_stripe_header(header: str) -> tuple[int, str] | None:
    timestamp: int | None = None
    signature: str | None = None
    for part in header.split(","):
        key, _, value = part.strip().partition("=")
        if key == "t":
            # `_coerce_int` statt `value.isdigit()` (Issue #463 Punkt 5): der
            # alte Test war zu freundlich UND zu naiv. `"²".isdigit()` ist
            # `True`, `int("²")` wirft aber `ValueError`; und ein sehr langer
            # Ziffernstring reisst CPythons Konversionslimit (~4300 Stellen,
            # ebenfalls `ValueError`). Beides schlug bisher als unbehandelte
            # Exception durch diese Funktion hindurch. Der Helfer wurde fuer
            # genau dieses Muster eingefuehrt (s. Kommentar bei `_coerce_int`).
            # Negative Werte bleiben abgewiesen wie zuvor — `isdigit()` liess
            # sie nie zu, und das aeussere Verhalten soll sich nicht aendern.
            parsed = _coerce_int(value)
            timestamp = parsed if parsed is not None and parsed >= 0 else None
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
    except ValueError:
        # `ValueError` statt nur `json.JSONDecodeError`/`UnicodeDecodeError`
        # (Issue #452 Befund 3): ein extrem langes Ziffern-Literal im Body
        # laesst `json.loads` selbst an CPythons Integer-String-Konvertierungs-
        # limit scheitern — mit einem nackten `ValueError`, keiner
        # `JSONDecodeError`. `JSONDecodeError`/`UnicodeDecodeError` sind beide
        # `ValueError`-Subklassen, das breitere except deckt also weiterhin
        # alles vorher Abgedeckte ab.
        return None
    if not isinstance(data, dict):
        return None
    return _coerce_int(data.get("created"))


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
        if not _HEX64_RE.fullmatch(signature):
            # Fail closed statt `TypeError`: `hmac.compare_digest` akzeptiert
            # bei `str`-Operanden nur ASCII (Befund 4) — ein Header darf hier
            # trotzdem Nicht-ASCII-Bytes tragen (Starlette dekodiert als
            # latin-1). Ein `v1=`-Wert, der nicht wie ein Hex-Digest aussieht,
            # ist ohnehin nie gueltig.
            return False
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
    if not _HEX64_RE.fullmatch(candidate):
        # Siehe Kommentar im Stripe-Zweig oben (Befund 4) — derselbe Grund.
        return False
    expected = hmac.new(secret_bytes, payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, candidate):
        return False

    # Plausibilitaets-Fenster auch im generischen Schema (Issue #452,
    # Massnahme 3 + Befund 1 aus dem Nachtrag): der Zeitstempel kommt mangels
    # Header-Zeitbezug aus dem Event-Payload selbst; fehlt er, wird
    # fail-closed abgewiesen. Bewusst `_GENERIC_EVENT_MAX_AGE_SECONDS`
    # (Tage), NICHT `_SIGNATURE_TOLERANCE_SECONDS` (Minuten) — siehe Kommentar
    # an der Konstante: ein Retry kann `created` nicht auffrischen, ohne die
    # Signatur zu brechen.
    created = _extract_event_timestamp(payload)
    if created is None:
        return False
    reference = now if now is not None else time.time()
    return abs(reference - created) <= _GENERIC_EVENT_MAX_AGE_SECONDS


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
    # `_coerce_int` statt nacktem `int(raw)` (Issue #452 Befund 3): derselbe
    # Metadaten-Kanal kann `NaN`/`Infinity` tragen, die `int(float(...))` mit
    # `OverflowError` statt `ValueError` quittiert — hier bislang unbehandelt.
    value = _coerce_int(raw)
    if value is None:
        raise WebhookError(f"Webhook-Metadatum '{key}' ist keine Ganzzahl.")
    return value


def _parse_period_end(
    obj: dict[str, Any], metadata: dict[str, Any], *, now: datetime | None = None
) -> datetime:
    """Liest das Periodenende eines Grant-Events. **Pflicht und plausibel.**

    Issue #452, Massnahme 1: ein Grant-Event ohne auflösbares Periodenende darf
    niemals ein unbefristetes Entitlement erzeugen (das wuerde die
    Ablaufpruefung in `Entitlement.is_active()` folgenlos umgehen). Statt
    stillschweigend `None` zurueckzugeben, wird fail-closed abgelehnt — ein
    Entitlement ohne Ablauf bleibt exklusiv dem OSS-/On-Prem-Default vorbehalten
    (`licensing/entitlement.py:OSS_ENTITLEMENT`).

    Befund 2 (Nachtrag): reine Existenz reicht nicht — ein Periodenende in der
    Vergangenheit (formal aktives, faktisch totes Entitlement) oder Jahre in
    der Zukunft (`current_period_end: 253402300799` waere inhaltlich wieder
    unbefristet) wird ebenso abgelehnt. Siehe `_MAX_PERIOD_HORIZON` fuer die
    Begruendung der Obergrenze.
    """
    raw = obj.get("current_period_end") or metadata.get("expires_at")
    if raw is None:
        raise WebhookError(
            "Grant-Event ohne Periodenende ('current_period_end'/'expires_at') "
            "wird abgelehnt — ein Provider-Ereignis darf kein unbefristetes "
            "Entitlement erzeugen."
        )
    if isinstance(raw, int | float):
        as_int = _coerce_int(raw)
        if as_int is None:
            raise WebhookError("Webhook-'current_period_end' ist keine gueltige Zahl.")
        parsed = _safe_fromtimestamp(as_int)
    elif isinstance(raw, str):
        as_int = _coerce_int(raw)
        if as_int is not None:
            parsed = _safe_fromtimestamp(as_int)
        else:
            try:
                candidate = datetime.fromisoformat(raw)
            except ValueError as exc:
                raise WebhookError("Webhook-'current_period_end' ist kein ISO-Datum.") from exc
            parsed = candidate if candidate.tzinfo else candidate.replace(tzinfo=UTC)
    else:
        raise WebhookError("Webhook-'current_period_end' hat einen unerwarteten Typ.")

    reference = now or datetime.now(UTC)
    if parsed <= reference:
        raise WebhookError(
            "Grant-Event-Periodenende liegt nicht in der Zukunft — kein aktives Entitlement."
        )
    if parsed - reference > _MAX_PERIOD_HORIZON:
        raise WebhookError(
            "Grant-Event-Periodenende liegt weiter als der Maximalhorizont "
            f"({_MAX_PERIOD_HORIZON.days} Tage) in der Zukunft."
        )
    return parsed


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
