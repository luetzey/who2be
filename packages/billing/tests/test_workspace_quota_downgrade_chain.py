"""Kettentest Downgrade → Entitlement → Workspace-Deckel (Issue #576).

Zwilling von `test_token_quota_downgrade_chain.py`, und aus demselben Grund
noetig: der Revoke-Pfad des Webhooks schreibt
`Entitlement(status="inactive", features=frozenset())` **ohne** die neue
Grenze, also landet `workspace_quota` als `NULL` in der SSoT-Zeile. Ohne den
Cloud-Rueckfall in `Entitlement.effective_workspace_quota` hiesse dieses `NULL`
„unbegrenzt" — ausgerechnet fuer eine gekuendigte Org.

Der Weg ist der reale: echtes `map_event_to_entitlement` → echte
`PgEntitlementRepository.upsert` (nur die DB-Verbindung ist ein In-Memory-Stub)
→ echter `CloudEntitlementAdapter` → echtes `WorkspaceQuotaService.enforce`.

Ein Unit-Test mit handgebautem `Entitlement` koennte das nicht belegen: er
wuerde die Annahme testen, dass der Webhook `NULL` schreibt, statt sie zu
pruefen.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from who2be_api.core.config import Settings
from who2be_api.core.errors import ApiError
from who2be_api.licensing.entitlement import FREE_WORKSPACE_QUOTA, PRO_WORKSPACE_QUOTA
from who2be_api.repositories.entitlement_repository import PgEntitlementRepository
from who2be_api.services.workspace_quota_service import WorkspaceQuotaService
from who2be_billing.webhook import map_event_to_entitlement


class _NullTransaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *exc: object) -> bool:
        return False


class _StubConnection:
    """Faengt die zwei Writes von `PgEntitlementRepository.upsert` ab."""

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
                token_quota,
                storage_quota_bytes,
                workspace_quota,
                grace_until,
                *_rest,
            ) = args
            self._pool.entitlement_rows[org_id] = {
                "status": status,
                "features": list(features),
                "expires_at": expires_at,
                "mcp_monthly_quota": mcp_monthly_quota,
                "mcp_rate_per_min": mcp_rate_per_min,
                "token_quota": token_quota,
                "storage_quota_bytes": storage_quota_bytes,
                "workspace_quota": workspace_quota,
                "grace_until": grace_until,
            }
        elif normalized.startswith("INSERT INTO entitlement_history"):
            pass  # Journal ist fuer diese Kette irrelevant — die SSoT genuegt.
        else:  # pragma: no cover - Schutz gegen stille Query-Drift
            raise AssertionError(f"StubPool.execute: unerwartete Query: {query!r}")


class _StubAcquire:
    def __init__(self, pool: StubPool) -> None:
        self._pool = pool

    async def __aenter__(self) -> _StubConnection:
        return _StubConnection(self._pool)

    async def __aexit__(self, *exc: object) -> bool:
        return False


class StubPool:
    """In-Memory-Ersatz fuer `asyncpg.Pool` — traegt echte Repositories."""

    def __init__(self, *, org_id: UUID, workspace_count: int) -> None:
        self._org_id = org_id
        self._workspace_count = workspace_count
        self.entitlement_rows: dict[UUID, dict[str, Any]] = {}
        self.count_calls = 0

    async def fetchval(self, query: str, *args: Any) -> Any:
        normalized = " ".join(query.split())
        if "FROM workspace WHERE org_id" in normalized:
            assert args[0] == self._org_id
            self.count_calls += 1
            return self._workspace_count
        raise AssertionError(f"StubPool.fetchval: unerwartete Query: {query!r}")

    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None:
        normalized = " ".join(query.split())
        if "FROM org_entitlement WHERE org_id" in normalized:
            return self.entitlement_rows.get(args[0])
        raise AssertionError(f"StubPool.fetchrow: unerwartete Query: {query!r}")

    def acquire(self) -> _StubAcquire:
        return _StubAcquire(self)


def _subscription_event(
    event_type: str,
    *,
    org_id: UUID,
    current_period_end: int | None = None,
    **meta: Any,
) -> dict[str, Any]:
    obj: dict[str, Any] = {
        "id": "sub_576",
        "metadata": {"org_id": str(org_id), **meta},
    }
    if current_period_end is not None:
        obj["current_period_end"] = current_period_end
    return {"type": event_type, "data": {"object": obj}}


def _persist_event(pool: StubPool, org_id: UUID, event: dict[str, Any]) -> None:
    """Echtes Mapping + echte Persistenz — nur die DB-Verbindung ist gefakt."""
    update = map_event_to_entitlement(event)
    assert update is not None
    assert update.org_id == org_id
    asyncio.run(
        PgEntitlementRepository(pool).upsert(
            org_id,
            update.entitlement,
            source="webhook",
            external_ref=update.external_ref,
        )
    )


def _enforce(pool: StubPool, org_id: UUID) -> None:
    service = WorkspaceQuotaService(pool, Settings(edition="cloud"))
    asyncio.run(service.enforce(org_id))


@pytest.mark.parametrize(
    "event_type",
    ["customer.subscription.deleted", "invoice.payment_failed"],
)
def test_downgrade_falls_back_to_free_workspace_quota(event_type: str) -> None:
    """Nach Kuendigung/Fehlzahlung gilt Free = 1 — nicht „unbegrenzt"."""
    org_id = uuid4()
    pool = StubPool(org_id=org_id, workspace_count=FREE_WORKSPACE_QUOTA)

    _persist_event(pool, org_id, _subscription_event(event_type, org_id=org_id))
    # Der Beleg, dass dieser Test den echten Pfad prueft und nicht eine Annahme:
    # in der persistierten SSoT-Zeile steht wirklich NULL.
    assert pool.entitlement_rows[org_id]["status"] == "inactive"
    assert pool.entitlement_rows[org_id]["workspace_quota"] is None

    with pytest.raises(ApiError) as exc:
        _enforce(pool, org_id)
    assert isinstance(exc.value, HTTPException)
    assert exc.value.status_code == 402
    assert exc.value.reason == "workspace_quota_exceeded"
    assert exc.value.params == {"limit": FREE_WORKSPACE_QUOTA}
    assert pool.count_calls == 1  # gezaehlt wurde wirklich, nicht durchgewunken


def test_legacy_paid_subscription_without_the_key_gets_the_pro_workspace_quota() -> None:
    """Bestands-Abo ohne `workspace_quota`-Metadatum: Pro-Wert, nicht Free.

    Eine vor #576 angelegte Subscription traegt den Metadata-Key nicht. Ein
    Backfill der DB-Spalte heilte das nicht, weil der naechste Webhook den Wert
    wieder auf NULL setzt — und ein Free-Rueckfall wuerde zahlende Kunden an
    ihrem zweiten Workspace aussperren.
    """
    org_id = uuid4()
    pool = StubPool(org_id=org_id, workspace_count=PRO_WORKSPACE_QUOTA - 1)

    _persist_event(
        pool,
        org_id,
        _subscription_event(
            "customer.subscription.updated",
            org_id=org_id,
            current_period_end=int(time.time()) + 30 * 24 * 3600,
            license_policy="core,agents",
        ),
    )
    assert pool.entitlement_rows[org_id]["status"] == "active"
    assert pool.entitlement_rows[org_id]["workspace_quota"] is None

    # Einer unter Pro geht durch …
    _enforce(pool, org_id)
    assert pool.count_calls == 1

    # … am Pro-Wert ist Schluss.
    pool_at_limit = StubPool(org_id=org_id, workspace_count=PRO_WORKSPACE_QUOTA)
    pool_at_limit.entitlement_rows = pool.entitlement_rows
    with pytest.raises(ApiError) as exc:
        _enforce(pool_at_limit, org_id)
    assert exc.value.params == {"limit": PRO_WORKSPACE_QUOTA}
