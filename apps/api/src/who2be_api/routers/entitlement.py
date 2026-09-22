"""Entitlement-Read-Endpoint (Kern, editionsunabhaengig).

Reiner **Read** auf die Org-SSoT (`org_entitlement` via `EntitlementPort`) +
aktueller MCP-Verbrauch — fuer den Billing-Slot der Web-UI. Bewusst im Kern (kein
`plans`/`mollie`): die Schreibseite (Webhook/Checkout/Override) lebt im optionalen
`who2be-billing`-Paket (ADR-0029) und ist im On-Prem-Artefakt nicht vorhanden.

On-Prem liefert dieser Endpoint `edition='onprem'`; die Web-UI blendet den
Billing-Slot dort ohnehin schon zur Build-Zeit aus (Tree-Shaking).
"""

from __future__ import annotations

from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from who2be_api.core.config import get_settings
from who2be_api.core.db import get_pool
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.licensing.edition import current_edition, is_cloud
from who2be_api.licensing.service import build_entitlement_port
from who2be_api.repositories.mcp_usage_repository import PgMcpUsageRepository

# Re-Export unter dem historischen Namen (`import … as …` = expliziter
# Re-Export): `who2be_billing.router` importiert `resolve_org_id` von hier;
# die Implementierung lebt jetzt geteilt im Workspace-Repository (COD-2).
from who2be_api.repositories.workspace_repository import resolve_org_id as resolve_org_id
from who2be_api.services.mcp_limit_service import current_period

# Dieselbe Summen-Query, die `StorageQuotaService` durchsetzt — importiert
# statt kopiert, damit Anzeige und Gate nicht auseinanderlaufen koennen.
from who2be_api.services.storage_quota_service import STORAGE_USED_SQL

router = APIRouter(prefix="/billing", tags=["billing"])

Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]
Pool = Annotated[asyncpg.Pool, Depends(get_pool)]


class EntitlementUsage(BaseModel):
    """Aktueller MCP-Verbrauch der laufenden Periode + belegter Speicher."""

    period: str
    count: int
    # Summe der abgelegten Blob-Bytes dieses Workspaces (Issue #536). Anders
    # als `count` ist das keine Periodengroesse, sondern ein Bestand.
    storage_bytes: int = 0


class EntitlementInfo(BaseModel):
    """Entitlement-Snapshot fuer die Web-Anzeige (Billing-Slot)."""

    edition: str
    status: str
    features: list[str]
    expires_at: str | None
    mcp_monthly_quota: int | None
    mcp_rate_per_min: int | None
    # Die **tatsaechlich geltende** Grenze (`Entitlement.effective_token_quota`),
    # nicht das rohe Feld: in der Cloud bedeutet ein leeres Feld nicht
    # „unbegrenzt", sondern „nicht gesetzt" und faellt auf den Tarifwert zurueck
    # (Issue #538). Anzeige und Gate duerfen nicht divergieren. `None` = wirklich
    # unbegrenzt (On-Prem/OSS).
    token_quota: int | None
    # `None` = unbegrenzt (On-Prem/OSS sowie Bestands-Entitlements vor 0084).
    storage_quota_bytes: int | None
    # Die **tatsaechlich geltende** Grenze (`Entitlement.effective_workspace_quota`),
    # aus demselben Grund wie bei `token_quota`: in der Cloud heisst ein leeres
    # Feld „nicht gesetzt" und faellt auf den Tarifwert zurueck (Issue #576).
    # `None` = wirklich unbegrenzt (On-Prem/OSS).
    workspace_quota: int | None
    # Dunning-Signal: gesetzt, solange eine fehlgeschlagene Zahlung in der
    # Grace-Period nachgeholt werden kann (Banner in der Web-UI).
    grace_until: str | None
    usage: EntitlementUsage


@router.get("/entitlement")
async def get_entitlement(ctx: Ctx, pool: Pool) -> EntitlementInfo:
    """Aufgeloestes Entitlement + MCP-Verbrauch der Org dieses Workspaces."""
    org_id = await resolve_org_id(pool, ctx.workspace_id)
    settings = get_settings()
    port = build_entitlement_port(pool, settings)
    entitlement = await port.resolve(org_id)
    period = current_period()
    count = await PgMcpUsageRepository(pool).current(org_id, period)
    # Belegter Speicher: dieselbe Summe, die `StorageQuotaService` durchsetzt —
    # bewusst dieselbe Query-Semantik, damit Anzeige und Gate nicht auseinander
    # laufen koennen. Der Tabellen-Store (ADR-0049) zaehlt in beiden nicht mit.
    used_storage = await pool.fetchval(STORAGE_USED_SQL, ctx.workspace_id)
    return EntitlementInfo(
        edition=current_edition(),
        status=entitlement.status,
        features=sorted(entitlement.features),
        expires_at=entitlement.expires_at.isoformat() if entitlement.expires_at else None,
        mcp_monthly_quota=entitlement.mcp_monthly_quota,
        mcp_rate_per_min=entitlement.mcp_rate_per_min,
        token_quota=entitlement.effective_token_quota(cloud=is_cloud(settings)),
        storage_quota_bytes=entitlement.storage_quota_bytes,
        workspace_quota=entitlement.effective_workspace_quota(cloud=is_cloud(settings)),
        grace_until=entitlement.grace_until.isoformat() if entitlement.grace_until else None,
        usage=EntitlementUsage(period=period, count=count, storage_bytes=int(used_storage or 0)),
    )
