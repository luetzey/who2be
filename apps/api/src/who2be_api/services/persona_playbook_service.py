"""Geschaeftslogik fuer die Persona-Playbook-Verknuepfung.

Listet und setzt die mit einer Persona verknuepften Playbooks. Setzen
ersetzt den Stand vollstaendig (PUT-Semantik); die Workspace-Pruefung
erfolgt atomar im Repository.
"""

from uuid import UUID

from fastapi import HTTPException, status

from who2be_api.core.security import WorkspaceContext, require_role
from who2be_api.repositories.persona_playbook_repository import (
    PersonaPlaybookRepository,
)
from who2be_models import PersonaPlaybookLinkSet, PlaybookRead, WorkspaceRole


def _persona_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona nicht gefunden.")


class PersonaPlaybookService:
    """Verwaltet die Playbook-Verknuepfungen einer Persona."""

    def __init__(self, link_repo: PersonaPlaybookRepository) -> None:
        self._repo = link_repo

    async def list_links(self, ctx: WorkspaceContext, persona_id: UUID) -> list[PlaybookRead]:
        if not await self._repo.persona_belongs_to(ctx.workspace_id, persona_id):
            raise _persona_not_found()
        return await self._repo.list_linked(persona_id, active_only=ctx.is_api_token)

    async def set_links(
        self, ctx: WorkspaceContext, persona_id: UUID, data: PersonaPlaybookLinkSet
    ) -> list[PlaybookRead]:
        """Ersetzt die Verknuepfungen; leere Liste loest alle."""
        require_role(ctx, WorkspaceRole.editor)
        # Reihenfolge erhaltend deduplizieren — doppelte Links sind keine.
        ids = list(dict.fromkeys(data.playbook_ids))
        result = await self._repo.set_links(ctx.workspace_id, ctx.user_id, persona_id, ids)
        if not result.persona_found:
            raise _persona_not_found()
        if result.missing_playbook_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mindestens ein Playbook existiert nicht oder "
                "gehoert einem anderen Workspace.",
            )
        return await self._repo.list_linked(persona_id, active_only=ctx.is_api_token)
