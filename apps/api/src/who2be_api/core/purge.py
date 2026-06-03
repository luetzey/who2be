"""Hard-Purge-Job fuer abgelaufene Soft-Deletes (Track O, Plan §3.2).

Raeumt nach Ablauf der 30-Tage-Grace endgueltig ab:
  * **Organizations** mit `deleted_at IS NOT NULL AND purge_after <= now` →
    `DELETE FROM organization` (CASCADE loescht die ganze Tenant-Hierarchie).
  * **Accounts** (`account_deletion`, `purge_after <= now`) → Personal-Org +
    API-Tokens + Memberships werden geloescht, danach der GoTrue-User
    (Service-Key, best-effort), zuletzt `purged_at` gesetzt.

Laeuft als **Owner-Connection** (`DATABASE_URL`, RLS-Bypass) wie der
Migrations-Runner, damit die CASCADE-Deletes workspace-uebergreifend
durchgreifen. Als Cron einplanbar (`who2be-purge`); idempotent — ein zweiter
Lauf ohne faellige Eintraege ist ein No-op.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

import asyncpg

from who2be_api.core.config import get_settings
from who2be_api.integrations.gotrue_admin import delete_auth_user
from who2be_api.repositories.account_repository import (
    AccountPurgeRepository,
    PgAccountPurgeRepository,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PurgeResult:
    """Zaehlt, was ein Purge-Lauf abgeraeumt hat."""

    organizations: int
    accounts: int


async def purge_expired(
    repo: AccountPurgeRepository,
    now: datetime | None = None,
) -> PurgeResult:
    """Raeumt faellige Org- und Account-Loeschungen ab. Liefert die Zaehlung.

    Die GoTrue-User-Loeschung ist best-effort: schlaegt sie fehl, wird der
    DB-seitige Purge dennoch finalisiert (`purged_at` gesetzt) — ein erneuter
    Lauf wuerde den Account sonst endlos wieder aufgreifen.
    """
    reference = now or datetime.now(UTC)

    org_ids = await repo.expired_organizations(reference)
    for org_id in org_ids:
        await repo.purge_organization(org_id)
        logger.info("Org %s endgueltig geloescht (Grace abgelaufen).", org_id)

    user_ids = await repo.expired_accounts(reference)
    for user_id in user_ids:
        await repo.purge_account_data(user_id)
        await delete_auth_user(user_id)
        await repo.mark_account_purged(user_id)
        logger.info("Account %s endgueltig geloescht (Grace abgelaufen).", user_id)

    return PurgeResult(organizations=len(org_ids), accounts=len(user_ids))


async def _run() -> PurgeResult:
    try:
        conn = await asyncpg.connect(get_settings().database_url)
    except (asyncpg.PostgresError, OSError) as exc:
        raise SystemExit(f"Datenbank nicht erreichbar: {exc}") from exc
    try:
        return await purge_expired(PgAccountPurgeRepository(conn))
    finally:
        await conn.close()


def cli() -> None:
    """Console-Entrypoint fuer `who2be-purge` (Cron)."""
    result = asyncio.run(_run())
    print(f"Purge: {result.organizations} Org(s), {result.accounts} Account(s) geloescht.")


if __name__ == "__main__":
    cli()
