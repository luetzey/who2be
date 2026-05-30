"""Geschaeftslogik fuer Agents.

Agents sind Konfig — kein Versions-Workflow. Schreiben verlangt
`editor`-Rolle (ADR-0023), Lesen ist fuer Viewer offen. Verweise auf
Persona/Template werden DB-seitig per Composite-FK auf den Workspace
gepinnt; ein 404 statt 422 ist die korrekte Antwort, wenn die referenzierte
Persona/Template nicht (mehr) existiert oder zu einem anderen Workspace
gehoert.
"""

from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status

from who2be_api.core.security import WorkspaceContext, require_role
from who2be_api.repositories.agent_repository import AgentRepository
from who2be_models import (
    AgentCreate,
    AgentRead,
    AgentStatus,
    AgentUpdate,
    WorkspaceRole,
    encode_cursor,
)


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent nicht gefunden.")


def _invalid_reference() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=("Persona oder Template existiert nicht in diesem Workspace."),
    )


class AgentService:
    """Agent-CRUD ohne Versionierung."""

    def __init__(self, repo: AgentRepository) -> None:
        self._repo = repo

    async def create(self, ctx: WorkspaceContext, data: AgentCreate) -> AgentRead:
        require_role(ctx, WorkspaceRole.editor)
        agent = await self._repo.insert(
            ctx.workspace_id,
            ctx.user_id,
            data.name,
            data.description,
            data.persona_id,
            data.system_prompt_template_id,
            data.status,
        )
        if agent is None:
            raise _invalid_reference()
        return agent

    async def list_all(
        self,
        ctx: WorkspaceContext,
        limit: int,
        cursor: tuple[datetime, UUID] | None,
    ) -> tuple[list[AgentRead], str | None]:
        rows = await self._repo.list_by_workspace(ctx.workspace_id, limit + 1, cursor)
        if len(rows) > limit:
            items = rows[:limit]
            tail = items[-1]
            return items, encode_cursor(tail.created_at, tail.id)
        return rows, None

    async def get(self, ctx: WorkspaceContext, agent_id: UUID) -> AgentRead:
        agent = await self._repo.fetch(ctx.workspace_id, agent_id)
        if agent is None:
            raise _not_found()
        return agent

    async def update(self, ctx: WorkspaceContext, agent_id: UUID, data: AgentUpdate) -> AgentRead:
        require_role(ctx, WorkspaceRole.editor)
        agent = await self._repo.update(
            ctx.workspace_id,
            agent_id,
            data.name,
            data.description,
            data.persona_id,
            data.system_prompt_template_id,
            data.status,
        )
        if agent is None:
            # Disambiguieren: existiert der Agent ueberhaupt? Wenn ja, dann
            # war der Composite-FK auf persona/template das Problem.
            existing = await self._repo.fetch(ctx.workspace_id, agent_id)
            if existing is None:
                raise _not_found()
            raise _invalid_reference()
        return agent

    async def delete(self, ctx: WorkspaceContext, agent_id: UUID) -> None:
        require_role(ctx, WorkspaceRole.editor)
        deleted = await self._repo.delete(ctx.workspace_id, agent_id)
        if not deleted:
            raise _not_found()

    @staticmethod
    def is_disabled(agent: AgentRead) -> bool:
        return agent.status == AgentStatus.disabled
