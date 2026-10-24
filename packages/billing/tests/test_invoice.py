"""Rechnung je Zahlung (ADR-0061 §3, §4, §7; Paket R2a).

- Unit-Teil ohne Netz und ohne DB: die Mollie-API ist immer gemockt, entweder
  als Fake-Gateway oder als `httpx.MockTransport` hinter dem echten
  `HttpSalesInvoiceGateway`. Kein Test spricht mit Mollie.
- Integrationsteil auf der echten DB in einem eigenen Schema: Migration
  `billing_0111`, `UNIQUE (payment_id)`, Trigger und der Doppel-Webhook ueber den
  ganzen Service-Pfad (Rot-Probe: ohne UNIQUE wird er rot).

Alle Namen, Adressen, IDs und USt-IdNr. sind Platzhalter (oeffentliches Repo).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import secrets
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import httpx
import pytest
from pydantic import ValidationError

from who2be_api.blobstore.adapters.memory import MemoryBlobStore
from who2be_api.core.config import Settings, get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations, billing_migrations_dir
from who2be_api.licensing.entitlement import Entitlement
from who2be_billing.billing_profile import (
    BillingProfile,
    BillingProfileInput,
    PgBillingProfileRepository,
)
from who2be_billing.invoice import (
    MAX_ATTEMPTS,
    RETRY_BATCH,
    CreatedInvoice,
    FoundInvoice,
    HttpSalesInvoiceGateway,
    InvoiceArchiveError,
    InvoiceRecord,
    InvoiceRejectedError,
    InvoiceReservation,
    InvoiceService,
    InvoiceStatus,
    InvoiceUncertainError,
    PgInvoiceRepository,
    archive_key,
    build_sales_invoice_payload,
    expected_total,
    is_due,
    line_description,
    retry_backoff,
    service_period,
)
from who2be_billing.mollie import MollieBillingService, MolliePayment, MollieSubscription
from who2be_billing.plans import PRO_PLAN
from who2be_billing.processed_event_repository import PgProcessedEventRepository
from who2be_billing.tax import (
    PriceBasis,
    TaxDecision,
    TaxInput,
    TaxMode,
    VatStatus,
    decide_tax,
)

_NOW = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
_PDF = b"%PDF-1.7\n% Platzhalter-PDF fuer Tests\n%%EOF\n"
_PAYMENT = "tr_Platzhalter01"
_CUSTOMER = "cst_Platzhalter01"
_INVOICE_ID = "invoice_Platzhalter01"
_PDF_URL = f"https://api.mollie.com/v2/sales-invoices/{_INVOICE_ID}/pdf"
_EMAIL = "rechnung@example.invalid"

_DE_CONSUMER: dict[str, Any] = {
    "customer_type": "consumer",
    "given_name": "Erika",
    "family_name": "Muster",
    "street": "Musterweg 2",
    "postal_code": "12345",
    "city": "Musterstadt",
    "country": "DE",
}
_AT_BUSINESS: dict[str, Any] = {
    "customer_type": "business",
    "company_name": "Beispiel GmbH",
    "street": "Musterstrasse 1",
    "postal_code": "1010",
    "city": "Musterstadt",
    "country": "AT",
    "vat_id": "ATU00000000",
}


def _profile(data: dict[str, Any], vat_status: str | None = None) -> BillingProfile:
    return BillingProfile.model_validate({**data, "vat_status": vat_status})


def _decision(profile: BillingProfile, tax_mode: TaxMode = "regular") -> TaxDecision:
    return decide_tax(
        TaxInput(
            tax_mode=tax_mode,
            price_basis="net",
            country=profile.country,
            customer_type=profile.customer_type,
            vat_id=profile.vat_id,
            vat_status=profile.vat_status,
        )
    )


# --- Fakes --------------------------------------------------------------------------


class FakeInvoiceRepository:
    """In-Memory-Spiegel von `PgInvoiceRepository` (gleiche Bedingungen in WHERE).

    `now` spielt den Trigger, der bei jedem UPDATE `updated_at` setzt.
    """

    def __init__(self) -> None:
        self.rows: dict[UUID, InvoiceRecord] = {}
        self.issued_with: dict[UUID, tuple[str | None, str]] = {}
        self.now = _NOW

    def _set(self, invoice_id: UUID, **changes: Any) -> None:
        self.rows[invoice_id] = replace(self.rows[invoice_id], updated_at=self.now, **changes)

    async def reserve(self, data: InvoiceReservation) -> InvoiceRecord:
        for row in self.rows.values():
            if row.payment_id == data.payment_id:
                return row
        record = InvoiceRecord(
            id=uuid4(),
            org_id=data.org_id,
            payment_id=data.payment_id,
            customer_id=data.customer_id,
            plan_code=data.plan_code,
            amount_value=data.amount_value,
            period_start=data.period_start,
            period_end=data.period_end,
            status="pending",
            created_at=self.now,
            updated_at=self.now,
        )
        self.rows[record.id] = record
        return record

    async def get(self, invoice_id: UUID) -> InvoiceRecord | None:
        return self.rows.get(invoice_id)

    async def open_invoices(self, limit: int = 500) -> list[InvoiceRecord]:
        rows = [r for r in self.rows.values() if r.status in ("pending", "issued")]
        return sorted(rows, key=lambda r: r.updated_at or _NOW)[:limit]

    async def start_post(self, invoice_id: UUID) -> bool:
        row = self.rows[invoice_id]
        if row.status != "pending" or row.post_started_at is not None:
            return False
        self._set(invoice_id, post_started_at=self.now)
        return True

    async def release_post(self, invoice_id: UUID, error: str) -> None:
        row = self.rows[invoice_id]
        if row.status == "pending":
            self._set(invoice_id, post_started_at=None, last_error=error)

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
        row = self.rows[invoice_id]
        if row.status != "pending":
            return None
        self.issued_with[invoice_id] = (tax_mode, price_basis)
        self._set(
            invoice_id,
            status="issued",
            mollie_invoice_id=created.id,
            invoice_number=created.invoice_number,
            issued_at=issued_at,
            last_error=None,
        )
        return self.rows[invoice_id]

    async def mark_archived(self, invoice_id: UUID, *, pdf_key: str, pdf_sha256: str) -> None:
        row = self.rows[invoice_id]
        if row.status == "issued":
            self._set(
                invoice_id,
                status="archived",
                pdf_key=pdf_key,
                pdf_sha256=pdf_sha256,
                last_error=None,
            )

    async def record_error(self, invoice_id: UUID, error: str) -> None:
        self._set(invoice_id, last_error=error)

    async def record_failure(self, invoice_id: UUID, error: str) -> InvoiceStatus | None:
        row = self.rows[invoice_id]
        if row.status not in ("pending", "issued"):
            return None
        attempts = row.attempts + 1
        status: InvoiceStatus = (
            "failed" if row.status == "pending" and attempts >= MAX_ATTEMPTS else row.status
        )
        self._set(invoice_id, attempts=attempts, last_error=error, status=status)
        return status


class FakeProfiles:
    def __init__(self, profile: BillingProfile | None) -> None:
        self.profile = profile
        self.vat_updates: list[tuple[str, str]] = []

    async def get(self, org_id: UUID) -> BillingProfile | None:
        return self.profile

    async def update_vat_status(
        self, org_id: UUID, vat_id: str, status: VatStatus, checked_at: datetime
    ) -> None:
        self.vat_updates.append((vat_id, status))
        if self.profile is not None and self.profile.vat_id == vat_id:
            self.profile = self.profile.model_copy(
                update={"vat_status": status, "vat_checked_at": checked_at}
            )


class FakeVatChecker:
    def __init__(self, status: VatStatus = "unchecked") -> None:
        self.status: VatStatus = status
        self.calls = 0

    async def check(self, vat_id: str) -> VatStatus:
        self.calls += 1
        return self.status


class FakeInvoiceGateway:
    """Fake der Sales Invoices API mit steuerbaren Fehlern.

    Die List-API (`find_invoice_for_payment`) sieht, was `create_sales_invoice`
    angelegt hat, auch wenn der POST danach als unklar geworfen hat — genau
    der Fall eines Lese-Timeouts nach erfolgreicher Anlage.
    """

    def __init__(
        self,
        *,
        email: str | None = _EMAIL,
        create_error: Exception | None = None,
        created_before_error: bool = False,
        lookup_error: Exception | None = None,
        pdf_error: Exception | None = None,
        pdf: bytes = _PDF,
        pdf_url: str | None = _PDF_URL,
    ) -> None:
        self.email = email
        self.create_error = create_error
        self.created_before_error = created_before_error
        self.lookup_error = lookup_error
        self.pdf_error = pdf_error
        self.pdf = pdf
        self.url = pdf_url
        self.payloads: list[dict[str, Any]] = []
        self.pdf_fetches: list[str] = []
        self.lookups: list[str] = []
        self.at_mollie: dict[str, tuple[CreatedInvoice, dict[str, Any]]] = {}

    async def customer_email(self, customer_id: str) -> str | None:
        return self.email

    async def create_sales_invoice(self, payload: dict[str, Any]) -> CreatedInvoice:
        self.payloads.append(payload)
        number = f"I-2026-{len(self.payloads):05d}"
        created = CreatedInvoice(id=_INVOICE_ID, invoice_number=number, pdf_url=self.url)
        if self.create_error is not None and not self.created_before_error:
            raise self.create_error
        self.at_mollie[payload["paymentDetails"]["sourceReference"]] = (created, payload)
        if self.create_error is not None:
            raise self.create_error
        return created

    async def find_invoice_for_payment(self, payment_id: str) -> FoundInvoice | None:
        self.lookups.append(payment_id)
        if self.lookup_error is not None:
            raise self.lookup_error
        hit = self.at_mollie.get(payment_id)
        if hit is None:
            return None
        created, payload = hit
        return FoundInvoice(
            created=created,
            vat_rate=Decimal(payload["lines"][0]["vatRate"]),
            vat_mode=payload["vatMode"],
            recipient_type=payload["recipient"]["type"],
            has_vat_number="vatNumber" in payload["recipient"],
            memo_key=None,
        )

    async def pdf_url(self, invoice_id: str) -> str | None:
        return self.url

    async def fetch_pdf(self, url: str) -> bytes:
        self.pdf_fetches.append(url)
        if self.pdf_error is not None:
            raise self.pdf_error
        return self.pdf


def _reservation(
    org_id: UUID, *, payment_id: str = _PAYMENT, amount: str | None = "11.89"
) -> InvoiceReservation:
    start, end = service_period(PRO_PLAN, date(2026, 10, 20))
    return InvoiceReservation(
        org_id=org_id,
        payment_id=payment_id,
        customer_id=_CUSTOMER,
        plan_code=PRO_PLAN.code,
        amount_value=Decimal(amount) if amount is not None else None,
        period_start=start,
        period_end=end,
    )


def _service(
    *,
    profile: BillingProfile | None = None,
    gateway: FakeInvoiceGateway | None = None,
    repo: FakeInvoiceRepository | None = None,
    blob: MemoryBlobStore | None = None,
    tax_mode: TaxMode | None = "regular",
    with_blob: bool = True,
    profiles: FakeProfiles | None = None,
    vat_checker: FakeVatChecker | None = None,
) -> tuple[InvoiceService, FakeInvoiceRepository, FakeInvoiceGateway, MemoryBlobStore | None]:
    repo = repo or FakeInvoiceRepository()
    gateway = gateway or FakeInvoiceGateway()
    store = (blob or MemoryBlobStore()) if with_blob else None
    service = InvoiceService(
        repo,
        profiles or FakeProfiles(profile if profile is not None else _profile(_DE_CONSUMER)),
        gateway,
        store,
        tax_mode=tax_mode,
        price_basis="net",
        vat_checker=vat_checker,
    )
    return service, repo, gateway, store


def _issue(service: InvoiceService, org_id: UUID, **kwargs: Any) -> InvoiceRecord | None:
    async def _run() -> InvoiceRecord | None:
        record = await service.reserve(_reservation(org_id, **kwargs))
        return await service.issue(record.id, now=_NOW)

    return asyncio.run(_run())


# --- reine Bausteine ----------------------------------------------------------------


def test_service_period_is_one_month_minus_a_day() -> None:
    assert service_period(PRO_PLAN, date(2026, 10, 20)) == (date(2026, 10, 20), date(2026, 11, 19))
    # Monatsende: 31.01. + 1 Monat faellt auf den 28.02., Ende einen Tag davor.
    assert service_period(PRO_PLAN, date(2027, 1, 31)) == (date(2027, 1, 31), date(2027, 2, 27))
    assert service_period(PRO_PLAN, date(2026, 12, 15))[1] == date(2027, 1, 14)


def test_service_period_rejects_an_unknown_interval() -> None:
    with pytest.raises(ValueError, match="Intervall"):
        service_period(replace(PRO_PLAN, interval="14 days"), date(2026, 10, 20))


def test_line_description_carries_the_period_and_stays_within_100_chars() -> None:
    start, end = date(2026, 10, 20), date(2026, 11, 19)
    de = line_description(PRO_PLAN, start, end, "de_DE")
    en = line_description(PRO_PLAN, start, end, "en_GB")
    assert de == "Who2Be Pro, Leistungszeitraum 20.10.2026 bis 19.11.2026"
    assert en == "Who2Be Pro, service period 20/10/2026 to 19/11/2026"
    long_plan = replace(PRO_PLAN, name="X" * 120)
    assert len(line_description(long_plan, start, end, "de_DE")) == 100


def test_expected_total_follows_rate_and_price_basis() -> None:
    de = _decision(_profile(_DE_CONSUMER))
    assert expected_total(PRO_PLAN, de) == Decimal("11.89")  # 9,99 + 19 % (1,8981 → 1,90)
    rc = _decision(_profile(_AT_BUSINESS, "valid"))
    assert expected_total(PRO_PLAN, rc) == Decimal("9.99")
    gross = replace(de, vat_mode="inclusive")
    assert expected_total(PRO_PLAN, gross) == Decimal("9.99")


def test_payload_for_de_consumer() -> None:
    profile = _profile(_DE_CONSUMER)
    record, *_ = _reserved_record()
    payload = build_sales_invoice_payload(
        record, profile=profile, decision=_decision(profile), plan=PRO_PLAN, email=_EMAIL
    )
    assert payload["status"] == "paid"
    assert payload["vatScheme"] == "standard"
    assert payload["vatMode"] == "exclusive"
    assert payload["paymentDetails"] == {"source": "payment", "sourceReference": _PAYMENT}
    assert payload["recipient"]["type"] == "consumer"
    assert payload["recipient"]["givenName"] == "Erika"
    assert payload["recipient"]["locale"] == "de_DE"
    assert "vatNumber" not in payload["recipient"]
    assert "memo" not in payload
    assert "emailDetails" not in payload  # Who2Be verschickt nichts ueber Mollie
    assert "testmode" not in payload  # der Modus folgt dem API-Key
    line = payload["lines"][0]
    assert line["vatRate"] == "19.00"
    assert line["unitPrice"] == {"currency": "EUR", "value": "9.99"}
    assert "20.10.2026 bis 19.11.2026" in line["description"]


def test_payload_for_eu_business_with_reverse_charge() -> None:
    profile = _profile(_AT_BUSINESS, "valid")
    record, *_ = _reserved_record()
    payload = build_sales_invoice_payload(
        record, profile=profile, decision=_decision(profile), plan=PRO_PLAN, email=_EMAIL
    )
    assert payload["recipient"]["type"] == "business"
    assert payload["recipient"]["organizationName"] == "Beispiel GmbH"
    assert payload["recipient"]["vatNumber"] == "ATU00000000"
    assert payload["lines"][0]["vatRate"] == "0.00"
    assert payload["memo"] == "Steuerschuldnerschaft des Leistungsempfängers."


def test_payload_for_third_country_is_english_with_memo() -> None:
    profile = _profile({**_DE_CONSUMER, "country": "US"})
    record, *_ = _reserved_record()
    payload = build_sales_invoice_payload(
        record, profile=profile, decision=_decision(profile), plan=PRO_PLAN, email=_EMAIL
    )
    assert payload["recipient"]["locale"] == "en_GB"
    assert payload["memo"] == "Service not subject to German VAT."
    assert "service period" in payload["lines"][0]["description"]


def test_archive_key_lies_outside_the_workspace_prefix() -> None:
    org = uuid4()
    assert archive_key(org, _NOW, "I-2026-00001") == f"invoices/{org}/2026/I-2026-00001.pdf"
    with pytest.raises(InvoiceArchiveError):
        archive_key(org, _NOW, "../../blobs/x")


def _reserved_record() -> tuple[InvoiceRecord, FakeInvoiceRepository]:
    repo = FakeInvoiceRepository()
    record = asyncio.run(repo.reserve(_reservation(uuid4())))
    return record, repo


# --- Service: Erfolg, Zurueckhalten, Fehler -----------------------------------------


def test_success_issues_once_and_archives_the_unchanged_pdf() -> None:
    org = uuid4()
    service, repo, gateway, store = _service()
    result = _issue(service, org)
    assert result is not None
    assert result.status == "archived"
    assert result.invoice_number == "I-2026-00001"
    assert result.pdf_key == f"invoices/{org}/2026/I-2026-00001.pdf"
    assert result.pdf_sha256 == hashlib.sha256(_PDF).hexdigest()
    assert store is not None
    assert asyncio.run(store.get(result.pdf_key)) == _PDF
    assert len(gateway.payloads) == 1
    assert repo.issued_with[result.id] == ("regular", "net")


def test_without_tax_mode_no_invoice_is_posted() -> None:
    service, repo, gateway, _ = _service(tax_mode=None)
    result = _issue(service, uuid4())
    assert result is not None
    assert result.status == "pending"
    assert result.last_error == "hold:tax_mode_missing"
    assert gateway.payloads == []


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"profile_missing": True}, "hold:profile_missing"),
        ({"email": None}, "hold:email_missing"),
        ({"amount": "9.99"}, "hold:amount_mismatch"),
        ({"amount": None}, "hold:amount_mismatch"),
        ({"vat_unchecked": True}, "hold:vat_id_unchecked"),
    ],
)
def test_invoice_is_held_back_instead_of_guessing(kwargs: dict[str, Any], reason: str) -> None:
    if kwargs.get("profile_missing"):
        profiles = FakeProfiles(None)
    elif kwargs.get("vat_unchecked"):
        profiles = FakeProfiles(_profile(_AT_BUSINESS, "unchecked"))
    else:
        profiles = FakeProfiles(_profile(_DE_CONSUMER))
    gateway = FakeInvoiceGateway(email=kwargs.get("email", _EMAIL))
    repo = FakeInvoiceRepository()
    service = InvoiceService(
        repo, profiles, gateway, MemoryBlobStore(), tax_mode="regular", price_basis="net"
    )
    amount = kwargs.get("amount", "11.89")
    result = _issue(service, uuid4(), amount=amount)
    assert result is not None
    assert result.status == "pending"
    assert result.last_error == reason
    assert result.post_started_at is None  # nichts gePOSTet, Worker darf spaeter
    assert gateway.payloads == []


def test_mollie_422_leaves_the_row_pending_and_retryable() -> None:
    gateway = FakeInvoiceGateway(
        create_error=InvoiceRejectedError("http_422:paymentDetails.sourceReference")
    )
    service, repo, _, _ = _service(gateway=gateway)
    result = _issue(service, uuid4())
    assert result is not None
    assert result.status == "pending"
    assert result.post_started_at is None  # sicher nichts angelegt ⇒ neu POSTen erlaubt
    assert result.last_error == "rejected:http_422:paymentDetails.sourceReference"


def test_timeout_after_creation_is_resolved_by_lookup_without_a_second_post() -> None:
    """Rot-Probe der Karte R2b: Lese-Timeout, aber Mollie HAT angelegt.

    Der naechste Lauf findet die Rechnung ueber die List-API und uebernimmt ID
    und Nummer. Wird die Suche neutralisiert (z. B. `_lookup` liefert immer
    „sicher keine“), POSTet der Lauf ein zweites Mal und dieser Test wird rot.
    """
    gateway = FakeInvoiceGateway(
        create_error=InvoiceUncertainError("ReadTimeout"), created_before_error=True
    )
    service, repo, _, _ = _service(gateway=gateway)
    org = uuid4()
    first = _issue(service, org)
    assert first is not None
    assert first.status == "pending"
    assert first.post_started_at is not None
    assert first.last_error == "uncertain:ReadTimeout"
    assert first.attempts == 1

    gateway.create_error = None
    again = asyncio.run(service.issue(first.id, now=_NOW))
    assert again is not None
    assert gateway.lookups == [_PAYMENT]
    assert len(gateway.payloads) == 1, "zweiter POST trotz vorhandener Rechnung"
    assert again.status == "archived"
    assert again.invoice_number == "I-2026-00001"
    assert repo.issued_with[first.id] == ("regular", "net")


def test_timeout_without_creation_posts_again_after_a_clean_lookup() -> None:
    gateway = FakeInvoiceGateway(create_error=InvoiceUncertainError("ReadTimeout"))
    service, _, _, _ = _service(gateway=gateway)
    first = _issue(service, uuid4())
    assert first is not None
    gateway.create_error = None
    again = asyncio.run(service.issue(first.id, now=_NOW))
    assert again is not None
    assert gateway.lookups == [_PAYMENT]
    assert len(gateway.payloads) == 2  # sicher keine Rechnung ⇒ neuer POST erlaubt
    assert again.status == "archived"


def test_unclear_lookup_never_posts() -> None:
    gateway = FakeInvoiceGateway(
        create_error=InvoiceUncertainError("ReadTimeout"),
        lookup_error=InvoiceUncertainError("list_page_limit"),
    )
    profiles = FakeProfiles(_profile(_DE_CONSUMER))
    service, _, _, _ = _service(gateway=gateway, profiles=profiles)
    first = _issue(service, uuid4())
    assert first is not None
    gateway.create_error = None
    # Fehlen die Daten inzwischen, darf die unklare Suche trotzdem nicht in die
    # Vorbereitung durchfallen: der Grund bleibt die Suche, nicht ein Hold.
    profiles.profile = None
    again = asyncio.run(service.issue(first.id, now=_NOW))
    assert again is not None
    assert again.status == "pending"
    assert again.post_started_at is not None
    assert again.last_error == "lookup:list_page_limit"
    assert again.attempts == 2
    assert len(gateway.payloads) == 1


def test_pdf_failure_leaves_the_invoice_issued() -> None:
    gateway = FakeInvoiceGateway(pdf_error=InvoiceArchiveError("pdf_http_500"))
    service, repo, _, store = _service(gateway=gateway)
    result = _issue(service, uuid4())
    assert result is not None
    assert result.status == "issued"
    assert result.last_error == "archive:pdf_http_500"
    assert store is not None
    assert asyncio.run(store.list_keys("invoices/")) == []

    # Naechster Lauf: kein neuer POST, nur das Archiv wird nachgeholt.
    gateway.pdf_error = None
    again = asyncio.run(service.issue(result.id, now=_NOW))
    assert again is not None
    assert again.status == "archived"
    assert len(gateway.payloads) == 1


def test_missing_blobstore_leaves_the_invoice_issued() -> None:
    service, _, gateway, _ = _service(with_blob=False)
    result = _issue(service, uuid4())
    assert result is not None
    assert result.status == "issued"
    assert result.last_error == "archive:blobstore_unconfigured"
    assert gateway.pdf_fetches == []


def test_archive_never_overwrites_a_different_pdf() -> None:
    org = uuid4()
    store = MemoryBlobStore()
    asyncio.run(store.put(f"invoices/{org}/2026/I-2026-00001.pdf", b"%PDF-anders", "x"))
    service, _, _, _ = _service(blob=store)
    result = _issue(service, org)
    assert result is not None
    assert result.status == "issued"
    assert result.last_error == "archive:archive_key_taken"
    stored = asyncio.run(store.get(f"invoices/{org}/2026/I-2026-00001.pdf"))
    assert stored == b"%PDF-anders"


def test_unexpected_error_never_escapes_issue() -> None:
    class _Broken(FakeProfiles):
        async def get(self, org_id: UUID) -> BillingProfile | None:
            raise RuntimeError("DB weg")

    repo = FakeInvoiceRepository()
    service = InvoiceService(
        repo,
        _Broken(None),
        FakeInvoiceGateway(),
        MemoryBlobStore(),
        tax_mode="regular",
        price_basis="net",
    )
    assert _issue(service, uuid4()) is None
    (row,) = repo.rows.values()
    assert row.status == "pending"
    assert row.last_error == "unexpected:RuntimeError"


def test_parallel_issue_posts_only_once() -> None:
    service, repo, gateway, _ = _service()

    async def _run() -> None:
        record = await service.reserve(_reservation(uuid4()))
        await asyncio.gather(service.issue(record.id, now=_NOW), service.issue(record.id, now=_NOW))

    asyncio.run(_run())
    assert len(gateway.payloads) == 1
    (row,) = repo.rows.values()
    assert row.status == "archived"


# --- Worker `invoice-retry`: Backoff, failed, Hold, VIES (R2b) ----------------------


def test_backoff_doubles_from_five_minutes_and_caps_at_six_hours() -> None:
    assert retry_backoff(0) == timedelta(0)
    assert retry_backoff(1) == timedelta(minutes=5)
    assert retry_backoff(2) == timedelta(minutes=10)
    assert retry_backoff(4) == timedelta(minutes=40)
    assert retry_backoff(7) == timedelta(hours=5, minutes=20)
    assert retry_backoff(8) == timedelta(hours=6)
    assert retry_backoff(50) == timedelta(hours=6)


def test_due_respects_backoff_and_hourly_hold_recheck() -> None:
    record, _ = _reserved_record()
    failed_once = replace(record, attempts=1, updated_at=_NOW, last_error="uncertain:x")
    assert not is_due(failed_once, _NOW + timedelta(minutes=4, seconds=59))
    assert is_due(failed_once, _NOW + timedelta(minutes=5))
    held = replace(record, attempts=0, updated_at=_NOW, last_error="hold:email_missing")
    assert not is_due(held, _NOW + timedelta(minutes=59))
    assert is_due(held, _NOW + timedelta(hours=1))
    assert not is_due(replace(record, status="archived"), _NOW + timedelta(days=1))
    assert not is_due(replace(record, status="failed"), _NOW + timedelta(days=1))


def _run_worker(
    service: InvoiceService, repo: FakeInvoiceRepository, at: datetime
) -> dict[str, int]:
    repo.now = at
    return asyncio.run(service.retry_open_invoices(at))


def test_worker_issues_a_reserved_invoice() -> None:
    service, repo, gateway, _ = _service()
    asyncio.run(service.reserve(_reservation(uuid4())))
    counters = _run_worker(service, repo, _NOW)
    assert counters == {
        "open": 1,
        "due": 1,
        "issued": 0,
        "archived": 1,
        "held": 0,
        "failed": 0,
        "vies_fallback": 0,
    }
    assert len(gateway.payloads) == 1
    # Archiviert ⇒ beim naechsten Lauf nicht mehr offen.
    assert _run_worker(service, repo, _NOW + timedelta(minutes=5))["open"] == 0


def test_worker_retries_with_backoff_and_fails_after_max_attempts(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Gefaelschte Uhr: ein Lauf je faelligem Zeitpunkt, nach 8 Fehlern `failed` + ERROR."""
    gateway = FakeInvoiceGateway(create_error=InvoiceRejectedError("ConnectError"))
    service, repo, _, _ = _service(gateway=gateway)
    record = asyncio.run(service.reserve(_reservation(uuid4())))
    at = _NOW
    for attempt in range(1, MAX_ATTEMPTS + 1):
        assert _run_worker(service, repo, at)["due"] == 1
        assert repo.rows[record.id].attempts == attempt
        # Eine Sekunde vor Ablauf des Backoffs passiert nichts.
        early = at + retry_backoff(attempt) - timedelta(seconds=1)
        if attempt < MAX_ATTEMPTS:
            assert _run_worker(service, repo, early)["due"] == 0
        at = at + retry_backoff(attempt)
    row = repo.rows[record.id]
    assert row.status == "failed"
    assert len(gateway.payloads) == MAX_ATTEMPTS
    assert "endgueltig fehlgeschlagen" in caplog.text
    # failed ist endgueltig: kein weiterer Versuch.
    assert _run_worker(service, repo, at + timedelta(days=1))["open"] == 0


def test_archive_failures_never_turn_an_issued_invoice_into_failed() -> None:
    gateway = FakeInvoiceGateway(pdf_error=InvoiceArchiveError("pdf_http_500"))
    service, repo, _, _ = _service(gateway=gateway)
    record = asyncio.run(service.reserve(_reservation(uuid4())))
    at = _NOW
    for _ in range(MAX_ATTEMPTS + 2):
        _run_worker(service, repo, at)
        at += timedelta(hours=6)
    row = repo.rows[record.id]
    assert row.status == "issued"
    assert row.attempts == MAX_ATTEMPTS + 2
    assert len(gateway.payloads) == 1


def test_held_rows_count_no_attempt() -> None:
    service, repo, gateway, _ = _service(gateway=FakeInvoiceGateway(email=None))
    record = asyncio.run(service.reserve(_reservation(uuid4())))
    for hours in range(0, 30):
        _run_worker(service, repo, _NOW + timedelta(hours=hours))
    row = repo.rows[record.id]
    assert row.status == "pending"
    assert row.last_error == "hold:email_missing"
    assert row.attempts == 0
    assert gateway.payloads == []


def test_worker_batch_is_limited() -> None:
    service, repo, gateway, _ = _service()
    for index in range(RETRY_BATCH + 3):
        asyncio.run(service.reserve(_reservation(uuid4(), payment_id=f"tr_Batch{index}")))
    counters = _run_worker(service, repo, _NOW)
    assert counters["open"] == RETRY_BATCH + 3
    assert counters["due"] == RETRY_BATCH
    assert _run_worker(service, repo, _NOW + timedelta(minutes=5))["due"] == 3


def test_vies_recheck_valid_issues_reverse_charge_and_stores_the_result() -> None:
    profiles = FakeProfiles(_profile(_AT_BUSINESS, "unchecked"))
    checker = FakeVatChecker("valid")
    service, repo, gateway, _ = _service(
        profiles=profiles, vat_checker=checker, repo=FakeInvoiceRepository()
    )
    asyncio.run(service.reserve(_reservation(uuid4(), amount="9.99")))
    counters = _run_worker(service, repo, _NOW + timedelta(hours=1))
    assert counters["archived"] == 1
    assert profiles.vat_updates == [("ATU00000000", "valid")]
    (payload,) = gateway.payloads
    assert payload["lines"][0]["vatRate"] == "0.00"
    assert payload["recipient"]["vatNumber"] == "ATU00000000"


def test_vies_recheck_invalid_issues_with_19_percent() -> None:
    profiles = FakeProfiles(_profile(_AT_BUSINESS, "unchecked"))
    service, repo, gateway, _ = _service(profiles=profiles, vat_checker=FakeVatChecker("invalid"))
    asyncio.run(service.reserve(_reservation(uuid4(), amount="11.89")))
    _run_worker(service, repo, _NOW)
    assert profiles.vat_updates == [("ATU00000000", "invalid")]
    (payload,) = gateway.payloads
    assert payload["lines"][0]["vatRate"] == "19.00"


def test_vies_silent_holds_until_72_hours_then_option_b(caplog: pytest.LogCaptureFixture) -> None:
    """W61-3 A mit gefaelschter Uhr: bis 72 h zurueckhalten, danach 19 % + WARN."""
    profiles = FakeProfiles(_profile(_AT_BUSINESS, "unchecked"))
    checker = FakeVatChecker("unchecked")
    service, repo, gateway, _ = _service(profiles=profiles, vat_checker=checker)
    record = asyncio.run(service.reserve(_reservation(uuid4(), amount="11.89")))

    just_before = _NOW + timedelta(hours=71, minutes=59, seconds=59)
    assert _run_worker(service, repo, just_before)["held"] == 1
    assert repo.rows[record.id].last_error == "hold:vat_id_unchecked"
    assert gateway.payloads == []
    # Naechste Nachpruefung erst nach einer Stunde, dann ist die Frist vorbei.
    assert _run_worker(service, repo, _NOW + timedelta(hours=72))["due"] == 0

    counters = _run_worker(service, repo, just_before + timedelta(hours=1))
    assert counters["vies_fallback"] == 1
    assert counters["archived"] == 1
    (payload,) = gateway.payloads
    assert payload["lines"][0]["vatRate"] == "19.00"
    assert "memo" not in payload
    assert profiles.vat_updates == []  # Rechnungsdaten bleiben `unchecked`
    assert profiles.profile is not None
    assert profiles.profile.vat_status == "unchecked"
    assert "W61-3" in caplog.text
    assert checker.calls == 2


def test_vies_grace_boundary_is_exactly_72_hours() -> None:
    for offset, expected in ((timedelta(hours=72, seconds=-1), 0), (timedelta(hours=72), 1)):
        profiles = FakeProfiles(_profile(_AT_BUSINESS, "unchecked"))
        service, repo, _, _ = _service(profiles=profiles, vat_checker=FakeVatChecker())
        asyncio.run(service.reserve(_reservation(uuid4(), amount="11.89")))
        assert _run_worker(service, repo, _NOW + offset)["vies_fallback"] == expected


# --- HTTP-Gateway gegen gemockte Mollie-API -----------------------------------------


def _gateway(handler: Callable[[httpx.Request], httpx.Response]) -> HttpSalesInvoiceGateway:
    return HttpSalesInvoiceGateway("test_Platzhalter", transport=httpx.MockTransport(handler))


def _created_body() -> dict[str, Any]:
    return {
        "resource": "sales-invoice",
        "id": _INVOICE_ID,
        "mode": "test",
        "invoiceNumber": "I-2026-00001",
        "status": "paid",
        "_links": {"pdfLink": {"href": _PDF_URL, "type": "application/pdf"}},
    }


def test_gateway_posts_with_bearer_and_parses_the_answer() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(201, json=_created_body())

    created = asyncio.run(_gateway(handler).create_sales_invoice({"status": "paid"}))
    assert created == CreatedInvoice(_INVOICE_ID, "I-2026-00001", _PDF_URL)
    (request,) = seen
    assert request.method == "POST"
    assert str(request.url) == "https://api.mollie.com/v2/sales-invoices"
    assert request.headers["Authorization"] == "Bearer test_Platzhalter"
    assert json.loads(request.content) == {"status": "paid"}


def test_gateway_422_is_rejected_without_echoing_details() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422,
            json={
                "status": 422,
                "title": "Unprocessable Entity",
                "detail": "Feld enthaelt rechnung@example.invalid",
                "field": "recipient.email",
            },
        )

    with pytest.raises(InvoiceRejectedError) as exc:
        asyncio.run(_gateway(handler).create_sales_invoice({}))
    assert exc.value.reason == "http_422:recipient.email"
    assert "example" not in exc.value.reason


def test_gateway_read_timeout_is_uncertain() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("zu langsam", request=request)

    with pytest.raises(InvoiceUncertainError) as exc:
        asyncio.run(_gateway(handler).create_sales_invoice({}))
    assert exc.value.reason == "ReadTimeout"


def test_gateway_connect_error_is_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("kein Netz", request=request)

    with pytest.raises(InvoiceRejectedError):
        asyncio.run(_gateway(handler).create_sales_invoice({}))


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, json={}),
        httpx.Response(201, content=b"kein json"),
        httpx.Response(201, json={"id": "falsch", "invoiceNumber": "I-1"}),
        httpx.Response(201, json={"id": _INVOICE_ID, "invoiceNumber": "../x"}),
    ],
)
def test_gateway_unusable_answers_are_uncertain(response: httpx.Response) -> None:
    with pytest.raises(InvoiceUncertainError):
        asyncio.run(_gateway(lambda _r: response).create_sales_invoice({}))


def test_gateway_fetches_the_pdf_only_from_the_mollie_api() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, content=_PDF, headers={"content-type": "application/pdf"})

    gateway = _gateway(handler)
    assert asyncio.run(gateway.fetch_pdf(_PDF_URL)) == _PDF
    for foreign in (
        "https://evil.example/pdf",
        "http://api.mollie.com/v2/x",
        "https://api.mollie.com:8443/v2/x",
        "https://api.mollie.com.evil.example/v2/x",
    ):
        with pytest.raises(InvoiceArchiveError, match="pdf_link_foreign"):
            asyncio.run(gateway.fetch_pdf(foreign))
    assert seen == [_PDF_URL]  # der Key ging nie an eine fremde Adresse


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (httpx.Response(404), "pdf_http_404"),
        (httpx.Response(200, content=b"<html>"), "pdf_not_a_pdf"),
    ],
)
def test_gateway_rejects_bad_pdfs(response: httpx.Response, message: str) -> None:
    with pytest.raises(InvoiceArchiveError, match=message):
        asyncio.run(_gateway(lambda _r: response).fetch_pdf(_PDF_URL))


def test_gateway_reads_customer_email_and_pdf_link() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == f"/v2/customers/{_CUSTOMER}":
            return httpx.Response(200, json={"id": _CUSTOMER, "email": _EMAIL})
        if request.url.path == f"/v2/sales-invoices/{_INVOICE_ID}":
            return httpx.Response(200, json=_created_body())
        return httpx.Response(404)

    gateway = _gateway(handler)
    assert asyncio.run(gateway.customer_email(_CUSTOMER)) == _EMAIL
    assert asyncio.run(gateway.customer_email("cst_Unbekannt")) is None
    assert asyncio.run(gateway.customer_email("../etwas")) is None  # keine ungepruefte ID
    assert asyncio.run(gateway.pdf_url(_INVOICE_ID)) == _PDF_URL
    assert asyncio.run(gateway.pdf_url("invoice_../x")) is None


def _listed(payment_id: str, **extra: Any) -> dict[str, Any]:
    return {
        **_created_body(),
        "vatMode": "exclusive",
        "recipient": {"type": "business", "vatNumber": "ATU00000000"},
        "lines": [{"vatRate": "0.00"}],
        "memo": "Steuerschuldnerschaft des Leistungsempfängers.",
        "paymentDetails": [{"source": "payment", "sourceReference": payment_id}],
        **extra,
    }


def _page(items: list[dict[str, Any]], next_href: str | None = None) -> dict[str, Any]:
    links: dict[str, Any] = {"next": {"href": next_href} if next_href else None}
    return {"count": len(items), "_embedded": {"sales_invoices": items}, "_links": links}


def test_gateway_finds_the_invoice_on_a_later_page() -> None:
    seen: list[str] = []
    next_url = "https://api.mollie.com/v2/sales-invoices?from=invoice_B&limit=250"

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if "from=" not in str(request.url):
            return httpx.Response(200, json=_page([_listed("tr_Anders")], next_url))
        return httpx.Response(200, json=_page([_listed(_PAYMENT)]))

    found = asyncio.run(_gateway(handler).find_invoice_for_payment(_PAYMENT))
    assert found is not None
    assert found.created.invoice_number == "I-2026-00001"
    assert found.vat_rate == Decimal("0.00")
    assert found.vat_mode == "exclusive"
    assert found.recipient_type == "business"
    assert found.has_vat_number is True
    assert found.memo_key == "reverse_charge"
    decision = found.decision()
    assert (decision.action, decision.include_vat_number) == ("issue", True)
    assert seen == ["https://api.mollie.com/v2/sales-invoices?limit=250", next_url]


def test_gateway_reports_none_only_after_the_last_page() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_page([_listed("tr_Anders")]))

    assert asyncio.run(_gateway(handler).find_invoice_for_payment(_PAYMENT)) is None


@pytest.mark.parametrize(
    ("handler", "reason"),
    [
        (
            lambda r: httpx.Response(
                200, json=_page([], "https://api.mollie.com/v2/sales-invoices?from=x")
            ),
            "list_page_limit",
        ),
        (
            lambda r: httpx.Response(200, json=_page([], "https://evil.example/next")),
            "list_next_foreign",
        ),
        (lambda r: httpx.Response(503), "list_http_503"),
        (lambda r: httpx.Response(200, json={"_embedded": {}}), "list_unreadable"),
        (
            lambda r: httpx.Response(200, json=_page([_listed(_PAYMENT, memo="frei erfunden")])),
            "found_memo_unknown",
        ),
        (
            lambda r: httpx.Response(200, json=_page([_listed(_PAYMENT, vatMode=None)])),
            "found_fields_missing",
        ),
        (
            lambda r: httpx.Response(200, json=_page([_listed(_PAYMENT, lines=[])])),
            "found_fields_missing",
        ),
    ],
)
def test_gateway_lookup_is_uncertain_rather_than_not_found(
    handler: Callable[[httpx.Request], httpx.Response], reason: str
) -> None:
    with pytest.raises(InvoiceUncertainError) as err:
        asyncio.run(_gateway(handler).find_invoice_for_payment(_PAYMENT))
    assert err.value.reason == reason


def test_gateway_lookup_timeout_is_uncertain() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    with pytest.raises(InvoiceUncertainError, match="ReadTimeout"):
        asyncio.run(_gateway(handler).find_invoice_for_payment(_PAYMENT))
    with pytest.raises(InvoiceUncertainError, match="payment_id_unusable"):
        asyncio.run(_gateway(handler).find_invoice_for_payment("tr_../x"))


def test_gateway_requires_a_key() -> None:
    with pytest.raises(ValueError, match="MOLLIE_API_KEY"):
        HttpSalesInvoiceGateway("")


# --- Schalter -----------------------------------------------------------------------


def test_tax_mode_has_no_default_and_blank_means_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WHO2BE_INVOICE_TAX_MODE", raising=False)
    monkeypatch.delenv("WHO2BE_INVOICE_PRICE_BASIS", raising=False)
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.invoice_tax_mode is None
    assert settings.invoice_price_basis == "net"

    monkeypatch.setenv("WHO2BE_INVOICE_TAX_MODE", "")
    monkeypatch.setenv("WHO2BE_INVOICE_PRICE_BASIS", " ")
    blank = Settings(_env_file=None)  # type: ignore[call-arg]
    assert blank.invoice_tax_mode is None
    assert blank.invoice_price_basis == "net"

    monkeypatch.setenv("WHO2BE_INVOICE_TAX_MODE", "Small_Business")
    monkeypatch.setenv("WHO2BE_INVOICE_PRICE_BASIS", "gross")
    set_ = Settings(_env_file=None)  # type: ignore[call-arg]
    assert set_.invoice_tax_mode == "small_business"
    assert set_.invoice_price_basis == "gross"


def test_tax_mode_typo_fails_at_start(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WHO2BE_INVOICE_TAX_MODE", "regulr")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


# --- Datenbank: Migration, UNIQUE, Trigger, Doppel-Webhook --------------------------


async def _migrated_schema(owner: asyncpg.Connection, schema: str) -> None:
    await owner.execute(f'CREATE SCHEMA "{schema}"')
    await owner.execute(f'SET search_path TO "{schema}"')
    await apply_migrations(owner, MIGRATIONS_DIR)
    billing_dir = billing_migrations_dir()
    assert billing_dir is not None
    applied = await apply_migrations(owner, billing_dir)
    assert "billing_0111_billing_invoice.sql" in applied


def _run_in_schema(prefix: str, body: Any) -> None:
    settings = get_settings()
    schema = f"{prefix}_{secrets.token_hex(6)}"

    async def _run() -> None:
        owner = await asyncpg.connect(settings.database_url)
        pool: asyncpg.Pool | None = None
        try:
            await _migrated_schema(owner, schema)
            pool = await asyncpg.create_pool(
                settings.database_url,
                min_size=1,
                max_size=4,
                server_settings={"search_path": schema},
            )
            await body(owner, pool)
        finally:
            if pool is not None:
                await pool.close()
            await owner.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            await owner.close()

    asyncio.run(_run())


async def _seed_org_with_profile(owner: asyncpg.Connection, pool: asyncpg.Pool) -> UUID:
    org: UUID = await owner.fetchval(
        "INSERT INTO organization (name, slug, kind) VALUES ('o', $1, 'company') RETURNING id",
        f"inv-{secrets.token_hex(4)}",
    )
    await PgBillingProfileRepository(pool).save(
        org, BillingProfileInput.model_validate(_DE_CONSUMER), None, None
    )
    return org


class _NoopEntitlements:
    def __init__(self) -> None:
        self.calls = 0

    async def fetch(self, org_id: UUID) -> Entitlement | None:
        return None

    async def upsert(self, *args: Any, **kwargs: Any) -> None:
        self.calls += 1


class _PaidRecurringGateway:
    """Mollie-Fake fuer eine bezahlte Folgezahlung (Abo aktiv)."""

    def __init__(self, org: UUID) -> None:
        self._payment = MolliePayment(
            id=_PAYMENT,
            is_paid=True,
            customer_id=_CUSTOMER,
            subscription_id="sub_Platzhalter01",
            mandate_id="mdt_Platzhalter01",
            metadata={},
            amount_value=Decimal("11.89"),
            paid_at=_NOW,
        )
        self._subscription = MollieSubscription(
            "sub_Platzhalter01", "active", dict(PRO_PLAN.metadata(org))
        )

    async def get_payment(self, payment_id: str) -> MolliePayment | None:
        return self._payment

    async def get_subscription(self, *_args: str) -> MollieSubscription | None:
        return self._subscription

    async def create_customer(self, **_kwargs: Any) -> str:  # pragma: no cover
        raise NotImplementedError

    async def create_first_payment(self, **_kwargs: Any) -> str:  # pragma: no cover
        raise NotImplementedError

    async def create_subscription(self, **_kwargs: Any) -> str:  # pragma: no cover
        raise NotImplementedError


@pytest.mark.integration
def test_double_webhook_creates_one_invoice_row_and_one_post() -> None:
    """Rot-Probe der Karte: ohne `UNIQUE (payment_id)` wird dieser Test rot.

    Zwei Webhooks zur selben Zahlung, jeder mit eigenem Dedupe-Ledger-Stand
    (z. B. nach einer Claim-Freigabe oder zwei API-Instanzen im Rennen): der
    Ledger schuetzt hier nicht, nur die Rechnungszeile.
    """

    async def body(owner: asyncpg.Connection, pool: asyncpg.Pool) -> None:
        org = await _seed_org_with_profile(owner, pool)
        invoice_gateway = FakeInvoiceGateway()
        store = MemoryBlobStore()

        def _billing_invoices() -> InvoiceService:
            return InvoiceService(
                PgInvoiceRepository(pool),
                PgBillingProfileRepository(pool),
                invoice_gateway,
                store,
                tax_mode="regular",
                price_basis="net",
            )

        def _billing() -> MollieBillingService:
            return MollieBillingService(
                _PaidRecurringGateway(org),
                _NoopEntitlements(),
                None,  # je Service ein eigener In-Memory-Ledger
                invoices=_billing_invoices(),
            )

        results = await asyncio.gather(
            _billing().handle_webhook(_PAYMENT, webhook_url=None, now=_NOW),
            _billing().handle_webhook(_PAYMENT, webhook_url=None, now=_NOW),
        )
        assert list(results) == [True, True]
        again = await _billing().handle_webhook(_PAYMENT, webhook_url=None, now=_NOW)
        assert again is True
        assert invoice_gateway.payloads == [], "der Webhook stellt nicht selbst aus (N1)"

        # Zwei Worker-Laeufe parallel (zwei Instanzen), dann ein dritter.
        await asyncio.gather(
            _billing_invoices().retry_open_invoices(_NOW),
            _billing_invoices().retry_open_invoices(_NOW),
        )
        await _billing_invoices().retry_open_invoices(_NOW)

        rows = await owner.fetch("SELECT status, payment_id FROM billing_invoice")
        assert len(rows) == 1, "zweite Rechnungszeile zur selben Zahlung"
        assert rows[0]["status"] == "archived"
        assert len(invoice_gateway.payloads) == 1, "zweiter POST zur selben Zahlung"

    _run_in_schema("billinv", body)


@pytest.mark.integration
def test_repository_lifecycle_and_guards() -> None:
    async def body(owner: asyncpg.Connection, pool: asyncpg.Pool) -> None:
        org = await _seed_org_with_profile(owner, pool)
        repo = PgInvoiceRepository(pool)
        record = await repo.reserve(_reservation(org))
        assert record.status == "pending"
        assert record.amount_value == Decimal("11.89")
        assert (await repo.reserve(_reservation(org))).id == record.id

        assert await repo.start_post(record.id) is True
        assert await repo.start_post(record.id) is False
        await repo.release_post(record.id, "rejected:http_422")
        released = await repo.get(record.id)
        assert released is not None
        assert released.post_started_at is None
        assert released.last_error == "rejected:http_422"
        assert await repo.start_post(record.id) is True

        decision = _decision(_profile(_DE_CONSUMER))
        created = CreatedInvoice(_INVOICE_ID, "I-2026-00001", _PDF_URL)
        issued = await repo.mark_issued(
            record.id,
            created,
            tax_mode="regular",
            price_basis="net",
            decision=decision,
            issued_at=_NOW,
        )
        assert issued is not None
        assert issued.status == "issued"
        stored = await owner.fetchrow(
            "SELECT tax_mode, price_basis, vat_rate, attempts FROM billing_invoice WHERE id = $1",
            record.id,
        )
        assert dict(stored) == {
            "tax_mode": "regular",
            "price_basis": "net",
            "vat_rate": Decimal("19.00"),
            "attempts": 0,  # POST-Starts zaehlen nicht, nur Fehlversuche (R2b)
        }
        digest = hashlib.sha256(_PDF).hexdigest()
        await repo.mark_archived(record.id, pdf_key="invoices/x.pdf", pdf_sha256=digest)

        # Unveraenderbarkeit: Hash, Nummer, Status zurueck und die Steuer- und
        # Rechnungsangaben der ausgestellten Rechnung — alles abgewiesen.
        for statement in (
            "UPDATE billing_invoice SET pdf_sha256 = repeat('0', 64)",
            "UPDATE billing_invoice SET invoice_number = 'I-2026-99999'",
            "UPDATE billing_invoice SET status = 'issued'",
            "UPDATE billing_invoice SET payment_id = 'tr_Anders'",
            "UPDATE billing_invoice SET vat_rate = 0",
            "UPDATE billing_invoice SET tax_mode = 'small_business'",
            "UPDATE billing_invoice SET price_basis = 'gross'",
            "UPDATE billing_invoice SET memo_key = 'other'",
            "UPDATE billing_invoice SET issued_at = now() - interval '400 days'",
            "UPDATE billing_invoice SET amount_value = 1.00",
            "UPDATE billing_invoice SET period_end = period_end + 1",
            "UPDATE billing_invoice SET plan_code = 'other'",
            "UPDATE billing_invoice SET customer_id = NULL",
        ):
            with pytest.raises(asyncpg.RaiseError):
                await owner.execute(statement)
        frozen = await owner.fetchrow(
            "SELECT tax_mode, vat_rate, issued_at FROM billing_invoice WHERE id = $1",
            record.id,
        )
        assert dict(frozen) == {
            "tax_mode": "regular",
            "vat_rate": Decimal("19.00"),
            "issued_at": _NOW,
        }

        # Eine pending-Zeile darf der Worker (R2b) dagegen noch korrigieren.
        open_row = await repo.reserve(_reservation(org, payment_id="tr_Offen"))
        await owner.execute(
            "UPDATE billing_invoice SET amount_value = 9.99 WHERE id = $1", open_row.id
        )
        corrected = await repo.get(open_row.id)
        assert corrected is not None
        assert corrected.amount_value == Decimal("9.99")

        # Ungepruefte IDs kommen gar nicht erst in die Tabelle.
        with pytest.raises(asyncpg.CheckViolationError):
            await repo.reserve(_reservation(org, payment_id="tr_../x"))

        # Fehlversuche: pending wird nach MAX_ATTEMPTS `failed`, updated_at laeuft mit.
        for _ in range(1, MAX_ATTEMPTS):
            assert await repo.record_failure(open_row.id, "uncertain:x") == "pending"
        assert await repo.record_failure(open_row.id, "uncertain:x") == "failed"
        failed = await repo.get(open_row.id)
        assert failed is not None
        assert failed.attempts == MAX_ATTEMPTS
        assert failed.created_at is not None and failed.updated_at is not None
        assert await repo.record_failure(open_row.id, "uncertain:x") is None  # endgueltig

        # Eine ausgestellte Zeile (Archiv fehlt) wird nie `failed`: die Rechnung existiert.
        issued_row = await repo.reserve(_reservation(org, payment_id="tr_Ausgestellt"))
        assert await repo.start_post(issued_row.id) is True
        assert (
            await repo.mark_issued(
                issued_row.id,
                CreatedInvoice("invoice_Zweite", "I-2026-00002", _PDF_URL),
                tax_mode="regular",
                price_basis="net",
                decision=decision,
                issued_at=_NOW,
            )
            is not None
        )
        for _ in range(MAX_ATTEMPTS + 1):
            assert await repo.record_failure(issued_row.id, "archive:pdf_http_500") == "issued"
        # Archiviert und failed sind nicht offen, die ausgestellte schon.
        assert [row.id for row in await repo.open_invoices()] == [issued_row.id]

    _run_in_schema("billinvrepo", body)


@pytest.mark.integration
def test_worker_entry_on_a_single_connection() -> None:
    """`run_invoice_retry` laeuft auf der Worker-Connection; ohne Mollie-Key No-Op."""
    from who2be_billing.invoice import run_invoice_retry

    async def body(owner: asyncpg.Connection, pool: asyncpg.Pool) -> None:
        org = await _seed_org_with_profile(owner, pool)
        await PgInvoiceRepository(pool).reserve(_reservation(org))
        settings = Settings(mollie_api_key="")
        counters = await run_invoice_retry(owner, _NOW, settings)
        assert counters == {"open": 1, "unconfigured": 1}
        assert await owner.fetchval("SELECT status FROM billing_invoice") == "pending"

        # VIES-Ergebnis zurueckschreiben, aber nur zur selben Nummer.
        profiles = PgBillingProfileRepository(owner)
        await profiles.save(
            org, BillingProfileInput.model_validate(_AT_BUSINESS), "unchecked", None
        )
        await profiles.update_vat_status(org, "ATU11111111", "valid", _NOW)
        stale = await profiles.get(org)
        assert stale is not None and stale.vat_status == "unchecked"
        await profiles.update_vat_status(org, "ATU00000000", "valid", _NOW)
        fresh = await profiles.get(org)
        assert fresh is not None
        assert (fresh.vat_status, fresh.vat_checked_at) == ("valid", _NOW)

    _run_in_schema("billinvworker", body)


@pytest.mark.integration
def test_invoice_row_survives_the_org_purge() -> None:
    """Aufbewahrung (ADR-0061 §9): kein FK, der Org-Purge laesst die Zeile stehen."""
    from who2be_api.repositories.account_repository import PgAccountPurgeRepository

    async def body(owner: asyncpg.Connection, pool: asyncpg.Pool) -> None:
        org = await _seed_org_with_profile(owner, pool)
        await PgInvoiceRepository(pool).reserve(_reservation(org))
        await PgAccountPurgeRepository(owner).purge_organization(org)
        assert await owner.fetchval("SELECT count(*) FROM billing_invoice") == 1
        assert await owner.fetchval("SELECT count(*) FROM billing_profile") == 0

    _run_in_schema("billinvpurge", body)


_APP_PASSWORD = "rls_test_secret"  # noqa: S105 — Test-Fixture, kein echtes Secret


@pytest.mark.integration
def test_app_role_cannot_delete_or_read_foreign_invoices() -> None:
    async def body(owner: asyncpg.Connection, pool: asyncpg.Pool) -> None:
        org_a = await _seed_org_with_profile(owner, pool)
        org_b = await _seed_org_with_profile(owner, pool)
        repo = PgInvoiceRepository(pool)
        await repo.reserve(_reservation(org_a, payment_id="tr_PlatzhalterA"))
        await repo.reserve(_reservation(org_b, payment_id="tr_PlatzhalterB"))

        schema = await owner.fetchval("SELECT current_schema()")
        await owner.execute(f"ALTER ROLE who2be_app WITH PASSWORD '{_APP_PASSWORD}'")
        app = await asyncpg.connect(
            get_settings().database_url, user="who2be_app", password=_APP_PASSWORD
        )
        try:
            await app.execute(f'SET search_path TO "{schema}"')
            await app.execute("SELECT set_config('app.current_org', $1, false)", str(org_a))
            rows = await app.fetch("SELECT org_id FROM billing_invoice")
            assert {row["org_id"] for row in rows} == {org_a}, "RLS leakt fremde Rechnungen"
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await app.execute("DELETE FROM billing_invoice")
        finally:
            await app.close()

    _run_in_schema("billinvrls", body)


@pytest.mark.integration
def test_ledger_release_then_redelivery_still_yields_one_invoice() -> None:
    """Echter Ledger: der erste Webhook scheitert nach dem Vormerken (Claim frei),
    Mollie stellt erneut zu — es bleibt bei einer Zeile und einem POST."""

    async def body(owner: asyncpg.Connection, pool: asyncpg.Pool) -> None:
        org = await _seed_org_with_profile(owner, pool)
        invoice_gateway = FakeInvoiceGateway()

        class _FlakyEntitlements(_NoopEntitlements):
            async def upsert(self, *args: Any, **kwargs: Any) -> None:
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError("transienter DB-Fehler")

        entitlements = _FlakyEntitlements()
        invoices = InvoiceService(
            PgInvoiceRepository(pool),
            PgBillingProfileRepository(pool),
            invoice_gateway,
            MemoryBlobStore(),
            tax_mode="regular",
            price_basis="net",
        )
        billing = MollieBillingService(
            _PaidRecurringGateway(org),
            entitlements,
            PgProcessedEventRepository(pool),
            invoices=invoices,
        )
        with pytest.raises(RuntimeError):
            await billing.handle_webhook(_PAYMENT, webhook_url=None, now=_NOW)
        assert await billing.handle_webhook(_PAYMENT, webhook_url=None, now=_NOW) is True
        await invoices.retry_open_invoices(_NOW)
        await invoices.retry_open_invoices(_NOW)
        assert await owner.fetchval("SELECT count(*) FROM billing_invoice") == 1
        assert len(invoice_gateway.payloads) == 1

    _run_in_schema("billinvledger", body)
