"""Cloud-Adapter: liest das vom Webhook persistierte Org-Entitlement (Plan §3.5).

Der Zahlungsanbieter (Stripe/Mollie) ist fuer den **Zahlungsstatus** fuehrend und
sendet Webhooks; der `billing`-Router schreibt daraus das Org-Entitlement
(`org_entitlement`). Dieser Adapter liest nur den persistierten Stand — der Kern
sieht ausschliesslich das aufgeloeste `Entitlement`, nie den Provider.

Orgs ohne persistierten Stand (frisch registriert, vor dem ersten Webhook)
bekommen `CLOUD_FREE_ENTITLEMENT` (aktiver Free-Tier mit knappem Kontingent).
"""

from __future__ import annotations

from uuid import UUID

from who2be_api.licensing.entitlement import CLOUD_FREE_ENTITLEMENT, Entitlement
from who2be_api.repositories.entitlement_repository import EntitlementRepository


class CloudEntitlementAdapter:
    """Loest das Entitlement aus der `org_entitlement`-Persistenz auf."""

    def __init__(self, repo: EntitlementRepository) -> None:
        self._repo = repo

    async def resolve(self, org_id: UUID) -> Entitlement:
        stored = await self._repo.fetch(org_id)
        return stored if stored is not None else CLOUD_FREE_ENTITLEMENT
