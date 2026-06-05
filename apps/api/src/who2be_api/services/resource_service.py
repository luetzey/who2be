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
from who2be_api.repositories.usage_repository import UsageRepository
from who2be_api.services.version_diff import compute_version_diff
from who2be_models import (
    DEFAULT_LOCALE,
    DeleteBlocked,
    ResourceContent,
    ResourceCreate,
    ResourceRead,
    ResourceRef,
    ResourceUpdate,
    ResourceUsage,
    ResourceVersionRead,
    VersionDiff,
    VersionStatus,
    WorkspaceRole,
    encode_cursor,
)


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource nicht gefunden.")


def _delete_blocked(playbooks: list[ResourceUsage], composites: list[ResourceRef]) -> HTTPException:
    """409: eingehende Referenzen blockieren das Resource-Delete.

    Blockierend sind referenzierende Playbooks (`playbook_resource_link`) UND
    Eltern-Composites (`resource_composition`). `detail` ist der strukturierte
    `DeleteBlocked`-Body (Klartext + maschinenlesbare Verwender-Listen).
    """
    parts: list[str] = []
    if playbooks:
        parts.append(
            f"{len(playbooks)} Playbook(s): " + ", ".join(u.playbook_name for u in playbooks)
        )
    if composites:
        parts.append(
            f"{len(composites)} Composite-Resource(s): " + ", ".join(c.name for c in composites)
        )
    detail = DeleteBlocked(
        message=(
            "Resource kann nicht geloescht werden — sie wird referenziert von "
            + "; ".join(parts)
            + ". Loese die Verknuepfungen zuerst."
        ),
        blocked_by={"playbooks": list(playbooks), "composites": list(composites)},
    )
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=detail.model_dump(mode="json"),
    )


def _invalid_against() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Ungueltiger 'against'-Parameter; erwartet 'active' oder eine Versions-Nummer.",
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


class ResourceService:
    """Legt Resources an, liest, listet (Keyset-Pagination), aktualisiert sie."""

    def __init__(
        self,
        resource_repo: ResourceRepository,
        usage_repo: UsageRepository | None = None,
    ) -> None:
        self._repo = resource_repo
        self._usage_repo = usage_repo

    async def create(self, ctx: WorkspaceContext, data: ResourceCreate) -> ResourceRead:
        require_role(ctx, WorkspaceRole.editor)
        return await self._repo.insert(
            ctx.workspace_id, ctx.user_id, data.name, data.content, data.locales
        )

    async def list_tags(self, ctx: WorkspaceContext, locale: str = DEFAULT_LOCALE) -> list[str]:
        """DISTINCT-Tags des Workspaces — Datenquelle fuer den Resource-Tag-Picker."""
        return await self._repo.list_distinct_tags(ctx.workspace_id, locale)

    async def list_all(
        self,
        ctx: WorkspaceContext,
        tag: str | None,
        limit: int,
        cursor: tuple[datetime, UUID] | None,
        locale: str = DEFAULT_LOCALE,
    ) -> tuple[list[ResourceRead], str | None]:
        rows = await self._repo.list_by_workspace(
            ctx.workspace_id, tag, limit + 1, cursor, active_only=ctx.is_api_token, locale=locale
        )
        if len(rows) > limit:
            items = rows[:limit]
            tail = items[-1]
            return items, encode_cursor(tail.created_at, tail.id)
        return rows, None

    async def get(
        self, ctx: WorkspaceContext, resource_id: UUID, locale: str = DEFAULT_LOCALE
    ) -> ResourceRead:
        resource = await self._repo.fetch(
            ctx.workspace_id, resource_id, active_only=ctx.is_api_token, locale=locale
        )
        if resource is None:
            raise _not_found()
        return resource

    async def update(
        self,
        ctx: WorkspaceContext,
        resource_id: UUID,
        data: ResourceUpdate,
        locale: str = DEFAULT_LOCALE,
    ) -> ResourceRead:
        """Erzeugt eine neue Version der Resource (Draft-on-Edit bei Active)."""
        require_role(ctx, WorkspaceRole.editor)
        outcome = await self._repo.update(
            ctx.workspace_id, ctx.user_id, resource_id, data.name, data.content, locale
        )
        if outcome.conflict == "draft_exists":
            raise _draft_conflict()
        if outcome.resource is None:
            raise _not_found()
        return outcome.resource

    async def update_draft(
        self,
        ctx: WorkspaceContext,
        resource_id: UUID,
        data: ResourceUpdate,
        locale: str = DEFAULT_LOCALE,
    ) -> ResourceRead:
        """Auto-Save-Pfad (PATCH `.../draft`) — upsertet die Draft-Version."""
        require_role(ctx, WorkspaceRole.editor)
        outcome = await self._repo.upsert_draft(
            ctx.workspace_id, ctx.user_id, resource_id, data.name, data.content, locale
        )
        if outcome.conflict == "review_pending":
            raise _review_conflict()
        if outcome.resource is None:
            raise _not_found()
        return outcome.resource

    async def list_versions(
        self, ctx: WorkspaceContext, resource_id: UUID, locale: str = DEFAULT_LOCALE
    ) -> list[ResourceVersionRead]:
        versions = await self._repo.list_versions(ctx.workspace_id, resource_id, locale)
        if versions is None:
            raise _not_found()
        return versions

    async def get_version(
        self, ctx: WorkspaceContext, resource_id: UUID, version: int, locale: str = DEFAULT_LOCALE
    ) -> ResourceVersionRead:
        found = await self._repo.fetch_version(ctx.workspace_id, resource_id, version, locale)
        if found is None:
            raise _not_found()
        return found

    async def restore(
        self,
        ctx: WorkspaceContext,
        resource_id: UUID,
        source_version: int,
        locale: str = DEFAULT_LOCALE,
    ) -> ResourceRead:
        """Stellt den Snapshot `source_version` als neue Draft wieder her (§3.1)."""
        require_role(ctx, WorkspaceRole.editor)
        snapshot = await self._repo.fetch_version(
            ctx.workspace_id, resource_id, source_version, locale
        )
        if snapshot is None:
            raise _not_found()
        outcome = await self._repo.restore_version(
            ctx.workspace_id, ctx.user_id, resource_id, snapshot.content, locale
        )
        if outcome.conflict == "draft_exists":
            raise _draft_conflict()
        if outcome.resource is None:
            raise _not_found()
        return outcome.resource

    async def diff(
        self,
        ctx: WorkspaceContext,
        resource_id: UUID,
        version: int,
        against: str,
        locale: str = DEFAULT_LOCALE,
    ) -> VersionDiff:
        """Strukturierter Feld-/Block-Diff der Version `version` gegen `against`."""
        target = await self._repo.fetch_version(ctx.workspace_id, resource_id, version, locale)
        if target is None:
            raise _not_found()
        versions = await self._repo.list_versions(ctx.workspace_id, resource_id, locale)
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
        self, against: str, versions: list[ResourceVersionRead]
    ) -> tuple[int | None, ResourceContent | None]:
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

    async def delete(self, ctx: WorkspaceContext, resource_id: UUID) -> None:
        """Hard-Delete der Resource (ADR-0032).

        Editor-Gate. Blockiert mit 409, solange Playbooks Bloecke referenzieren
        oder Eltern-Composites die Resource einbetten (der 409-Body listet beide
        Quellen). 404, wenn die Resource nicht (mehr) existiert. Die FK-Kaskaden
        raeumen Versionen und ausgehende Composition-Kanten beim DELETE selbst ab.
        """
        require_role(ctx, WorkspaceRole.editor)
        resource = await self._repo.fetch(ctx.workspace_id, resource_id)
        if resource is None:
            raise _not_found()
        if self._usage_repo is None:  # pragma: no cover - im Prod immer gesetzt
            raise RuntimeError("ResourceService.delete benoetigt ein UsageRepository.")
        playbooks = await self._usage_repo.list_resource_usages(ctx.workspace_id, resource_id)
        composites = await self._usage_repo.list_resource_parent_composites(
            ctx.workspace_id, resource_id
        )
        if playbooks or composites:
            raise _delete_blocked(playbooks, composites)
        deleted = await self._repo.delete(ctx.workspace_id, resource_id)
        if not deleted:
            raise _not_found()
