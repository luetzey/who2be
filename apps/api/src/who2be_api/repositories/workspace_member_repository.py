"""Persistenz fuer `workspace_member` (Phase 2.3-B).

Listet Mitglieder eines Workspaces, aendert Rollen und entfernt Mitglieder.
Schutz-Invariante: der **letzte** admin eines Workspaces darf sich nicht
selbst herabstufen oder entfernen — sonst bliebe der Workspace fuehrungslos.
Die Pruefung laeuft transaktional gegen `count(*) WHERE role='admin'`, damit
zwei parallele Downgrades nicht beide durchrutschen.
"""

from typing import Protocol
from uuid import UUID

import asyncpg

from who2be_models import WorkspaceMemberRead, WorkspaceRole


class LastAdminError(Exception):
    """Der letzte admin eines Workspaces sollte herabgestuft/entfernt werden."""


class WorkspaceMemberRepository(Protocol):
    """Service-seitige Abstraktion fuer den Member-Zugriff."""

    async def list_by_workspace(self, workspace_id: UUID) -> list[WorkspaceMemberRead]: ...

    async def update_role(
        self, workspace_id: UUID, user_id: UUID, new_role: WorkspaceRole
    ) -> WorkspaceMemberRead | None: ...

    async def remove(self, workspace_id: UUID, user_id: UUID) -> bool: ...


_COLUMNS = "workspace_id, user_id, role, joined_at"

# Mit Email-Join (auth.users). Wird bevorzugt; faellt auf `_COLUMNS` zurueck,
# wenn das `auth`-Schema fehlt (reine API-Test-DB ohne GoTrue) — analog
# `PgMeRepository._lookup_email`.
_LIST_WITH_EMAIL = (
    "SELECT m.workspace_id, m.user_id, m.role, m.joined_at, u.email "
    "FROM workspace_member m "
    "LEFT JOIN auth.users u ON u.id = m.user_id "
    "WHERE m.workspace_id = $1 "
    "ORDER BY m.joined_at ASC, m.user_id ASC"
)
_LIST_NO_EMAIL = (
    f"SELECT {_COLUMNS} FROM workspace_member WHERE workspace_id = $1 "
    "ORDER BY joined_at ASC, user_id ASC"
)


class PgWorkspaceMemberRepository:
    """asyncpg-Implementierung von `WorkspaceMemberRepository`."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def list_by_workspace(self, workspace_id: UUID) -> list[WorkspaceMemberRead]:
        try:
            rows = await self._pool.fetch(_LIST_WITH_EMAIL, workspace_id)
        except asyncpg.PostgresError:
            # `auth.users` existiert nicht (Test-DB) → ohne Email-Join lesen.
            rows = await self._pool.fetch(_LIST_NO_EMAIL, workspace_id)
        return [WorkspaceMemberRead.model_validate(dict(row)) for row in rows]

    async def update_role(
        self, workspace_id: UUID, user_id: UUID, new_role: WorkspaceRole
    ) -> WorkspaceMemberRead | None:
        async with self._pool.acquire() as conn, conn.transaction():
            current = await conn.fetchval(
                "SELECT role FROM workspace_member "
                "WHERE workspace_id = $1 AND user_id = $2 FOR UPDATE",
                workspace_id,
                user_id,
            )
            if current is None:
                return None
            if current == "admin" and new_role != WorkspaceRole.admin:
                if await self._last_admin(conn, workspace_id):
                    raise LastAdminError
            row = await conn.fetchrow(
                f"UPDATE workspace_member SET role = $3 "
                f"WHERE workspace_id = $1 AND user_id = $2 RETURNING {_COLUMNS}",
                workspace_id,
                user_id,
                new_role.value,
            )
        return WorkspaceMemberRead.model_validate(dict(row))

    async def remove(self, workspace_id: UUID, user_id: UUID) -> bool:
        async with self._pool.acquire() as conn, conn.transaction():
            current = await conn.fetchval(
                "SELECT role FROM workspace_member "
                "WHERE workspace_id = $1 AND user_id = $2 FOR UPDATE",
                workspace_id,
                user_id,
            )
            if current is None:
                return False
            if current == "admin" and await self._last_admin(conn, workspace_id):
                raise LastAdminError
            await conn.execute(
                "DELETE FROM workspace_member WHERE workspace_id = $1 AND user_id = $2",
                workspace_id,
                user_id,
            )
        return True

    @staticmethod
    async def _last_admin(conn: asyncpg.Connection, workspace_id: UUID) -> bool:
        admin_count = await conn.fetchval(
            "SELECT count(*) FROM workspace_member WHERE workspace_id = $1 AND role = 'admin'",
            workspace_id,
        )
        return bool(admin_count <= 1)
