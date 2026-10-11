"""On-Prem-Admin-Bootstrap beim ersten Boot (Track D, Plan §3.5, Entscheidung #10).

Wenn die Instanz frisch ist (kein einziger Tenant) und `WHO2BE_BOOTSTRAP_ADMIN_EMAIL`
gesetzt ist, wird deterministisch ein Admin + Personal-Org + Default-Workspace
geseedet — damit eine self-hosted Instanz nicht mit einem leeren, unbedienbaren
Zustand startet. Idempotent: laeuft nur, solange noch kein `org_member` existiert.

Bewusst **offline** (Guardrail §3.6, kein Phone-Home): die Mitgliedschaften
gehoeren zunaechst einem Platzhalter, dessen User-ID deterministisch aus der
Email abgeleitet wird (`uuid5`). GoTrue vergibt beim ersten Login eine eigene,
zufaellige UUID. Diese Naht schliesst `claim_bootstrap_org`: beim ersten
`/v1/me` eines Kontos ohne Mitgliedschaft wandern die Mitgliedschaften des
Platzhalters auf das Konto — aber nur, wenn dessen E-Mail in GoTrue
**bestaetigt** ist und der Bootstrap-Adresse entspricht. Eine unbestaetigte
Adresse uebernimmt nie eine Org. Die Tenancy-Tabellen tragen keine FK auf
`auth.users`, daher ist der Seed eigenstaendig testbar.
"""

from __future__ import annotations

import logging
from uuid import NAMESPACE_URL, UUID, uuid5

import asyncpg

from who2be_api.core.config import Settings, get_settings
from who2be_api.core.tenancy import scope_to_self
from who2be_api.licensing.edition import is_onprem
from who2be_api.repositories.audit_log_repository import PgAuditLogRepository

logger = logging.getLogger(__name__)

_BOOTSTRAP_NAMESPACE = "who2be:bootstrap-admin"

BOOTSTRAP_CLAIMED_AUDIT_ACTION = "org.bootstrap_claimed"


def _deterministic_user_id(email: str) -> UUID:
    """Stabile User-ID je Email — derselbe Seed liefert immer denselben Admin."""
    return uuid5(NAMESPACE_URL, f"{_BOOTSTRAP_NAMESPACE}:{email.strip().lower()}")


async def seed_bootstrap_tenant(conn: asyncpg.Connection, email: str) -> UUID | None:
    """Legt Org + Owner + Default-Workspace + Admin fuer den Platzhalter an.

    Erwartet eine umgebende Transaktion. Gibt die Org-ID zurueck, `None`, wenn
    die Org schon existiert (Race/erneuter Lauf).
    """
    user_id = _deterministic_user_id(email)
    org_id: UUID | None = await conn.fetchval(
        "INSERT INTO organization (name, slug, kind) "
        "VALUES ($1, $2, 'personal') "
        "ON CONFLICT (kind, slug) DO NOTHING "
        "RETURNING id",
        f"{email} (personal)",
        user_id.hex[:12],
    )
    if org_id is None:
        return None
    await conn.execute(
        "INSERT INTO org_member (org_id, user_id, role) VALUES ($1, $2, 'owner')",
        org_id,
        user_id,
    )
    ws_id = await conn.fetchval(
        "INSERT INTO workspace (org_id, name, slug) VALUES ($1, 'Default', 'default') RETURNING id",
        org_id,
    )
    await conn.execute(
        "INSERT INTO workspace_member (workspace_id, user_id, role) VALUES ($1, $2, 'admin')",
        ws_id,
        user_id,
    )
    return org_id


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

    async with pool.acquire() as conn, conn.transaction():
        org_id = await seed_bootstrap_tenant(conn, email)
    if org_id is None:
        return False

    logger.info(
        "On-Prem-Bootstrap: Admin '%s' geseedet (org=%s). "
        "Magic-Link/Initialpasswort fuer diese Email senden; der erste Login "
        "mit bestaetigter Adresse uebernimmt die Org.",
        email,
        org_id,
    )
    return True


async def claim_bootstrap_org(
    conn: asyncpg.Connection, user_id: UUID, settings: Settings | None = None
) -> bool:
    """Haengt die Mitgliedschaften des Bootstrap-Platzhalters auf `user_id` um.

    Nur On-Prem, nur mit gesetzter `WHO2BE_BOOTSTRAP_ADMIN_EMAIL` und nur, wenn
    die eigene GoTrue-Adresse (`w2b_self_account()`, Migrationen 0093/0094)
    **bestaetigt** ist und der Variable entspricht (ohne Gross-/Kleinschreibung).
    Erwartet eine umgebende Transaktion (`scope_to_self` ist transaktionslokal).
    True = mindestens eine Mitgliedschaft uebernommen. Idempotent: nach der
    Uebernahme haelt der Platzhalter nichts mehr, ein zweiter Lauf ist ein No-Op.
    Die Uebernahme schreibt `org.bootstrap_claimed` in `audit_log` (dieselbe
    Transaktion). Parallele Erst-Logins serialisiert der Aufrufer
    (`PgMeRepository.fetch`, Advisory-Lock je User).
    """
    resolved = settings or get_settings()
    email = resolved.bootstrap_admin_email.strip().lower()
    if not email or not is_onprem(resolved):
        return False

    placeholder = _deterministic_user_id(email)
    if placeholder == user_id:
        return False

    try:
        async with conn.transaction():
            await scope_to_self(conn, user_id)
            row = await conn.fetchrow("SELECT email, email_confirmed FROM w2b_self_account()")
    except asyncpg.PostgresError:
        # Test-DB ohne GoTrue: fail-closed, nichts uebernehmen.
        return False
    if row is None or not row["email_confirmed"]:
        return False
    if (row["email"] or "").strip().lower() != email:
        return False

    org_ids = await conn.fetch(
        "UPDATE org_member SET user_id = $1 WHERE user_id = $2 RETURNING org_id",
        user_id,
        placeholder,
    )
    ws_rows = await conn.fetch(
        "UPDATE workspace_member m SET user_id = $1 FROM workspace w "
        "WHERE m.user_id = $2 AND w.id = m.workspace_id "
        "RETURNING m.workspace_id, w.org_id",
        user_id,
        placeholder,
    )
    if not org_ids:
        return False
    # Admin-/Security-Event (ADR-0031): der User wird Owner einer Org und Admin
    # ihres Workspaces. Eine Zeile je uebernommenem Workspace, in derselben
    # Transaktion wie die Uebernahme. Akteur und Ziel sind der User selbst —
    # die Konto-Purge (E1-1b, `_ANONYMIZE_AUDIT_LOG_SQL`) erfasst die Zeile
    # ueber `actor_id`/`target`.
    audit = PgAuditLogRepository()
    for ws in ws_rows:
        await audit.insert(
            conn,
            action=BOOTSTRAP_CLAIMED_AUDIT_ACTION,
            org_id=ws["org_id"],
            workspace_id=ws["workspace_id"],
            actor_id=user_id,
            target=str(user_id),
        )
    logger.info("On-Prem-Bootstrap: Org des Bootstrap-Admins an User %s uebergeben.", user_id)
    return True
