"""Token-Quota-Gate fuer die Token-Anlage (Issue #538).

Zwilling zu `entity_quota_service`, aber fuer **API-Token**: bevor ein neuer
Token angelegt wird, prueft dieses Gate, ob das Org-Entitlement noch Luft im
Token-Kontingent des Workspaces hat.

Greift **ausschliesslich** in der **Cloud**-Edition (`is_cloud()`); On-Prem/OSS
ist unbegrenzt. Derselbe Vertrag wie beim Entity-Limit: **kein Datenverlust** —
bestehende Tokens bleiben nutzbar und rotierbar, auch ueber der Grenze; nur
NEUE Anlagen werden mit `402` + Upgrade-Hinweis geblockt. Sonst sperrte ein
Downgrade laufende Agenten aus.

Genau deshalb haengt das Gate an `TokenService.create` und **nicht** an
`rotate`: Rotation ersetzt ein Secret, sie legt keinen Token an. Ein Gate dort
wuerde die Secret-Rotation (RUNBOOK §Secret-Rotation) ueber der Grenze
aussperren — also genau in dem Moment, in dem sie am dringendsten gebraucht
wird.

Zaehl-Granularitaet ist **pro Workspace**, wortgleich zum Entity-Zwilling
(`entity_quota_service.py:12-15`): das Gate laeuft im Create-Request des
Workspaces. Fuer den Free-Tier (Personal-Org mit genau einem Workspace) ist das
deckungsgleich mit „pro Org".

Anders als `Entitlement.entity_limit()` ist die Grenze hier ein echtes
Entitlement-**Feld** (`token_quota`) und keine Ableitung: die Ableitung kann nur
„Free-Zahl oder unbegrenzt" ausdruecken, Pro hat hier aber eine eigene endliche
Zahl (25).
"""

from __future__ import annotations

from typing import cast
from uuid import UUID

import asyncpg
from fastapi import status

from who2be_api.core.config import Settings, get_settings
from who2be_api.core.errors import ApiError
from who2be_api.core.security import WorkspaceContext
from who2be_api.licensing.edition import is_cloud
from who2be_api.licensing.entitlement import Entitlement
from who2be_api.licensing.service import build_entitlement_port

# Gezaehlt wird, was sich noch authentifizieren kann: dieselbe Bedingung, unter
# der `PgTokenRepository.fetch_auth_by_hash` einen Token akzeptiert
# (`token_repository.py:172-177`). Widerrufene zaehlen damit nicht mit (AK4),
# abgelaufene ebenso wenig — sie koennen keinen Agenten mehr betreiben und
# duerfen deshalb auch keinen Slot blockieren.
TOKEN_COUNT_SQL = (
    "SELECT count(*) FROM api_token "
    "WHERE workspace_id = $1 "
    "  AND revoked_at IS NULL "
    "  AND (expires_at IS NULL OR expires_at > now())"
)


class TokenQuotaService:
    """Setzt das Token-Kontingent des Org-Entitlements an der Anlage durch."""

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
            raise ApiError(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Workspace ohne Organisation.",
                reason="workspace_org_missing",
            )
        return cast(UUID, org_id)

    async def _count_tokens(self, workspace_id: UUID) -> int:
        return cast(int, await self._pool.fetchval(TOKEN_COUNT_SQL, workspace_id))

    async def enforce(self, ctx: WorkspaceContext) -> None:
        """Wirft `402`, wenn ein weiterer Token das Kontingent sprengt."""
        if not is_cloud(self._settings):
            return

        org_id = await self._resolve_org_id(ctx.workspace_id)
        port = build_entitlement_port(self._pool, self._settings)
        entitlement: Entitlement = await port.resolve(org_id)

        limit = entitlement.token_quota
        if limit is None:
            return  # Unbegrenzt (On-Prem-Lizenz, Bestand vor 0085) — kein Roundtrip.

        current = await self._count_tokens(ctx.workspace_id)
        if current >= limit:
            # `params` statt eines Grundes je Grenze: die erreichte Zahl gehoert
            # in die Daten, nicht in den Locale-Key (ADR-0051). Steigt das
            # Kontingent, aendert sich hier nichts und keine Uebersetzung.
            raise ApiError(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=(
                    f"Der Tarif erlaubt {limit} aktive API-Tokens je Workspace. "
                    "Widerrufe einen bestehenden Token oder wechsle den Tarif — "
                    "bestehende Tokens bleiben nutzbar und rotierbar."
                ),
                reason="token_quota_exceeded",
                params={"limit": limit},
            )
