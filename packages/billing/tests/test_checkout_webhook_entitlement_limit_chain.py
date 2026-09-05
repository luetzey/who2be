"""Kettentest Checkout → Webhook → Entitlement → Limit (Issue #451, WP-4 von #428).

Belegt End-to-End, dass ein bezahltes Abo tatsaechlich ein schaerferes MCP-Limit
freischaltet — nicht nur, dass Checkout, Webhook, Entitlement-Schreibpfad und
Limit je einzeln funktionieren:

1. Vor dem Webhook (frische Org) greift `CLOUD_FREE_ENTITLEMENT` — derselbe
   Aufruf, der spaeter durchgeht, wird mit dem von `mcp_limit_service`
   vorgesehenen Status (429, Rate-Limit) abgewiesen.
2. Checkout (`MollieBillingService.start_checkout`) legt Customer + Erstzahlung
   beim (Fake-)Gateway an.
3. Ein simulierter Mollie-Webhook-Ping (Erstzahlung bezahlt, Metadata traegt
   den Pro-Tier) schreibt das Entitlement — ueber die ECHTE
   `PgEntitlementRepository`, nur die DB-Verbindung selbst ist ein In-Memory-
   `StubPool` (kein Docker/Postgres in dieser Umgebung, ADR-0041).
4. Derselbe Aufruf, der eben unter Free abgewiesen wurde, geht jetzt durch —
   `McpLimitService.enforce` loest das Entitlement ueber den echten
   `build_entitlement_port`-Pfad auf (kein Fake-Port, anders als
   `apps/api/tests/test_mcp_limit_service.py`).

Einzig gefakt sind die Prozessgrenzen: die Mollie-API (`FakeMollieGateway`, wie
`test_mollie_adapter.py`, netzfrei) und der DB-Pool (`StubPool`, In-Memory statt
Postgres). Repository, Adapter, Service und die Entitlement-Entscheidungslogik
(`Entitlement.is_active()`, Quota-Vergleich, `increment_if_allowed`) sind
unveraendert Produktivcode.
"""

from __future__ import annotations

import asyncio
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException, Request
from test_mollie_adapter import FakeMollieGateway  # type: ignore[import-not-found]

from who2be_api.core.config import Settings
from who2be_api.core.rate_limit import token_rate_limiter
from who2be_api.core.security import WorkspaceContext
from who2be_api.repositories.entitlement_repository import PgEntitlementRepository
from who2be_api.repositories.mcp_usage_repository import PgMcpUsageRepository
from who2be_api.services.mcp_limit_service import McpLimitService
from who2be_billing.mollie import MollieBillingService, MolliePayment
from who2be_billing.plans import PRO_PLAN
from who2be_models import WorkspaceRole

# CLOUD_FREE_ENTITLEMENT.mcp_rate_per_min (licensing/entitlement.py) — die
# Test-Last, die unter Free gerade noch durchgeht, bevor der 31. Aufruf ins
# Rate-Limit laeuft.
_FREE_RATE_PER_MIN = 30


class _NullTransaction:
    """`conn.transaction()`-Stub: `PgEntitlementRepository.upsert` schreibt
    SSoT + Journal in einer Transaktion — hier ist nur die DB-Grenze gefakt."""

    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *exc: object) -> bool:
        return False


class _StubConnection:
    """Faengt die zwei Writes von `PgEntitlementRepository.upsert` ab (SSoT +
    Journal, `apps/api/.../repositories/entitlement_repository.py:61-132`)."""

    def __init__(self, pool: StubPool) -> None:
        self._pool = pool

    def transaction(self) -> _NullTransaction:
        return _NullTransaction()

    async def execute(self, query: str, *args: Any) -> None:
        normalized = " ".join(query.split())
        if normalized.startswith("INSERT INTO org_entitlement"):
            (
                org_id,
                status,
                features,
                expires_at,
                mcp_monthly_quota,
                mcp_rate_per_min,
                grace_until,
                *_rest,
            ) = args
            self._pool.entitlement_rows[org_id] = {
                "status": status,
                "features": list(features),
                "expires_at": expires_at,
                "mcp_monthly_quota": mcp_monthly_quota,
                "mcp_rate_per_min": mcp_rate_per_min,
                "grace_until": grace_until,
            }
        elif normalized.startswith("INSERT INTO entitlement_history"):
            pass  # Journal ist fuer diese Kette irrelevant — SSoT genuegt.
        else:
            raise AssertionError(f"StubPool.execute: unerwartete Query: {query!r}")


class _StubAcquire:
    def __init__(self, pool: StubPool) -> None:
        self._pool = pool

    async def __aenter__(self) -> _StubConnection:
        return _StubConnection(self._pool)

    async def __aexit__(self, *exc: object) -> bool:
        return False


class StubPool:
    """In-Memory-Ersatz fuer `asyncpg.Pool` — traegt echte Repositories.

    Bedient genau die Queries, die `McpLimitService._resolve_org_id`,
    `PgEntitlementRepository` (fetch/upsert) und `PgMcpUsageRepository`
    (`increment_if_allowed`) stellen. `_increment_usage` bildet die reale
    atomare `INSERT ... ON CONFLICT ... WHERE count < $3 ... RETURNING count`
    nach (siehe `repositories/mcp_usage_repository.py:33-46`): der erste Read
    einer Periode legt die Zeile unbedingt an (count=1), jeder weitere nur,
    wenn der bisherige Zaehler noch unter dem Quota liegt — exakt die
    Semantik, die die reale SQL-Anweisung liefert. Repository, Adapter und
    Service bleiben dabei Produktivcode; gefakt ist ausschliesslich die
    DB-Verbindung.
    """

    def __init__(self, *, workspace_id: UUID, org_id: UUID) -> None:
        self._workspace_id = workspace_id
        self._org_id = org_id
        self.entitlement_rows: dict[UUID, dict[str, Any]] = {}
        self._usage_counts: dict[tuple[UUID, str], int] = {}

    async def fetchval(self, query: str, *args: Any) -> Any:
        normalized = " ".join(query.split())
        if "FROM workspace WHERE id" in normalized:
            assert args[0] == self._workspace_id
            return self._org_id
        if normalized.startswith("INSERT INTO mcp_usage"):
            org_id, period, quota = args
            return self._increment_usage(org_id, period, quota)
        raise AssertionError(f"StubPool.fetchval: unerwartete Query: {query!r}")

    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None:
        normalized = " ".join(query.split())
        if "FROM org_entitlement WHERE org_id" in normalized:
            return self.entitlement_rows.get(args[0])
        raise AssertionError(f"StubPool.fetchrow: unerwartete Query: {query!r}")

    def acquire(self) -> _StubAcquire:
        return _StubAcquire(self)

    def _increment_usage(self, org_id: UUID, period: str, quota: int) -> int | None:
        key = (org_id, period)
        current = self._usage_counts.get(key)
        if current is None:
            self._usage_counts[key] = 1
            return 1
        if current < quota:
            self._usage_counts[key] = current + 1
            return self._usage_counts[key]
        return None


class _FakeRequest:
    """Minimaler Request-Stub: `rate_limit_key` liest nur `headers.get` (wie
    `apps/api/tests/test_mcp_limit_service.py`)."""

    def __init__(self, token: str) -> None:
        self.headers = {"authorization": f"Bearer {token}"}


def _enforce(service: McpLimitService, ctx: WorkspaceContext, token: str) -> None:
    asyncio.run(service.enforce(cast(Request, _FakeRequest(token)), ctx))


def setup_function() -> None:
    token_rate_limiter.reset()


def test_paid_checkout_unlocks_mcp_limit_that_free_tier_denies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Checkout → Webhook → Entitlement → Limit, inkl. Gegenfall Free-Default.

    AC1: derselbe Aufruf, der unter Free abgewiesen wird, geht nach dem Webhook
    durch. AC2: der Gegenfall (kein Webhook ⇒ Free-Default) steht davor, mit
    dem Status, den `mcp_limit_service` fuer ein Rate-Limit vorsieht (429).
    """
    workspace_id = uuid4()
    org_id = uuid4()
    pool = StubPool(workspace_id=workspace_id, org_id=org_id)
    settings = Settings(edition="cloud")
    limit_service = McpLimitService(pool, PgMcpUsageRepository(pool), settings)
    ctx = WorkspaceContext(
        workspace_id=workspace_id,
        user_id=uuid4(),
        role=WorkspaceRole.viewer,
        is_api_token=True,
    )
    token = "w2b_chain"

    # --- Gegenfall zuerst: kein Webhook ⇒ CLOUD_FREE_ENTITLEMENT (30 req/min) ---
    for _ in range(_FREE_RATE_PER_MIN):
        _enforce(limit_service, ctx, token)
    with pytest.raises(HTTPException) as exc:
        _enforce(limit_service, ctx, token)
    assert exc.value.status_code == 429

    # --- Checkout anstossen (Fake-Gateway, netzfrei wie test_mollie_adapter.py) ---
    gateway = FakeMollieGateway()
    repo = PgEntitlementRepository(pool)
    billing_service = MollieBillingService(gateway, repo)
    checkout_url = asyncio.run(
        billing_service.start_checkout(
            org_id=org_id,
            plan=PRO_PLAN,
            customer_name="Acme",
            customer_email="ops@example.com",
            redirect_url="https://app.example/settings/billing",
            webhook_url="https://api.example/v1/billing/mollie/webhook",
        )
    )
    assert checkout_url == gateway.checkout_url

    # --- Webhook-Ereignis simulieren: Erstzahlung bezahlt, Metadata traegt Pro ---
    gateway.payment = MolliePayment(
        id="tr_chain",
        is_paid=True,
        customer_id=gateway.new_customer_id,
        subscription_id=None,
        mandate_id="mdt_chain",
        metadata=dict(PRO_PLAN.metadata(org_id)),
    )
    applied = asyncio.run(billing_service.handle_webhook("tr_chain", webhook_url=None))
    assert applied is True
    written = pool.entitlement_rows[org_id]
    assert written["status"] == "active"
    assert written["mcp_rate_per_min"] == PRO_PLAN.mcp_rate_per_min
    assert written["mcp_rate_per_min"] > _FREE_RATE_PER_MIN

    # --- Limit-Pruefung: derselbe Aufruf, eben abgewiesen, geht jetzt durch ---
    token_rate_limiter.reset()
    for _ in range(_FREE_RATE_PER_MIN + 1):
        _enforce(limit_service, ctx, token)
