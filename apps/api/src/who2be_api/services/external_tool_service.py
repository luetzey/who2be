"""Geschaeftslogik fuer das ExternalTool-Aggregat (WP-1 + WP-3).

Workspace-Pruefung liegt im SQL der Repository-Schicht; der Service
uebersetzt ein fehlendes Ergebnis (`None`) in `HTTPException 404` und den
Draft-on-Edit-Konflikt in `409`. Aufbau analog `resource_service.py`: Reads
sind Read-Scope-gefiltert (`external_tool_read`, WP-3 — `none` sperrt komplett;
`assigned` verhaelt sich wie `all`, siehe `require_external_tool_read`),
Writes sind capability- (`external_tool_write`), tag- und rate-gated.
"""

from datetime import datetime
from uuid import UUID

import asyncpg
from fastapi import HTTPException, status

from who2be_api.core.agent_scope import require_external_tool_read
from who2be_api.core.security import (
    WorkspaceContext,
    require_capability,
    require_role,
    require_unmanaged,
    require_write_rate,
    require_write_tags,
)
from who2be_api.repositories.external_tool_repository import ExternalToolRepository
from who2be_api.services.slug import slugify
from who2be_models import (
    DEFAULT_LOCALE,
    AgentCapability,
    ExternalToolCreate,
    ExternalToolRead,
    ExternalToolUpdate,
    ExternalToolVersionRead,
    WorkspaceRole,
    encode_cursor,
)

_ALIAS_FALLBACK = "tool"
_WRITE_DOMAIN = "external_tool"


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Externes Tool nicht gefunden."
    )


def _alias_conflict() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Ein externes Tool mit diesem Alias existiert bereits.",
    )


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


class ExternalToolService:
    """Legt ExternalTools an, liest, listet (Keyset-Pagination), aktualisiert sie."""

    def __init__(self, repo: ExternalToolRepository) -> None:
        self._repo = repo

    async def create(self, ctx: WorkspaceContext, data: ExternalToolCreate) -> ExternalToolRead:
        require_role(ctx, WorkspaceRole.editor)
        require_capability(ctx, AgentCapability.external_tool_write)
        require_write_rate(ctx)
        require_write_tags(ctx, _WRITE_DOMAIN, data.content.tags)
        # Alias beim Create aus dem Namen ableiten, falls nicht gesetzt (spiegelt
        # ResourceService.create). Workspace-eindeutig — Kollision -> 409
        # (partieller UNIQUE-Index, Migration 0065).
        alias = data.alias or slugify(data.name, fallback=_ALIAS_FALLBACK)
        try:
            return await self._repo.insert(
                ctx.workspace_id, ctx.user_id, data.name, data.content, data.locales, alias=alias
            )
        except asyncpg.UniqueViolationError as exc:
            raise _alias_conflict() from exc

    async def list_all(
        self,
        ctx: WorkspaceContext,
        limit: int,
        cursor: tuple[datetime, UUID] | None,
        locale: str = DEFAULT_LOCALE,
    ) -> tuple[list[ExternalToolRead], str | None]:
        require_external_tool_read(ctx)
        rows = await self._repo.list_by_workspace(
            ctx.workspace_id,
            limit + 1,
            cursor,
            active_only=not ctx.sees_drafts(AgentCapability.external_tool_write),
            locale=locale,
        )
        next_cursor: str | None = None
        if len(rows) > limit:
            rows = rows[:limit]
            tail = rows[-1]
            next_cursor = encode_cursor(tail.created_at, tail.id)
        return rows, next_cursor

    async def get(
        self, ctx: WorkspaceContext, tool_id: UUID, locale: str = DEFAULT_LOCALE
    ) -> ExternalToolRead:
        require_external_tool_read(ctx)
        tool = await self._repo.fetch(
            ctx.workspace_id,
            tool_id,
            active_only=not ctx.sees_drafts(AgentCapability.external_tool_write),
            locale=locale,
        )
        if tool is None:
            raise _not_found()
        return tool

    async def _check_update_tags(
        self, ctx: WorkspaceContext, tool_id: UUID, incoming_tags: list[str], locale: str
    ) -> None:
        """Tag-Scope beim Update: eingehende Tags + (nur bei Restriktion) Bestand."""
        require_write_tags(ctx, _WRITE_DOMAIN, incoming_tags)
        policy = ctx.tool_policy
        if policy is not None and policy.write_tags_for(_WRITE_DOMAIN) is not None:
            existing = await self.get(ctx, tool_id, locale)
            require_write_tags(ctx, _WRITE_DOMAIN, existing.content.tags)

    async def update(
        self,
        ctx: WorkspaceContext,
        tool_id: UUID,
        data: ExternalToolUpdate,
        locale: str = DEFAULT_LOCALE,
    ) -> ExternalToolRead:
        """Erzeugt eine neue Version des Tools (Draft-on-Edit bei Active)."""
        require_role(ctx, WorkspaceRole.editor)
        require_capability(ctx, AgentCapability.external_tool_write)
        require_unmanaged(await self._repo.is_managed(ctx.workspace_id, tool_id))
        require_write_rate(ctx)
        await self._check_update_tags(ctx, tool_id, data.content.tags, locale)
        outcome = await self._repo.update(
            ctx.workspace_id, ctx.user_id, tool_id, data.name, data.content, locale
        )
        if outcome.conflict == "draft_exists":
            raise _draft_conflict()
        if outcome.tool is None:
            raise _not_found()
        return outcome.tool

    async def update_draft(
        self,
        ctx: WorkspaceContext,
        tool_id: UUID,
        data: ExternalToolUpdate,
        locale: str = DEFAULT_LOCALE,
    ) -> ExternalToolRead:
        """Auto-Save-Pfad (PATCH `.../draft`) — upsertet die Draft-Version."""
        require_role(ctx, WorkspaceRole.editor)
        require_capability(ctx, AgentCapability.external_tool_write)
        require_unmanaged(await self._repo.is_managed(ctx.workspace_id, tool_id))
        require_write_rate(ctx)
        await self._check_update_tags(ctx, tool_id, data.content.tags, locale)
        outcome = await self._repo.upsert_draft(
            ctx.workspace_id, ctx.user_id, tool_id, data.name, data.content, locale
        )
        if outcome.conflict == "review_pending":
            raise _review_conflict()
        if outcome.tool is None:
            raise _not_found()
        return outcome.tool

    async def list_versions(
        self, ctx: WorkspaceContext, tool_id: UUID, locale: str = DEFAULT_LOCALE
    ) -> list[ExternalToolVersionRead]:
        require_external_tool_read(ctx)
        versions = await self._repo.list_versions(ctx.workspace_id, tool_id, locale)
        if versions is None:
            raise _not_found()
        return versions

    async def get_version(
        self, ctx: WorkspaceContext, tool_id: UUID, version: int, locale: str = DEFAULT_LOCALE
    ) -> ExternalToolVersionRead:
        require_external_tool_read(ctx)
        found = await self._repo.fetch_version(ctx.workspace_id, tool_id, version, locale)
        if found is None:
            raise _not_found()
        return found

    async def restore(
        self,
        ctx: WorkspaceContext,
        tool_id: UUID,
        source_version: int,
        locale: str = DEFAULT_LOCALE,
    ) -> ExternalToolRead:
        """Stellt den Snapshot `source_version` als neue Draft wieder her (§3.1)."""
        require_role(ctx, WorkspaceRole.editor)
        require_capability(ctx, AgentCapability.external_tool_write)
        require_unmanaged(await self._repo.is_managed(ctx.workspace_id, tool_id))
        require_write_rate(ctx)
        snapshot = await self._repo.fetch_version(ctx.workspace_id, tool_id, source_version, locale)
        if snapshot is None:
            raise _not_found()
        require_write_tags(ctx, _WRITE_DOMAIN, snapshot.content.tags)
        outcome = await self._repo.restore_version(
            ctx.workspace_id, ctx.user_id, tool_id, snapshot.content, locale
        )
        if outcome.conflict == "draft_exists":
            raise _draft_conflict()
        if outcome.tool is None:
            raise _not_found()
        return outcome.tool

    async def delete(self, ctx: WorkspaceContext, tool_id: UUID) -> None:
        """Hard-Delete des ExternalTools (ADR-0032).

        Editor-Gate + `external_tool_write`-Capability. 404, wenn das Tool
        nicht (mehr) existiert. Anders als Resource gibt es keine eingehenden
        Referenzen zu pruefen — `tool-ref`-Placeholder loesen erst zur
        Fetch-Zeit ueber den Alias auf (WP-2); ein geloeschtes Tool fuehrt dort
        zu einem sauberen Miss (`unresolved_key`), nicht zu einer blockierten
        Loeschung.
        """
        require_role(ctx, WorkspaceRole.editor)
        require_capability(ctx, AgentCapability.external_tool_write)
        require_write_rate(ctx)
        tool = await self._repo.fetch(ctx.workspace_id, tool_id)
        if tool is None:
            raise _not_found()
        require_unmanaged(tool.is_managed)
        deleted = await self._repo.delete(ctx.workspace_id, tool_id)
        if not deleted:
            raise _not_found()
