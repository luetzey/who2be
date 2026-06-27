"""Persistenz fuer das API-Token-Aggregat (`api_token`).

Verantwortung: SQL + Row↔Model-Mapping, keine Geschaeftsregeln. SQL-Werte
ausschliesslich ueber asyncpg-Parameter-Binding (§6).

Phase 2.1a-2: Token sind pro Workspace gepinnt. List/Revoke filtern auf
`workspace_id`; `fetch_auth_by_hash` liefert zusaetzlich den Workspace-
Snapshot fuer die Cross-Workspace-Pruefung in `get_current_workspace`.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

import asyncpg

from who2be_models import TokenRead, WorkspaceRole


@dataclass(frozen=True)
class TokenAuthRow:
    """Snapshot eines gehashten Tokens: Owner + Workspace + Rolle (ADR-0023).

    `agent_id` ist gesetzt, wenn der Token an einen Agenten gebunden ist — dann
    erbt der Aufruf dessen MCP-Tool-Policy (`get_current_workspace`).
    """

    owner_id: UUID
    workspace_id: UUID
    role: WorkspaceRole
    agent_id: UUID | None = None


class TokenRepository(Protocol):
    """Service-seitige Abstraktion fuer den Token-Zugriff."""

    async def insert(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        name: str,
        token_hash: str,
        role: WorkspaceRole,
        agent_id: UUID | None = None,
        expires_at: datetime | None = None,
    ) -> TokenRead: ...

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        limit: int,
        after: tuple[datetime, UUID] | None,
    ) -> list[TokenRead]: ...

    async def list_by_agent(
        self,
        workspace_id: UUID,
        agent_id: UUID,
        limit: int,
        after: tuple[datetime, UUID] | None,
    ) -> list[TokenRead]: ...

    async def fetch_auth_by_hash(self, token_hash: str) -> TokenAuthRow | None: ...

    async def rename(self, workspace_id: UUID, token_id: UUID, name: str) -> TokenRead | None: ...

    async def rotate(
        self, workspace_id: UUID, token_id: UUID, new_hash: str
    ) -> TokenRead | None: ...

    async def revoke(self, workspace_id: UUID, token_id: UUID) -> bool: ...

    async def touch_last_used(self, token_hash: str) -> None: ...


class PgTokenRepository:
    """asyncpg-Implementierung von `TokenRepository`."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def insert(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        name: str,
        token_hash: str,
        role: WorkspaceRole,
        agent_id: UUID | None = None,
        expires_at: datetime | None = None,
    ) -> TokenRead:
        row = await self._pool.fetchrow(
            "INSERT INTO api_token "
            "(workspace_id, owner_id, name, token_hash, role, agent_id, expires_at) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7) "
            "RETURNING id, workspace_id, name, role, agent_id, "
            "created_at, last_used_at, revoked_at",
            workspace_id,
            owner_id,
            name,
            token_hash,
            role.value,
            agent_id,
            expires_at,
        )
        return TokenRead.model_validate(dict(row))

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        limit: int,
        after: tuple[datetime, UUID] | None,
    ) -> list[TokenRead]:
        if after is None:
            rows = await self._pool.fetch(
                "SELECT id, workspace_id, name, role, agent_id, "
                "created_at, last_used_at, revoked_at "
                "FROM api_token WHERE workspace_id = $1 "
                "ORDER BY created_at DESC, id DESC LIMIT $2",
                workspace_id,
                limit,
            )
        else:
            rows = await self._pool.fetch(
                "SELECT id, workspace_id, name, role, agent_id, "
                "created_at, last_used_at, revoked_at "
                "FROM api_token WHERE workspace_id = $1 "
                "AND (created_at, id) < ($2, $3) "
                "ORDER BY created_at DESC, id DESC LIMIT $4",
                workspace_id,
                after[0],
                after[1],
                limit,
            )
        return [TokenRead.model_validate(dict(row)) for row in rows]

    async def list_by_agent(
        self,
        workspace_id: UUID,
        agent_id: UUID,
        limit: int,
        after: tuple[datetime, UUID] | None,
    ) -> list[TokenRead]:
        if after is None:
            rows = await self._pool.fetch(
                "SELECT id, workspace_id, name, role, agent_id, "
                "created_at, last_used_at, revoked_at "
                "FROM api_token WHERE workspace_id = $1 AND agent_id = $2 "
                "ORDER BY created_at DESC, id DESC LIMIT $3",
                workspace_id,
                agent_id,
                limit,
            )
        else:
            rows = await self._pool.fetch(
                "SELECT id, workspace_id, name, role, agent_id, "
                "created_at, last_used_at, revoked_at "
                "FROM api_token WHERE workspace_id = $1 AND agent_id = $2 "
                "AND (created_at, id) < ($3, $4) "
                "ORDER BY created_at DESC, id DESC LIMIT $5",
                workspace_id,
                agent_id,
                after[0],
                after[1],
                limit,
            )
        return [TokenRead.model_validate(dict(row)) for row in rows]

    async def fetch_auth_by_hash(self, token_hash: str) -> TokenAuthRow | None:
        row = await self._pool.fetchrow(
            "SELECT owner_id, workspace_id, role, agent_id FROM api_token "
            "WHERE token_hash = $1 AND revoked_at IS NULL "
            "AND (expires_at IS NULL OR expires_at > now())",
            token_hash,
        )
        if row is None:
            return None
        return TokenAuthRow(
            owner_id=row["owner_id"],
            workspace_id=row["workspace_id"],
            role=WorkspaceRole(row["role"]),
            agent_id=row["agent_id"],
        )

    async def rename(self, workspace_id: UUID, token_id: UUID, name: str) -> TokenRead | None:
        row = await self._pool.fetchrow(
            "UPDATE api_token SET name = $3 "
            "WHERE id = $1 AND workspace_id = $2 AND revoked_at IS NULL "
            "RETURNING id, workspace_id, name, role, agent_id, "
            "created_at, last_used_at, revoked_at",
            token_id,
            workspace_id,
            name,
        )
        return TokenRead.model_validate(dict(row)) if row is not None else None

    async def rotate(self, workspace_id: UUID, token_id: UUID, new_hash: str) -> TokenRead | None:
        # In-place: nur der Hash wird ersetzt, `last_used_at` zurueckgesetzt
        # (neues Secret). id/agent_id/role/name/created_at bleiben — Snapshot
        # intakt (ADR-0023). Das alte Secret hashed auf den alten Wert und wird
        # von `fetch_auth_by_hash` ab sofort nicht mehr gefunden.
        row = await self._pool.fetchrow(
            "UPDATE api_token SET token_hash = $3, last_used_at = NULL "
            "WHERE id = $1 AND workspace_id = $2 AND revoked_at IS NULL "
            "RETURNING id, workspace_id, name, role, agent_id, "
            "created_at, last_used_at, revoked_at",
            token_id,
            workspace_id,
            new_hash,
        )
        return TokenRead.model_validate(dict(row)) if row is not None else None

    async def revoke(self, workspace_id: UUID, token_id: UUID) -> bool:
        result = await self._pool.execute(
            "UPDATE api_token SET revoked_at = now() "
            "WHERE id = $1 AND workspace_id = $2 AND revoked_at IS NULL",
            token_id,
            workspace_id,
        )
        return bool(result == "UPDATE 1")

    async def touch_last_used(self, token_hash: str) -> None:
        await self._pool.execute(
            "UPDATE api_token SET last_used_at = now() "
            "WHERE token_hash = $1 AND revoked_at IS NULL",
            token_hash,
        )
