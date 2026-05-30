"""Persistenz fuer das Organization-Aggregat (TASK-301).

Liest und schreibt `organization`/`org_member`. Eine Company-Org-Anlage
erzeugt zusaetzlich einen Default-Workspace und macht den anlegenden User
zum admin in beiden Tabellen — atomar in einer Transaktion.
"""

from typing import Protocol
from uuid import UUID

import asyncpg

from who2be_models import OrganizationRead


class OrganizationRepository(Protocol):
    """Service-seitige Abstraktion fuer den Organization-Zugriff."""

    async def list_by_user(self, user_id: UUID) -> list[OrganizationRead]: ...

    async def create_company(
        self, user_id: UUID, name: str, slug: str, default_workspace_name: str
    ) -> tuple[OrganizationRead, UUID]: ...

    async def fetch(self, user_id: UUID, organization_id: UUID) -> OrganizationRead | None: ...


class PgOrganizationRepository:
    """asyncpg-Implementierung."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def list_by_user(self, user_id: UUID) -> list[OrganizationRead]:
        rows = await self._pool.fetch(
            "SELECT o.id, o.name, o.slug, o.kind, o.created_at "
            "FROM organization o "
            "JOIN org_member m ON m.org_id = o.id "
            "WHERE m.user_id = $1 "
            "ORDER BY o.created_at ASC, o.id ASC",
            user_id,
        )
        return [OrganizationRead.model_validate(dict(row)) for row in rows]

    async def fetch(self, user_id: UUID, organization_id: UUID) -> OrganizationRead | None:
        row = await self._pool.fetchrow(
            "SELECT o.id, o.name, o.slug, o.kind, o.created_at "
            "FROM organization o "
            "JOIN org_member m ON m.org_id = o.id "
            "WHERE o.id = $1 AND m.user_id = $2",
            organization_id,
            user_id,
        )
        return OrganizationRead.model_validate(dict(row)) if row is not None else None

    async def create_company(
        self, user_id: UUID, name: str, slug: str, default_workspace_name: str
    ) -> tuple[OrganizationRead, UUID]:
        """Legt Org + Owner-Membership + Default-Workspace + Admin atomar an.

        `default_workspace_name` ist der Anzeigename; der Slug ist fest
        `default` (in 2.3 austauschbar). Gibt die neue Org plus die UUID
        des Default-Workspaces zurueck.
        """
        async with self._pool.acquire() as conn, conn.transaction():
            org_row = await conn.fetchrow(
                "INSERT INTO organization (name, slug, kind) "
                "VALUES ($1, $2, 'company') "
                "RETURNING id, name, slug, kind, created_at",
                name,
                slug,
            )
            org_id = org_row["id"]
            await conn.execute(
                "INSERT INTO org_member (org_id, user_id, role) VALUES ($1, $2, 'owner')",
                org_id,
                user_id,
            )
            ws_id = await conn.fetchval(
                "INSERT INTO workspace (org_id, name, slug) "
                "VALUES ($1, $2, 'default') RETURNING id",
                org_id,
                default_workspace_name,
            )
            await conn.execute(
                "INSERT INTO workspace_member (workspace_id, user_id, role) "
                "VALUES ($1, $2, 'admin')",
                ws_id,
                user_id,
            )
        return OrganizationRead.model_validate(dict(org_row)), ws_id
