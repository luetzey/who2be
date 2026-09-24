"""Kettentest Downgrade → Entitlement → Token-Quota-Gate (Issue #538, Review R1).

Belegt End-to-End, dass eine **gekuendigte oder zahlungssaeumige** Cloud-Org
nicht unbegrenzt Tokens anlegen kann. Der Weg ist der reale:

1. Ein echtes Revoke-Event (`customer.subscription.deleted` bzw.
   `invoice.payment_failed`) geht durch das **echte**
   `map_event_to_entitlement` — nicht durch ein handgebautes `Entitlement`.
   Genau das ist der Punkt: der Webhook schreibt beim Revoke
   `Entitlement(status="inactive", features=frozenset())` **ohne**
   `token_quota` (`webhook.py:441`).
2. Die **echte** `PgEntitlementRepository.upsert` persistiert das (nur die
   DB-Verbindung ist ein In-Memory-`StubPool`, wie in
   `test_checkout_webhook_entitlement_limit_chain.py`) — `token_quota` landet
   als `None` in der SSoT-Zeile.
3. Der **echte** `CloudEntitlementAdapter` liest sie zurueck, und das **echte**
   `TokenQuotaService.enforce` entscheidet.

Ohne den Cloud-Rueckfall in `Entitlement.effective_token_quota` liefe Schritt 3
kommentarlos durch (`None` = unbegrenzt) und eine gekuendigte Org duerfte
beliebig viele Tokens anlegen. Mit ihm gilt nach der Kuendigung Free = 3.

Derselbe Weg deckt den zweiten Fall mit ab, den ein Backfill nicht loest: eine
**Bestands-Subscription**, die vor #538 angelegt wurde und den Metadata-Key
`token_quota` schlicht nicht traegt.
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
from who2be_api.licensing.entitlement import FREE_TOKEN_QUOTA, PRO_TOKEN_QUOTA
from who2be_api.repositories.entitlement_repository import PgEntitlementRepository
from who2be_api.services.token_quota_service import TokenQuotaService
from who2be_billing.webhook import map_event_to_entitlement
from who2be_models import WorkspaceRole


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
    """In-Memory-Ersatz fuer `asyncpg.Pool` — traegt echte Repositories.

    Bedient die Queries von `PgEntitlementRepository` (fetch/upsert) und die
    zwei Reads von `TokenQuotaService` (Workspace→Org, Token-Count).
    """

    def __init__(self, *, workspace_id: UUID, org_id: UUID, token_count: int) -> None:
        self._workspace_id = workspace_id
        self._org_id = org_id
        self._token_count = token_count
        self.entitlement_rows: dict[UUID, dict[str, Any]] = {}
        self.count_calls = 0

    async def fetchval(self, query: str, *args: Any) -> Any:
        normalized = " ".join(query.split())
        if "FROM workspace WHERE id" in normalized:
            assert args[0] == self._workspace_id
            return self._org_id
        if "FROM api_token" in normalized:
            self.count_calls += 1
            return self._token_count
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
        "id": "sub_538",
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


def _ctx(workspace_id: UUID) -> WorkspaceContext:
    return WorkspaceContext(
        workspace_id=workspace_id,
        user_id=uuid4(),
        role=WorkspaceRole.editor,
        is_api_token=False,
    )


def _enforce(pool: StubPool, workspace_id: UUID) -> None:
    service = TokenQuotaService(pool, Settings(edition="cloud"))
    asyncio.run(service.enforce(_ctx(workspace_id)))


@pytest.mark.parametrize(
    "event_type",
    ["customer.subscription.deleted", "invoice.payment_failed"],
)
def test_downgrade_falls_back_to_free_quota_instead_of_unlimited(event_type: str) -> None:
    """Nach Kuendigung/Fehlzahlung gilt Free = 3 — nicht „unbegrenzt".

    Der Revoke-Pfad des Webhooks kennt `token_quota` nicht und schreibt NULL.
    Ohne Cloud-Rueckfall hiesse das unbegrenzt; dieser Test haelt fest, dass es
    stattdessen auf `FREE_TOKEN_QUOTA` faellt.
    """
    workspace_id, org_id = uuid4(), uuid4()
    pool = StubPool(workspace_id=workspace_id, org_id=org_id, token_count=FREE_TOKEN_QUOTA)

    _persist_event(pool, org_id, _subscription_event(event_type, org_id=org_id))
    # Der Beleg, dass dieser Test den echten Pfad prueft und nicht eine Annahme:
    # in der persistierten SSoT-Zeile steht wirklich NULL.
    assert pool.entitlement_rows[org_id]["status"] == "inactive"
    assert pool.entitlement_rows[org_id]["token_quota"] is None

    with pytest.raises(ApiError) as exc:
        _enforce(pool, workspace_id)
    assert isinstance(exc.value, HTTPException)
    assert exc.value.status_code == 402
    assert exc.value.reason == "token_quota_exceeded"
    assert exc.value.params == {"limit": FREE_TOKEN_QUOTA}
    assert pool.count_calls == 1  # gezaehlt wurde wirklich, nicht durchgewunken


def test_legacy_paid_subscription_without_the_key_gets_the_pro_quota() -> None:
    """Bestands-Abo ohne `token_quota`-Metadatum: Pro-Wert, nicht unbegrenzt.

    Eine vor #538 angelegte Subscription traegt den Metadata-Key nicht — ein
    Backfill der DB-Spalte wuerde das nicht heilen, weil der naechste Webhook
    den Wert wieder auf NULL setzt. Ein zahlender Kunde darf dabei aber auch
    nicht still auf den Free-Wert gedeckelt werden.
    """
    workspace_id, org_id = uuid4(), uuid4()
    pool = StubPool(workspace_id=workspace_id, org_id=org_id, token_count=PRO_TOKEN_QUOTA - 1)

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
    assert pool.entitlement_rows[org_id]["token_quota"] is None

    # Einer unter Pro geht durch …
    _enforce(pool, workspace_id)
    assert pool.count_calls == 1

    # … am Pro-Wert ist Schluss.
    pool_at_limit = StubPool(workspace_id=workspace_id, org_id=org_id, token_count=PRO_TOKEN_QUOTA)
    pool_at_limit.entitlement_rows = pool.entitlement_rows
    with pytest.raises(ApiError) as exc:
        _enforce(pool_at_limit, workspace_id)
    assert exc.value.params == {"limit": PRO_TOKEN_QUOTA}
