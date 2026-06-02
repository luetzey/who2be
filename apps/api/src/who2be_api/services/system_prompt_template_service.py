"""Geschaeftslogik fuer SystemPromptTemplate-Aggregate.

Workspace-Pruefung liegt im SQL der Repository-Schicht; der Service
uebersetzt fehlende Ergebnisse in `HTTPException 404`. Slug wird beim Create
deterministisch aus dem Namen abgeleitet, wenn der Client keinen liefert —
das deckt die Standard-UI ab (Editor schickt nur Name + Body).
"""

import re
import unicodedata
from datetime import datetime
from uuid import UUID

import asyncpg
from fastapi import HTTPException, status

from who2be_api.core.security import WorkspaceContext, require_role
from who2be_api.repositories.system_prompt_template_repository import (
    SystemPromptTemplateRepository,
)
from who2be_api.services.version_diff import compute_version_diff
from who2be_models import (
    SystemPromptTemplateContent,
    SystemPromptTemplateCreate,
    SystemPromptTemplateRead,
    SystemPromptTemplateUpdate,
    SystemPromptTemplateVersionRead,
    VersionDiff,
    VersionStatus,
    WorkspaceRole,
    encode_cursor,
)

_SLUG_FALLBACK = "template"


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="System-Prompt-Template nicht gefunden.",
    )


def _draft_conflict() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            "Es existiert bereits ein Draft. Promote oder verwirf den "
            "bestehenden Draft, bevor du erneut editierst."
        ),
    )


def _slug_conflict() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Ein Template mit diesem Slug existiert bereits.",
    )


def _invalid_against() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Ungueltiger 'against'-Parameter; erwartet 'active' oder eine Versions-Nummer.",
    )


def slugify(text: str) -> str:
    """Erzeugt einen URL-tauglichen Slug aus dem Namen.

    Standard-NFKD + ASCII-Zwang: Umlaute werden zerlegt, Punkte/Sonderzeichen
    fallen raus, Whitespace wird zu `-`, mehrfache Bindestriche zusammengefasst.
    Bewusst klein gehalten — fuer alles weitere uebergibt der Client den Slug.
    """
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    return cleaned or _SLUG_FALLBACK


class SystemPromptTemplateService:
    """Legt Templates an, liest, listet, aktualisiert."""

    def __init__(self, repo: SystemPromptTemplateRepository) -> None:
        self._repo = repo

    async def create(
        self, ctx: WorkspaceContext, data: SystemPromptTemplateCreate
    ) -> SystemPromptTemplateRead:
        require_role(ctx, WorkspaceRole.editor)
        slug = data.slug or slugify(data.name)
        try:
            return await self._repo.insert(
                ctx.workspace_id,
                ctx.user_id,
                data.name,
                slug,
                data.content,
            )
        except asyncpg.UniqueViolationError as exc:
            raise _slug_conflict() from exc

    async def list_all(
        self,
        ctx: WorkspaceContext,
        limit: int,
        cursor: tuple[datetime, UUID] | None,
    ) -> tuple[list[SystemPromptTemplateRead], str | None]:
        rows = await self._repo.list_by_workspace(ctx.workspace_id, limit + 1, cursor)
        if len(rows) > limit:
            items = rows[:limit]
            tail = items[-1]
            return items, encode_cursor(tail.created_at, tail.id)
        return rows, None

    async def get(self, ctx: WorkspaceContext, template_id: UUID) -> SystemPromptTemplateRead:
        template = await self._repo.fetch(ctx.workspace_id, template_id)
        if template is None:
            raise _not_found()
        return template

    async def update(
        self,
        ctx: WorkspaceContext,
        template_id: UUID,
        data: SystemPromptTemplateUpdate,
    ) -> SystemPromptTemplateRead:
        """Erzeugt eine neue Version des Templates (Draft-on-Edit bei Active)."""
        require_role(ctx, WorkspaceRole.editor)
        outcome = await self._repo.update(
            ctx.workspace_id, ctx.user_id, template_id, data.name, data.content
        )
        if outcome.conflict == "draft_exists":
            raise _draft_conflict()
        if outcome.template is None:
            raise _not_found()
        return outcome.template

    async def list_versions(
        self, ctx: WorkspaceContext, template_id: UUID
    ) -> list[SystemPromptTemplateVersionRead]:
        versions = await self._repo.list_versions(ctx.workspace_id, template_id)
        if versions is None:
            raise _not_found()
        return versions

    async def get_version(
        self, ctx: WorkspaceContext, template_id: UUID, version: int
    ) -> SystemPromptTemplateVersionRead:
        found = await self._repo.fetch_version(ctx.workspace_id, template_id, version)
        if found is None:
            raise _not_found()
        return found

    async def restore(
        self, ctx: WorkspaceContext, template_id: UUID, source_version: int
    ) -> SystemPromptTemplateRead:
        """Stellt den Snapshot `source_version` als neue Draft wieder her (§3.1).

        409 bei bereits offenem Draft.
        """
        require_role(ctx, WorkspaceRole.editor)
        snapshot = await self._repo.fetch_version(ctx.workspace_id, template_id, source_version)
        if snapshot is None:
            raise _not_found()
        outcome = await self._repo.restore_version(
            ctx.workspace_id, ctx.user_id, template_id, snapshot.content
        )
        if outcome.conflict == "draft_exists":
            raise _draft_conflict()
        if outcome.template is None:
            raise _not_found()
        return outcome.template

    async def diff(
        self, ctx: WorkspaceContext, template_id: UUID, version: int, against: str
    ) -> VersionDiff:
        """Strukturierter Feld-Diff der Version `version` gegen `against`."""
        target = await self._repo.fetch_version(ctx.workspace_id, template_id, version)
        if target is None:
            raise _not_found()
        versions = await self._repo.list_versions(ctx.workspace_id, template_id)
        if versions is None:
            raise _not_found()
        base_version, base_content = self._resolve_against(against, versions)
        before = base_content.model_dump(mode="json") if base_content is not None else {}
        return compute_version_diff(
            version=version,
            against=against,
            against_version=base_version,
            before=before,
            after=target.content.model_dump(mode="json"),
        )

    def _resolve_against(
        self, against: str, versions: list[SystemPromptTemplateVersionRead]
    ) -> tuple[int | None, SystemPromptTemplateContent | None]:
        if against == "active":
            for candidate in versions:
                if candidate.status == VersionStatus.active:
                    return candidate.version, candidate.content
            return None, None
        try:
            wanted = int(against)
        except ValueError:
            raise _invalid_against() from None
        for candidate in versions:
            if candidate.version == wanted:
                return candidate.version, candidate.content
        raise _not_found()
