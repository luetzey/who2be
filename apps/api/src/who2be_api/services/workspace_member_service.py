"""Geschaeftslogik fuer Workspace-Mitglieder (Phase 2.3-B).

Listet Mitglieder, aendert Rollen und entfernt Mitglieder. Das Repository
erzwingt die Last-admin-Invariante transaktional; hier wird sie auf 409
gemappt, fehlende Mitglieder auf 404.
"""

from uuid import UUID

from fastapi import HTTPException, status

from who2be_api.repositories.token_repository import TokenRepository
from who2be_api.repositories.workspace_member_repository import (
    LastAdminError,
    WorkspaceMemberRepository,
)
from who2be_models import WorkspaceMemberRead, WorkspaceRole

_LAST_ADMIN_DETAIL = "Der letzte Admin kann nicht herabgestuft oder entfernt werden."
_NOT_FOUND_DETAIL = "Mitglied nicht gefunden."


class WorkspaceMemberService:
    """CRUD-Adapter um das Member-Repository.

    Beim Entfernen und beim Rollenwechsel eines Mitglieds werden dessen aktive
    API-Tokens in diesem Workspace mit-widerrufen (Deprovisioning, Security-
    Review): der statische Token-Pfad (`get_current_workspace`) prueft die
    Membership nicht live, ein gepinnter Token (Snapshot-Rolle) ueberlebte sonst
    das Entfernen/Herabstufen. Push-Revocation analog zum OAuth-Refresh-Kill.
    """

    def __init__(self, member_repo: WorkspaceMemberRepository, token_repo: TokenRepository) -> None:
        self._repo = member_repo
        self._tokens = token_repo

    async def list_members(self, workspace_id: UUID) -> list[WorkspaceMemberRead]:
        return await self._repo.list_by_workspace(workspace_id)

    async def update_role(
        self,
        workspace_id: UUID,
        user_id: UUID,
        new_role: WorkspaceRole,
        *,
        actor_id: UUID | None = None,
    ) -> WorkspaceMemberRead:
        try:
            member = await self._repo.update_role(
                workspace_id, user_id, new_role, actor_id=actor_id
            )
        except LastAdminError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=_LAST_ADMIN_DETAIL
            ) from exc
        if member is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND_DETAIL)
        # Rollenwechsel invalidiert die gepinnte Snapshot-Rolle bestehender
        # Tokens des Mitglieds — daher alle mit-widerrufen (Neu-Ausstellung mit
        # der neuen Rolle bleibt moeglich).
        await self._tokens.revoke_by_owner(workspace_id, user_id)
        return member

    async def remove(
        self,
        workspace_id: UUID,
        user_id: UUID,
        *,
        actor_id: UUID | None = None,
    ) -> None:
        try:
            removed = await self._repo.remove(workspace_id, user_id, actor_id=actor_id)
        except LastAdminError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=_LAST_ADMIN_DETAIL
            ) from exc
        if not removed:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND_DETAIL)
        # Entferntes Mitglied: seine aktiven Tokens in diesem Workspace sofort
        # widerrufen — sonst behielte ein Ex-Admin lebende Credentials.
        await self._tokens.revoke_by_owner(workspace_id, user_id)
