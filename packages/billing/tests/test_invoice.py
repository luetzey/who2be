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
from datetime import UTC, date, datetime
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
    CreatedInvoice,
    HttpSalesInvoiceGateway,
    InvoiceArchiveError,
    InvoiceRecord,
    InvoiceRejectedError,
    InvoiceReservation,
    InvoiceService,
    InvoiceUncertainError,
    PgInvoiceRepository,
    archive_key,
    build_sales_invoice_payload,
    expected_total,
    line_description,
    service_period,
)
from who2be_billing.mollie import MollieBillingService, MolliePayment, MollieSubscription
from who2be_billing.plans import PRO_PLAN
from who2be_billing.processed_event_repository import PgProcessedEventRepository
from who2be_billing.tax import PriceBasis, TaxDecision, TaxInput, TaxMode, decide_tax

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
    """In-Memory-Spiegel von `PgInvoiceRepository` (gleiche Bedingungen in WHERE)."""

    def __init__(self) -> None:
        self.rows: dict[UUID, InvoiceRecord] = {}
        self.issued_with: dict[UUID, tuple[str, str]] = {}

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
        )
        self.rows[record.id] = record
        return record

    async def get(self, invoice_id: UUID) -> InvoiceRecord | None:
        return self.rows.get(invoice_id)

    async def start_post(self, invoice_id: UUID) -> bool:
        row = self.rows[invoice_id]
        if row.status != "pending" or row.post_started_at is not None:
            return False
        self.rows[invoice_id] = replace(row, post_started_at=_NOW)
        return True

    async def release_post(self, invoice_id: UUID, error: str) -> None:
        row = self.rows[invoice_id]
        if row.status == "pending":
            self.rows[invoice_id] = replace(row, post_started_at=None, last_error=error)

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
        row = self.rows[invoice_id]
        if row.status != "pending":
            return None
        self.issued_with[invoice_id] = (tax_mode, price_basis)
        self.rows[invoice_id] = replace(
            row,
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
            self.rows[invoice_id] = replace(
                row, status="archived", pdf_key=pdf_key, pdf_sha256=pdf_sha256, last_error=None
            )

    async def record_error(self, invoice_id: UUID, error: str) -> None:
        self.rows[invoice_id] = replace(self.rows[invoice_id], last_error=error)


class FakeProfiles:
    def __init__(self, profile: BillingProfile | None) -> None:
        self.profile = profile

    async def get(self, org_id: UUID) -> BillingProfile | None:
        return self.profile

    async def save(self, *args: Any, **kwargs: Any) -> BillingProfile:  # pragma: no cover
        raise NotImplementedError


class FakeInvoiceGateway:
    """Fake der Sales Invoices API mit steuerbaren Fehlern."""

    def __init__(
        self,
        *,
        email: str | None = _EMAIL,
        create_error: Exception | None = None,
        pdf_error: Exception | None = None,
        pdf: bytes = _PDF,
        pdf_url: str | None = _PDF_URL,
    ) -> None:
        self.email = email
        self.create_error = create_error
        self.pdf_error = pdf_error
        self.pdf = pdf
        self.url = pdf_url
        self.payloads: list[dict[str, Any]] = []
        self.pdf_fetches: list[str] = []

    async def customer_email(self, customer_id: str) -> str | None:
        return self.email

    async def create_sales_invoice(self, payload: dict[str, Any]) -> CreatedInvoice:
        self.payloads.append(payload)
        if self.create_error is not None:
            raise self.create_error
        number = f"I-2026-{len(self.payloads):05d}"
        return CreatedInvoice(id=_INVOICE_ID, invoice_number=number, pdf_url=self.url)

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
) -> tuple[InvoiceService, FakeInvoiceRepository, FakeInvoiceGateway, MemoryBlobStore | None]:
    repo = repo or FakeInvoiceRepository()
    gateway = gateway or FakeInvoiceGateway()
    store = (blob or MemoryBlobStore()) if with_blob else None
    service = InvoiceService(
        repo,
        FakeProfiles(profile if profile is not None else _profile(_DE_CONSUMER)),
        gateway,
        store,
        tax_mode=tax_mode,
        price_basis="net",
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


def test_timeout_keeps_the_post_marker_and_never_posts_twice() -> None:
    """Nach einem Timeout ist offen, ob Mollie angelegt hat: kein zweiter POST."""
    gateway = FakeInvoiceGateway(create_error=InvoiceUncertainError("ReadTimeout"))
    service, repo, _, _ = _service(gateway=gateway)
    org = uuid4()
    first = _issue(service, org)
    assert first is not None
    assert first.status == "pending"
    assert first.post_started_at is not None
    assert first.last_error == "uncertain:ReadTimeout"

    gateway.create_error = None
    again = asyncio.run(service.issue(first.id, now=_NOW))
    assert again is not None
    assert again.status == "pending"
    assert len(gateway.payloads) == 1  # nur die List-API-Suche (R2b) darf weiter


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

        def _billing() -> MollieBillingService:
            invoices = InvoiceService(
                PgInvoiceRepository(pool),
                PgBillingProfileRepository(pool),
                invoice_gateway,
                store,
                tax_mode="regular",
                price_basis="net",
            )
            return MollieBillingService(
                _PaidRecurringGateway(org),
                _NoopEntitlements(),
                None,  # je Service ein eigener In-Memory-Ledger
                invoices=invoices,
            )

        results = await asyncio.gather(
            _billing().handle_webhook(_PAYMENT, webhook_url=None, now=_NOW),
            _billing().handle_webhook(_PAYMENT, webhook_url=None, now=_NOW),
        )
        assert list(results) == [True, True]
        again = await _billing().handle_webhook(_PAYMENT, webhook_url=None, now=_NOW)
        assert again is True

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
            "attempts": 2,
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

    _run_in_schema("billinvrepo", body)


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
        assert await owner.fetchval("SELECT count(*) FROM billing_invoice") == 1
        assert len(invoice_gateway.payloads) == 1

    _run_in_schema("billinvledger", body)
