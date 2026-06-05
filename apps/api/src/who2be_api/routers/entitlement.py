"""Entitlement-Read-Endpoint (Kern, editionsunabhaengig).

Reiner **Read** auf die Org-SSoT (`org_entitlement` via `EntitlementPort`) +
aktueller MCP-Verbrauch — fuer den Billing-Slot der Web-UI. Bewusst im Kern (kein
`plans`/`mollie`): die Schreibseite (Webhook/Checkout/Override) lebt im optionalen
`who2be-billing`-Paket (ADR-0029) und ist im On-Prem-Artefakt nicht vorhanden.

On-Prem liefert dieser Endpoint `edition='onprem'`; die Web-UI blendet den
Billing-Slot dort ohnehin schon zur Build-Zeit aus (Tree-Shaking).
"""

from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from who2be_api.core.config import get_settings
from who2be_api.core.db import get_pool
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.licensing.edition import current_edition
from who2be_api.licensing.service import build_entitlement_port
from who2be_api.repositories.mcp_usage_repository import PgMcpUsageRepository
from who2be_api.services.mcp_limit_service import current_period

router = APIRouter(prefix="/billing", tags=["billing"])

Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]
Pool = Annotated[asyncpg.Pool, Depends(get_pool)]


class EntitlementUsage(BaseModel):
    """Aktueller MCP-Verbrauch der laufenden Periode."""

    period: str
    count: int


class EntitlementInfo(BaseModel):
    """Entitlement-Snapshot fuer die Web-Anzeige (Billing-Slot)."""

    edition: str
    status: str
    features: list[str]
    expires_at: str | None
    mcp_monthly_quota: int | None
    mcp_rate_per_min: int | None
    # Dunning-Signal: gesetzt, solange eine fehlgeschlagene Zahlung in der
    # Grace-Period nachgeholt werden kann (Banner in der Web-UI).
    grace_until: str | None
    usage: EntitlementUsage


async def resolve_org_id(pool: asyncpg.Pool, workspace_id: UUID) -> UUID:
    org_id = await pool.fetchval("SELECT org_id FROM workspace WHERE id = $1", workspace_id)
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Workspace ohne Organisation.",
        )
    return cast(UUID, org_id)


@router.get("/entitlement")
async def get_entitlement(ctx: Ctx, pool: Pool) -> EntitlementInfo:
    """Aufgeloestes Entitlement + MCP-Verbrauch der Org dieses Workspaces."""
    org_id = await resolve_org_id(pool, ctx.workspace_id)
    port = build_entitlement_port(pool, get_settings())
    entitlement = await port.resolve(org_id)
    period = current_period()
    count = await PgMcpUsageRepository(pool).current(org_id, period)
    return EntitlementInfo(
        edition=current_edition(),
        status=entitlement.status,
        features=sorted(entitlement.features),
        expires_at=entitlement.expires_at.isoformat() if entitlement.expires_at else None,
        mcp_monthly_quota=entitlement.mcp_monthly_quota,
        mcp_rate_per_min=entitlement.mcp_rate_per_min,
        grace_until=entitlement.grace_until.isoformat() if entitlement.grace_until else None,
        usage=EntitlementUsage(period=period, count=count),
    )
