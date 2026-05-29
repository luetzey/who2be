"""Geschaeftslogik fuer Playbook->Resource-Block-Refs.

Listet und setzt die Block-Refs eines Playbooks. Setzen ersetzt den Stand
vollstaendig (PUT-Semantik); die Workspace-Pruefung erfolgt atomar im
Repository. Doppelte `(resource_id, block_id)`-Paare werden dedupliziert
(Primaerschluessel-Schutz, Reihenfolge bleibt erhalten).
"""

from uuid import UUID

from fastapi import HTTPException, status

from who2be_api.core.security import WorkspaceContext
from who2be_api.repositories.playbook_resource_link_repository import (
    PlaybookResourceLinkRepository,
)
from who2be_models import ResourceLinkItem, ResourceLinkRead, ResourceLinkSet


def _playbook_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Playbook nicht gefunden."
    )


class PlaybookResourceLinkService:
    """Verwaltet die Resource-Block-Refs eines Playbooks."""

    def __init__(self, link_repo: PlaybookResourceLinkRepository) -> None:
        self._repo = link_repo

    async def list_links(
        self, ctx: WorkspaceContext, playbook_id: UUID
    ) -> list[ResourceLinkRead]:
        links = await self._repo.list_links(ctx.workspace_id, playbook_id)
        if links is None:
            raise _playbook_not_found()
        return links

    async def set_links(
        self, ctx: WorkspaceContext, playbook_id: UUID, data: ResourceLinkSet
    ) -> list[ResourceLinkRead]:
        """Ersetzt die Block-Refs; leere Liste loest alle."""
        deduped: dict[tuple[UUID, str], ResourceLinkItem] = {}
        for item in data.links:
            deduped.setdefault((item.resource_id, item.block_id), item)
        result = await self._repo.set_links(
            ctx.workspace_id, ctx.user_id, playbook_id, list(deduped.values())
        )
        if not result.playbook_found:
            raise _playbook_not_found()
        if result.missing_resource_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mindestens eine Resource existiert nicht oder "
                "gehoert einem anderen Workspace.",
            )
        links = await self._repo.list_links(ctx.workspace_id, playbook_id)
        return links if links is not None else []
