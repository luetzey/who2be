"""`EntitlementPort` — die Grenze zwischen Kern und Lizenz-Herkunft (Plan §3.5/§3.6).

Hexagonal (Ports & Adapters): der Kern kennt nur `resolve(org_id) -> Entitlement`.
Welcher Adapter dahinter steckt — Cloud-Webhook-DB (`adapters/cloud.py`) oder
offline signierte On-Prem-Lizenz (`adapters/onprem.py`) — ist austauschbar und
fuer die gated Checks unsichtbar.
"""

from typing import Protocol
from uuid import UUID

from who2be_api.licensing.entitlement import Entitlement


class EntitlementPort(Protocol):
    """Loest die Nutzungsrechte einer Org auf — Herkunft ist Adapter-Sache."""

    async def resolve(self, org_id: UUID) -> Entitlement: ...
