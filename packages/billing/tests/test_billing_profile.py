"""Rechnungsdaten (ADR-0061 §10, Paket R1): Validierung, VIES, Endpunkt, Purge.

- Validierung und VIES-Auswertung laufen ohne Netz und ohne DB. VIES ist immer
  gemockt (`httpx.MockTransport`); kein Test spricht mit der EU-Kommission.
- Die Endpunkt-Tests ersetzen Org-Aufloesung, Repository und Pruefer ueber
  `dependency_overrides` (wie der Mollie-Checkout-Test).
- Der Integrationsteil laeuft auf der echten DB in einem eigenen Schema:
  Migration, Upsert, CHECKs und die Purge-Wege (Org und Konto).

Alle Namen, Adressen und USt-IdNr. sind Platzhalter (oeffentliches Repo).
"""

from __future__ import annotations

import asyncio
import secrets
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from who2be_api.core.config import get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations, billing_migrations_dir
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.main import create_app
from who2be_api.repositories.account_repository import PgAccountPurgeRepository
from who2be_billing.billing_profile import (
    COUNTRY_CODES,
    BillingProfile,
    BillingProfileInput,
    PgBillingProfileRepository,
    ViesVatChecker,
    save_billing_profile,
)
from who2be_billing.router import BillingProfileDeps, get_billing_profile_deps
from who2be_billing.tax import EU_COUNTRIES, VatStatus
from who2be_models import WorkspaceRole

_BUSINESS: dict[str, Any] = {
    "customer_type": "business",
    "company_name": "Beispiel GmbH",
    "street": "Musterstrasse 1",
    "postal_code": "1010",
    "city": "Musterstadt",
    "country": "AT",
    "vat_id": "ATU00000000",
}
_CONSUMER: dict[str, Any] = {
    "customer_type": "consumer",
    "given_name": "Erika",
    "family_name": "Muster",
    "street": "Musterweg 2",
    "postal_code": "12345",
    "city": "Musterstadt",
    "country": "DE",
}


# --- Validierung ------------------------------------------------------------------


def test_business_input_is_normalized() -> None:
    data = BillingProfileInput.model_validate(
        {**_BUSINESS, "country": " at ", "vat_id": "atu 000.000-00", "given_name": "  "}
    )
    assert data.country == "AT"
    assert data.vat_id == "ATU00000000"
    assert data.given_name is None


def test_consumer_input_is_valid_without_company() -> None:
    data = BillingProfileInput.model_validate(_CONSUMER)
    assert data.company_name is None
    assert data.vat_id is None


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"company_name": ""}, "company_name"),
        ({"street": " "}, "street"),
        ({"country": "XX"}, "country"),
        ({"country": "DEU"}, "country"),
        ({"vat_id": "DE000000000"}, "Laenderpraefix"),
        ({"vat_id": "AT#"}, "Format"),
        ({"country": "CH", "vat_id": "CHE000000000"}, "EU"),
    ],
)
def test_business_input_rejects(overrides: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        BillingProfileInput.model_validate({**_BUSINESS, **overrides})


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"given_name": None}, "given_name"),
        ({"family_name": ""}, "family_name"),
        ({"vat_id": "DE000000000"}, "Geschaeftskunden"),
    ],
)
def test_consumer_input_rejects(overrides: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        BillingProfileInput.model_validate({**_CONSUMER, **overrides})


def test_greek_vat_id_uses_the_el_prefix() -> None:
    data = BillingProfileInput.model_validate(
        {**_BUSINESS, "country": "GR", "vat_id": "EL000000000"}
    )
    assert data.vat_id == "EL000000000"
    with pytest.raises(ValidationError, match="Laenderpraefix"):
        BillingProfileInput.model_validate({**_BUSINESS, "country": "GR", "vat_id": "GR000000000"})


def test_country_list_covers_the_eu() -> None:
    assert EU_COUNTRIES <= set(COUNTRY_CODES)
    assert list(COUNTRY_CODES) == sorted(COUNTRY_CODES)


# --- VIES (gemockt) ---------------------------------------------------------------


def _vies(handler: Any) -> ViesVatChecker:
    return ViesVatChecker(url="https://vies.invalid/check", transport=httpx.MockTransport(handler))


def _check(checker: ViesVatChecker, vat_id: str = "ATU00000000") -> VatStatus:
    return asyncio.run(checker.check(vat_id))


def test_vies_valid_and_invalid_answers() -> None:
    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        body = json.loads(request.content)
        seen.append(body)
        return httpx.Response(200, json={"valid": body["vatNumber"] == "U00000000"})

    checker = _vies(handler)
    assert _check(checker, "ATU00000000") == "valid"
    assert _check(checker, "ATU99999999") == "invalid"
    assert seen[0] == {"countryCode": "AT", "vatNumber": "U00000000"}


@pytest.mark.parametrize(
    "payload",
    [
        {"valid": False, "userError": "MS_UNAVAILABLE"},
        {"valid": False, "userError": "TIMEOUT"},
        {"valid": False, "userError": "SERVICE_UNAVAILABLE"},
        {"userError": "VALID"},
        {"valid": "yes"},
        ["not", "an", "object"],
    ],
)
def test_vies_service_errors_are_unchecked_not_invalid(payload: object) -> None:
    """Ein Dienstfehler ist keine Aussage ueber die Nummer."""
    assert _check(_vies(lambda _r: httpx.Response(200, json=payload))) == "unchecked"


def test_vies_userError_valid_is_a_real_answer() -> None:
    checker = _vies(lambda _r: httpx.Response(200, json={"valid": True, "userError": "VALID"}))
    assert _check(checker) == "valid"


@pytest.mark.parametrize("status_code", [400, 500, 503])
def test_vies_http_error_is_unchecked(status_code: int) -> None:
    assert _check(_vies(lambda _r: httpx.Response(status_code, json={}))) == "unchecked"


def test_vies_timeout_is_unchecked() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    assert _check(_vies(handler)) == "unchecked"


def test_vies_connection_error_and_garbage_are_unchecked() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    assert _check(_vies(refuse)) == "unchecked"
    assert _check(_vies(lambda _r: httpx.Response(200, content=b"<html>"))) == "unchecked"


def test_vies_checker_has_a_hard_timeout() -> None:
    assert 0 < ViesVatChecker().timeout <= 10


# --- Anwendungsfall mit Fakes -----------------------------------------------------


class FakeRepo:
    def __init__(self) -> None:
        self.rows: dict[UUID, BillingProfile] = {}

    async def get(self, org_id: UUID) -> BillingProfile | None:
        return self.rows.get(org_id)

    async def save(
        self,
        org_id: UUID,
        data: BillingProfileInput,
        vat_status: VatStatus | None,
        vat_checked_at: datetime | None,
    ) -> BillingProfile:
        profile = BillingProfile(
            **data.model_dump(),
            vat_status=vat_status,
            vat_checked_at=vat_checked_at,
            updated_at=datetime.now(tz=UTC),
        )
        self.rows[org_id] = profile
        return profile


class FakeChecker:
    def __init__(self, status: VatStatus = "valid") -> None:
        self.status: VatStatus = status
        self.calls: list[str] = []

    async def check(self, vat_id: str) -> VatStatus:
        self.calls.append(vat_id)
        return self.status


_NOW = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)


def _save(repo: FakeRepo, checker: FakeChecker, org: UUID, data: dict[str, Any]) -> BillingProfile:
    payload = BillingProfileInput.model_validate(data)
    return asyncio.run(save_billing_profile(repo, checker, org, payload, now=_NOW))


def test_save_checks_the_vat_id_and_records_the_time() -> None:
    repo, checker, org = FakeRepo(), FakeChecker("valid"), uuid4()
    profile = _save(repo, checker, org, _BUSINESS)
    assert profile.vat_status == "valid"
    assert profile.vat_checked_at == _NOW
    assert checker.calls == ["ATU00000000"]


def test_save_stores_unchecked_when_vies_is_down() -> None:
    """VIES-Ausfall blockiert das Speichern nicht (ADR-0061 §6)."""
    repo, checker, org = FakeRepo(), FakeChecker("unchecked"), uuid4()
    profile = _save(repo, checker, org, _BUSINESS)
    assert profile.vat_status == "unchecked"
    assert profile.vat_checked_at is None
    assert org in repo.rows


def test_save_does_not_recheck_an_unchanged_valid_vat_id() -> None:
    repo, checker, org = FakeRepo(), FakeChecker("valid"), uuid4()
    _save(repo, checker, org, _BUSINESS)
    profile = _save(repo, checker, org, {**_BUSINESS, "city": "Andere Stadt"})
    assert checker.calls == ["ATU00000000"]
    assert profile.vat_status == "valid"
    assert profile.city == "Andere Stadt"


def test_save_rechecks_after_an_unchecked_result_or_a_new_number() -> None:
    repo, checker, org = FakeRepo(), FakeChecker("unchecked"), uuid4()
    _save(repo, checker, org, _BUSINESS)
    checker.status = "valid"
    assert _save(repo, checker, org, _BUSINESS).vat_status == "valid"
    checker.status = "invalid"
    assert _save(repo, checker, org, {**_BUSINESS, "vat_id": "ATU11111111"}).vat_status == (
        "invalid"
    )
    assert len(checker.calls) == 3


def test_save_without_vat_id_skips_vies() -> None:
    repo, checker, org = FakeRepo(), FakeChecker(), uuid4()
    profile = _save(repo, checker, org, _CONSUMER)
    assert profile.vat_status is None
    assert checker.calls == []


# --- Endpunkt ---------------------------------------------------------------------

_ORG = UUID("00000000-0000-4000-8000-0000000000a1")


def _ctx(role: WorkspaceRole = WorkspaceRole.admin) -> WorkspaceContext:
    return WorkspaceContext(
        workspace_id=uuid4(), user_id=uuid4(), role=role, is_api_token=False, aal="aal2"
    )


async def _resolve(_ws: UUID) -> UUID:
    return _ORG


@pytest.fixture
def cloud_app(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[FastAPI, FakeRepo, FakeChecker]]:
    monkeypatch.setenv("WHO2BE_EDITION", "cloud")
    get_settings.cache_clear()
    app = create_app()
    repo, checker = FakeRepo(), FakeChecker("valid")
    app.dependency_overrides[get_billing_profile_deps] = lambda: BillingProfileDeps(
        _resolve, repo, checker
    )
    app.dependency_overrides[get_current_workspace] = lambda: _ctx()
    yield app, repo, checker
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def _url() -> str:
    return f"/v1/workspaces/{uuid4()}/billing/profile"


_AUTH = {"Authorization": "Bearer w2b_dummy"}


def test_get_returns_null_profile_and_the_country_lists(
    cloud_app: tuple[FastAPI, FakeRepo, FakeChecker],
) -> None:
    app, _repo, _checker = cloud_app
    with TestClient(app) as client:
        resp = client.get(_url(), headers=_AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["profile"] is None
    assert "DE" in body["countries"]
    assert set(body["eu_countries"]) == EU_COUNTRIES


def test_put_saves_for_the_workspace_org_and_returns_the_status(
    cloud_app: tuple[FastAPI, FakeRepo, FakeChecker],
) -> None:
    app, repo, _checker = cloud_app
    with TestClient(app) as client:
        resp = client.put(_url(), headers=_AUTH, json={**_BUSINESS, "org_id": str(uuid4())})
    assert resp.status_code == 200
    assert resp.json()["profile"]["vat_status"] == "valid"
    # Die Org kommt aus dem Workspace, ein `org_id` im Body wird ignoriert.
    assert list(repo.rows) == [_ORG]


def test_put_rejects_invalid_input_with_422(
    cloud_app: tuple[FastAPI, FakeRepo, FakeChecker],
) -> None:
    app, repo, _checker = cloud_app
    with TestClient(app) as client:
        resp = client.put(_url(), headers=_AUTH, json={**_CONSUMER, "family_name": ""})
    assert resp.status_code == 422
    assert repo.rows == {}


@pytest.mark.parametrize("method", ["get", "put"])
def test_non_admin_gets_403(cloud_app: tuple[FastAPI, FakeRepo, FakeChecker], method: str) -> None:
    app, repo, _checker = cloud_app
    app.dependency_overrides[get_current_workspace] = lambda: _ctx(WorkspaceRole.editor)
    with TestClient(app) as client:
        resp = client.request(method.upper(), _url(), headers=_AUTH, json=_CONSUMER)
    assert resp.status_code == 403
    assert repo.rows == {}


def test_profile_route_does_not_exist_on_prem(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WHO2BE_EDITION", "onprem")
    get_settings.cache_clear()
    try:
        app = create_app()
        app.dependency_overrides[get_current_workspace] = lambda: _ctx()
        with TestClient(app) as client:
            assert client.get(_url(), headers=_AUTH).status_code == 404
    finally:
        get_settings.cache_clear()


# --- Datenbank: Migration, Repository, Purge ----------------------------------------


async def _migrated_schema(owner: asyncpg.Connection, schema: str) -> None:
    await owner.execute(f'CREATE SCHEMA "{schema}"')
    await owner.execute(f'SET search_path TO "{schema}"')
    await apply_migrations(owner, MIGRATIONS_DIR)
    billing_dir = billing_migrations_dir()
    assert billing_dir is not None
    applied = await apply_migrations(owner, billing_dir)
    assert "billing_0109_billing_profile.sql" in applied


async def _seed_org(owner: asyncpg.Connection, *, kind: str, slug: str) -> UUID:
    org_id: UUID = await owner.fetchval(
        "INSERT INTO organization (name, slug, kind) VALUES ('o', $1, $2) RETURNING id",
        slug,
        kind,
    )
    return org_id


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
def test_repository_roundtrip_and_check_constraints() -> None:
    async def body(owner: asyncpg.Connection, pool: asyncpg.Pool) -> None:
        org = await _seed_org(owner, kind="company", slug=f"c-{secrets.token_hex(4)}")
        repo = PgBillingProfileRepository(pool)
        assert await repo.get(org) is None

        saved = await repo.save(
            org, BillingProfileInput.model_validate(_BUSINESS), "unchecked", None
        )
        assert saved.vat_status == "unchecked"
        assert saved.updated_at is not None

        # Upsert: zweiter Save ueberschreibt dieselbe Zeile.
        again = await repo.save(org, BillingProfileInput.model_validate(_CONSUMER), None, None)
        assert again.customer_type == "consumer"
        assert again.vat_id is None
        assert await owner.fetchval("SELECT count(*) FROM billing_profile") == 1

        # Die CHECKs halten auch an der Validierung vorbei geschriebene Zeilen auf.
        with pytest.raises(asyncpg.CheckViolationError):
            await owner.execute(
                "UPDATE billing_profile SET vat_id = 'ATU00000000' WHERE org_id = $1", org
            )
        with pytest.raises(asyncpg.CheckViolationError):
            await owner.execute(
                "UPDATE billing_profile SET customer_type = 'business' WHERE org_id = $1", org
            )
        with pytest.raises(asyncpg.CheckViolationError):
            await owner.execute("UPDATE billing_profile SET country = 'de' WHERE org_id = $1", org)

    _run_in_schema("billprof", body)


@pytest.mark.integration
def test_org_purge_removes_the_billing_profile() -> None:
    async def body(owner: asyncpg.Connection, pool: asyncpg.Pool) -> None:
        doomed = await _seed_org(owner, kind="company", slug=f"d-{secrets.token_hex(4)}")
        kept = await _seed_org(owner, kind="company", slug=f"k-{secrets.token_hex(4)}")
        repo = PgBillingProfileRepository(pool)
        data = BillingProfileInput.model_validate(_BUSINESS)
        await repo.save(doomed, data, "valid", _NOW)
        await repo.save(kept, data, "valid", _NOW)

        await PgAccountPurgeRepository(owner).purge_organization(doomed)

        assert await repo.get(doomed) is None
        assert await repo.get(kept) is not None

    _run_in_schema("billpurge", body)


@pytest.mark.integration
def test_account_purge_removes_the_personal_org_billing_profile() -> None:
    """Konto-Loeschung: die Personal-Org faellt, ihre Rechnungsdaten mit ihr."""

    async def body(owner: asyncpg.Connection, pool: asyncpg.Pool) -> None:
        user = uuid4()
        personal = await _seed_org(owner, kind="personal", slug=str(user))
        other = await _seed_org(owner, kind="company", slug=f"o-{secrets.token_hex(4)}")
        repo = PgBillingProfileRepository(pool)
        await repo.save(personal, BillingProfileInput.model_validate(_CONSUMER), None, None)
        await repo.save(other, BillingProfileInput.model_validate(_CONSUMER), None, None)

        await PgAccountPurgeRepository(owner).purge_account_data(user)

        assert await repo.get(personal) is None
        assert await repo.get(other) is not None

    _run_in_schema("billacct", body)
