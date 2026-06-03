"""Persistenz fuer Account-/Org-Lifecycle (Track O, Plan §3.2).

Control-plane-Zugriffe (organization/org_member/workspace_member/api_token/
account_deletion tragen kein RLS): Soft-Delete einer Org, Vormerkung einer
Account-Loeschung sowie die Scan-/Purge-Queries fuer den Hard-Purge-Job.

Der Hard-Purge nutzt bewusst `DELETE FROM organization` — die bestehenden
ON-DELETE-CASCADE-FKs (workspace → persona/playbook/resource/agent/… →
*_version, plus org_entitlement/mcp_usage) raeumen die gesamte Tenant-Hierarchie
atomar ab.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

import asyncpg


class AccountLifecycleRepository(Protocol):
    """Service-seitige Abstraktion fuer Lifecycle-Schreibzugriffe."""

    async def is_org_owner(self, org_id: UUID, user_id: UUID) -> bool: ...

    async def org_kind(self, org_id: UUID) -> str | None: ...

    async def soft_delete_organization(self, org_id: UUID, purge_after: datetime) -> datetime: ...

    async def sole_owner_company_orgs(self, user_id: UUID) -> list[str]: ...

    async def request_account_deletion(self, user_id: UUID, purge_after: datetime) -> None: ...


class PgAccountLifecycleRepository:
    """asyncpg-Implementierung (App-Pool, control-plane ohne RLS)."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def is_org_owner(self, org_id: UUID, user_id: UUID) -> bool:
        role: str | None = await self._pool.fetchval(
            "SELECT role FROM org_member WHERE org_id = $1 AND user_id = $2",
            org_id,
            user_id,
        )
        return role == "owner"

    async def org_kind(self, org_id: UUID) -> str | None:
        kind: str | None = await self._pool.fetchval(
            "SELECT kind FROM organization WHERE id = $1 AND deleted_at IS NULL",
            org_id,
        )
        return kind

    async def soft_delete_organization(self, org_id: UUID, purge_after: datetime) -> datetime:
        """Markiert die Org als zur Loeschung vorgemerkt; liefert den effektiven
        Purge-Termin. Idempotent: ist die Org bereits vorgemerkt, bleibt der
        urspruengliche `purge_after` bestehen und wird zurueckgegeben (kein
        verlaengertes Grace-Fenster bei erneutem Loeschen)."""
        stored: datetime | None = await self._pool.fetchval(
            "UPDATE organization SET deleted_at = now(), purge_after = $2 "
            "WHERE id = $1 AND deleted_at IS NULL RETURNING purge_after",
            org_id,
            purge_after,
        )
        if stored is not None:
            return stored
        existing: datetime | None = await self._pool.fetchval(
            "SELECT purge_after FROM organization WHERE id = $1",
            org_id,
        )
        return existing if existing is not None else purge_after

    async def sole_owner_company_orgs(self, user_id: UUID) -> list[str]:
        """Namen aktiver Company-Orgs, in denen `user_id` der EINZIGE Owner ist.

        Solche Orgs duerfen nicht ueber die Konto-Loeschung verwaist werden —
        der Service blockt die Account-Loeschung, bis sie uebertragen oder
        separat geloescht sind."""
        rows = await self._pool.fetch(
            "SELECT o.name FROM organization o "
            "JOIN org_member m ON m.org_id = o.id AND m.user_id = $1 AND m.role = 'owner' "
            "WHERE o.kind = 'company' AND o.deleted_at IS NULL "
            "  AND NOT EXISTS ("
            "    SELECT 1 FROM org_member m2 "
            "    WHERE m2.org_id = o.id AND m2.role = 'owner' AND m2.user_id <> $1"
            "  ) "
            "ORDER BY o.name ASC",
            user_id,
        )
        return [row["name"] for row in rows]

    async def request_account_deletion(self, user_id: UUID, purge_after: datetime) -> None:
        """Merkt den Account vor und mottet die Personal-Org des Users ein.

        Atomar; idempotent (mehrfaches Loeschen behaelt den fruehesten
        `purge_after`-Termin). Company-Orgs bleiben unangetastet — sie werden
        separat ueber `DELETE /v1/organizations/{id}` geloescht; der
        Account-Purge entfernt nur die Memberships des Users.
        """
        async with self._pool.acquire() as conn, conn.transaction():
            await conn.execute(
                "INSERT INTO account_deletion (user_id, purge_after) VALUES ($1, $2) "
                "ON CONFLICT (user_id) DO UPDATE SET "
                "  purge_after = LEAST(account_deletion.purge_after, EXCLUDED.purge_after), "
                "  purged_at = NULL",
                user_id,
                purge_after,
            )
            # Personal-Org des Users (slug == user_id, kind='personal') einmotten.
            await conn.execute(
                "UPDATE organization SET deleted_at = now(), purge_after = $2 "
                "WHERE kind = 'personal' AND slug = $1 AND deleted_at IS NULL",
                str(user_id),
                purge_after,
            )


class AccountPurgeRepository(Protocol):
    """Service-seitige Abstraktion fuer den Hard-Purge-Job (Owner-Connection)."""

    async def expired_organizations(self, now: datetime) -> list[UUID]: ...

    async def purge_organization(self, org_id: UUID) -> None: ...

    async def expired_accounts(self, now: datetime) -> list[UUID]: ...

    async def purge_account_data(self, user_id: UUID) -> None: ...

    async def mark_account_purged(self, user_id: UUID) -> None: ...


class PgAccountPurgeRepository:
    """asyncpg-Implementierung des Purge-Jobs auf einer Owner-Connection.

    Bewusst eine einzelne Connection (kein Pool): der Purge laeuft als
    Owner-Rolle (`DATABASE_URL`) ausserhalb von RLS, damit die CASCADE-Deletes
    workspace-uebergreifend durchgreifen.
    """

    def __init__(self, conn: asyncpg.Connection) -> None:
        self._conn = conn

    async def expired_organizations(self, now: datetime) -> list[UUID]:
        rows = await self._conn.fetch(
            "SELECT id FROM organization "
            "WHERE deleted_at IS NOT NULL AND purge_after <= $1",
            now,
        )
        return [row["id"] for row in rows]

    async def purge_organization(self, org_id: UUID) -> None:
        # CASCADE raeumt Workspaces, Entities, Versionen, Entitlement + Usage.
        await self._conn.execute("DELETE FROM organization WHERE id = $1", org_id)

    async def expired_accounts(self, now: datetime) -> list[UUID]:
        rows = await self._conn.fetch(
            "SELECT user_id FROM account_deletion "
            "WHERE purged_at IS NULL AND purge_after <= $1",
            now,
        )
        return [row["user_id"] for row in rows]

    async def purge_account_data(self, user_id: UUID) -> None:
        """Loescht die User-eigenen Daten: Personal-Org (CASCADE), API-Tokens
        und alle Memberships. Atomar."""
        async with self._conn.transaction():
            await self._conn.execute(
                "DELETE FROM organization WHERE kind = 'personal' AND slug = $1",
                str(user_id),
            )
            await self._conn.execute("DELETE FROM api_token WHERE owner_id = $1", user_id)
            await self._conn.execute("DELETE FROM org_member WHERE user_id = $1", user_id)
            await self._conn.execute("DELETE FROM workspace_member WHERE user_id = $1", user_id)

    async def mark_account_purged(self, user_id: UUID) -> None:
        await self._conn.execute(
            "UPDATE account_deletion SET purged_at = now() WHERE user_id = $1",
            user_id,
        )
