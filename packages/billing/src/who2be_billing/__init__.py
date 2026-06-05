"""who2be-billing — optionales Cloud-Billing-Paket (ADR-0029).

Build-Zeit-Isolation: Dieses Paket (inkl. Mollie-SDK, Tarif-/Checkout-/Webhook-
Logik) ist **nur** in der Cloud-Edition installiert. Das On-Prem-Artefakt enthaelt
es physisch nicht. Richtung der Abhaengigkeit: `who2be-billing → who2be-api`
(hexagonal); der Kern kennt dieses Paket nie statisch — `who2be_api.main` bindet
es ueber optionalen Import + `is_cloud()` ein.

Die einzige Schreib-Schnittstelle zur App ist `org_entitlement` ueber
`who2be_api.repositories.entitlement_repository.EntitlementRepository`
(ADR-0028) — keine anderen App-Interna werden beruehrt.
"""

from __future__ import annotations

from fastapi import FastAPI

from who2be_billing import router as _router

__all__ = ["include_routers"]


def include_routers(app: FastAPI, *, workspace_prefix: str) -> None:
    """Registriert die Billing-Schreib-Routen an der Kern-App.

    - Top-Level (anonyme, signatur-/pull-gesicherte Webhooks): `/v1/billing/...`.
    - Workspace-scoped (Checkout/Override, admin): unter `workspace_prefix`.
    """
    app.include_router(_router.webhook_router)
    app.include_router(_router.mollie_webhook_router)
    app.include_router(_router.router, prefix=workspace_prefix)
