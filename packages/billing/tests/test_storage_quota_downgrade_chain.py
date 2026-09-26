"""Kettentest Downgrade → Entitlement → Speicher-Deckel (Issue #536, Karte W8/P2).

Dritter Zwilling von `test_token_quota_downgrade_chain.py` (#538) und
`test_workspace_quota_downgrade_chain.py` (#576), und aus demselben Grund
noetig: der Revoke-Pfad des Webhooks schreibt
`Entitlement(status="inactive", features=frozenset())` **ohne** die Grenze,
also landet `storage_quota_bytes` als `NULL` in der SSoT-Zeile. Ohne den
Cloud-Rueckfall in `Entitlement.effective_storage_quota_bytes` hiesse dieses
`NULL` „unbegrenzt" — ausgerechnet fuer eine gekuendigte Org. Bei den beiden
Zwillingen war dieser Fehler schon einmal gefunden worden; auf #536 wurde die
Lehre zunaechst nicht zurueckportiert.

Der Weg ist der reale: echtes `map_event_to_entitlement` → echte
`PgEntitlementRepository.upsert` (nur die DB-Verbindung ist ein In-Memory-Stub)
→ echter `CloudEntitlementAdapter` → echtes `StorageQuotaService.enforce`.

Ein Unit-Test mit handgebautem `Entitlement` koennte das nicht belegen: er
wuerde die Annahme testen, dass der Webhook `NULL` schreibt, statt sie zu
pruefen.

`sum_calls` ist der Beleg, dass das Gate wirklich gezaehlt hat: ohne Rueckfall
steigt `enforce` am `limit is None`-Early-Return aus, **ohne** die
Verbrauchssumme abzufragen — der Zaehler bliebe bei 0.
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
from who2be_api.core.security import WorkspaceContext
from who2be_api.licensing.entitlement import (
    FREE_STORAGE_QUOTA_BYTES,
    PRO_STORAGE_QUOTA_BYTES,
)
from who2be_api.repositories.entitlement_repository import PgEntitlementRepository
from who2be_api.services.storage_quota_service import StorageQuotaService
from who2be_billing.webhook import map_event_to_entitlement
from who2be_models import WorkspaceRole

# Verbrauch klar ueber Free (100 MiB), klar unter Pro (10 GiB) — dieselbe
# Gegenprobe wie in der Befund-Sonde der Karte.
USED_BYTES = 200 * 1024 * 1024


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

    def __init__(self, *, org_id: UUID, workspace_id: UUID, used_bytes: int) -> None:
        self._org_id = org_id
        self._workspace_id = workspace_id
        self._used_bytes = used_bytes
        self.entitlement_rows: dict[UUID, dict[str, Any]] = {}
        self.sum_calls = 0

    async def fetchval(self, query: str, *args: Any) -> Any:
        normalized = " ".join(query.split())
        if "FROM workspace WHERE id" in normalized:
            assert args[0] == self._workspace_id
            return self._org_id
        if "FROM wa_blob WHERE workspace_id" in normalized:
            assert args[0] == self._workspace_id
            self.sum_calls += 1
            return self._used_bytes
        raise AssertionError(f"StubPool.fetchval: unerwartete Query: {query!r}")

    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None:
        normalized = " ".join(query.split())
        if "FROM org_entitlement WHERE org_id" in normalized:
            return self.entitlement_rows.get(args[0])
        raise AssertionError(f"StubPool.fetchrow: unerwartete Query: {query!r}")

    def acquire(self) -> _StubAcquire:
        return _StubAcquire(self)


def _ctx(workspace_id: UUID) -> WorkspaceContext:
    return WorkspaceContext(
        workspace_id=workspace_id,
        user_id=uuid4(),
        role=WorkspaceRole.admin,
        is_api_token=False,
    )


def _subscription_event(
    event_type: str,
    *,
    org_id: UUID,
    current_period_end: int | None = None,
    **meta: Any,
) -> dict[str, Any]:
    obj: dict[str, Any] = {
        "id": "sub_536",
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


def _enforce(pool: StubPool, workspace_id: UUID) -> None:
    service = StorageQuotaService(pool, Settings(edition="cloud"))
    asyncio.run(service.enforce(_ctx(workspace_id)))


def _activate_pro(pool: StubPool, org_id: UUID) -> None:
    _persist_event(
        pool,
        org_id,
        _subscription_event(
            "customer.subscription.updated",
            org_id=org_id,
            current_period_end=int(time.time()) + 30 * 24 * 3600,
            license_policy="core agents",
            storage_quota_bytes=str(PRO_STORAGE_QUOTA_BYTES),
        ),
    )


@pytest.mark.parametrize(
    "event_type",
    ["customer.subscription.deleted", "invoice.payment_failed"],
)
def test_downgrade_falls_back_to_free_storage_quota(event_type: str) -> None:
    """Nach Kuendigung/Fehlzahlung gilt Free = 100 MiB — nicht „unbegrenzt"."""
    org_id, workspace_id = uuid4(), uuid4()
    pool = StubPool(org_id=org_id, workspace_id=workspace_id, used_bytes=USED_BYTES)

    # 1) Pro aktiv: 10 GiB Grenze, 200 MiB belegt — der Ingest geht durch.
    _activate_pro(pool, org_id)
    assert pool.entitlement_rows[org_id]["storage_quota_bytes"] == PRO_STORAGE_QUOTA_BYTES
    _enforce(pool, workspace_id)
    assert pool.sum_calls == 1

    # 2) Kuendigung/Fehlzahlung: der Revoke-Pfad schreibt das Feld nicht. Der
    #    Beleg, dass dieser Test den echten Pfad prueft und nicht eine Annahme:
    #    in der persistierten SSoT-Zeile steht wirklich NULL.
    _persist_event(pool, org_id, _subscription_event(event_type, org_id=org_id))
    assert pool.entitlement_rows[org_id]["status"] == "inactive"
    assert pool.entitlement_rows[org_id]["storage_quota_bytes"] is None

    # 3) Erneuter Ingest: 402, weil 200 MiB ueber dem Free-Wert liegen.
    assert USED_BYTES > FREE_STORAGE_QUOTA_BYTES
    with pytest.raises(ApiError) as exc:
        _enforce(pool, workspace_id)
    assert isinstance(exc.value, HTTPException)
    assert exc.value.status_code == 402
    assert exc.value.reason == "storage_quota_exceeded"
    assert exc.value.params == {"limit": FREE_STORAGE_QUOTA_BYTES, "used": USED_BYTES}
    # Gezaehlt wurde wirklich — ohne Rueckfall waere das Gate am
    # `limit is None`-Early-Return ausgestiegen und der Zaehler bei 1 geblieben.
    assert pool.sum_calls == 2


def test_legacy_paid_subscription_without_the_key_gets_the_pro_storage_quota() -> None:
    """Bestands-Abo ohne `storage_quota_bytes`-Metadatum: Pro-Wert, nicht Free.

    Eine vor #536 angelegte Subscription traegt den Metadata-Key nicht. Ein
    Backfill der DB-Spalte heilte das nicht, weil der naechste Webhook den Wert
    wieder auf NULL setzt — und ein Free-Rueckfall wuerde zahlende Kunden bei
    200 MiB aussperren.
    """
    org_id, workspace_id = uuid4(), uuid4()
    pool = StubPool(org_id=org_id, workspace_id=workspace_id, used_bytes=USED_BYTES)

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
    assert pool.entitlement_rows[org_id]["storage_quota_bytes"] is None

    # 200 MiB unter Pro geht durch — und die Summe wurde abgefragt, das Gate
    # hat also nicht bloss durchgewunken.
    _enforce(pool, workspace_id)
    assert pool.sum_calls == 1

    # … am Pro-Wert ist Schluss.
    pool_at_limit = StubPool(
        org_id=org_id,
        workspace_id=workspace_id,
        used_bytes=PRO_STORAGE_QUOTA_BYTES,
    )
    pool_at_limit.entitlement_rows = pool.entitlement_rows
    with pytest.raises(ApiError) as exc:
        _enforce(pool_at_limit, workspace_id)
    assert exc.value.params == {
        "limit": PRO_STORAGE_QUOTA_BYTES,
        "used": PRO_STORAGE_QUOTA_BYTES,
    }
