"""Persistenz fuer das Agent-Aggregat.

Agents sind die Top-Level-Konfiguration der Phase-3-Runde-3-Domain (Track 3):
genau eine Persona, genau ein Template, optionaler Status. Keine
Versionshistorie — direkte UPDATEs auf `agent`.

Die Composite-FKs (workspace_id, persona_id) / (workspace_id, template_id)
aus Migration 0023 erzwingen, dass Persona + Template aus demselben
Workspace stammen. INSERT/UPDATE bekommen daher nur die `workspace_id` des
Aufrufers; Cross-Workspace-Verweise werden DB-seitig abgewiesen.
"""

from datetime import datetime
from typing import Protocol
from uuid import UUID

import asyncpg

from who2be_models import AgentRead, AgentStatus

_SELECT = """
    SELECT a.id, a.workspace_id, a.owner_id, a.name, a.description,
           a.persona_id, a.system_prompt_template_id, a.status,
           a.created_at, a.updated_at
    FROM agent a
"""


class AgentRepository(Protocol):
    """Service-seitige Abstraktion."""

    async def insert(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        name: str,
        description: str,
        persona_id: UUID | None,
        template_id: UUID | None,
        status: AgentStatus,
    ) -> AgentRead | None: ...

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        limit: int,
        after: tuple[datetime, UUID] | None,
    ) -> list[AgentRead]: ...

    async def fetch(self, workspace_id: UUID, agent_id: UUID) -> AgentRead | None: ...

    async def update(
        self,
        workspace_id: UUID,
        agent_id: UUID,
        name: str | None,
        description: str | None,
        persona_id: UUID | None,
        template_id: UUID | None,
        status: AgentStatus | None,
    ) -> AgentRead | None: ...

    async def delete(self, workspace_id: UUID, agent_id: UUID) -> bool: ...


class PgAgentRepository:
    """asyncpg-Implementierung."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def insert(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        name: str,
        description: str,
        persona_id: UUID | None,
        template_id: UUID | None,
        status: AgentStatus,
    ) -> AgentRead | None:
        try:
            row = await self._pool.fetchrow(
                "INSERT INTO agent (workspace_id, owner_id, name, description, "
                "  persona_id, system_prompt_template_id, status) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7) "
                "RETURNING id, workspace_id, owner_id, name, description, "
                "persona_id, system_prompt_template_id, status, created_at, "
                "updated_at",
                workspace_id,
                owner_id,
                name,
                description,
                persona_id,
                template_id,
                status.value,
            )
        except asyncpg.ForeignKeyViolationError:
            # Composite-FK auf persona/template ausgeloest — Referenz lebt
            # nicht im gleichen Workspace (oder wurde geloescht).
            return None
        return AgentRead.model_validate(dict(row))

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        limit: int,
        after: tuple[datetime, UUID] | None,
    ) -> list[AgentRead]:
        if after is None:
            rows = await self._pool.fetch(
                f"{_SELECT} WHERE a.workspace_id = $1 "
                "ORDER BY a.created_at DESC, a.id DESC LIMIT $2",
                workspace_id,
                limit,
            )
        else:
            rows = await self._pool.fetch(
                f"{_SELECT} WHERE a.workspace_id = $1 "
                "AND (a.created_at, a.id) < ($2, $3) "
                "ORDER BY a.created_at DESC, a.id DESC LIMIT $4",
                workspace_id,
                after[0],
                after[1],
                limit,
            )
        return [AgentRead.model_validate(dict(row)) for row in rows]

    async def fetch(self, workspace_id: UUID, agent_id: UUID) -> AgentRead | None:
        row = await self._pool.fetchrow(
            f"{_SELECT} WHERE a.id = $1 AND a.workspace_id = $2",
            agent_id,
            workspace_id,
        )
        return AgentRead.model_validate(dict(row)) if row is not None else None

    async def update(
        self,
        workspace_id: UUID,
        agent_id: UUID,
        name: str | None,
        description: str | None,
        persona_id: UUID | None,
        template_id: UUID | None,
        status: AgentStatus | None,
    ) -> AgentRead | None:
        try:
            row = await self._pool.fetchrow(
                "UPDATE agent SET "
                "  name = COALESCE($3, name), "
                "  description = COALESCE($4, description), "
                "  persona_id = COALESCE($5, persona_id), "
                "  system_prompt_template_id = COALESCE($6, system_prompt_template_id), "
                "  status = COALESCE($7, status), "
                "  updated_at = now() "
                "WHERE id = $1 AND workspace_id = $2 "
                "RETURNING id, workspace_id, owner_id, name, description, "
                "persona_id, system_prompt_template_id, status, created_at, "
                "updated_at",
                agent_id,
                workspace_id,
                name,
                description,
                persona_id,
                template_id,
                status.value if status is not None else None,
            )
        except asyncpg.ForeignKeyViolationError:
            return None
        return AgentRead.model_validate(dict(row)) if row is not None else None

    async def delete(self, workspace_id: UUID, agent_id: UUID) -> bool:
        result = await self._pool.execute(
            "DELETE FROM agent WHERE id = $1 AND workspace_id = $2",
            agent_id,
            workspace_id,
        )
        # asyncpg gibt "DELETE <n>" zurueck; n=0 wenn nichts geloescht wurde.
        return bool(result.split()[-1] != "0")
