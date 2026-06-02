"""On-Prem-Admin-Bootstrap beim ersten Boot (Track D, Plan §3.5, Entscheidung #10).

Wenn die Instanz frisch ist (kein einziger Tenant) und `WHO2BE_BOOTSTRAP_ADMIN_EMAIL`
gesetzt ist, wird deterministisch ein Admin + Personal-Org + Default-Workspace
geseedet — damit eine self-hosted Instanz nicht mit einem leeren, unbedienbaren
Zustand startet. Idempotent: laeuft nur, solange noch kein `org_member` existiert.

Bewusst **offline** (Guardrail §3.6, kein Phone-Home): die User-ID wird
deterministisch aus der Email abgeleitet (`uuid5`). Die GoTrue-Anbindung
(Magic-Link/Initialpasswort) ist die Naht zur Auth-Schicht — der erste Login
ueber diese Email wird gegen den geseedeten Tenant aufgeloest. Die Tenancy-Tabellen
tragen keine FK auf `auth.users`, daher ist der Seed eigenstaendig testbar.
"""

from __future__ import annotations

import logging
from uuid import NAMESPACE_URL, UUID, uuid5

import asyncpg

from who2be_api.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

_BOOTSTRAP_NAMESPACE = "who2be:bootstrap-admin"


def _deterministic_user_id(email: str) -> UUID:
    """Stabile User-ID je Email — derselbe Seed liefert immer denselben Admin."""
    return uuid5(NAMESPACE_URL, f"{_BOOTSTRAP_NAMESPACE}:{email.strip().lower()}")


async def bootstrap_admin_if_needed(pool: asyncpg.Pool, settings: Settings | None = None) -> bool:
    """Seedet Admin + Personal-Org + Workspace, falls noetig. True = geseedet."""
    resolved = settings or get_settings()
    email = resolved.bootstrap_admin_email.strip()
    if not email:
        return False

    existing = await pool.fetchval("SELECT 1 FROM org_member LIMIT 1")
    if existing is not None:
        # Bereits ein Tenant vorhanden — niemals einen bestehenden Stand veraendern.
        return False

    user_id = _deterministic_user_id(email)
    slug = user_id.hex[:12]
    async with pool.acquire() as conn, conn.transaction():
        org_id = await conn.fetchval(
            "INSERT INTO organization (name, slug, kind) "
            "VALUES ($1, $2, 'personal') "
            "ON CONFLICT (kind, slug) DO NOTHING "
            "RETURNING id",
            f"{email} (personal)",
            slug,
        )
        if org_id is None:
            # Org existierte schon (Race/erneuter Lauf) — nichts zu tun.
            return False
        await conn.execute(
            "INSERT INTO org_member (org_id, user_id, role) VALUES ($1, $2, 'owner')",
            org_id,
            user_id,
        )
        ws_id = await conn.fetchval(
            "INSERT INTO workspace (org_id, name, slug) "
            "VALUES ($1, 'Default', 'default') RETURNING id",
            org_id,
        )
        await conn.execute(
            "INSERT INTO workspace_member (workspace_id, user_id, role) VALUES ($1, $2, 'admin')",
            ws_id,
            user_id,
        )

    logger.info(
        "On-Prem-Bootstrap: Admin '%s' geseedet (org=%s, workspace=%s). "
        "Magic-Link/Initialpasswort fuer diese Email senden, um den ersten Login zu ermoeglichen.",
        email,
        org_id,
        ws_id,
    )
    return True
