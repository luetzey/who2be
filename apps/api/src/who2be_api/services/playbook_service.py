"""Geschaeftslogik fuer das Playbook-Aggregat.

Workspace-Pruefung liegt im SQL der Repository-Schicht; der Service
uebersetzt ein fehlendes Ergebnis (`None`) in ein `HTTPException 404`.
"""

from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status

from who2be_api.core.security import WorkspaceContext
from who2be_api.repositories.playbook_repository import PlaybookRepository
from who2be_models import (
    PlaybookCreate,
    PlaybookRead,
    PlaybookUpdate,
    PlaybookVersionRead,
    encode_cursor,
)


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playbook nicht gefunden.")


class PlaybookService:
    """Legt Playbooks an, liest, listet (mit Filtern), aktualisiert sie."""

    def __init__(self, playbook_repo: PlaybookRepository) -> None:
        self._repo = playbook_repo

    async def create(self, ctx: WorkspaceContext, data: PlaybookCreate) -> PlaybookRead:
        return await self._repo.insert(
            ctx.workspace_id, ctx.user_id, data.name, data.content
        )

    async def list_all(
        self,
        ctx: WorkspaceContext,
        tag: str | None,
        trigger: str | None,
        limit: int,
        cursor: tuple[datetime, UUID] | None,
    ) -> tuple[list[PlaybookRead], str | None]:
        rows = await self._repo.list_by_workspace(
            ctx.workspace_id, tag, trigger, limit + 1, cursor
        )
        if len(rows) > limit:
            items = rows[:limit]
            tail = items[-1]
            return items, encode_cursor(tail.created_at, tail.id)
        return rows, None

    async def get(self, ctx: WorkspaceContext, playbook_id: UUID) -> PlaybookRead:
        playbook = await self._repo.fetch(ctx.workspace_id, playbook_id)
        if playbook is None:
            raise _not_found()
        return playbook

    async def update(
        self, ctx: WorkspaceContext, playbook_id: UUID, data: PlaybookUpdate
    ) -> PlaybookRead:
        """Erzeugt eine neue Version des Playbooks."""
        playbook = await self._repo.update(
            ctx.workspace_id, ctx.user_id, playbook_id, data.name, data.content
        )
        if playbook is None:
            raise _not_found()
        return playbook

    async def list_versions(
        self, ctx: WorkspaceContext, playbook_id: UUID
    ) -> list[PlaybookVersionRead]:
        versions = await self._repo.list_versions(ctx.workspace_id, playbook_id)
        if versions is None:
            raise _not_found()
        return versions

    async def get_version(
        self, ctx: WorkspaceContext, playbook_id: UUID, version: int
    ) -> PlaybookVersionRead:
        found = await self._repo.fetch_version(ctx.workspace_id, playbook_id, version)
        if found is None:
            raise _not_found()
        return found
