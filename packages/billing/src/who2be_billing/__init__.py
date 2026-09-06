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

from who2be_api.core.config import Settings
from who2be_billing import router as _router

__all__ = ["include_routers"]


def include_routers(app: FastAPI, *, workspace_prefix: str, settings: Settings) -> None:
    """Registriert die Billing-Schreib-Routen an der Kern-App.

    - Top-Level (anonyme, signatur-/pull-gesicherte Webhooks): `/v1/billing/...`.
    - Workspace-scoped (Checkout/Override, admin): unter `workspace_prefix`.

    Der generische HMAC-Webhook (`webhook_router`) wird **nur** gemountet, wenn
    ein `billing_webhook_secret` konfiguriert ist (Issue #452, Massnahme 5):
    ohne Secret waere jede Signatur ohnehin fail-closed ungueltig (400) — die
    Route soll dann aber gar nicht erst existieren (404), statt als
    unkonfigurierter Endpunkt discoverable zu sein. Der Mollie-Pull-Webhook
    braucht kein Signatur-Secret (eigene Absicherung ueber den aktiven Fetch,
    siehe `mollie.py`) und wird davon unabhaengig immer gemountet.

    `settings` wird uebergeben statt hier selbst geholt (Issue #463 Punkt 2):
    der einzige Aufrufer (`who2be_api.main._register_billing_if_present`) haelt
    das Objekt bereits und entscheidet eine Zeile darueber mit `is_cloud(settings)`
    daran. Ein eigener `get_settings()`-Aufruf haette hier bedeutet, dass ein
    `create_app(settings=…)` mit abweichendem `billing_webhook_secret` nach der
    UMGEBUNG mountet statt nach dem uebergebenen Objekt — die Abweichung war der
    Selbstaufruf, nicht das Durchreichen.
    """
    if settings.billing_webhook_secret:
        app.include_router(_router.webhook_router)
    app.include_router(_router.mollie_webhook_router)
    app.include_router(_router.router, prefix=workspace_prefix)
