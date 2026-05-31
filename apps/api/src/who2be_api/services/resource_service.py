"""Geschaeftslogik fuer das Resource-Aggregat.

Workspace-Pruefung liegt im SQL der Repository-Schicht; der Service
uebersetzt ein fehlendes Ergebnis (`None`) in `HTTPException 404` und den
Draft-on-Edit-Konflikt in `409`. Aufbau analog `playbook_service.py`.
"""

from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status

from who2be_api.core.security import WorkspaceContext, require_role
from who2be_api.repositories.resource_repository import ResourceRepository
from who2be_models import (
    ResourceCreate,
    ResourceRead,
    ResourceUpdate,
    ResourceVersionRead,
    WorkspaceRole,
    encode_cursor,
)


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource nicht gefunden.")


def _draft_conflict() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            "Es existiert bereits ein Draft. Promote oder verwirf den "
            "bestehenden Draft, bevor du erneut editierst."
        ),
    )


def _review_conflict() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            "Diese Version steht in der Review — Auto-Save ist deaktiviert. "
            "Lehne die Review erst ab, bevor du weiter editierst."
        ),
    )


class ResourceService:
    """Legt Resources an, liest, listet (Keyset-Pagination), aktualisiert sie."""

    def __init__(self, resource_repo: ResourceRepository) -> None:
        self._repo = resource_repo

    async def create(self, ctx: WorkspaceContext, data: ResourceCreate) -> ResourceRead:
        require_role(ctx, WorkspaceRole.editor)
        return await self._repo.insert(ctx.workspace_id, ctx.user_id, data.name, data.content)

    async def list_all(
        self,
        ctx: WorkspaceContext,
        limit: int,
        cursor: tuple[datetime, UUID] | None,
    ) -> tuple[list[ResourceRead], str | None]:
        rows = await self._repo.list_by_workspace(
            ctx.workspace_id, limit + 1, cursor, active_only=ctx.is_api_token
        )
        if len(rows) > limit:
            items = rows[:limit]
            tail = items[-1]
            return items, encode_cursor(tail.created_at, tail.id)
        return rows, None

    async def get(self, ctx: WorkspaceContext, resource_id: UUID) -> ResourceRead:
        resource = await self._repo.fetch(
            ctx.workspace_id, resource_id, active_only=ctx.is_api_token
        )
        if resource is None:
            raise _not_found()
        return resource

    async def update(
        self, ctx: WorkspaceContext, resource_id: UUID, data: ResourceUpdate
    ) -> ResourceRead:
        """Erzeugt eine neue Version der Resource (Draft-on-Edit bei Active)."""
        require_role(ctx, WorkspaceRole.editor)
        outcome = await self._repo.update(
            ctx.workspace_id, ctx.user_id, resource_id, data.name, data.content
        )
        if outcome.conflict == "draft_exists":
            raise _draft_conflict()
        if outcome.resource is None:
            raise _not_found()
        return outcome.resource

    async def update_draft(
        self, ctx: WorkspaceContext, resource_id: UUID, data: ResourceUpdate
    ) -> ResourceRead:
        """Auto-Save-Pfad (PATCH `.../draft`) — upsertet die Draft-Version."""
        require_role(ctx, WorkspaceRole.editor)
        outcome = await self._repo.upsert_draft(
            ctx.workspace_id, ctx.user_id, resource_id, data.name, data.content
        )
        if outcome.conflict == "review_pending":
            raise _review_conflict()
        if outcome.resource is None:
            raise _not_found()
        return outcome.resource

    async def list_versions(
        self, ctx: WorkspaceContext, resource_id: UUID
    ) -> list[ResourceVersionRead]:
        versions = await self._repo.list_versions(ctx.workspace_id, resource_id)
        if versions is None:
            raise _not_found()
        return versions

    async def get_version(
        self, ctx: WorkspaceContext, resource_id: UUID, version: int
    ) -> ResourceVersionRead:
        found = await self._repo.fetch_version(ctx.workspace_id, resource_id, version)
        if found is None:
            raise _not_found()
        return found
