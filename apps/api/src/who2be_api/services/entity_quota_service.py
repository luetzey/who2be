"""Entity-Quota-Gate fuer Create-Mutationen (Plan §3.2 — Downgrade-Enforcement).

Spiegelbild zu `mcp_limit_service`, aber fuer **Schreib**-Pfade: bevor eine
neue Persona/Playbook/Resource/Agent angelegt wird, prueft dieses Gate, ob das
Org-Entitlement noch Luft im Entity-Kontingent hat.

Greift **ausschliesslich** in der **Cloud**-Edition (`is_cloud()`); On-Prem/OSS
ist unbegrenzt. Der Vertrag aus §3.2: **kein Datenverlust** — Bestand bleibt
les- und editierbar, nur NEUE Creates ueber das Free-Limit werden mit `402` +
Upgrade-Hinweis geblockt.

Zaehl-Granularitaet ist **pro Workspace**: das Gate laeuft im `tenant_scope` des
Create-Requests, unter dem RLS nur den aktuellen Workspace sichtbar macht. Fuer
den Free-Tier (Personal-Org mit genau einem Workspace) ist das deckungsgleich
mit „pro Org".
"""

from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID

import asyncpg
from fastapi import Depends, HTTPException, status

from who2be_api.core.config import Settings, get_settings
from who2be_api.core.db import get_pool
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.licensing.edition import is_cloud
from who2be_api.licensing.entitlement import Entitlement
from who2be_api.licensing.service import build_entitlement_port

# Summiert die Inhalts-Entities eines Workspaces. Die App-seitigen
# `workspace_id`-Filter bleiben erste Verteidigungslinie (RLS ist die zweite).
_COUNT_QUERY = (
    "SELECT "
    "  (SELECT count(*) FROM persona  WHERE workspace_id = $1) "
    "+ (SELECT count(*) FROM playbook WHERE workspace_id = $1) "
    "+ (SELECT count(*) FROM resource WHERE workspace_id = $1) "
    "+ (SELECT count(*) FROM agent    WHERE workspace_id = $1)"
)


class EntityQuotaService:
    """Setzt das Entity-Kontingent des Org-Entitlements an Create-Routen durch."""

    def __init__(self, pool: asyncpg.Pool, settings: Settings | None = None) -> None:
        self._pool = pool
        self._settings = settings or get_settings()

    async def _resolve_org_id(self, workspace_id: UUID) -> UUID:
        org_id = await self._pool.fetchval(
            "SELECT org_id FROM workspace WHERE id = $1",
            workspace_id,
        )
        if org_id is None:
            # Sollte nie passieren — die Workspace-Membership ist bereits geprueft.
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Workspace ohne Organisation.",
            )
        return cast(UUID, org_id)

    async def _count_entities(self, workspace_id: UUID) -> int:
        return cast(int, await self._pool.fetchval(_COUNT_QUERY, workspace_id))

    async def enforce(self, ctx: WorkspaceContext) -> None:
        """Wirft `402`, wenn ein weiterer Create das Free-Entity-Limit sprengt."""
        if not is_cloud(self._settings):
            return

        org_id = await self._resolve_org_id(ctx.workspace_id)
        port = build_entitlement_port(self._pool, self._settings)
        entitlement: Entitlement = await port.resolve(org_id)

        limit = entitlement.entity_limit()
        if limit is None:
            return  # Paid/unbegrenzt — kein Zaehl-Roundtrip noetig.

        current = await self._count_entities(ctx.workspace_id)
        if current >= limit:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=(
                    f"Free-Tarif erreicht das Limit von {limit} Eintraegen je Workspace. "
                    "Upgrade auf Pro hebt die Grenze auf — Bestehendes bleibt nutzbar."
                ),
            )


async def enforce_entity_quota(
    ctx: Annotated[WorkspaceContext, Depends(get_current_workspace)],
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> None:
    """FastAPI-Dependency: haengt an den POST-Create-Routen der Inhalts-Entities."""
    service = EntityQuotaService(pool)
    await service.enforce(ctx)
