"""Billing — Cloud-Schreibseite (optionales `who2be-billing`-Paket, ADR-0029).

Drei Schreib-Endpunkte, alle **nur in der Cloud-Edition** aktiv (das Paket ist im
On-Prem-Artefakt gar nicht installiert; zusaetzlich Runtime-`_require_cloud` als
Defense-in-Depth):
- ``POST /v1/billing/webhook`` (top-level, anonym): generischer HMAC-Webhook,
  **verifiziert die Signatur immer**, leitet daraus das Org-Entitlement ab.
- ``POST /v1/billing/mollie/webhook`` (top-level, form ``id=``): Mollie-Pull-Ping
  → aktiver API-Fetch → Entitlement-Upsert.
- ``POST /v1/workspaces/{ws}/billing/checkout`` (admin): startet einen Mollie-
  Checkout fuer den gebuchten Tier.

Guardrails (ADR-0028): kein Webhook ohne Signaturpruefung; Schreiben ausschliesslich
in `org_entitlement` ueber `EntitlementRepository`; Zugriff am Entitlement, nicht am
rohen Zahlungsstatus.
"""

from __future__ import annotations

import hmac
import logging
from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from pydantic import BaseModel

from who2be_api.core.config import Settings, get_settings
from who2be_api.core.db import get_pool
from who2be_api.core.security import WorkspaceContext, get_current_workspace, require_role
from who2be_api.licensing.edition import is_cloud
from who2be_api.repositories.entitlement_repository import PgEntitlementRepository
from who2be_api.routers.entitlement import resolve_org_id
from who2be_billing.mollie import MollieBillingService, MollieError, SdkMollieGateway
from who2be_billing.plans import plan_by_code
from who2be_billing.processed_event_repository import PgProcessedEventRepository
from who2be_billing.webhook import (
    WebhookError,
    map_event_to_entitlement,
    parse_event,
    verify_webhook_signature,
)
from who2be_models import WorkspaceRole

logger = logging.getLogger(__name__)

webhook_router = APIRouter(prefix="/v1/billing", tags=["billing"])
mollie_webhook_router = APIRouter(prefix="/v1/billing/mollie", tags=["billing"])
router = APIRouter(prefix="/billing", tags=["billing"])

Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]

# Provider-Signatur-Header (Stripe: `Stripe-Signature`; generisch: `X-Webhook-Signature`).
_SIGNATURE_HEADERS = ("stripe-signature", "x-webhook-signature")


def _require_cloud() -> None:
    if not is_cloud():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nicht verfuegbar.")


def _signature_header(request: Request) -> str | None:
    for name in _SIGNATURE_HEADERS:
        value = request.headers.get(name)
        if value:
            return value
    return None


def get_mollie_service() -> MollieBillingService:
    """Dependency: baut den Mollie-Pull-Service (nur Cloud + konfigurierter Key).

    Die Reihenfolge ist bewusst **Cloud-Check zuerst** (404 On-Prem, ohne DB-/
    Key-Kontakt), dann Key (503), dann lazy Pool (503). Tests ueberschreiben diese
    Dependency mit einem Fake-Gateway-Service und umgehen so Cloud/Key/Pool.
    """
    _require_cloud()
    settings = get_settings()
    if not settings.mollie_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mollie ist nicht konfiguriert.",
        )
    try:
        pool = get_pool()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Datenbank nicht verfuegbar.",
        ) from exc
    gateway = SdkMollieGateway(settings.mollie_api_key)
    return MollieBillingService(
        gateway,
        PgEntitlementRepository(pool),
        PgProcessedEventRepository(pool),
        grace_days=settings.mollie_grace_days,
    )


MollieService = Annotated[MollieBillingService, Depends(get_mollie_service)]


def _verify_mollie_token(request: Request, settings: Settings) -> None:
    """Optionales Token-Gate fuer den Mollie-Webhook (`?token=…`).

    Mollie signiert seine Webhooks nicht — die Hauptsicherung ist das aktive
    Nachfetchen ueber die Mollie-API. Ist zusaetzlich ein `MOLLIE_WEBHOOK_SECRET`
    gesetzt, muss der Query-Token konstant-zeitlich passen, sonst 403.
    """
    secret = settings.mollie_webhook_secret
    if not secret:
        return
    token = request.query_params.get("token") or ""
    if not hmac.compare_digest(token, secret):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ungueltiges Webhook-Token.",
        )


async def _fetch_billing_identity(
    pool: asyncpg.Pool, org_id: UUID, user_id: UUID
) -> tuple[str, str | None]:
    """Org-Name (Mollie-Customer-Name) + best-effort User-Email fuer den Checkout."""
    org_name = await pool.fetchval("SELECT name FROM organization WHERE id = $1", org_id)
    email: str | None = None
    try:
        raw_email = await pool.fetchval("SELECT email FROM auth.users WHERE id = $1", user_id)
        email = raw_email if isinstance(raw_email, str) and raw_email else None
    except asyncpg.PostgresError:
        # `auth.users` fehlt in reinen Test-DBs — Email ist fuer Mollie optional.
        email = None
    return (str(org_name) if org_name else "Who2Be Organisation", email)


@webhook_router.post("/webhook", status_code=status.HTTP_200_OK)
async def billing_webhook(request: Request) -> dict[str, bool]:
    """Verifiziert + verarbeitet ein Provider-Webhook (nur Cloud).

    Der DB-Pool wird bewusst **lazy** geholt (nicht als Dependency): die 404-/400-
    Abweisungen — On-Prem bzw. fehlende/ungueltige Signatur — sollen ohne jeden
    DB-Kontakt greifen.
    """
    _require_cloud()
    settings = get_settings()
    raw = await request.body()
    signature = _signature_header(request)
    if not verify_webhook_signature(raw, signature, settings.billing_webhook_secret):
        # Fail closed: ungueltige/fehlende Signatur ODER fehlendes Secret.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ungueltige Webhook-Signatur.",
        )
    try:
        event = parse_event(raw)
        update = map_event_to_entitlement(event)
    except WebhookError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if update is None:
        # Quittiert, aber fuer das Entitlement irrelevant — der Provider soll nicht
        # erneut zustellen.
        return {"received": True}

    try:
        pool = get_pool()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Datenbank nicht verfuegbar.",
        ) from exc
    repo = PgEntitlementRepository(pool)
    await repo.upsert(
        update.org_id,
        update.entitlement,
        source="cloud",
        external_ref=update.external_ref,
    )
    return {"received": True}


# --- Mollie: Pull-Webhook + Checkout (Plan §3.2) ---------------------------------


class CheckoutRequest(BaseModel):
    """Checkout-Anfrage: welcher kostenpflichtige Tier gebucht wird."""

    plan: str = "pro"


class CheckoutResponse(BaseModel):
    """Hosted-Checkout-URL, auf die das Frontend weiterleitet."""

    checkout_url: str


@mollie_webhook_router.post("/webhook", status_code=status.HTTP_200_OK)
async def mollie_webhook(
    request: Request,
    service: MollieService,
    id: Annotated[str, Form()],
) -> dict[str, bool]:
    """Mollie-Webhook-Ping (form `id=`) → aktiver Pull + Entitlement-Upsert.

    Quittiert grundsaetzlich mit 200, damit Mollie nicht in einen Retry-Sturm
    geraet. Ein unbrauchbares/fremdes Objekt (`MollieError`, keine `org_id`) wird
    geloggt und verworfen — die Pull-Verifikation ist die Sicherung gegen
    gefaelschte Pings (Plan §3.2/M2).
    """
    _verify_mollie_token(request, get_settings())
    try:
        applied = await service.handle_webhook(
            id, webhook_url=get_settings().mollie_webhook_url or None
        )
    except MollieError:
        logger.warning("Mollie-Webhook verworfen: unbrauchbare/fremde Metadata.")
        return {"received": True}
    return {"received": applied}


@router.post("/checkout", status_code=status.HTTP_201_CREATED)
async def create_checkout(
    body: CheckoutRequest,
    ctx: Ctx,
    service: MollieService,
) -> CheckoutResponse:
    """Startet einen Mollie-Checkout fuer den gebuchten Tier (admin-only)."""
    require_role(ctx, WorkspaceRole.admin)
    plan = plan_by_code(body.plan)
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unbekannter oder nicht buchbarer Plan '{body.plan}'.",
        )
    pool = get_pool()
    org_id = await resolve_org_id(pool, ctx.workspace_id)
    customer_name, customer_email = await _fetch_billing_identity(pool, org_id, ctx.user_id)
    settings = get_settings()
    redirect_url = f"{settings.web_base_url.rstrip('/')}/settings/billing"
    checkout_url = await service.start_checkout(
        org_id=org_id,
        plan=plan,
        customer_name=customer_name,
        customer_email=customer_email,
        redirect_url=redirect_url,
        webhook_url=settings.mollie_webhook_url or None,
    )
    return CheckoutResponse(checkout_url=checkout_url)
