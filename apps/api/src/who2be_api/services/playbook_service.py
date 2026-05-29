"""Geschaeftslogik fuer das Playbook-Aggregat.

Workspace-Pruefung liegt im SQL der Repository-Schicht; der Service
uebersetzt ein fehlendes Ergebnis (`None`) in ein `HTTPException 404`.

Phase 2.1b: `active_only` ueber `ctx.is_api_token` (MCP-Pfad) und
Draft-on-Edit-Konflikt aus dem Repo → 409.
"""

from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status

from who2be_api.core.security import WorkspaceContext, require_role
from who2be_api.repositories.playbook_repository import PlaybookRepository
from who2be_models import (
    PlaybookCreate,
    PlaybookRead,
    PlaybookUpdate,
    PlaybookVersionRead,
    WorkspaceRole,
    encode_cursor,
)


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playbook nicht gefunden.")


def _draft_conflict() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            "Es existiert bereits ein Draft. Promote oder verwirf den "
            "bestehenden Draft, bevor du erneut editierst."
        ),
    )


class PlaybookService:
    """Legt Playbooks an, liest, listet (mit Filtern), aktualisiert sie."""

    def __init__(self, playbook_repo: PlaybookRepository) -> None:
        self._repo = playbook_repo

    async def create(self, ctx: WorkspaceContext, data: PlaybookCreate) -> PlaybookRead:
        require_role(ctx, WorkspaceRole.editor)
        return await self._repo.insert(ctx.workspace_id, ctx.user_id, data.name, data.content)

    async def list_all(
        self,
        ctx: WorkspaceContext,
        tag: str | None,
        trigger: str | None,
        limit: int,
        cursor: tuple[datetime, UUID] | None,
    ) -> tuple[list[PlaybookRead], str | None]:
        rows = await self._repo.list_by_workspace(
            ctx.workspace_id,
            tag,
            trigger,
            limit + 1,
            cursor,
            active_only=ctx.is_api_token,
        )
        if len(rows) > limit:
            items = rows[:limit]
            tail = items[-1]
            return items, encode_cursor(tail.created_at, tail.id)
        return rows, None

    async def get(self, ctx: WorkspaceContext, playbook_id: UUID) -> PlaybookRead:
        playbook = await self._repo.fetch(
            ctx.workspace_id, playbook_id, active_only=ctx.is_api_token
        )
        if playbook is None:
            raise _not_found()
        return playbook

    async def update(
        self, ctx: WorkspaceContext, playbook_id: UUID, data: PlaybookUpdate
    ) -> PlaybookRead:
        """Erzeugt eine neue Version des Playbooks (Draft-on-Edit bei Active)."""
        require_role(ctx, WorkspaceRole.editor)
        outcome = await self._repo.update(
            ctx.workspace_id, ctx.user_id, playbook_id, data.name, data.content
        )
        if outcome.conflict == "draft_exists":
            raise _draft_conflict()
        if outcome.playbook is None:
            raise _not_found()
        return outcome.playbook

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

    async def list_tags(self, ctx: WorkspaceContext) -> list[str]:
        """DISTINCT-Tags des Workspaces — Datenquelle fuer den Tag-Picker."""
        return await self._repo.list_distinct_tags(ctx.workspace_id)
