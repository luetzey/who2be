"""Mollie-Pull-Adapter: Billing nach dem **Pull-after-Ping**-Modell (Plan §3.2, M2).

Mollie sendet — anders als Stripe — **keine** signierten Webhook-Bodies, sondern
nur einen Ping mit der Zahlungs-`id`. Der generische HMAC-Adapter (`billing.py`)
passt darauf nicht. Stattdessen:

1. **Checkout** legt einen Mollie-Customer + eine erste Zahlung (`sequenceType=first`)
   mit Plan-Metadata an und liefert die Hosted-Checkout-URL.
2. Der **Webhook** (`POST /v1/billing/mollie/webhook`, form `id=`) fetcht das Objekt
   aktiv ueber die Mollie-API (`MOLLIE_API_KEY`) — *das* ist die Sicherheit: ein
   gefaelschter Ping liefert ein Objekt ohne unsere `org_id`-Metadata und wird
   verworfen. Bezahlte Erstzahlung ⇒ Subscription anlegen + Entitlement aktiv;
   Folge-Ping ⇒ Subscription-Status (`active`/`canceled`/`suspended`) ⇒ Tier
   bleiben/zurueck auf Free.

Die freigeschalteten Features + Limits kommen ausschliesslich aus der
**Metadata** (Guardrail §3.6: kein hartkodiertes Produkt→Feature-Mapping). Die
einzige Stelle, die einen Tier *schreibt*, ist der Checkout (`plans.py`).

**Trust-Boundary (Webhook):** `org_id` und alle Limits/Features werden NIE aus
dem Request gelesen, sondern aus dem serverseitig ueber die Mollie-API gefetchten
Objekt. Die Metadata wiederum wird ausschliesslich von unserem **admin-only**
Checkout gesetzt (`Plan.metadata(org_id)`); sie zu faelschen erfordert bereits
den `MOLLIE_API_KEY`. Ein gefaelschter/erratener Ping mit fremder `id` liefert
daher ein Objekt ohne unsere `org_id` ⇒ `MollieError` ⇒ verworfen. Tiefere
Defense-in-Depth (bezahlten Betrag gegen `plan.price_eur` pruefen, per-IP-Rate-
Limit auf dem Webhook-Pfad) ist als spaeterer Hardening-Schritt vorgemerkt
(Plan §5, Mollie-Iteration).

Die Mollie-SDK ist synchron (auf `requests`); alle Calls laufen daher in
`asyncio.to_thread`, damit der Event-Loop nicht blockiert. Die `MollieGateway`-
Schnittstelle isoliert die SDK vom Kern und macht den Service ohne Netz testbar.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from mollie.api.client import Client

from who2be_api.licensing.billing import EntitlementUpdate
from who2be_api.licensing.entitlement import CLOUD_FREE_ENTITLEMENT, Entitlement
from who2be_api.licensing.plans import (
    META_LICENSE_POLICY,
    META_MCP_MONTHLY_QUOTA,
    META_MCP_RATE_PER_MIN,
    META_ORG_ID,
    META_PLAN_CODE,
    Plan,
    plan_by_code,
)
from who2be_api.repositories.entitlement_repository import EntitlementRepository

_STATUS_ACTIVE = "active"


class MollieError(Exception):
    """Mollie-Objekt ist fuer das Entitlement unbrauchbar (fehlende/ungueltige Metadata)."""


# --- Value-Objects (entkoppeln den Kern von der SDK) -----------------------------


@dataclass(frozen=True)
class MolliePayment:
    """Reduzierte Sicht auf eine Mollie-Zahlung (nur was der Pull-Pfad braucht)."""

    id: str
    is_paid: bool
    customer_id: str | None
    subscription_id: str | None
    mandate_id: str | None
    metadata: dict[str, Any]


@dataclass(frozen=True)
class MollieSubscription:
    """Reduzierte Sicht auf eine Mollie-Subscription."""

    subscription_id: str
    status: str
    metadata: dict[str, Any]


# --- Port ------------------------------------------------------------------------


class MollieGateway(Protocol):
    """Schmale Mollie-API-Grenze — der Service kennt nur diese Operationen."""

    async def create_customer(
        self, *, name: str, email: str | None, metadata: dict[str, str]
    ) -> str: ...

    async def create_first_payment(
        self,
        *,
        customer_id: str,
        amount_eur: str,
        description: str,
        redirect_url: str,
        webhook_url: str | None,
        metadata: dict[str, str],
    ) -> str: ...

    async def get_payment(self, payment_id: str) -> MolliePayment | None: ...

    async def create_subscription(
        self,
        *,
        customer_id: str,
        amount_eur: str,
        interval: str,
        description: str,
        webhook_url: str | None,
        metadata: dict[str, str],
    ) -> str: ...

    async def get_subscription(
        self, customer_id: str, subscription_id: str
    ) -> MollieSubscription | None: ...


# --- Metadata-Parsing (Konvention §3.2) ------------------------------------------


def _metadata(raw: Any) -> dict[str, Any]:
    return raw if isinstance(raw, dict) else {}


def metadata_org_id(metadata: dict[str, Any]) -> UUID:
    """Liest `org_id` aus der Metadata — Pflichtfeld, sonst `MollieError`."""
    raw = metadata.get(META_ORG_ID)
    if not isinstance(raw, str):
        raise MollieError("Mollie-Metadata traegt keine 'org_id'.")
    try:
        return UUID(raw)
    except ValueError as exc:
        raise MollieError("Mollie-'org_id' ist keine gueltige UUID.") from exc


def _metadata_features(metadata: dict[str, Any]) -> frozenset[str]:
    raw = metadata.get(META_LICENSE_POLICY) or ""
    if not isinstance(raw, str):
        return frozenset()
    tokens = [tok.strip() for tok in raw.replace(",", " ").split()]
    return frozenset(tok for tok in tokens if tok)


def _metadata_int(metadata: dict[str, Any], key: str) -> int | None:
    raw = metadata.get(key)
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise MollieError(f"Mollie-Metadatum '{key}' ist keine Ganzzahl.") from exc


def metadata_to_entitlement(metadata: dict[str, Any]) -> Entitlement:
    """Aktives Entitlement aus der Metadata (Features + Limits)."""
    return Entitlement(
        status="active",
        features=_metadata_features(metadata),
        expires_at=None,
        mcp_monthly_quota=_metadata_int(metadata, META_MCP_MONTHLY_QUOTA),
        mcp_rate_per_min=_metadata_int(metadata, META_MCP_RATE_PER_MIN),
    )


def subscription_to_update(subscription: MollieSubscription) -> EntitlementUpdate:
    """Bildet eine Subscription auf ein Org-Entitlement ab.

    `active` ⇒ gebuchter Tier aus der Metadata; jeder andere Status
    (`canceled`/`suspended`/`completed`/`pending`) ⇒ zurueck auf **Free**
    (Guardrail §3.6: Zugriff am Entitlement, nicht am rohen Zahlungsstatus —
    Free bleibt nutzbar, statt die Org hart zu sperren).
    """
    org_id = metadata_org_id(subscription.metadata)
    if subscription.status == _STATUS_ACTIVE:
        entitlement = metadata_to_entitlement(subscription.metadata)
    else:
        entitlement = CLOUD_FREE_ENTITLEMENT
    return EntitlementUpdate(
        org_id=org_id,
        entitlement=entitlement,
        external_ref=subscription.subscription_id,
    )


# --- SDK-Gateway (duenne, in to_thread gewrappte Anbindung) ----------------------


class SdkMollieGateway:
    """`MollieGateway` auf Basis der synchronen Mollie-SDK (in `asyncio.to_thread`)."""

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise MollieError("MOLLIE_API_KEY ist nicht konfiguriert.")
        self._client = Client()
        self._client.set_api_key(api_key)

    async def create_customer(
        self, *, name: str, email: str | None, metadata: dict[str, str]
    ) -> str:
        def _call() -> str:
            data: dict[str, Any] = {"name": name, "metadata": metadata}
            if email:
                data["email"] = email
            customer = self._client.customers.create(data)
            return str(customer.id)

        return await asyncio.to_thread(_call)

    async def create_first_payment(
        self,
        *,
        customer_id: str,
        amount_eur: str,
        description: str,
        redirect_url: str,
        webhook_url: str | None,
        metadata: dict[str, str],
    ) -> str:
        def _call() -> str:
            data: dict[str, Any] = {
                "amount": {"currency": "EUR", "value": amount_eur},
                "customerId": customer_id,
                "sequenceType": "first",
                "description": description,
                "redirectUrl": redirect_url,
                "metadata": metadata,
            }
            if webhook_url:
                data["webhookUrl"] = webhook_url
            payment = self._client.payments.create(data)
            url = payment.checkout_url
            if not isinstance(url, str) or not url:
                raise MollieError("Mollie lieferte keine Checkout-URL.")
            return url

        return await asyncio.to_thread(_call)

    async def get_payment(self, payment_id: str) -> MolliePayment | None:
        def _call() -> MolliePayment | None:
            payment = self._client.payments.get(payment_id)
            if payment is None:
                return None
            return MolliePayment(
                id=str(payment.id),
                is_paid=bool(payment.is_paid),
                customer_id=payment.customer_id,
                subscription_id=payment.subscription_id,
                mandate_id=payment.mandate_id,
                metadata=_metadata(payment.metadata),
            )

        return await asyncio.to_thread(_call)

    async def create_subscription(
        self,
        *,
        customer_id: str,
        amount_eur: str,
        interval: str,
        description: str,
        webhook_url: str | None,
        metadata: dict[str, str],
    ) -> str:
        def _call() -> str:
            customer = self._client.customers.get(customer_id)
            data: dict[str, Any] = {
                "amount": {"currency": "EUR", "value": amount_eur},
                "interval": interval,
                "description": description,
                "metadata": metadata,
            }
            if webhook_url:
                data["webhookUrl"] = webhook_url
            subscription = customer.subscriptions.create(data)
            return str(subscription.id)

        return await asyncio.to_thread(_call)

    async def get_subscription(
        self, customer_id: str, subscription_id: str
    ) -> MollieSubscription | None:
        def _call() -> MollieSubscription | None:
            customer = self._client.customers.get(customer_id)
            subscription = customer.subscriptions.get(subscription_id)
            if subscription is None:
                return None
            return MollieSubscription(
                subscription_id=str(subscription.id),
                status=str(subscription.status),
                metadata=_metadata(subscription.metadata),
            )

        return await asyncio.to_thread(_call)


# --- Service (Orchestrierung Gateway + Entitlement-Persistenz) -------------------


class MollieBillingService:
    """Verbindet das Mollie-Gateway mit der `org_entitlement`-Persistenz.

    Bewusst **nicht** im Kern (Guardrail §3.6): der Router aktiviert den Service
    nur unter `is_cloud()`. Der Kern liest spaeter ausschliesslich das
    persistierte Entitlement (`CloudEntitlementAdapter`), nie Mollie direkt.
    """

    def __init__(self, gateway: MollieGateway, repo: EntitlementRepository) -> None:
        self._gateway = gateway
        self._repo = repo

    async def start_checkout(
        self,
        *,
        org_id: UUID,
        plan: Plan,
        customer_name: str,
        customer_email: str | None,
        redirect_url: str,
        webhook_url: str | None,
    ) -> str:
        """Legt Customer + Erstzahlung an und liefert die Hosted-Checkout-URL."""
        metadata = plan.metadata(org_id)
        customer_id = await self._gateway.create_customer(
            name=customer_name,
            email=customer_email,
            metadata={META_ORG_ID: str(org_id)},
        )
        return await self._gateway.create_first_payment(
            customer_id=customer_id,
            amount_eur=plan.price_eur,
            description=f"Who2Be {plan.name}",
            redirect_url=redirect_url,
            webhook_url=webhook_url,
            metadata=metadata,
        )

    async def handle_webhook(self, payment_id: str, *, webhook_url: str | None) -> bool:
        """Verarbeitet einen Mollie-Ping. True, wenn ein Entitlement geschrieben wurde.

        Drei Faelle:
        - **Folgezahlung** (Payment traegt `subscriptionId`) ⇒ Subscription-Status
          fetchen und Tier setzen/zurueckfallen.
        - **Erstzahlung bezahlt** (Mandat vorhanden, Plan-Metadata) ⇒ Subscription
          anlegen und Tier aktiv setzen.
        - sonst ⇒ No-Op (noch nicht bezahlt / irrelevant), quittiert mit `False`.
        """
        payment = await self._gateway.get_payment(payment_id)
        if payment is None:
            return False

        if payment.subscription_id and payment.customer_id:
            subscription = await self._gateway.get_subscription(
                payment.customer_id, payment.subscription_id
            )
            if subscription is None:
                return False
            update = subscription_to_update(subscription)
            await self._repo.upsert(
                update.org_id,
                update.entitlement,
                source="mollie",
                external_ref=update.external_ref,
            )
            return True

        if payment.is_paid and payment.customer_id and payment.mandate_id:
            return await self._activate_from_first_payment(payment, webhook_url=webhook_url)

        return False

    async def _activate_from_first_payment(
        self, payment: MolliePayment, *, webhook_url: str | None
    ) -> bool:
        org_id = metadata_org_id(payment.metadata)
        plan = self._plan_for(payment.metadata)
        subscription_id = await self._gateway.create_subscription(
            customer_id=payment.customer_id or "",
            amount_eur=plan.price_eur,
            interval=plan.interval,
            description=f"Who2Be {plan.name}",
            webhook_url=webhook_url,
            metadata={key: str(value) for key, value in payment.metadata.items()},
        )
        await self._repo.upsert(
            org_id,
            metadata_to_entitlement(payment.metadata),
            source="mollie",
            external_ref=subscription_id,
        )
        return True

    @staticmethod
    def _plan_for(metadata: dict[str, Any]) -> Plan:
        code = metadata.get(META_PLAN_CODE)
        plan = plan_by_code(code) if isinstance(code, str) else None
        if plan is None:
            raise MollieError("Mollie-Metadata traegt keinen bekannten 'plan_code'.")
        return plan
