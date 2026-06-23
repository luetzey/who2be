"""Geschaeftslogik fuer die Sub-Resource-Relation (Track E, §3.3).

Listet und setzt die geordneten Sub-Resources einer Resource. Setzen ersetzt
den Stand vollstaendig (PUT-Semantik); Workspace-Pruefung und azyklischer
Zyklus-Guard erfolgen atomar im Repository — Aufbau analog
`PlaybookCompositionService`.
"""

from uuid import UUID

import asyncpg
from fastapi import HTTPException, status

from who2be_api.core.agent_scope import visible_resource_ids
from who2be_api.core.security import WorkspaceContext, require_capability, require_role
from who2be_api.repositories.resource_composition_repository import (
    ResourceCompositionRepository,
)
from who2be_models import (
    AgentCapability,
    ResourceRef,
    SubResourceLinkItem,
    SubResourceLinkSet,
    SubResourceRead,
    WorkspaceRole,
)


def _resource_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Resource nicht gefunden.",
    )


class ResourceCompositionService:
    """Verwaltet die Sub-Resource-Sequenz einer Resource."""

    def __init__(
        self, repo: ResourceCompositionRepository, pool: asyncpg.Pool | None = None
    ) -> None:
        self._repo = repo
        self._pool = pool

    async def list_children(self, ctx: WorkspaceContext, parent_id: UUID) -> list[SubResourceRead]:
        """Gibt die geordneten direkten Sub-Resources zurueck.

        Read-Scoping: nur fuer eine dem Agenten zugewiesene Resource (sonst
        404) — ihre Sub-Resources liegen ueber die assigned-Closure im Scope.
        """
        if not await self._repo.parent_belongs_to(ctx.workspace_id, parent_id):
            raise _resource_not_found()
        scope = await visible_resource_ids(self._pool, ctx)
        if scope is not None and parent_id not in scope:
            raise _resource_not_found()
        return await self._repo.list_children(
            ctx.workspace_id,
            parent_id,
            active_only=not ctx.sees_drafts(AgentCapability.resource_write),
        )

    async def list_parents(self, ctx: WorkspaceContext, child_id: UUID) -> list[ResourceRef]:
        """Gibt die Parent-Resources (Used-By) zurueck.

        Read-Scoping: das Kind muss zugewiesen sein (sonst 404); die Eltern
        liegen nicht in der Closure und werden gegen die sichtbare Menge
        gefiltert (siehe `PlaybookCompositionService.list_parents`).
        """
        if not await self._repo.parent_belongs_to(ctx.workspace_id, child_id):
            raise _resource_not_found()
        scope = await visible_resource_ids(self._pool, ctx)
        if scope is not None and child_id not in scope:
            raise _resource_not_found()
        parents = await self._repo.list_parents(ctx.workspace_id, child_id)
        if scope is not None:
            parents = [p for p in parents if p.id in scope]
        return parents

    async def set_links(
        self,
        ctx: WorkspaceContext,
        parent_id: UUID,
        data: SubResourceLinkSet,
    ) -> list[SubResourceRead]:
        """Ersetzt die Sub-Resource-Liste vollstaendig (PUT-Semantik).

        Erfordert mindestens `editor`-Rolle. Dedupliziert reihenfolge-erhaltend
        ueber `(child_id, link_scope, block_id)` (die partiellen Unique-Indexe
        wuerden Dubletten sonst mit IntegrityError quittieren) und filtert
        defensiv den direkten Self-Ref heraus (auch per DB-CHECK abgesichert).
        Fehlercodes:
        - 403: Rolle ungenuegend.
        - 404: Parent nicht gefunden oder Kind nicht im Workspace.
        - 409: Verknuepfung wuerde einen Zyklus erzeugen.
        """
        require_role(ctx, WorkspaceRole.editor)
        require_capability(ctx, AgentCapability.resource_write)

        seen: set[tuple[UUID, str, str | None]] = set()
        items: list[SubResourceLinkItem] = []
        for item in data.links:
            if item.child_id == parent_id:
                continue
            key = (item.child_id, item.link_scope, item.block_id)
            if key in seen:
                continue
            seen.add(key)
            items.append(item)

        result = await self._repo.set_links(ctx.workspace_id, ctx.user_id, parent_id, items)

        if not result.parent_found:
            raise _resource_not_found()
        if result.missing_child_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mindestens eine Sub-Resource existiert nicht oder "
                "gehoert einem anderen Workspace.",
            )
        if result.cycle:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Verknuepfung wuerde einen Zyklus erzeugen.",
            )

        return await self._repo.list_children(
            ctx.workspace_id,
            parent_id,
            active_only=not ctx.sees_drafts(AgentCapability.resource_write),
        )
