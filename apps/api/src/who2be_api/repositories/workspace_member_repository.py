"""Persistenz fuer `workspace_member` (Phase 2.3-B).

Listet Mitglieder eines Workspaces, aendert Rollen und entfernt Mitglieder.
Schutz-Invariante: der **letzte** admin eines Workspaces darf sich nicht
selbst herabstufen oder entfernen — sonst bliebe der Workspace fuehrungslos.

Race-Schutz (WP-B): ein PG-Advisory-Lock auf `('ws_admins:'||workspace_id)`
serialisiert konkurrierende Rollen-Downgrades/Removals desselben Workspaces
auch unter READ COMMITTED. Ohne diesen Lock konnten zwei parallele Drops
verschiedener Admins beide `count = 2` lesen und durchschluepfen
(`docs/security-findings-phase-2.md:171-179`).

Audit (WP-B): bei einem erfolgreichen Rollenwechsel/Removal wird in derselben
Transaktion ein Eintrag in `audit_log` geschrieben (`member.role_changed`/
`member.removed`), wenn ein `AuditLogRepository` und `actor_id` mitgegeben
werden — atomar mit der Mutation.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

import asyncpg

from who2be_api.repositories.audit_log_repository import AuditLogRepository
from who2be_models import WorkspaceMemberRead, WorkspaceRole


class LastAdminError(Exception):
    """Der letzte admin eines Workspaces sollte herabgestuft/entfernt werden."""


class WorkspaceMemberRepository(Protocol):
    """Service-seitige Abstraktion fuer den Member-Zugriff."""

    async def list_by_workspace(self, workspace_id: UUID) -> list[WorkspaceMemberRead]: ...

    async def update_role(
        self,
        workspace_id: UUID,
        user_id: UUID,
        new_role: WorkspaceRole,
        *,
        actor_id: UUID | None = None,
    ) -> WorkspaceMemberRead | None: ...

    async def remove(
        self,
        workspace_id: UUID,
        user_id: UUID,
        *,
        actor_id: UUID | None = None,
    ) -> bool: ...


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

    def __init__(
        self,
        pool: asyncpg.Pool,
        audit_repo: AuditLogRepository | None = None,
    ) -> None:
        self._pool = pool
        self._audit_repo = audit_repo

    async def list_by_workspace(self, workspace_id: UUID) -> list[WorkspaceMemberRead]:
        try:
            rows = await self._pool.fetch(_LIST_WITH_EMAIL, workspace_id)
        except asyncpg.PostgresError:
            # `auth.users` existiert nicht (Test-DB) → ohne Email-Join lesen.
            rows = await self._pool.fetch(_LIST_NO_EMAIL, workspace_id)
        return [WorkspaceMemberRead.model_validate(dict(row)) for row in rows]

    async def update_role(
        self,
        workspace_id: UUID,
        user_id: UUID,
        new_role: WorkspaceRole,
        *,
        actor_id: UUID | None = None,
    ) -> WorkspaceMemberRead | None:
        async with self._pool.acquire() as conn, conn.transaction():
            await self._lock_workspace_admins(conn, workspace_id)
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
            if self._audit_repo is not None and actor_id is not None:
                await self._audit_repo.insert(
                    conn,
                    action="member.role_changed",
                    workspace_id=workspace_id,
                    actor_id=actor_id,
                    target=str(user_id),
                    detail={"from": current, "to": new_role.value},
                )
        return WorkspaceMemberRead.model_validate(dict(row))

    async def remove(
        self,
        workspace_id: UUID,
        user_id: UUID,
        *,
        actor_id: UUID | None = None,
    ) -> bool:
        async with self._pool.acquire() as conn, conn.transaction():
            await self._lock_workspace_admins(conn, workspace_id)
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
            # Persoenliche Agent-Favoriten des Mitglieds (#427) in derselben
            # Transaktion. Die FKs von `agent_favorite` haengen an `workspace`
            # und `agent` — beide bestehen weiter, wenn nur die Mitgliedschaft
            # endet. Ohne diese Zeile ueberleben die Markierungen unbegrenzt in
            # einem Workspace, zu dem der Mensch keinen Zugang mehr hat, und
            # tauchten bei einer Re-Einladung wieder auf.
            await conn.execute(
                "DELETE FROM agent_favorite WHERE workspace_id = $1 AND user_id = $2",
                workspace_id,
                user_id,
            )
            if self._audit_repo is not None and actor_id is not None:
                await self._audit_repo.insert(
                    conn,
                    action="member.removed",
                    workspace_id=workspace_id,
                    actor_id=actor_id,
                    target=str(user_id),
                    detail={"role": current},
                )
        return True

    @staticmethod
    async def _last_admin(conn: asyncpg.Connection, workspace_id: UUID) -> bool:
        admin_count = await conn.fetchval(
            "SELECT count(*) FROM workspace_member WHERE workspace_id = $1 AND role = 'admin'",
            workspace_id,
        )
        return bool(admin_count <= 1)

    @staticmethod
    async def _lock_workspace_admins(conn: asyncpg.Connection, workspace_id: UUID) -> None:
        """Serialisiert konkurrierende Admin-Downgrades/Removals desselben
        Workspaces. `hashtext` mappt den Schluessel auf den `bigint`-Lock-Raum;
        `xact_lock` gibt die Sperre am Tx-Ende automatisch frei.
        """
        await conn.execute(
            "SELECT pg_advisory_xact_lock(hashtext($1))",
            f"ws_admins:{workspace_id}",
        )
