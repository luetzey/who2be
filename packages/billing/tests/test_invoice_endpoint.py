"""Rechnungen im Web: Liste und PDF-Download (ADR-0061 §7, Paket R3).

Endpunkt-Tests laufen ohne DB ueber `dependency_overrides` (wie die
Rechnungsdaten-Tests in `test_billing_profile.py`); der Rechte-Schnitt am
echten SQL laeuft als Integrationstest am Ende.

Nur Platzhalter: keine echten Rechnungsnummern, IDs oder Adressen.
"""

from __future__ import annotations

import asyncio
import hashlib
import secrets
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from who2be_api.blobstore.adapters.memory import MemoryBlobStore
from who2be_api.core.config import get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations, billing_migrations_dir
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.main import create_app
from who2be_billing.invoice import InvoiceRecord, InvoiceStatus, PgInvoiceRepository
from who2be_billing.router import InvoiceReadDeps, get_invoice_read_deps
from who2be_models import WorkspaceRole

_ORG = UUID("00000000-0000-4000-8000-0000000000a1")
_OTHER_ORG = UUID("00000000-0000-4000-8000-0000000000b2")
_PDF = b"%PDF-1.7\n% Platzhalter-Rechnung\n%%EOF\n"
_AUTH = {"Authorization": "Bearer w2b_dummy"}
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def _record(
    org: UUID = _ORG,
    *,
    number: str = "TEST-2026-00001",
    status: str = "archived",
    issued_at: datetime = datetime(2026, 10, 1, 9, 0, tzinfo=UTC),
    pdf: bytes | None = _PDF,
) -> InvoiceRecord:
    archived = status == "archived"
    return InvoiceRecord(
        id=uuid4(),
        org_id=org,
        payment_id=f"tr_Platzhalter{secrets.token_hex(4)}",
        customer_id="cst_Platzhalter01",
        plan_code="pro",
        amount_value=Decimal("11.89"),
        period_start=date(2026, 10, 1),
        period_end=date(2026, 10, 31),
        status=status,  # type: ignore[arg-type]
        mollie_invoice_id="invoice_Platzhalter01" if status != "pending" else None,
        invoice_number=number if status != "pending" else None,
        issued_at=issued_at if status != "pending" else None,
        pdf_key=f"invoices/{org}/2026/{number}.pdf" if archived else None,
        pdf_sha256=hashlib.sha256(pdf).hexdigest() if archived and pdf is not None else None,
    )


class FakeReader:
    """Lesesicht mit demselben Org- und Status-Filter wie das SQL."""

    def __init__(self, records: list[InvoiceRecord]) -> None:
        self.records = records
        self.list_calls: list[UUID] = []

    @staticmethod
    def _visible(record: InvoiceRecord) -> bool:
        return record.status in ("issued", "archived")

    async def list_for_org(self, org_id: UUID, limit: int = 240) -> list[InvoiceRecord]:
        self.list_calls.append(org_id)
        rows = [r for r in self.records if r.org_id == org_id and self._visible(r)]
        rows.sort(key=lambda r: r.issued_at or _EPOCH, reverse=True)
        return rows[:limit]

    async def get_for_org(self, org_id: UUID, invoice_id: UUID) -> InvoiceRecord | None:
        for record in self.records:
            if record.id == invoice_id and record.org_id == org_id and self._visible(record):
                return record
        return None


def _ctx(role: WorkspaceRole = WorkspaceRole.admin) -> WorkspaceContext:
    return WorkspaceContext(
        workspace_id=uuid4(), user_id=uuid4(), role=role, is_api_token=False, aal="aal2"
    )


async def _resolve(_ws: UUID) -> UUID:
    return _ORG


Setup = tuple[FastAPI, FakeReader, MemoryBlobStore]


@pytest.fixture
def cloud_app(monkeypatch: pytest.MonkeyPatch) -> Iterator[Setup]:
    monkeypatch.setenv("WHO2BE_EDITION", "cloud")
    get_settings.cache_clear()
    app = create_app()
    reader, store = FakeReader([]), MemoryBlobStore()
    app.dependency_overrides[get_invoice_read_deps] = lambda: InvoiceReadDeps(
        _resolve, reader, store
    )
    app.dependency_overrides[get_current_workspace] = lambda: _ctx()
    yield app, reader, store
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def _list_url() -> str:
    return f"/v1/workspaces/{uuid4()}/billing/invoices"


def _pdf_url(invoice_id: UUID | str) -> str:
    return f"/v1/workspaces/{uuid4()}/billing/invoices/{invoice_id}/pdf"


async def _archive(store: MemoryBlobStore, record: InvoiceRecord, pdf: bytes = _PDF) -> None:
    assert record.pdf_key is not None
    await store.put(record.pdf_key, pdf, "application/pdf")


# --- Liste --------------------------------------------------------------------------


def test_empty_list(cloud_app: Setup) -> None:
    app, reader, _store = cloud_app
    with TestClient(app) as client:
        resp = client.get(_list_url(), headers=_AUTH)
    assert resp.status_code == 200
    assert resp.json() == {"invoices": []}
    assert reader.list_calls == [_ORG]


def test_list_shows_only_own_issued_invoices_newest_first(cloud_app: Setup) -> None:
    app, reader, _store = cloud_app
    older = _record(number="TEST-2026-00001", issued_at=datetime(2026, 9, 1, tzinfo=UTC))
    newer = _record(
        number="TEST-2026-00002", status="issued", issued_at=datetime(2026, 10, 1, tzinfo=UTC)
    )
    reader.records = [
        older,
        newer,
        _record(status="pending"),
        replace(_record(number="TEST-2026-00003"), status="failed"),
        _record(_OTHER_ORG, number="FREMD-2026-00001"),
    ]
    with TestClient(app) as client:
        body = client.get(_list_url(), headers=_AUTH).json()
    assert [i["invoice_number"] for i in body["invoices"]] == [
        "TEST-2026-00002",
        "TEST-2026-00001",
    ]
    first = body["invoices"][0]
    assert first == {
        "id": str(newer.id),
        "invoice_number": "TEST-2026-00002",
        "issued_at": "2026-10-01T00:00:00Z",
        "amount_value": "11.89",
        "currency": "EUR",
        "status": "issued",
    }
    assert body["invoices"][1]["status"] == "archived"
    # Interna (Mollie-ID, Ablageort, Hash, Fehler) verlassen den Server nicht.
    assert "pdf_key" not in first and "mollie_invoice_id" not in first


# --- PDF-Download -------------------------------------------------------------------


def test_download_returns_the_archived_pdf(cloud_app: Setup) -> None:
    app, reader, store = cloud_app
    record = _record()
    reader.records = [record]
    asyncio.run(_archive(store, record))
    with TestClient(app) as client:
        resp = client.get(_pdf_url(record.id), headers=_AUTH)
    assert resp.status_code == 200
    assert resp.content == _PDF
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.headers["content-disposition"] == 'attachment; filename="TEST-2026-00001.pdf"'
    assert "no-store" in resp.headers["cache-control"]


def test_foreign_invoice_is_404(cloud_app: Setup) -> None:
    """Rechte-Test der Karte: die Rechnung einer anderen Org ist nicht sichtbar."""
    app, reader, store = cloud_app
    foreign = _record(_OTHER_ORG, number="FREMD-2026-00001")
    reader.records = [foreign]
    asyncio.run(_archive(store, foreign))
    with TestClient(app) as client:
        resp = client.get(_pdf_url(foreign.id), headers=_AUTH)
    assert resp.status_code == 404
    assert resp.content != _PDF


@pytest.mark.parametrize("status", ["issued", "pending", "failed"])
def test_invoice_without_archived_pdf_is_404(cloud_app: Setup, status: InvoiceStatus) -> None:
    app, reader, _store = cloud_app
    record = replace(_record(), status=status)
    reader.records = [record]
    with TestClient(app) as client:
        assert client.get(_pdf_url(record.id), headers=_AUTH).status_code == 404


def test_unknown_invoice_is_404(cloud_app: Setup) -> None:
    app, _reader, _store = cloud_app
    with TestClient(app) as client:
        assert client.get(_pdf_url(uuid4()), headers=_AUTH).status_code == 404


@pytest.mark.parametrize("bad_id", ["1", "..%2F..%2Fsecret", "not-a-uuid"])
def test_non_uuid_id_is_rejected_before_any_lookup(cloud_app: Setup, bad_id: str) -> None:
    app, reader, _store = cloud_app
    reader.records = [_record()]
    with TestClient(app) as client:
        resp = client.get(_pdf_url(bad_id), headers=_AUTH)
    assert resp.status_code in (404, 422)
    assert resp.content != _PDF


def test_tampered_pdf_is_not_served(cloud_app: Setup) -> None:
    app, reader, store = cloud_app
    record = _record()
    reader.records = [record]
    asyncio.run(_archive(store, record, b"%PDF-1.7\n% veraendert\n"))
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get(_pdf_url(record.id), headers=_AUTH)
    assert resp.status_code == 500
    assert b"veraendert" not in resp.content


def test_missing_blob_is_500_without_content(cloud_app: Setup) -> None:
    app, reader, _store = cloud_app
    record = _record()
    reader.records = [record]
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.get(_pdf_url(record.id), headers=_AUTH).status_code == 500


def test_download_without_blobstore_is_503(cloud_app: Setup) -> None:
    app, reader, _store = cloud_app
    record = _record()
    reader.records = [record]
    app.dependency_overrides[get_invoice_read_deps] = lambda: InvoiceReadDeps(
        _resolve, reader, None
    )
    with TestClient(app) as client:
        assert client.get(_pdf_url(record.id), headers=_AUTH).status_code == 503
        # Die Liste bleibt ohne Archiv lesbar.
        assert client.get(_list_url(), headers=_AUTH).status_code == 200


# --- Rolle und Edition --------------------------------------------------------------


@pytest.mark.parametrize("role", [WorkspaceRole.editor, WorkspaceRole.viewer])
def test_non_admin_gets_403_for_list_and_pdf(cloud_app: Setup, role: WorkspaceRole) -> None:
    app, reader, store = cloud_app
    record = _record()
    reader.records = [record]
    asyncio.run(_archive(store, record))
    app.dependency_overrides[get_current_workspace] = lambda: _ctx(role)
    with TestClient(app) as client:
        assert client.get(_list_url(), headers=_AUTH).status_code == 403
        resp = client.get(_pdf_url(record.id), headers=_AUTH)
    assert resp.status_code == 403
    assert reader.list_calls == []


def test_invoice_routes_do_not_exist_on_prem(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WHO2BE_EDITION", "onprem")
    get_settings.cache_clear()
    try:
        app = create_app()
        app.dependency_overrides[get_current_workspace] = lambda: _ctx()
        with TestClient(app) as client:
            assert client.get(_list_url(), headers=_AUTH).status_code == 404
            assert client.get(_pdf_url(uuid4()), headers=_AUTH).status_code == 404
    finally:
        get_settings.cache_clear()


# --- Datenbank: Org- und Status-Filter am echten SQL --------------------------------


async def _seed(owner: asyncpg.Connection, org: UUID, number: str, status: str) -> UUID:
    issued = status != "pending"
    archived = status == "archived"
    invoice_id: UUID = await owner.fetchval(
        """
        INSERT INTO billing_invoice (
            org_id, payment_id, plan_code, amount_value, period_start, period_end, status,
            mollie_invoice_id, invoice_number, issued_at, pdf_key, pdf_sha256)
        VALUES ($1, $2, 'pro', 11.89, '2026-10-01', '2026-10-31', $3, $4, $5, $6, $7, $8)
        RETURNING id
        """,
        org,
        f"tr_Platzhalter{secrets.token_hex(4)}",
        status,
        f"invoice_Platzhalter{secrets.token_hex(4)}" if issued else None,
        number if issued else None,
        datetime(2026, 10, 1, tzinfo=UTC) if issued else None,
        f"invoices/{org}/2026/{number}.pdf" if archived else None,
        hashlib.sha256(_PDF).hexdigest() if archived else None,
    )
    return invoice_id


def _run_in_schema(prefix: str, body: Any) -> None:
    settings = get_settings()
    schema = f"{prefix}_{secrets.token_hex(6)}"

    async def _run() -> None:
        owner = await asyncpg.connect(settings.database_url)
        pool: asyncpg.Pool | None = None
        try:
            await owner.execute(f'CREATE SCHEMA "{schema}"')
            await owner.execute(f'SET search_path TO "{schema}"')
            await apply_migrations(owner, MIGRATIONS_DIR)
            billing_dir = billing_migrations_dir()
            assert billing_dir is not None
            await apply_migrations(owner, billing_dir)
            pool = await asyncpg.create_pool(
                settings.database_url,
                min_size=1,
                max_size=2,
                server_settings={"search_path": schema},
            )
            await body(owner, pool)
        finally:
            if pool is not None:
                await pool.close()
            await owner.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            await owner.close()

    asyncio.run(_run())


@pytest.mark.integration
def test_repository_reads_only_the_own_orgs_issued_invoices() -> None:
    async def body(owner: asyncpg.Connection, pool: asyncpg.Pool) -> None:
        org_a, org_b = uuid4(), uuid4()  # bewusst ohne FK (billing_0111)
        own = await _seed(owner, org_a, "TEST-2026-00001", "archived")
        issued = await _seed(owner, org_a, "TEST-2026-00002", "issued")
        pending = await _seed(owner, org_a, "-", "pending")
        foreign = await _seed(owner, org_b, "FREMD-2026-00001", "archived")

        repo = PgInvoiceRepository(pool)
        listed = await repo.list_for_org(org_a)
        assert {r.id for r in listed} == {own, issued}
        assert await repo.get_for_org(org_a, own) is not None
        assert await repo.get_for_org(org_a, foreign) is None, "fremde Rechnung sichtbar"
        assert await repo.get_for_org(org_a, pending) is None
        assert await repo.list_for_org(org_a, limit=1) != []
        assert len(await repo.list_for_org(org_a, limit=1)) == 1

    _run_in_schema("billinvr3", body)
