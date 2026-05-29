"""Geschaeftslogik fuer Playbook->Resource-Block-Refs.

Listet und setzt die Block-Refs eines Playbooks. Setzen ersetzt den Stand
vollstaendig (PUT-Semantik); die Workspace-Pruefung erfolgt atomar im
Repository. Doppelte `(resource_id, block_id)`-Paare werden dedupliziert
(Primaerschluessel-Schutz, Reihenfolge bleibt erhalten).

Phase 3-A: vor dem Schreiben pruefen wir gegen die Active- bzw.
Current-Version jeder referenzierten Resource, dass jeder Anker-Block
entweder fehlt (Backward-Compat: Bestand bleibt aenderbar) oder ein
Heading-Block ist. Non-Heading-Anker werden mit 422 abgelehnt.
"""

from uuid import UUID

from fastapi import HTTPException, status

from who2be_api.core.security import WorkspaceContext, require_role
from who2be_api.repositories.playbook_resource_link_repository import (
    PlaybookResourceLinkRepository,
    is_heading_block,
)
from who2be_models import ResourceLinkItem, ResourceLinkRead, ResourceLinkSet, WorkspaceRole


def _playbook_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playbook nicht gefunden.")


class PlaybookResourceLinkService:
    """Verwaltet die Resource-Block-Refs eines Playbooks."""

    def __init__(self, link_repo: PlaybookResourceLinkRepository) -> None:
        self._repo = link_repo

    async def list_links(self, ctx: WorkspaceContext, playbook_id: UUID) -> list[ResourceLinkRead]:
        links = await self._repo.list_links(ctx.workspace_id, playbook_id)
        if links is None:
            raise _playbook_not_found()
        return links

    async def set_links(
        self, ctx: WorkspaceContext, playbook_id: UUID, data: ResourceLinkSet
    ) -> list[ResourceLinkRead]:
        """Ersetzt die Block-Refs; leere Liste loest alle."""
        require_role(ctx, WorkspaceRole.editor)
        deduped: dict[tuple[UUID, str], ResourceLinkItem] = {}
        for item in data.links:
            deduped.setdefault((item.resource_id, item.block_id), item)
        items = list(deduped.values())
        await self._validate_heading_anchors(ctx.workspace_id, items)
        result = await self._repo.set_links(ctx.workspace_id, ctx.user_id, playbook_id, items)
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

    async def _validate_heading_anchors(
        self, workspace_id: UUID, items: list[ResourceLinkItem]
    ) -> None:
        """Wirft 422, wenn ein vorhandener Anker kein Heading ist.

        Fehlende Anker (Block nicht in Active und nicht in Current) gelten
        als "noch nicht resolved"; der Set bleibt zulaessig, weil ein
        Heading nach Edit-Discard rueckverfuegbar werden kann. Der Read
        meldet solche Refs spaeter als `available_in=None`.
        """
        if not items:
            return
        resource_ids = list({item.resource_id for item in items})
        blocks_per_resource = await self._repo.load_resource_blocks(workspace_id, resource_ids)
        for item in items:
            blocks = blocks_per_resource.get(item.resource_id, [])
            anchor = next(
                (b for b in blocks if b.get("id") == item.block_id),
                None,
            )
            if anchor is not None and not is_heading_block(anchor):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Nur Heading-Bloecke sind als Anker erlaubt.",
                )
