"""Rechnung je bezahlter Zahlung ueber Mollie Invoicing (ADR-0061 §3, §4, §7; R2a, R2b).

1. **Vormerken** (`InvoiceService.reserve`, aus dem Mollie-Webhook in
   `mollie.py`): eine Zeile `pending` in `billing_invoice`, eine je
   `payment_id` (`UNIQUE`, Migration `billing_0111`). Ab hier ist die
   Rechnung geschuldet. Mehr tut der Webhook nicht: jeder Mollie-Aufruf kostet
   bis zu 5 s, und die Zustellfrist des Webhooks soll nie daran haengen (R2b).
2. **Ausstellen** (`InvoiceService.issue`, aus der Worker-Routine
   `invoice-retry` ueber `run_invoice_retry`): Steuerfall aus den
   Rechnungsdaten der Org und den Schaltern (`tax.decide_tax`), dann
   `POST /v2/sales-invoices` mit `status=paid` und
   `paymentDetails.source=payment`. Vor dem POST wird `post_started_at` atomar
   gesetzt; wer das nicht schafft, POSTet nicht.
3. **Archivieren**: PDF serverseitig ueber `_links.pdfLink` mit dem API-Key
   holen, unveraendert unter `invoices/<org_id>/<jahr>/<nummer>.pdf` im
   BlobStore ablegen (Weiche W61-1 A), SHA-256 in die Zeile.

**Unklare Antwort.** Steht `post_started_at` noch (Timeout, 5xx), ist offen, ob
Mollie die Rechnung angelegt hat. Dann sucht der naechste Lauf sie zuerst ueber
die List-API (`paymentDetails[].sourceReference == payment_id`). Gefunden ⇒
ID und Nummer uebernehmen, kein POST. Sicher nicht gefunden ⇒ Marker loesen,
neu POSTen. Bleibt die Suche selbst unklar ⇒ kein POST (ADR-0061 §4).

**Wiederholung.** Technische Fehler zaehlen `attempts` hoch; der naechste
Versuch kommt nach `retry_backoff` (5 min, verdoppelt, hoechstens 6 h). Nach
`MAX_ATTEMPTS` Fehlern steht die Zeile auf `failed` und der Worker schreibt eine
ERROR-Zeile fuer den Betreiber. Keine Rechnung geht still verloren.

Zurueckgehalten (`pending`, `last_error = "hold:<grund>"`, kein Versuch
gezaehlt, Nachpruefung stuendlich) wird die Rechnung, wenn kein Steuermodus
gesetzt ist, Rechnungsdaten oder Empfaenger-E-Mail fehlen oder der bezahlte
Betrag nicht zum Rechnungsbetrag passt. Eine Rechnung ueber einen anderen
Betrag als den bezahlten entsteht nie.

**Ungepruefte USt-IdNr.** (Weiche W61-3 A): der Worker fragt VIES erneut und
schreibt das Ergebnis in die Rechnungsdaten; danach entscheidet die
Steuerfunktion wie sonst. Hat VIES `VIES_GRACE` (72 h) nach dem Vormerken
noch kein Ergebnis geliefert, wird die Rechnung wie bei ungueltiger Nummer
mit 19 % ausgestellt (Option B) und der Worker schreibt eine WARN-Zeile.

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
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Literal, Protocol, TypeAlias, cast
from uuid import UUID

import asyncpg
import httpx

from who2be_api.blobstore.port import BlobNotFoundError, BlobStorePort
from who2be_api.blobstore.service import build_blob_store
from who2be_api.core.config import Settings, get_settings
from who2be_billing.billing_profile import (
    BillingProfile,
    PgBillingProfileRepository,
    VatChecker,
    ViesVatChecker,
)
from who2be_billing.plans import Plan, plan_by_code
from who2be_billing.tax import (
    MEMO_TEXTS,
    CustomerType,
    InvoiceLocale,
    MemoKey,
    PriceBasis,
    TaxDecision,
    TaxInput,
    TaxMode,
    VatMode,
    VatStatus,
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

#: Wiederholung (ADR-0061 §4, R2b). Erster Versuch sofort, danach 5 min,
#: verdoppelt je Fehler, hoechstens 6 h. Nach `MAX_ATTEMPTS` Fehlern ist die
#: Zeile `failed` (rund 16 h nach dem ersten Fehler).
RETRY_BASE = timedelta(minutes=5)
RETRY_MAX = timedelta(hours=6)
MAX_ATTEMPTS = 8
#: Zurueckgehaltene Zeilen (`hold:*`) prueft der Worker so oft erneut.
HOLD_RECHECK = timedelta(hours=1)
#: W61-3 A: so lange wartet eine Rechnung mit ungepruefter USt-IdNr. auf VIES,
#: gerechnet ab dem Vormerken. Danach Option B (19 %, Betreiber-Hinweis).
VIES_GRACE = timedelta(hours=72)
#: Zeilen je Worker-Lauf; der Rest kommt im naechsten Lauf (alle 5 min).
RETRY_BATCH = 25

#: List-API (`GET /v2/sales-invoices`) hat keinen Filter nach Zahlung
#: (Referenz „List sales invoices“: nur `from`, `limit`). Gelesen wird
#: seitenweise, hoechstens so viele Seiten; danach gilt die Suche als unklar.
LIST_PAGE_SIZE = 250
MAX_LIST_PAGES = 4

_HOLD_PREFIX = "hold:"

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
    #: Technische Fehlversuche (zurueckgehaltene Laeufe zaehlen nicht).
    attempts: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


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


@dataclass(frozen=True)
class FoundInvoice:
    """Rechnung, die die List-API zu einer Zahlung gefunden hat (R2b).

    Steuerangaben stammen aus der Mollie-Rechnung selbst: sie ist das, was
    ausgestellt wurde, auch wenn sich Schalter oder Rechnungsdaten seit dem
    POST geaendert haben.
    """

    created: CreatedInvoice
    vat_rate: Decimal
    vat_mode: VatMode
    recipient_type: CustomerType
    has_vat_number: bool
    memo_key: MemoKey | None

    def decision(self) -> TaxDecision:
        return TaxDecision(
            action="issue",
            hold_reason=None,
            vat_rate=self.vat_rate,
            vat_mode=self.vat_mode,
            recipient_type=self.recipient_type,
            include_vat_number=self.has_vat_number,
            memo_key=self.memo_key,
        )


# --- Ports -------------------------------------------------------------------------


class InvoiceRepository(Protocol):
    async def reserve(self, data: InvoiceReservation) -> InvoiceRecord:
        """Legt die Zeile an oder liefert die schon vorhandene zur `payment_id`."""
        ...

    async def get(self, invoice_id: UUID) -> InvoiceRecord | None: ...

    async def open_invoices(self, limit: int = ...) -> list[InvoiceRecord]:
        """Zeilen in `pending` oder `issued`, am laengsten unberuehrte zuerst."""
        ...

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
        tax_mode: TaxMode | None,
        price_basis: PriceBasis,
        decision: TaxDecision,
        issued_at: datetime,
    ) -> InvoiceRecord | None: ...

    async def mark_archived(self, invoice_id: UUID, *, pdf_key: str, pdf_sha256: str) -> None: ...

    async def record_error(self, invoice_id: UUID, error: str) -> None:
        """Haelt den letzten Fehler fest, ohne Status oder Versuche zu aendern."""
        ...

    async def record_failure(self, invoice_id: UUID, error: str) -> InvoiceStatus | None:
        """Zaehlt einen Fehlversuch. Ab `MAX_ATTEMPTS` wird `pending` zu `failed`.

        Liefert den Status danach. `issued` wird nie `failed`: die Rechnung
        existiert bei Mollie, nur das Archiv fehlt noch.
        """
        ...


class InvoiceProfileRepository(Protocol):
    """Was der Rechnungsweg an den Rechnungsdaten braucht."""

    async def get(self, org_id: UUID) -> BillingProfile | None: ...

    async def update_vat_status(
        self, org_id: UUID, vat_id: str, status: VatStatus, checked_at: datetime
    ) -> None: ...


class SalesInvoiceGateway(Protocol):
    """Schmale Grenze zur Mollie-API fuer Rechnungen (Tests setzen einen Fake ein)."""

    async def customer_email(self, customer_id: str) -> str | None: ...

    async def create_sales_invoice(self, payload: dict[str, Any]) -> CreatedInvoice: ...

    async def find_invoice_for_payment(self, payment_id: str) -> FoundInvoice | None:
        """Sucht die Rechnung zur Zahlung ueber die List-API.

        `None` heisst: sicher keine. Ist das nicht sicher (Fehler, Seitenlimit),
        wirft sie `InvoiceUncertainError`.
        """
        ...

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


def retry_backoff(attempts: int) -> timedelta:
    """Wartezeit nach `attempts` Fehlversuchen: 0, 5 min, 10 min … hoechstens 6 h."""
    if attempts <= 0:
        return timedelta(0)
    backoff: timedelta = RETRY_BASE * 2 ** min(attempts - 1, 16)
    return min(backoff, RETRY_MAX)


def is_held(record: InvoiceRecord) -> bool:
    """Zurueckgehalten (`hold:*`): wartet auf Daten, nicht auf einen Wiederholversuch."""
    return record.last_error is not None and record.last_error.startswith(_HOLD_PREFIX)


def is_due(record: InvoiceRecord, now: datetime) -> bool:
    """Ob der Worker die Zeile in diesem Lauf anfasst (Backoff bzw. Nachpruefung)."""
    if record.status not in ("pending", "issued"):
        return False
    if record.updated_at is None:
        return True
    waited = now - record.updated_at
    if record.status == "pending" and is_held(record):
        return waited >= HOLD_RECHECK
    if record.attempts <= 0:
        return True  # noch kein Fehlversuch: sofort (auch bei Uhrenversatz DB/Worker)
    return waited >= retry_backoff(record.attempts)


def _price_basis_of(vat_mode: VatMode) -> PriceBasis:
    return "net" if vat_mode == "exclusive" else "gross"


_COUNTERS = ("open", "due", "issued", "archived", "held", "failed", "vies_fallback")


# --- Anwendungsfall ----------------------------------------------------------------


class InvoiceService:
    """Vormerken (Webhook), Ausstellen und Archivieren (Worker). `issue` wirft nie."""

    def __init__(
        self,
        repo: InvoiceRepository,
        profiles: InvoiceProfileRepository,
        gateway: SalesInvoiceGateway,
        blob_store: BlobStorePort | None,
        *,
        tax_mode: TaxMode | None,
        price_basis: PriceBasis,
        vat_checker: VatChecker | None = None,
    ) -> None:
        self._repo = repo
        self._profiles = profiles
        self._gateway = gateway
        self._blob_store = blob_store
        self._tax_mode = tax_mode
        self._price_basis = price_basis
        self._vat_checker = vat_checker
        self._vies_fallbacks = 0

    async def reserve(self, data: InvoiceReservation) -> InvoiceRecord:
        """Rechnung zur Zahlung vormerken (idempotent je `payment_id`)."""
        return await self._repo.reserve(data)

    async def issue(self, invoice_id: UUID, *, now: datetime | None = None) -> InvoiceRecord | None:
        """Stellt aus und archiviert, soweit moeglich. Fehler landen in der Zeile."""
        try:
            return await self._issue(invoice_id, now or datetime.now(UTC))
        except Exception as exc:  # noqa: BLE001 - ein Fehler gilt nur dieser Zeile
            logger.exception("Rechnung %s: unerwarteter Fehler", invoice_id)
            try:
                await self._fail(invoice_id, f"unexpected:{type(exc).__name__}")
            except Exception:  # noqa: BLE001
                logger.exception("Rechnung %s: Fehler nicht speicherbar", invoice_id)
            return None

    async def retry_open_invoices(
        self, now: datetime, *, limit: int = RETRY_BATCH
    ) -> dict[str, int]:
        """Ein Lauf der Worker-Routine `invoice-retry`: faellige Zeilen abarbeiten.

        Liefert nur Zaehler (ADR-0057 §4). `failed` und `vies_fallback` sind die
        Faelle fuer den Betreiber; beide stehen zusaetzlich als ERROR- bzw.
        WARN-Zeile im Worker-Log.
        """
        counters = dict.fromkeys(_COUNTERS, 0)
        rows = await self._repo.open_invoices()
        counters["open"] = len(rows)
        self._vies_fallbacks = 0
        for row in [row for row in rows if is_due(row, now)][:limit]:
            counters["due"] += 1
            after = await self.issue(row.id, now=now)
            if after is None:
                continue
            if after.status in ("failed", "archived", "issued"):
                counters[after.status] += 1
            elif is_held(after):
                counters["held"] += 1
        counters["vies_fallback"] = self._vies_fallbacks
        return counters

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

    async def _fail(self, invoice_id: UUID, error: str) -> None:
        """Zaehlt einen Fehlversuch; beim letzten ein Hinweis an den Betreiber."""
        status = await self._repo.record_failure(invoice_id, _short(error))
        if status == "failed":
            logger.error(
                "Rechnung %s endgueltig fehlgeschlagen nach %d Versuchen (%s). Betreiber: in "
                "Mollie pruefen, ob zur Zahlung schon eine Rechnung existiert, sonst von Hand "
                "ausstellen.",
                invoice_id,
                MAX_ATTEMPTS,
                _short(error),
            )

    async def _lookup(
        self, record: InvoiceRecord, now: datetime
    ) -> tuple[InvoiceRecord, str | None] | bool:
        """Nach einem unklaren POST: erst nachschlagen, nie blind neu POSTen.

        Gefunden ⇒ ausgestellte Zeile (ohne POST). Sicher keine ⇒ `True`, der
        Marker ist geloest und der Aufrufer darf POSTen. Unklar ⇒ `False`.
        """
        try:
            found = await self._gateway.find_invoice_for_payment(record.payment_id)
        except InvoiceUncertainError as exc:
            logger.warning("Rechnung %s: Suche unklar (%s), kein POST", record.id, exc.reason)
            await self._fail(record.id, f"lookup:{exc.reason}")
            return False
        if found is None:
            logger.info("Rechnung %s: Mollie hat keine Rechnung zur Zahlung, neuer POST", record.id)
            await self._repo.release_post(record.id, "lookup:not_found")
            return True
        decision = found.decision()
        issued = await self._repo.mark_issued(
            record.id,
            found.created,
            tax_mode=self._tax_mode,
            price_basis=_price_basis_of(decision.vat_mode),
            decision=decision,
            issued_at=now,
        )
        if issued is None:
            return False
        logger.info("Rechnung %s: bei Mollie gefunden, ohne neuen POST uebernommen", record.id)
        return issued, found.created.pdf_url

    async def _hold(self, record: InvoiceRecord, reason: str) -> None:
        if reason == "tax_mode_missing":
            logger.warning(
                "Rechnung %s zurueckgehalten: WHO2BE_INVOICE_TAX_MODE ist nicht gesetzt.",
                record.id,
            )
        else:
            logger.info("Rechnung %s zurueckgehalten: %s", record.id, reason)
        await self._repo.record_error(record.id, f"{_HOLD_PREFIX}{reason}")

    async def _recheck_vat(
        self, record: InvoiceRecord, profile: BillingProfile, now: datetime
    ) -> BillingProfile:
        """W61-3 A: ungepruefte USt-IdNr. bei VIES nachpruefen, nach 72 h Option B.

        Ein Ergebnis (`valid`/`invalid`) geht in die Rechnungsdaten, damit auch
        der naechste Checkout es kennt. Bleibt VIES bis `VIES_GRACE` nach dem
        Vormerken stumm, gilt die Nummer fuer DIESE Rechnung als ungueltig (19 %);
        die Rechnungsdaten bleiben `unchecked`.
        """
        vat_id = profile.vat_id
        if vat_id is None:
            return profile
        if self._vat_checker is not None:
            status: VatStatus = await self._vat_checker.check(vat_id)
            if status != "unchecked":
                await self._profiles.update_vat_status(record.org_id, vat_id, status, now)
                logger.info("Rechnung %s: USt-IdNr. nachgeprueft (%s)", record.id, status)
                return profile.model_copy(update={"vat_status": status, "vat_checked_at": now})
        if record.created_at is not None and now - record.created_at >= VIES_GRACE:
            self._vies_fallbacks += 1
            logger.warning(
                "Rechnung %s: USt-IdNr. nach 72 h weiter ungeprueft, Ausstellung mit 19 %% "
                "(W61-3, Option B). Betreiber: Steuerfall pruefen.",
                record.id,
            )
            return profile.model_copy(update={"vat_status": "invalid"})
        return profile

    def _decide(self, profile: BillingProfile) -> TaxDecision:
        return decide_tax(
            TaxInput(
                tax_mode=self._tax_mode,
                price_basis=self._price_basis,
                country=profile.country,
                customer_type=profile.customer_type,
                vat_id=profile.vat_id,
                vat_status=profile.vat_status,
            )
        )

    async def _prepare(
        self, record: InvoiceRecord, now: datetime
    ) -> tuple[dict[str, Any], TaxDecision] | str:
        """Baut den POST-Body oder liefert den Grund, warum zurueckgehalten wird."""
        if self._tax_mode is None:
            return "tax_mode_missing"
        plan = plan_by_code(record.plan_code)
        if plan is None:
            return "plan_unknown"
        profile = await self._profiles.get(record.org_id)
        if profile is None:
            return "profile_missing"
        decision = self._decide(profile)
        if decision.hold_reason == "vat_id_unchecked":
            profile = await self._recheck_vat(record, profile, now)
            decision = self._decide(profile)
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
            # Ein frueherer POST endete ohne klare Antwort. Erst die List-API.
            looked_up = await self._lookup(record, now)
            if looked_up is False:
                return None
            if looked_up is not True:
                return looked_up
        prepared = await self._prepare(record, now)
        if isinstance(prepared, str):
            await self._hold(record, prepared)
            return None
        payload, decision = prepared
        if not await self._repo.start_post(record.id):
            return None
        try:
            created = await self._gateway.create_sales_invoice(payload)
        except InvoiceRejectedError as exc:
            logger.warning("Rechnung %s von Mollie abgelehnt: %s", record.id, exc.reason)
            await self._repo.release_post(record.id, _short(f"rejected:{exc.reason}"))
            await self._fail(record.id, f"rejected:{exc.reason}")
            return None
        except InvoiceUncertainError as exc:
            logger.warning(
                "Rechnung %s: Antwort unklar (%s), naechster Lauf sucht", record.id, exc.reason
            )
            await self._fail(record.id, f"uncertain:{exc.reason}")
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
            await self._fail(record.id, "archive:blobstore_unconfigured")
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
            await self._fail(record.id, f"archive:{exc}")
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


async def run_invoice_retry(
    conn: asyncpg.Connection, now: datetime, settings: Settings | None = None
) -> dict[str, int]:
    """Einstieg der Worker-Routine `invoice-retry` (ADR-0057, ADR-0061 §4).

    Der Kern ruft das ueber einen dynamischen Import (ADR-0029). Ohne Mollie-Key
    gibt es nichts auszustellen; offene Zeilen bleiben stehen (fail closed).
    """
    settings = settings or get_settings()
    repo = PgInvoiceRepository(conn)
    if not settings.mollie_api_key:
        open_rows = await repo.open_invoices()
        if open_rows:
            logger.warning(
                "invoice-retry: MOLLIE_API_KEY fehlt, %d Rechnungen offen.", len(open_rows)
            )
        return {"open": len(open_rows), "unconfigured": 1}
    service = InvoiceService(
        repo,
        PgBillingProfileRepository(conn),
        HttpSalesInvoiceGateway(settings.mollie_api_key),
        build_blob_store(settings),
        tax_mode=settings.invoice_tax_mode,
        price_basis=settings.invoice_price_basis,
        vat_checker=ViesVatChecker(),
    )
    return await service.retry_open_invoices(now)


# --- Repository --------------------------------------------------------------------

_COLUMNS = (
    "id, org_id, payment_id, customer_id, plan_code, amount_value, period_start, period_end, "
    "status, post_started_at, mollie_invoice_id, invoice_number, issued_at, pdf_key, "
    "pdf_sha256, last_error, attempts, created_at, updated_at"
)

#: Obergrenze, wie viele offene Zeilen ein Worker-Lauf liest (Faelligkeit
#: entscheidet danach `is_due`). Mehr offene Zeilen sind kein Normalbetrieb.
OPEN_SCAN_LIMIT = 500

Executor: TypeAlias = asyncpg.Pool | asyncpg.Connection


def _record(row: asyncpg.Record) -> InvoiceRecord:
    return InvoiceRecord(**dict(row))


class PgInvoiceRepository:
    """asyncpg-Implementierung ohne Org-Scope (Webhook auf dem Pool, Worker auf der Connection)."""

    def __init__(self, pool: Executor) -> None:
        self._pool = pool

    async def open_invoices(self, limit: int = OPEN_SCAN_LIMIT) -> list[InvoiceRecord]:
        rows = await self._pool.fetch(
            f"SELECT {_COLUMNS} FROM billing_invoice WHERE status IN ('pending', 'issued') "  # noqa: S608
            "ORDER BY updated_at, id LIMIT $1",
            limit,
        )
        return [_record(row) for row in rows]

    async def record_failure(self, invoice_id: UUID, error: str) -> InvoiceStatus | None:
        status = await self._pool.fetchval(
            """
            UPDATE billing_invoice
               SET attempts = attempts + 1, last_error = $2,
                   status = CASE WHEN status = 'pending' AND attempts + 1 >= $3
                                 THEN 'failed' ELSE status END
             WHERE id = $1 AND status IN ('pending', 'issued')
            RETURNING status
            """,
            invoice_id,
            _short(error),
            MAX_ATTEMPTS,
        )
        return cast("InvoiceStatus | None", status)

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
            "UPDATE billing_invoice SET post_started_at = now() "
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
        tax_mode: TaxMode | None,
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

    async def find_invoice_for_payment(self, payment_id: str) -> FoundInvoice | None:
        """List-API seitenweise nach `paymentDetails[].sourceReference` durchsuchen.

        Die API filtert nicht nach Zahlung; neueste zuerst, hoechstens
        `MAX_LIST_PAGES` Seiten. Ohne Treffer bis zur letzten Seite ⇒ `None`;
        bricht die Suche vorher ab (Fehler, Seitenlimit) ⇒ unklar.
        """
        if not PAYMENT_ID_PATTERN.fullmatch(payment_id):
            raise InvoiceUncertainError("payment_id_unusable")
        url: str | None = f"{self._base_url}/sales-invoices?limit={LIST_PAGE_SIZE}"
        pages = 0
        async with self._client() as client:
            while url is not None:
                if pages >= MAX_LIST_PAGES:
                    raise InvoiceUncertainError("list_page_limit")
                pages += 1
                try:
                    response = await client.get(url)
                except httpx.HTTPError as exc:
                    raise InvoiceUncertainError(f"list:{type(exc).__name__}") from exc
                if response.status_code != httpx.codes.OK:
                    raise InvoiceUncertainError(f"list_http_{response.status_code}")
                try:
                    body = response.json()
                except ValueError as exc:
                    raise InvoiceUncertainError("list_unreadable") from exc
                invoices, url = _list_page(body)
                for invoice in invoices:
                    if _references_payment(invoice, payment_id):
                        return _found_invoice(invoice)
                if url is not None and not _is_mollie_api_url(url):
                    raise InvoiceUncertainError("list_next_foreign")
        return None

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


def _list_page(body: object) -> tuple[list[dict[str, Any]], str | None]:
    """Eintraege und `_links.next.href` einer List-Antwort; Form falsch ⇒ unklar."""
    if not isinstance(body, dict):
        raise InvoiceUncertainError("list_unreadable")
    embedded = body.get("_embedded")
    items = embedded.get("sales_invoices") if isinstance(embedded, dict) else None
    if not isinstance(items, list):
        raise InvoiceUncertainError("list_unreadable")
    links = body.get("_links")
    nxt = links.get("next") if isinstance(links, dict) else None
    href = nxt.get("href") if isinstance(nxt, dict) else None
    return [item for item in items if isinstance(item, dict)], (
        href if isinstance(href, str) and href else None
    )


def _references_payment(invoice: dict[str, Any], payment_id: str) -> bool:
    details = invoice.get("paymentDetails")
    entries = details if isinstance(details, list) else [details]
    return any(
        isinstance(entry, dict)
        and entry.get("source") == "payment"
        and entry.get("sourceReference") == payment_id
        for entry in entries
    )


def _memo_key(memo: object) -> MemoKey | None:
    """Vermerk-Schluessel zum Mollie-`memo` (exakt einer unserer Texte, sonst unklar)."""
    if memo is None or memo == "":
        return None
    for key, texts in MEMO_TEXTS.items():
        if memo in texts.values():
            return key
    raise InvoiceUncertainError("found_memo_unknown")


def _found_invoice(invoice: dict[str, Any]) -> FoundInvoice:
    """Gefundene Rechnung samt Steuerangaben; was fehlt oder fremd ist ⇒ unklar.

    Unklar heisst hier: kein zweiter POST, die Zeile laeuft ueber den Backoff
    nach `failed` und landet beim Betreiber. Lieber von Hand als doppelt.
    """
    created = _created_invoice(invoice)
    vat_mode = invoice.get("vatMode")
    recipient = invoice.get("recipient")
    lines = invoice.get("lines")
    rate_raw = (
        lines[0].get("vatRate")
        if isinstance(lines, list) and lines and isinstance(lines[0], dict)
        else None
    )
    if vat_mode not in ("exclusive", "inclusive") or not isinstance(recipient, dict):
        raise InvoiceUncertainError("found_fields_missing")
    recipient_type = recipient.get("type")
    if recipient_type not in ("business", "consumer"):
        raise InvoiceUncertainError("found_fields_missing")
    try:
        vat_rate = Decimal(str(rate_raw)).quantize(_CENT)
    except (InvalidOperation, ValueError) as exc:
        raise InvoiceUncertainError("found_fields_missing") from exc
    return FoundInvoice(
        created=created,
        vat_rate=vat_rate,
        vat_mode=cast("VatMode", vat_mode),
        recipient_type=cast("CustomerType", recipient_type),
        has_vat_number=bool(recipient.get("vatNumber")),
        memo_key=_memo_key(invoice.get("memo")),
    )
