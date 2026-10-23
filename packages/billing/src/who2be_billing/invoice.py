"""Rechnung je bezahlter Zahlung ueber Mollie Invoicing (ADR-0061 §3, §4, §7; Paket R2a).

Ablauf, aufgerufen aus dem Mollie-Webhook (`mollie.py`):

1. **Vormerken** (`InvoiceService.reserve`): eine Zeile `pending` in
   `billing_invoice`, eine je `payment_id` (`UNIQUE`, Migration
   `billing_0111`). Ab hier ist die Rechnung geschuldet.
2. **Ausstellen** (`InvoiceService.issue`): Steuerfall aus den Rechnungsdaten
   der Org und den Schaltern (`tax.decide_tax`), dann
   `POST /v2/sales-invoices` mit `status=paid` und
   `paymentDetails.source=payment`. Vor dem POST wird `post_started_at` atomar
   gesetzt; wer das nicht schafft, POSTet nicht.
3. **Archivieren**: PDF serverseitig ueber `_links.pdfLink` mit dem API-Key
   holen, unveraendert unter `invoices/<org_id>/<jahr>/<nummer>.pdf` im
   BlobStore ablegen (Weiche W61-1 A), SHA-256 in die Zeile.

Fehler brechen den Webhook nie ab. Die Zeile bleibt `pending` bzw. `issued`
und traegt `last_error`; den Retry baut R2b (Worker `invoice-retry`). Ist nach
einem Timeout offen, ob Mollie die Rechnung angelegt hat, bleibt
`post_started_at` stehen: dann darf nur die List-API-Suche (R2b) weitermachen,
nie ein zweiter POST.

Zurueckgehalten (`pending`, `last_error = "hold:<grund>"`) wird die Rechnung,
wenn kein Steuermodus gesetzt ist, die USt-IdNr. ungeprueft ist, Rechnungsdaten
oder Empfaenger-E-Mail fehlen oder der bezahlte Betrag nicht zum Rechnungsbetrag
passt. Eine Rechnung ueber einen anderen Betrag als den bezahlten entsteht nie.

> **Keine Steuer- oder Rechtsberatung.** Steuerfall und Vermerke kommen aus
> `tax.py` und sind mit dem Steuerberater zu bestaetigen.

Beispiele in Tests verwenden nur Platzhalter (oeffentliches Repo).
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Literal, Protocol
from uuid import UUID

import asyncpg
import httpx

from who2be_api.blobstore.port import BlobNotFoundError, BlobStorePort
from who2be_billing.billing_profile import BillingProfile, BillingProfileRepository
from who2be_billing.plans import Plan, plan_by_code
from who2be_billing.tax import (
    InvoiceLocale,
    PriceBasis,
    TaxDecision,
    TaxInput,
    TaxMode,
    decide_tax,
    invoice_locale,
    memo_text,
)

logger = logging.getLogger(__name__)

InvoiceStatus = Literal["pending", "issued", "archived", "failed"]

#: Mollie-API, gegen die Rechnungen ausgestellt und PDFs geholt werden. Der
#: API-Key geht nie an einen anderen Host (pdfLink wird dagegen geprueft).
MOLLIE_API_BASE = "https://api.mollie.com/v2"
_MOLLIE_API_HOST = "api.mollie.com"

#: Zeitgrenzen je Aufruf. Der Webhook wartet darauf; was laenger dauert, holt
#: der Worker nach (R2b).
MOLLIE_INVOICE_TIMEOUT = httpx.Timeout(5.0, connect=2.0)

#: Obergrenze fuer ein Rechnungs-PDF (Testbericht P3d: rund 170 KB).
MAX_PDF_BYTES = 10 * 1024 * 1024

#: Mollie begrenzt die Positionsbeschreibung auf 100 Zeichen (Testbericht P4).
MAX_LINE_DESCRIPTION = 100

#: Laenge von `last_error` (CHECK in `billing_0111`).
MAX_ERROR_LENGTH = 500

PAYMENT_ID_PATTERN = re.compile(r"^tr_[A-Za-z0-9]{1,64}$")
CUSTOMER_ID_PATTERN = re.compile(r"^cst_[A-Za-z0-9]{1,64}$")
_INVOICE_ID = re.compile(r"^invoice_[A-Za-z0-9]{1,64}$")
_INVOICE_NUMBER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_ERROR_FIELD = re.compile(r"^[A-Za-z0-9.\[\]_]{1,80}$")
_INTERVAL = re.compile(r"^(\d{1,2}) months?$")

_CENT = Decimal("0.01")


# --- Fehler ------------------------------------------------------------------------


class InvoiceRejectedError(Exception):
    """Mollie hat die Anfrage sicher NICHT ausgefuehrt (4xx, kein Verbindungsaufbau).

    Ein neuer Versuch darf neu POSTen. `reason` ist kurz und ohne Personendaten,
    er landet in `last_error`.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class InvoiceUncertainError(Exception):
    """Unklar, ob Mollie die Rechnung angelegt hat (Timeout, 5xx, kaputte Antwort).

    Ein neuer POST koennte eine zweite Rechnung erzeugen; R2b sucht zuerst ueber
    die List-API.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class InvoiceArchiveError(Exception):
    """PDF ist nicht abrufbar oder nicht ablegbar; die Rechnung bleibt `issued`."""


# --- Werte -------------------------------------------------------------------------


@dataclass(frozen=True)
class InvoiceRecord:
    """Eine Zeile aus `billing_invoice`."""

    id: UUID
    org_id: UUID
    payment_id: str
    customer_id: str | None
    plan_code: str
    amount_value: Decimal | None
    period_start: date
    period_end: date
    status: InvoiceStatus
    post_started_at: datetime | None = None
    mollie_invoice_id: str | None = None
    invoice_number: str | None = None
    issued_at: datetime | None = None
    pdf_key: str | None = None
    pdf_sha256: str | None = None
    last_error: str | None = None


@dataclass(frozen=True)
class InvoiceReservation:
    """Was der Webhook zur Zahlung weiss, wenn er die Rechnung vormerkt."""

    org_id: UUID
    payment_id: str
    customer_id: str | None
    plan_code: str
    amount_value: Decimal | None
    period_start: date
    period_end: date


@dataclass(frozen=True)
class CreatedInvoice:
    """Antwort von `POST /v2/sales-invoices`, auf das Noetige reduziert."""

    id: str
    invoice_number: str
    pdf_url: str | None


# --- Ports -------------------------------------------------------------------------


class InvoiceRepository(Protocol):
    async def reserve(self, data: InvoiceReservation) -> InvoiceRecord:
        """Legt die Zeile an oder liefert die schon vorhandene zur `payment_id`."""
        ...

    async def get(self, invoice_id: UUID) -> InvoiceRecord | None: ...

    async def start_post(self, invoice_id: UUID) -> bool:
        """Setzt `post_started_at` atomar. False ⇒ jemand anderes POSTet bzw. hat."""
        ...

    async def release_post(self, invoice_id: UUID, error: str) -> None:
        """Mollie hat sicher nichts angelegt: `post_started_at` zuruecksetzen."""
        ...

    async def mark_issued(
        self,
        invoice_id: UUID,
        created: CreatedInvoice,
        *,
        tax_mode: TaxMode,
        price_basis: PriceBasis,
        decision: TaxDecision,
        issued_at: datetime,
    ) -> InvoiceRecord | None: ...

    async def mark_archived(self, invoice_id: UUID, *, pdf_key: str, pdf_sha256: str) -> None: ...

    async def record_error(self, invoice_id: UUID, error: str) -> None:
        """Haelt den letzten Fehler fest, ohne den Status zu aendern."""
        ...


class SalesInvoiceGateway(Protocol):
    """Schmale Grenze zur Mollie-API fuer Rechnungen (Tests setzen einen Fake ein)."""

    async def customer_email(self, customer_id: str) -> str | None: ...

    async def create_sales_invoice(self, payload: dict[str, Any]) -> CreatedInvoice: ...

    async def pdf_url(self, invoice_id: str) -> str | None: ...

    async def fetch_pdf(self, url: str) -> bytes: ...


# --- reine Bausteine ---------------------------------------------------------------


def _add_months(start: date, months: int) -> date:
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = start.day
    while day > 28:
        try:
            return date(year, month, day)
        except ValueError:
            day -= 1
    return date(year, month, day)


def service_period(plan: Plan, start: date) -> tuple[date, date]:
    """Leistungszeitraum einer bezahlten Periode: Starttag bis Tag vor dem naechsten."""
    match = _INTERVAL.fullmatch(plan.interval.strip())
    if match is None:
        raise ValueError(f"Plan-Intervall nicht unterstuetzt: {plan.interval!r}")
    end = _add_months(start, int(match.group(1))) - timedelta(days=1)
    return start, end


def line_description(plan: Plan, start: date, end: date, locale: InvoiceLocale) -> str:
    """Positionsbeschreibung mit Leistungszeitraum, hoechstens 100 Zeichen."""
    if locale == "de_DE":
        text = f"Who2Be {plan.name}, Leistungszeitraum {start:%d.%m.%Y} bis {end:%d.%m.%Y}"
    else:
        text = f"Who2Be {plan.name}, service period {start:%d/%m/%Y} to {end:%d/%m/%Y}"
    return text[:MAX_LINE_DESCRIPTION]


def expected_total(plan: Plan, decision: TaxDecision) -> Decimal:
    """Bruttobetrag, den die Rechnung ausweist (eine Position, Menge 1).

    Preisbasis brutto: der Planpreis enthaelt die Steuer schon (W61-2 A, auch
    bei 0 % derselbe Betrag). Preisbasis netto: Planpreis plus Steuer.
    """
    price = Decimal(plan.price_eur)
    if decision.vat_mode == "inclusive":
        return price.quantize(_CENT)
    vat = (price * decision.vat_rate / Decimal(100)).quantize(_CENT, rounding=ROUND_HALF_UP)
    return (price + vat).quantize(_CENT)


def _recipient(profile: BillingProfile, decision: TaxDecision, email: str) -> dict[str, Any]:
    recipient: dict[str, Any] = {
        "type": decision.recipient_type,
        "email": email,
        "streetAndNumber": profile.street,
        "postalCode": profile.postal_code,
        "city": profile.city,
        "country": profile.country,
        "locale": invoice_locale(profile.country),
    }
    if decision.recipient_type == "business":
        recipient["organizationName"] = profile.company_name
        if decision.include_vat_number and profile.vat_id:
            recipient["vatNumber"] = profile.vat_id
    else:
        recipient["givenName"] = profile.given_name
        recipient["familyName"] = profile.family_name
    return recipient


def build_sales_invoice_payload(
    record: InvoiceRecord,
    *,
    profile: BillingProfile,
    decision: TaxDecision,
    plan: Plan,
    email: str,
) -> dict[str, Any]:
    """Body fuer `POST /v2/sales-invoices` (ADR-0061 §3 Schritt 4).

    `vatScheme=standard`, weil das Konto nicht fuer OSS registriert ist
    (Testbericht P2b). Kein `emailDetails`: Who2Be verschickt die Rechnung
    nicht ueber Mollie, sie liegt im eigenen Archiv. Kein `testmode`: der
    Modus folgt dem API-Key (Create-Sales-Invoice-Referenz).
    """
    locale = invoice_locale(profile.country)
    payload: dict[str, Any] = {
        "currency": "EUR",
        "status": "paid",
        "vatScheme": "standard",
        "vatMode": decision.vat_mode,
        "recipientIdentifier": f"org-{record.org_id}",
        "recipient": _recipient(profile, decision, email),
        "lines": [
            {
                "description": line_description(
                    plan, record.period_start, record.period_end, locale
                ),
                "quantity": 1,
                "vatRate": f"{decision.vat_rate:.2f}",
                "unitPrice": {"currency": "EUR", "value": plan.price_eur},
            }
        ],
        "paymentDetails": {"source": "payment", "sourceReference": record.payment_id},
    }
    if decision.memo_key is not None:
        payload["memo"] = memo_text(decision.memo_key, locale)
    return payload


def archive_key(org_id: UUID, issued_at: datetime, invoice_number: str) -> str:
    """Ablageort `invoices/<org_id>/<jahr>/<nummer>.pdf` (W61-1 A).

    Bewusst ausserhalb von `blobs/<workspace_id>/`, den der Workspace-Purge
    raeumt. Die Nummer kommt von Mollie und wird vor dem Key-Bau geprueft.
    """
    if not _INVOICE_NUMBER.fullmatch(invoice_number):
        raise InvoiceArchiveError("invoice_number_unusable")
    return f"invoices/{org_id}/{issued_at.year:04d}/{invoice_number}.pdf"


def _short(error: str) -> str:
    return error[:MAX_ERROR_LENGTH]


# --- Anwendungsfall ----------------------------------------------------------------


class InvoiceService:
    """Vormerken, Ausstellen, Archivieren. `issue` wirft nie."""

    def __init__(
        self,
        repo: InvoiceRepository,
        profiles: BillingProfileRepository,
        gateway: SalesInvoiceGateway,
        blob_store: BlobStorePort | None,
        *,
        tax_mode: TaxMode | None,
        price_basis: PriceBasis,
    ) -> None:
        self._repo = repo
        self._profiles = profiles
        self._gateway = gateway
        self._blob_store = blob_store
        self._tax_mode = tax_mode
        self._price_basis = price_basis

    async def reserve(self, data: InvoiceReservation) -> InvoiceRecord:
        """Rechnung zur Zahlung vormerken (idempotent je `payment_id`)."""
        return await self._repo.reserve(data)

    async def issue(self, invoice_id: UUID, *, now: datetime | None = None) -> InvoiceRecord | None:
        """Stellt aus und archiviert, soweit moeglich. Fehler landen in der Zeile."""
        try:
            return await self._issue(invoice_id, now or datetime.now(UTC))
        except Exception as exc:  # noqa: BLE001 - der Webhook darf hieran nie scheitern
            logger.exception("Rechnung %s: unerwarteter Fehler", invoice_id)
            try:
                await self._repo.record_error(invoice_id, f"unexpected:{type(exc).__name__}")
            except Exception:  # noqa: BLE001
                logger.exception("Rechnung %s: Fehler nicht speicherbar", invoice_id)
            return None

    async def _issue(self, invoice_id: UUID, now: datetime) -> InvoiceRecord | None:
        record = await self._repo.get(invoice_id)
        if record is None:
            return None
        pdf_url: str | None = None
        if record.status == "pending":
            outcome = await self._post(record, now)
            if outcome is None:
                return await self._repo.get(invoice_id)
            record, pdf_url = outcome
        if record.status == "issued":
            await self._archive(record, pdf_url)
            return await self._repo.get(invoice_id)
        return record

    async def _hold(self, record: InvoiceRecord, reason: str) -> None:
        if reason == "tax_mode_missing":
            logger.warning(
                "Rechnung %s zurueckgehalten: WHO2BE_INVOICE_TAX_MODE ist nicht gesetzt.",
                record.id,
            )
        else:
            logger.info("Rechnung %s zurueckgehalten: %s", record.id, reason)
        await self._repo.record_error(record.id, f"hold:{reason}")

    async def _prepare(self, record: InvoiceRecord) -> tuple[dict[str, Any], TaxDecision] | str:
        """Baut den POST-Body oder liefert den Grund, warum zurueckgehalten wird."""
        if self._tax_mode is None:
            return "tax_mode_missing"
        plan = plan_by_code(record.plan_code)
        if plan is None:
            return "plan_unknown"
        profile = await self._profiles.get(record.org_id)
        if profile is None:
            return "profile_missing"
        decision = decide_tax(
            TaxInput(
                tax_mode=self._tax_mode,
                price_basis=self._price_basis,
                country=profile.country,
                customer_type=profile.customer_type,
                vat_id=profile.vat_id,
                vat_status=profile.vat_status,
            )
        )
        if decision.action == "hold":
            return decision.hold_reason or "tax"
        if record.amount_value is None or record.amount_value != expected_total(plan, decision):
            return "amount_mismatch"
        email = None
        if record.customer_id and CUSTOMER_ID_PATTERN.fullmatch(record.customer_id):
            email = await self._gateway.customer_email(record.customer_id)
        if not email:
            return "email_missing"
        payload = build_sales_invoice_payload(
            record, profile=profile, decision=decision, plan=plan, email=email
        )
        return payload, decision

    async def _post(
        self, record: InvoiceRecord, now: datetime
    ) -> tuple[InvoiceRecord, str | None] | None:
        if record.post_started_at is not None:
            # Ein frueherer POST endete ohne klare Antwort. Ob Mollie angelegt
            # hat, klaert nur die List-API (R2b) — hier kein zweiter POST.
            return None
        prepared = await self._prepare(record)
        if isinstance(prepared, str):
            await self._hold(record, prepared)
            return None
        payload, decision = prepared
        assert self._tax_mode is not None  # von _prepare geprueft
        if not await self._repo.start_post(record.id):
            return None
        try:
            created = await self._gateway.create_sales_invoice(payload)
        except InvoiceRejectedError as exc:
            logger.warning("Rechnung %s von Mollie abgelehnt: %s", record.id, exc.reason)
            await self._repo.release_post(record.id, _short(f"rejected:{exc.reason}"))
            return None
        except InvoiceUncertainError as exc:
            logger.warning("Rechnung %s: Antwort unklar (%s), Worker klaert", record.id, exc.reason)
            await self._repo.record_error(record.id, _short(f"uncertain:{exc.reason}"))
            return None
        issued = await self._repo.mark_issued(
            record.id,
            created,
            tax_mode=self._tax_mode,
            price_basis=self._price_basis,
            decision=decision,
            issued_at=now,
        )
        if issued is None:
            return None
        logger.info("Rechnung %s ausgestellt", record.id)
        return issued, created.pdf_url

    async def _archive(self, record: InvoiceRecord, pdf_url: str | None) -> None:
        if self._blob_store is None:
            await self._repo.record_error(record.id, "archive:blobstore_unconfigured")
            return
        if record.mollie_invoice_id is None or record.invoice_number is None:
            return  # durch billing_invoice_issued_check ausgeschlossen
        try:
            url = pdf_url or await self._gateway.pdf_url(record.mollie_invoice_id)
            if url is None:
                raise InvoiceArchiveError("pdf_link_missing")
            pdf = await self._gateway.fetch_pdf(url)
            issued_at = record.issued_at or datetime.now(UTC)
            key = archive_key(record.org_id, issued_at, record.invoice_number)
            digest = hashlib.sha256(pdf).hexdigest()
            await self._store_once(key, pdf, digest)
        except (InvoiceArchiveError, InvoiceRejectedError, InvoiceUncertainError) as exc:
            logger.warning("Rechnung %s: Archiv fehlgeschlagen (%s)", record.id, exc)
            await self._repo.record_error(record.id, _short(f"archive:{exc}"))
            return
        await self._repo.mark_archived(record.id, pdf_key=key, pdf_sha256=digest)

    async def _store_once(self, key: str, pdf: bytes, digest: str) -> None:
        """Legt das PDF ab, ueberschreibt aber nie ein anderes unter demselben Key."""
        assert self._blob_store is not None
        try:
            existing = await self._blob_store.get(key)
        except BlobNotFoundError:
            await self._blob_store.put(key, pdf, "application/pdf")
            return
        if hashlib.sha256(existing).hexdigest() != digest:
            raise InvoiceArchiveError("archive_key_taken")


# --- Repository --------------------------------------------------------------------

_COLUMNS = (
    "id, org_id, payment_id, customer_id, plan_code, amount_value, period_start, period_end, "
    "status, post_started_at, mollie_invoice_id, invoice_number, issued_at, pdf_key, "
    "pdf_sha256, last_error"
)


def _record(row: asyncpg.Record) -> InvoiceRecord:
    return InvoiceRecord(**dict(row))


class PgInvoiceRepository:
    """asyncpg-Implementierung auf dem App-Pool (Webhook ohne Org-Scope)."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def reserve(self, data: InvoiceReservation) -> InvoiceRecord:
        row = await self._pool.fetchrow(
            f"""
            INSERT INTO billing_invoice (org_id, payment_id, customer_id, plan_code,
                                         amount_value, period_start, period_end)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (payment_id) DO NOTHING
            RETURNING {_COLUMNS}
            """,  # noqa: S608 - _COLUMNS ist eine Konstante
            data.org_id,
            data.payment_id,
            data.customer_id,
            data.plan_code,
            data.amount_value,
            data.period_start,
            data.period_end,
        )
        if row is None:
            row = await self._pool.fetchrow(
                f"SELECT {_COLUMNS} FROM billing_invoice WHERE payment_id = $1",  # noqa: S608
                data.payment_id,
            )
        assert row is not None  # Konflikt heisst: die Zeile existiert
        return _record(row)

    async def get(self, invoice_id: UUID) -> InvoiceRecord | None:
        row = await self._pool.fetchrow(
            f"SELECT {_COLUMNS} FROM billing_invoice WHERE id = $1",  # noqa: S608
            invoice_id,
        )
        return _record(row) if row is not None else None

    async def start_post(self, invoice_id: UUID) -> bool:
        claimed = await self._pool.fetchval(
            "UPDATE billing_invoice SET post_started_at = now(), attempts = attempts + 1 "
            "WHERE id = $1 AND status = 'pending' AND post_started_at IS NULL RETURNING id",
            invoice_id,
        )
        return claimed is not None

    async def release_post(self, invoice_id: UUID, error: str) -> None:
        await self._pool.execute(
            "UPDATE billing_invoice SET post_started_at = NULL, last_error = $2 "
            "WHERE id = $1 AND status = 'pending'",
            invoice_id,
            _short(error),
        )

    async def mark_issued(
        self,
        invoice_id: UUID,
        created: CreatedInvoice,
        *,
        tax_mode: TaxMode,
        price_basis: PriceBasis,
        decision: TaxDecision,
        issued_at: datetime,
    ) -> InvoiceRecord | None:
        row = await self._pool.fetchrow(
            f"""
            UPDATE billing_invoice
               SET status = 'issued', mollie_invoice_id = $2, invoice_number = $3,
                   tax_mode = $4, price_basis = $5, vat_rate = $6, memo_key = $7,
                   issued_at = $8, last_error = NULL
             WHERE id = $1 AND status = 'pending'
            RETURNING {_COLUMNS}
            """,  # noqa: S608 - _COLUMNS ist eine Konstante
            invoice_id,
            created.id,
            created.invoice_number,
            tax_mode,
            price_basis,
            decision.vat_rate,
            decision.memo_key,
            issued_at,
        )
        return _record(row) if row is not None else None

    async def mark_archived(self, invoice_id: UUID, *, pdf_key: str, pdf_sha256: str) -> None:
        await self._pool.execute(
            "UPDATE billing_invoice SET status = 'archived', pdf_key = $2, pdf_sha256 = $3, "
            "archived_at = now(), last_error = NULL WHERE id = $1 AND status = 'issued'",
            invoice_id,
            pdf_key,
            pdf_sha256,
        )

    async def record_error(self, invoice_id: UUID, error: str) -> None:
        await self._pool.execute(
            "UPDATE billing_invoice SET last_error = $2 WHERE id = $1",
            invoice_id,
            _short(error),
        )


# --- Mollie-HTTP-Gateway -----------------------------------------------------------


def _is_mollie_api_url(url: str) -> bool:
    try:
        parsed = httpx.URL(url)
    except (httpx.InvalidURL, TypeError):
        return False
    return parsed.scheme == "https" and parsed.host == _MOLLIE_API_HOST and parsed.port is None


def _rejection_reason(response: httpx.Response) -> str:
    """`http_<code>` plus Feldname aus der Mollie-Fehlerantwort, nie `detail`.

    `detail` kann Eingaben zurueckspiegeln (Adresse, E-Mail); in `last_error`
    gehoert nur, was keine Personendaten traegt.
    """
    reason = f"http_{response.status_code}"
    try:
        body = response.json()
    except ValueError:
        return reason
    field = body.get("field") if isinstance(body, dict) else None
    if isinstance(field, str) and _ERROR_FIELD.fullmatch(field):
        reason = f"{reason}:{field}"
    return reason


class HttpSalesInvoiceGateway:
    """Sales Invoices API ueber httpx (das Mollie-SDK kennt sie nicht).

    Fehlerklassen fuer den POST: sicher nicht ausgefuehrt (Verbindung kam nicht
    zustande, 4xx) ⇒ `InvoiceRejectedError`; alles danach (Lese-Timeout, 5xx,
    unlesbare Antwort) ⇒ `InvoiceUncertainError`.
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = MOLLIE_API_BASE,
        timeout: httpx.Timeout = MOLLIE_INVOICE_TIMEOUT,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("MOLLIE_API_KEY ist nicht konfiguriert.")
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=self._timeout,
            transport=self._transport,
            headers=self._headers,
            follow_redirects=False,
        )

    async def customer_email(self, customer_id: str) -> str | None:
        if not CUSTOMER_ID_PATTERN.fullmatch(customer_id):
            return None
        try:
            async with self._client() as client:
                response = await client.get(f"{self._base_url}/customers/{customer_id}")
            if response.status_code != httpx.codes.OK:
                logger.info("Mollie-Customer nicht lesbar: HTTP %s", response.status_code)
                return None
            email = response.json().get("email")
        except (httpx.HTTPError, ValueError, AttributeError) as exc:
            logger.info("Mollie-Customer nicht lesbar: %s", type(exc).__name__)
            return None
        return email if isinstance(email, str) and "@" in email else None

    async def create_sales_invoice(self, payload: dict[str, Any]) -> CreatedInvoice:
        try:
            async with self._client() as client:
                response = await client.post(f"{self._base_url}/sales-invoices", json=payload)
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout) as exc:
            raise InvoiceRejectedError(type(exc).__name__) from exc
        except httpx.HTTPError as exc:
            raise InvoiceUncertainError(type(exc).__name__) from exc
        if 400 <= response.status_code < 500:
            raise InvoiceRejectedError(_rejection_reason(response))
        if response.status_code != httpx.codes.CREATED:
            raise InvoiceUncertainError(f"http_{response.status_code}")
        try:
            body = response.json()
        except ValueError as exc:
            raise InvoiceUncertainError("body_unreadable") from exc
        return _created_invoice(body)

    async def pdf_url(self, invoice_id: str) -> str | None:
        if not _INVOICE_ID.fullmatch(invoice_id):
            return None
        try:
            async with self._client() as client:
                response = await client.get(f"{self._base_url}/sales-invoices/{invoice_id}")
            if response.status_code != httpx.codes.OK:
                return None
            return _pdf_href(response.json())
        except (httpx.HTTPError, ValueError) as exc:
            raise InvoiceArchiveError(f"invoice_unreadable:{type(exc).__name__}") from exc

    async def fetch_pdf(self, url: str) -> bytes:
        # Der API-Key geht nur an die Mollie-API, nie an eine fremde Adresse.
        if not _is_mollie_api_url(url):
            raise InvoiceArchiveError("pdf_link_foreign")
        try:
            async with self._client() as client:
                response = await client.get(url)
        except httpx.HTTPError as exc:
            raise InvoiceArchiveError(f"pdf_unreachable:{type(exc).__name__}") from exc
        if response.status_code != httpx.codes.OK:
            raise InvoiceArchiveError(f"pdf_http_{response.status_code}")
        data = response.content
        if len(data) > MAX_PDF_BYTES:
            raise InvoiceArchiveError("pdf_too_large")
        if not data.startswith(b"%PDF-"):
            raise InvoiceArchiveError("pdf_not_a_pdf")
        return data


def _pdf_href(body: object) -> str | None:
    if not isinstance(body, dict):
        return None
    links = body.get("_links")
    pdf = links.get("pdfLink") if isinstance(links, dict) else None
    href = pdf.get("href") if isinstance(pdf, dict) else None
    return href if isinstance(href, str) and href else None


def _created_invoice(body: object) -> CreatedInvoice:
    if not isinstance(body, dict):
        raise InvoiceUncertainError("body_unreadable")
    invoice_id = body.get("id")
    number = body.get("invoiceNumber")
    if not isinstance(invoice_id, str) or not _INVOICE_ID.fullmatch(invoice_id):
        raise InvoiceUncertainError("invoice_id_unusable")
    if not isinstance(number, str) or not _INVOICE_NUMBER.fullmatch(number):
        raise InvoiceUncertainError("invoice_number_unusable")
    return CreatedInvoice(id=invoice_id, invoice_number=number, pdf_url=_pdf_href(body))
