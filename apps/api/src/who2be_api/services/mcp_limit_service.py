"""MCP-Limit-Gate fuer agent-facing Reads (Track D, Plan §3.5, Entscheidung #9).

Greift **ausschliesslich**:
- in der **Cloud**-Edition (`is_cloud()`) — On-Prem ist unbegrenzt,
- fuer **API-Token-Aufrufer** (`WorkspaceContext.is_api_token`, also der MCP-Server) —
  Operator-/Web-Reads (JWT) passieren ungehindert.

Zwei Schranken, beide aus dem **Org-Entitlement** (SSoT, nie aus dem rohen
Zahlungsstatus):
1. **Rate** (`mcp_rate_per_min`) — Sliding-Window, **zwei** Fenster mit demselben
   Ceiling: pro Token *und* pro Organisation (#537). Effektiv gilt das Minimum,
   damit N Tokens nicht N × die beworbene Rate ergeben.
2. **Monats-Kontingent** (`mcp_monthly_quota`) — `mcp_usage(org_id, period)`.

Die Reihenfolge ist bewusst Rate-vor-Kontingent: ein vom Rate-Limit abgewiesener
Read soll das Monatskontingent nicht verbrauchen. Ein inaktives Entitlement
(`status='inactive'`, Kuendigung/Fehlzahlung) blockt sofort (402).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn, cast
from uuid import UUID

import asyncpg
from fastapi import Depends, Request, status

from who2be_api.core.config import Settings, get_settings
from who2be_api.core.db import get_pool
from who2be_api.core.errors import ApiError
from who2be_api.core.rate_limit import rate_limit_key, token_rate_limiter
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.licensing.edition import is_cloud
from who2be_api.licensing.entitlement import Entitlement
from who2be_api.licensing.service import build_entitlement_port
from who2be_api.repositories.mcp_usage_repository import (
    McpUsageRepository,
    PgMcpUsageRepository,
)


def current_period(now: datetime | None = None) -> str:
    """Aktuelle Abrechnungsperiode als 'YYYYMM' (UTC)."""
    return (now or datetime.now(UTC)).strftime("%Y%m")


class McpLimitService:
    """Setzt Rate + Monats-Kontingent fuer agent-facing Reads durch."""

    def __init__(
        self,
        pool: asyncpg.Pool,
        usage_repo: McpUsageRepository,
        settings: Settings | None = None,
    ) -> None:
        self._pool = pool
        self._usage_repo = usage_repo
        self._settings = settings or get_settings()

    async def _resolve_org_id(self, workspace_id: UUID) -> UUID:
        org_id = await self._pool.fetchval(
            "SELECT org_id FROM workspace WHERE id = $1",
            workspace_id,
        )
        if org_id is None:
            # Sollte nie passieren — die Workspace-Membership ist bereits geprueft.
            # Wortgleich zum Zwilling in `entity_quota_service._resolve_org_id`
            # (gleicher Status, gleicher Text) ⇒ derselbe Grund.
            raise ApiError(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Workspace ohne Organisation.",
                reason="workspace_org_missing",
            )
        return cast(UUID, org_id)

    @staticmethod
    def _raise_rate_limited(rate: int | None) -> NoReturn:
        """429 fuer beide Rate-Fenster (Token und Org) — identische Antwort.

        Die Grenze gehoert in `params`, nicht in den Locale-Key (ADR-0051)
        — sonst braucht jeder Tarif seine eigene Uebersetzung. `rate` ist
        hier faktisch nie `None` (ein `None`-Limit laesst der Limiter
        durch); der Guard haelt mypy strict, ohne den Pfad zu aendern.
        """
        raise ApiError(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Token-Ratenlimit ueberschritten.",
            reason="mcp_rate_limited",
            params={"limit": rate} if rate is not None else None,
            headers={"Retry-After": "60"},
        )

    async def enforce(self, request: Request, ctx: WorkspaceContext) -> None:
        """Prueft das Org-Entitlement und verbucht den Read; wirft bei Verletzung."""
        if not is_cloud(self._settings):
            return
        if not ctx.is_api_token:
            return

        org_id = await self._resolve_org_id(ctx.workspace_id)
        port = build_entitlement_port(self._pool, self._settings)
        entitlement: Entitlement = await port.resolve(org_id)

        if not entitlement.is_active():
            raise ApiError(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Kein aktives Abonnement fuer diese Organisation.",
                reason="subscription_inactive",
            )

        # 1) Rate zuerst — abgewiesene Reads verbrauchen kein Kontingent.
        #    Zwei Fenster mit demselben Ceiling (#537, Option A): pro Token UND
        #    pro Organisation. Effektiv gilt das Minimum — ein Einzel-Token-Kunde
        #    merkt nichts, N Tokens ergeben nicht mehr N × Rate.
        rate = entitlement.mcp_rate_per_min
        token_key = rate_limit_key(request)
        org_key = f"org:{org_id}"
        # Erst beide `peek()` (nicht-konsumierend), dann beide `allow()`: sonst
        # verbraucht ein vom Org-Fenster abgelehnter Request das Token-Fenster
        # (und umgekehrt). Genau dafuer existiert `peek()`.
        if not token_rate_limiter.peek(token_key, rate) or not token_rate_limiter.peek(
            org_key, rate
        ):
            self._raise_rate_limited(rate)
        # Beide zaehlen (kein Short-Circuit — die Fenster bleiben symmetrisch).
        token_ok = token_rate_limiter.allow(token_key, rate)
        org_ok = token_rate_limiter.allow(org_key, rate)
        if not token_ok or not org_ok:
            # Nur unter Nebenlauf erreichbar: zwischen `peek` und `allow` hat ein
            # paralleler Read das Fenster gefuellt.
            self._raise_rate_limited(rate)

        # 2) Monats-Kontingent (None ⇒ unbegrenzt, dann nicht mitzaehlen).
        quota = entitlement.mcp_monthly_quota
        if quota is None:
            return
        # Harter, atomarer Check-and-Increment: `None` ⇒ Kontingent bereits erreicht
        # (kein weiterer Verbrauch). `quota <= 0` blockt jeden Read direkt.
        if quota <= 0:
            allowed: int | None = None
        else:
            allowed = await self._usage_repo.increment_if_allowed(org_id, current_period(), quota)
        if allowed is None:
            raise ApiError(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Monatliches MCP-Kontingent erschoepft.",
                reason="mcp_quota_exceeded",
                params={"limit": quota},
                headers={"Retry-After": "3600"},
            )


async def enforce_mcp_read_limit(
    request: Request,
    ctx: Annotated[WorkspaceContext, Depends(get_current_workspace)],
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> None:
    """FastAPI-Dependency: haengt an agent-facing Read-Routen (Plan §3.5, Punkt 4)."""
    service = McpLimitService(pool, PgMcpUsageRepository(pool))
    await service.enforce(request, ctx)
