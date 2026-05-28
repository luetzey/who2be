"""Persistenz fuer das Workspace-Aggregat (TASK-301).

Liest und schreibt `workspace`. Die Membership-Pruefung ist Aufgabe der
`WorkspaceMemberRepository`; dieses Repo arbeitet auf der Workspace-Ebene
und bekommt die User-Identitaet vom Service-Layer durchgereicht.
"""

from typing import Protocol
from uuid import UUID

import asyncpg

from who2be_models import WorkspaceRead


class WorkspaceRepository(Protocol):
    """Service-seitige Abstraktion fuer den Workspace-Zugriff."""

    async def list_by_org_for_user(
        self, org_id: UUID, user_id: UUID
    ) -> list[WorkspaceRead]: ...

    async def fetch(self, workspace_id: UUID) -> WorkspaceRead | None: ...

    async def create(
        self, org_id: UUID, user_id: UUID, name: str, slug: str
    ) -> WorkspaceRead: ...

    async def update_name(
        self, workspace_id: UUID, name: str
    ) -> WorkspaceRead | None: ...


class PgWorkspaceRepository:
    """asyncpg-Implementierung."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def list_by_org_for_user(
        self, org_id: UUID, user_id: UUID
    ) -> list[WorkspaceRead]:
        rows = await self._pool.fetch(
            "SELECT w.id, w.org_id, w.name, w.slug, w.created_at "
            "FROM workspace w "
            "JOIN workspace_member m ON m.workspace_id = w.id "
            "WHERE w.org_id = $1 AND m.user_id = $2 "
            "ORDER BY w.created_at ASC, w.id ASC",
            org_id,
            user_id,
        )
        return [WorkspaceRead.model_validate(dict(row)) for row in rows]

    async def fetch(self, workspace_id: UUID) -> WorkspaceRead | None:
        row = await self._pool.fetchrow(
            "SELECT id, org_id, name, slug, created_at "
            "FROM workspace WHERE id = $1",
            workspace_id,
        )
        return WorkspaceRead.model_validate(dict(row)) if row is not None else None

    async def create(
        self, org_id: UUID, user_id: UUID, name: str, slug: str
    ) -> WorkspaceRead:
        """Neuer Workspace + Admin-Membership fuer den Anlegenden, atomar."""
        async with self._pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                "INSERT INTO workspace (org_id, name, slug) VALUES ($1, $2, $3) "
                "RETURNING id, org_id, name, slug, created_at",
                org_id,
                name,
                slug,
            )
            await conn.execute(
                "INSERT INTO workspace_member (workspace_id, user_id, role) "
                "VALUES ($1, $2, 'admin')",
                row["id"],
                user_id,
            )
        return WorkspaceRead.model_validate(dict(row))

    async def update_name(
        self, workspace_id: UUID, name: str
    ) -> WorkspaceRead | None:
        row = await self._pool.fetchrow(
            "UPDATE workspace SET name = $1 WHERE id = $2 "
            "RETURNING id, org_id, name, slug, created_at",
            name,
            workspace_id,
        )
        return WorkspaceRead.model_validate(dict(row)) if row is not None else None
