"""Geschaeftslogik fuer die Reverse-Lookups (Phase 3-A).

Mappt fehlende Playbook-/Resource-IDs auf 404. Workspace-Check liegt in der
Repo-Schicht; der Service liest nur und braucht keinen Role-Gate (alle
Mitglieder duerfen Backlinks sehen).
"""

from uuid import UUID

from fastapi import HTTPException, status

from who2be_api.core.security import WorkspaceContext
from who2be_api.repositories.usage_repository import UsageRepository
from who2be_models import PlaybookUsage, ResourceUsage


def _playbook_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playbook nicht gefunden.")


def _resource_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource nicht gefunden.")


class UsageService:
    """Liest die Backlinks fuer ein Playbook bzw. eine Resource."""

    def __init__(self, repo: UsageRepository) -> None:
        self._repo = repo

    async def list_playbook_usages(
        self, ctx: WorkspaceContext, playbook_id: UUID
    ) -> list[PlaybookUsage]:
        if not await self._repo.playbook_belongs_to(ctx.workspace_id, playbook_id):
            raise _playbook_not_found()
        return await self._repo.list_playbook_usages(ctx.workspace_id, playbook_id)

    async def list_resource_usages(
        self, ctx: WorkspaceContext, resource_id: UUID
    ) -> list[ResourceUsage]:
        if not await self._repo.resource_belongs_to(ctx.workspace_id, resource_id):
            raise _resource_not_found()
        return await self._repo.list_resource_usages(ctx.workspace_id, resource_id)
