"""Geschaeftslogik fuer das Workspace-Aggregat (TASK-301).

Anlage + Update fuer Workspaces innerhalb einer Organization. Membership/
Org-Pruefung laufen ueber das Organization-Repo, damit kein User in einer
fremden Org Workspaces erzeugt.
"""

from uuid import UUID

import asyncpg
from fastapi import status

from who2be_api.core.errors import ApiError
from who2be_api.repositories.organization_repository import OrganizationRepository
from who2be_api.repositories.workspace_repository import (
    LastWorkspaceError,
    WorkspaceRepository,
)
from who2be_models import WorkspaceCreate, WorkspaceRead, WorkspaceUpdate


def _not_found() -> ApiError:
    return ApiError(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Workspace nicht gefunden.",
        reason="workspace_not_found",
    )


def _org_not_found() -> ApiError:
    """Org unbekannt **oder** ohne Mitgliedschaft — bewusst derselbe Fehler.

    Die Unterscheidung waere ein Enumerations-Kanal (existiert die Org?);
    deshalb tragen beide Faelle denselben Grund wie schon denselben `detail`.
    """
    return ApiError(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Organization nicht gefunden.",
        reason="organization_not_found",
    )


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
            raise _org_not_found()
        return await self._workspaces.list_by_org_for_user(org_id, user_id)

    async def create(self, org_id: UUID, user_id: UUID, data: WorkspaceCreate) -> WorkspaceRead:
        if await self._orgs.fetch(user_id, org_id) is None:
            raise _org_not_found()
        try:
            return await self._workspaces.create(
                org_id, user_id, data.name, data.slug, data.content_locale
            )
        except asyncpg.UniqueViolationError as exc:
            raise ApiError(
                status_code=status.HTTP_409_CONFLICT,
                detail="Workspace-Slug ist in dieser Organization vergeben.",
                reason="workspace_slug_conflict",
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

    async def delete(self, workspace_id: UUID) -> None:
        try:
            deleted = await self._workspaces.delete(workspace_id)
        except LastWorkspaceError as exc:
            raise ApiError(
                status_code=status.HTTP_409_CONFLICT,
                detail="Der letzte Workspace einer Organization kann nicht geloescht werden.",
                reason="last_workspace_undeletable",
            ) from exc
        if not deleted:
            raise _not_found()
