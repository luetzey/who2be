"""Geschaeftslogik fuer das Workspace-Aggregat (TASK-301).

Anlage + Update fuer Workspaces innerhalb einer Organization. Membership/
Org-Pruefung laufen ueber das Organization-Repo, damit kein User in einer
fremden Org Workspaces erzeugt.
"""

from uuid import UUID

import asyncpg
from fastapi import HTTPException, status

from who2be_api.repositories.organization_repository import OrganizationRepository
from who2be_api.repositories.workspace_repository import WorkspaceRepository
from who2be_models import WorkspaceCreate, WorkspaceRead, WorkspaceUpdate


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace nicht gefunden.")


class WorkspaceService:
    """Workspace-CRUD inkl. Org-Membership-Gate."""

    def __init__(
        self,
        workspace_repo: WorkspaceRepository,
        organization_repo: OrganizationRepository,
    ) -> None:
        self._workspaces = workspace_repo
        self._orgs = organization_repo

    async def list_for_org(self, org_id: UUID, user_id: UUID) -> list[WorkspaceRead]:
        if await self._orgs.fetch(user_id, org_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization nicht gefunden.",
            )
        return await self._workspaces.list_by_org_for_user(org_id, user_id)

    async def create(self, org_id: UUID, user_id: UUID, data: WorkspaceCreate) -> WorkspaceRead:
        if await self._orgs.fetch(user_id, org_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization nicht gefunden.",
            )
        try:
            return await self._workspaces.create(org_id, user_id, data.name, data.slug)
        except asyncpg.UniqueViolationError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Workspace-Slug ist in dieser Organization vergeben.",
            ) from exc

    async def update(self, workspace_id: UUID, data: WorkspaceUpdate) -> WorkspaceRead:
        if data.name is None:
            current = await self._workspaces.fetch(workspace_id)
            if current is None:
                raise _not_found()
            return current
        updated = await self._workspaces.update_name(workspace_id, data.name)
        if updated is None:
            raise _not_found()
        return updated

    async def fetch(self, workspace_id: UUID) -> WorkspaceRead:
        ws = await self._workspaces.fetch(workspace_id)
        if ws is None:
            raise _not_found()
        return ws
