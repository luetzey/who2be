"""Persistenz des Org-Entitlements (`org_entitlement`, Migration 0030).

Nur der **Cloud**-Pfad persistiert hier: der Webhook-Adapter schreibt das vom
Zahlungsanbieter abgeleitete Entitlement, der Cloud-Read-Adapter liest es. Der
On-Prem-Pfad geht nie ueber diese Tabelle (offline Lizenzdatei).
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

import asyncpg

from who2be_api.licensing.entitlement import Entitlement


def _row_to_entitlement(row: asyncpg.Record) -> Entitlement:
    features = row["features"]
    return Entitlement(
        status=row["status"],
        features=frozenset(features if isinstance(features, list) else []),
        expires_at=row["expires_at"],
        mcp_monthly_quota=row["mcp_monthly_quota"],
        mcp_rate_per_min=row["mcp_rate_per_min"],
        grace_until=row["grace_until"],
    )


class EntitlementRepository(Protocol):
    """Service-seitige Abstraktion fuer den `org_entitlement`-Zugriff."""

    async def fetch(self, org_id: UUID) -> Entitlement | None: ...

    async def upsert(
        self,
        org_id: UUID,
        entitlement: Entitlement,
        source: str,
        external_ref: str | None,
        created_by: UUID | None = None,
        reason: str | None = None,
    ) -> None: ...


class PgEntitlementRepository:
    """asyncpg-Implementierung von `EntitlementRepository`."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def fetch(self, org_id: UUID) -> Entitlement | None:
        row = await self._pool.fetchrow(
            "SELECT status, features, expires_at, mcp_monthly_quota, mcp_rate_per_min, "
            "       grace_until "
            "FROM org_entitlement WHERE org_id = $1",
            org_id,
        )
        return _row_to_entitlement(row) if row is not None else None

    async def upsert(
        self,
        org_id: UUID,
        entitlement: Entitlement,
        source: str,
        external_ref: str | None,
        created_by: UUID | None = None,
        reason: str | None = None,
    ) -> None:
        # `features` als sortierte Liste persistieren (jsonb) — stabile Reihenfolge
        # erleichtert Diffs/Debugging; die Domaene nutzt ohnehin ein frozenset.
        # `created_by`/`reason` sind das Audit des befristeten `manual_override`
        # (ADR-0028); andere Quellen schreiben hier NULL — ein neuer regulaerer
        # Stand (Mollie/Webhook) hebt damit einen vorherigen Override korrekt auf.
        await self._pool.execute(
            "INSERT INTO org_entitlement "
            "(org_id, status, features, expires_at, mcp_monthly_quota, "
            " mcp_rate_per_min, grace_until, source, external_ref, "
            " created_by, reason, updated_at) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, now()) "
            "ON CONFLICT (org_id) DO UPDATE SET "
            "  status = EXCLUDED.status, "
            "  features = EXCLUDED.features, "
            "  expires_at = EXCLUDED.expires_at, "
            "  mcp_monthly_quota = EXCLUDED.mcp_monthly_quota, "
            "  mcp_rate_per_min = EXCLUDED.mcp_rate_per_min, "
            "  grace_until = EXCLUDED.grace_until, "
            "  source = EXCLUDED.source, "
            "  external_ref = EXCLUDED.external_ref, "
            "  created_by = EXCLUDED.created_by, "
            "  reason = EXCLUDED.reason, "
            "  updated_at = now()",
            org_id,
            entitlement.status,
            sorted(entitlement.features),
            entitlement.expires_at,
            entitlement.mcp_monthly_quota,
            entitlement.mcp_rate_per_min,
            entitlement.grace_until,
            source,
            external_ref,
            created_by,
            reason,
        )
