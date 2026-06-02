"""`EntitlementService` + Adapter-Auswahl (Plan §3.5/§3.6).

Der Service ist der einzige Kern-Einstieg: `resolve(org_id) -> Entitlement`.
`build_entitlement_port` waehlt den Adapter rein nach Edition — Cloud liest die
Webhook-Persistenz, On-Prem die offline signierte Lizenz. Kein gated Check kennt
den konkreten Adapter.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg

from who2be_api.core.config import Settings, get_settings
from who2be_api.licensing.adapters.cloud import CloudEntitlementAdapter
from who2be_api.licensing.adapters.onprem import OnPremEntitlementAdapter
from who2be_api.licensing.edition import is_cloud
from who2be_api.licensing.entitlement import Entitlement
from who2be_api.licensing.port import EntitlementPort
from who2be_api.repositories.entitlement_repository import PgEntitlementRepository


def build_entitlement_port(pool: asyncpg.Pool, settings: Settings | None = None) -> EntitlementPort:
    """Waehlt den Adapter nach Edition: Cloud-DB vs. On-Prem-Lizenzdatei."""
    resolved = settings or get_settings()
    if is_cloud(resolved):
        return CloudEntitlementAdapter(PgEntitlementRepository(pool))
    return OnPremEntitlementAdapter(resolved)


class EntitlementService:
    """Kern-Fassade: loest die Org-Nutzungsrechte ueber den Port auf."""

    def __init__(self, port: EntitlementPort) -> None:
        self._port = port

    async def resolve(self, org_id: UUID) -> Entitlement:
        return await self._port.resolve(org_id)
