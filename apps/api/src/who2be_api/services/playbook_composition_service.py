"""Geschaeftslogik fuer die Playbook-Composition-Relation (Gap 2.1, ADR-0024).

Listet und setzt die geordneten Kinder-Playbooks eines Composite. Setzen
ersetzt den Stand vollstaendig (PUT-Semantik); die Workspace-Pruefung und der
Zyklus-Guard erfolgen atomar im Repository.
"""

from uuid import UUID

from fastapi import HTTPException, status

from who2be_api.core.security import WorkspaceContext, require_capability, require_role
from who2be_api.repositories.playbook_composition_repository import (
    PlaybookCompositionRepository,
)
from who2be_models import (
    AgentCapability,
    PlaybookCompositionLinkSet,
    PlaybookRead,
    PlaybookRef,
    WorkspaceRole,
)


def _parent_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Playbook nicht gefunden.",
    )


class PlaybookCompositionService:
    """Verwaltet die Composition (Sub-Playbook-Sequenz) eines Playbooks."""

    def __init__(self, repo: PlaybookCompositionRepository) -> None:
        self._repo = repo

    async def list_children(self, ctx: WorkspaceContext, parent_id: UUID) -> list[PlaybookRead]:
        """Gibt die geordneten Kinder des Composite zurueck.

        `active_only` wird aus `ctx.is_api_token` abgeleitet (MCP-Pfad).
        """
        if not await self._repo.parent_belongs_to(ctx.workspace_id, parent_id):
            raise _parent_not_found()
        return await self._repo.list_children(parent_id, active_only=ctx.is_api_token)

    async def list_parents(self, ctx: WorkspaceContext, child_id: UUID) -> list[PlaybookRef]:
        """Gibt die Parent-Playbooks (Composed-By) zurueck."""
        if not await self._repo.parent_belongs_to(ctx.workspace_id, child_id):
            raise _parent_not_found()
        return await self._repo.list_parents(child_id)

    async def set_composition(
        self,
        ctx: WorkspaceContext,
        parent_id: UUID,
        data: PlaybookCompositionLinkSet,
    ) -> list[PlaybookRead]:
        """Ersetzt die Kinder-Liste vollstaendig (PUT-Semantik).

        Erfordert mindestens `editor`-Rolle. Deduplication ist
        reihenfolge-erhaltend via `dict.fromkeys`. Die Parent-ID wird defensiv
        aus der Liste gefiltert (direkter Selbst-Ref auch per DB-CHECK abgefangen).
        Fehlercodes:
        - 403: Rolle ungenuegend.
        - 404: Parent nicht gefunden oder Kind nicht im Workspace.
        - 409: Verknuepfung wuerde einen Zyklus erzeugen.
        """
        require_role(ctx, WorkspaceRole.editor)
        require_capability(ctx, AgentCapability.playbook_write)

        # Reihenfolge-erhaltend dedupen + defensiv self-ref entfernen
        ids: list[UUID] = [cid for cid in dict.fromkeys(data.child_ids) if cid != parent_id]

        result = await self._repo.set_composition(ctx.workspace_id, ctx.user_id, parent_id, ids)

        if not result.parent_found:
            raise _parent_not_found()
        if result.missing_child_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mindestens ein Sub-Playbook existiert nicht oder "
                "gehoert einem anderen Workspace.",
            )
        if result.cycle:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Verknuepfung wuerde einen Zyklus erzeugen.",
            )

        return await self._repo.list_children(parent_id, active_only=ctx.is_api_token)
