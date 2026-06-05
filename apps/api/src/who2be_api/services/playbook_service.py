"""Geschaeftslogik fuer das Playbook-Aggregat.

Workspace-Pruefung liegt im SQL der Repository-Schicht; der Service
uebersetzt ein fehlendes Ergebnis (`None`) in ein `HTTPException 404`.

Phase 2.1b: `active_only` ueber `ctx.is_api_token` (MCP-Pfad) und
Draft-on-Edit-Konflikt aus dem Repo → 409.
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
from fastapi import HTTPException, status
from pydantic import BaseModel

from who2be_api.core.security import WorkspaceContext, require_role
from who2be_api.repositories.playbook_repository import PlaybookRepository
from who2be_api.repositories.usage_repository import UsageRepository
from who2be_api.services.placeholders import RenderContext, render_template_body
from who2be_api.services.playbook_body_pills import extract_pills
from who2be_api.services.playbook_composition_service import PlaybookCompositionService
from who2be_api.services.playbook_resource_link_service import PlaybookResourceLinkService
from who2be_api.services.version_diff import compute_version_diff
from who2be_models import (
    DEFAULT_LOCALE,
    DeleteBlocked,
    PlaybookCompositionLinkSet,
    PlaybookContent,
    PlaybookCreate,
    PlaybookRead,
    PlaybookRef,
    PlaybookUpdate,
    PlaybookUsage,
    PlaybookVersionRead,
    ResourceLinkSet,
    TriggerOverview,
    VersionDiff,
    VersionStatus,
    WorkspaceRole,
    encode_cursor,
)


class PlaybookRenderResponse(BaseModel):
    """Antwort des Render-Endpoints: expandierter Body + offene Placeholder-Keys.

    Spiegelt den Agent-Render-Vertrag: `body_rendered` ist der Plain-Text-Output
    von `render_template_body` (Track B: Body ist immer BlockNote). `unresolved`
    listet deduplizierte, lexikografisch sortierte Miss-Keys.
    """

    body_rendered: str
    unresolved: list[str]


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playbook nicht gefunden.")


def _delete_blocked(personas: list[PlaybookUsage], composites: list[PlaybookRef]) -> HTTPException:
    """409: eingehende Referenzen blockieren das Playbook-Delete.

    Blockierend sind verlinkende Personas (`persona_playbook`) UND Eltern-
    Composites (`playbook_composition`). `detail` ist der strukturierte
    `DeleteBlocked`-Body (Klartext + maschinenlesbare Verwender-Listen).
    """
    parts: list[str] = []
    if personas:
        parts.append(f"{len(personas)} Persona(s): " + ", ".join(u.persona_name for u in personas))
    if composites:
        parts.append(
            f"{len(composites)} Composite-Playbook(s): " + ", ".join(c.name for c in composites)
        )
    detail = DeleteBlocked(
        message=(
            "Playbook kann nicht geloescht werden — es wird referenziert von "
            + "; ".join(parts)
            + ". Loese die Verknuepfungen zuerst."
        ),
        blocked_by={"personas": list(personas), "composites": list(composites)},
    )
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=detail.model_dump(mode="json"),
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


def _invalid_against() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Ungueltiger 'against'-Parameter; erwartet 'active' oder eine Versions-Nummer.",
    )


class PlaybookService:
    """Legt Playbooks an, liest, listet (mit Filtern), aktualisiert sie.

    B5/B3: Der Service haelt zusaetzlich den Pool (fuer den Render-Pfad) und die
    Composition-/Resource-Link-Services (fuer den Save-Sync „Body treibt"). Letztere
    werden injiziert, damit Dedup/Self-Ref/Zyklus/Heading-Anker-Validierung in
    einer Quelle bleibt (kein direkter Repo-Zugriff).
    """

    def __init__(
        self,
        playbook_repo: PlaybookRepository,
        pool: asyncpg.Pool,
        composition_service: PlaybookCompositionService,
        resource_link_service: PlaybookResourceLinkService,
        usage_repo: UsageRepository | None = None,
    ) -> None:
        self._repo = playbook_repo
        self._pool = pool
        self._composition_service = composition_service
        self._resource_link_service = resource_link_service
        self._usage_repo = usage_repo

    async def create(self, ctx: WorkspaceContext, data: PlaybookCreate) -> PlaybookRead:
        require_role(ctx, WorkspaceRole.editor)
        playbook = await self._repo.insert(
            ctx.workspace_id, ctx.user_id, data.name, data.content, data.locales
        )
        await self._sync_body_pills(ctx, playbook.id, data.content)
        return playbook

    async def render(
        self, ctx: WorkspaceContext, playbook_id: UUID, locale: str = DEFAULT_LOCALE
    ) -> PlaybookRenderResponse:
        """Expandiert den Playbook-Body durch den Placeholder-Renderer (B5).

        Track B: Der Body ist immer BlockNote-JSON; Inline-Pills werden
        serverseitig expandiert. MCP nutzt diesen Endpoint, da der MCP-Prozess
        keinen DB-Zugriff hat.
        """
        playbook = await self.get(ctx, playbook_id, locale=locale)
        render_ctx = RenderContext(
            workspace_id=ctx.workspace_id,
            persona_id=None,
            now=datetime.now(UTC),
        )
        async with self._pool.acquire() as conn:
            body_rendered, unresolved = await render_template_body(
                playbook.content.body,
                render_ctx,
                conn,
            )
        return PlaybookRenderResponse(body_rendered=body_rendered, unresolved=unresolved)

    async def _sync_body_pills(
        self, ctx: WorkspaceContext, playbook_id: UUID, content: PlaybookContent
    ) -> None:
        """Save-Sync „Body treibt" (B3): extrahiert Inline-Pills und synct sie.

        Track B: Der Body ist immer BlockNote; `extract_pills` toleriert leere/
        ungueltige Bodies (liefert dann leere Listen).

        Delegiert an die Services (nicht die Repos), damit Dedup, Self-Ref-Filter,
        Zyklus-Guard und Heading-Anker-Validierung greifen. Ein Zyklus (→ 409) oder
        ungueltiger Block-Anker (→ 422) propagiert als HTTPException nach oben.
        """
        child_ids, resource_links = extract_pills(content.body)
        await self._composition_service.set_composition(
            ctx, playbook_id, PlaybookCompositionLinkSet(child_ids=child_ids)
        )
        await self._resource_link_service.set_links(
            ctx, playbook_id, ResourceLinkSet(links=resource_links)
        )

    async def list_all(
        self,
        ctx: WorkspaceContext,
        tag: str | None,
        trigger: str | None,
        limit: int,
        cursor: tuple[datetime, UUID] | None,
        locale: str = DEFAULT_LOCALE,
    ) -> tuple[list[PlaybookRead], str | None]:
        rows = await self._repo.list_by_workspace(
            ctx.workspace_id,
            tag,
            trigger,
            limit + 1,
            cursor,
            active_only=ctx.is_api_token,
            locale=locale,
        )
        if len(rows) > limit:
            items = rows[:limit]
            tail = items[-1]
            return items, encode_cursor(tail.created_at, tail.id)
        return rows, None

    async def get(
        self, ctx: WorkspaceContext, playbook_id: UUID, locale: str = DEFAULT_LOCALE
    ) -> PlaybookRead:
        playbook = await self._repo.fetch(
            ctx.workspace_id, playbook_id, active_only=ctx.is_api_token, locale=locale
        )
        if playbook is None:
            raise _not_found()
        return playbook

    async def update(
        self,
        ctx: WorkspaceContext,
        playbook_id: UUID,
        data: PlaybookUpdate,
        locale: str = DEFAULT_LOCALE,
    ) -> PlaybookRead:
        """Erzeugt eine neue Version des Playbooks (Draft-on-Edit bei Active)."""
        require_role(ctx, WorkspaceRole.editor)
        outcome = await self._repo.update(
            ctx.workspace_id, ctx.user_id, playbook_id, data.name, data.content, locale
        )
        if outcome.conflict == "draft_exists":
            raise _draft_conflict()
        if outcome.playbook is None:
            raise _not_found()
        await self._sync_body_pills(ctx, outcome.playbook.id, data.content)
        return outcome.playbook

    async def update_draft(
        self,
        ctx: WorkspaceContext,
        playbook_id: UUID,
        data: PlaybookUpdate,
        locale: str = DEFAULT_LOCALE,
    ) -> PlaybookRead:
        """Auto-Save-Pfad (PATCH `.../draft`) — upsertet die Draft-Version."""
        require_role(ctx, WorkspaceRole.editor)
        outcome = await self._repo.upsert_draft(
            ctx.workspace_id, ctx.user_id, playbook_id, data.name, data.content, locale
        )
        if outcome.conflict == "review_pending":
            raise _review_conflict()
        if outcome.playbook is None:
            raise _not_found()
        await self._sync_body_pills(ctx, outcome.playbook.id, data.content)
        return outcome.playbook

    async def list_versions(
        self, ctx: WorkspaceContext, playbook_id: UUID, locale: str = DEFAULT_LOCALE
    ) -> list[PlaybookVersionRead]:
        versions = await self._repo.list_versions(ctx.workspace_id, playbook_id, locale)
        if versions is None:
            raise _not_found()
        return versions

    async def get_version(
        self, ctx: WorkspaceContext, playbook_id: UUID, version: int, locale: str = DEFAULT_LOCALE
    ) -> PlaybookVersionRead:
        found = await self._repo.fetch_version(ctx.workspace_id, playbook_id, version, locale)
        if found is None:
            raise _not_found()
        return found

    async def restore(
        self,
        ctx: WorkspaceContext,
        playbook_id: UUID,
        source_version: int,
        locale: str = DEFAULT_LOCALE,
    ) -> PlaybookRead:
        """Stellt den Snapshot `source_version` als neue Draft wieder her (§3.1).

        Body-Pills werden hier bewusst NICHT gesynct (Track-A-Grenze: Pill-Logik
        bleibt unberuehrt) — der naechste Save/Auto-Save zieht Composition-/
        Resource-Links wieder aus dem Body nach.
        """
        require_role(ctx, WorkspaceRole.editor)
        snapshot = await self._repo.fetch_version(
            ctx.workspace_id, playbook_id, source_version, locale
        )
        if snapshot is None:
            raise _not_found()
        outcome = await self._repo.restore_version(
            ctx.workspace_id, ctx.user_id, playbook_id, snapshot.content, locale
        )
        if outcome.conflict == "draft_exists":
            raise _draft_conflict()
        if outcome.playbook is None:
            raise _not_found()
        return outcome.playbook

    async def diff(
        self,
        ctx: WorkspaceContext,
        playbook_id: UUID,
        version: int,
        against: str,
        locale: str = DEFAULT_LOCALE,
    ) -> VersionDiff:
        """Strukturierter Feld-/Block-Diff der Version `version` gegen `against`."""
        target = await self._repo.fetch_version(ctx.workspace_id, playbook_id, version, locale)
        if target is None:
            raise _not_found()
        versions = await self._repo.list_versions(ctx.workspace_id, playbook_id, locale)
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
        self, against: str, versions: list[PlaybookVersionRead]
    ) -> tuple[int | None, PlaybookContent | None]:
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

    async def list_tags(self, ctx: WorkspaceContext, locale: str = DEFAULT_LOCALE) -> list[str]:
        """DISTINCT-Tags des Workspaces — Datenquelle fuer den Tag-Picker."""
        return await self._repo.list_distinct_tags(ctx.workspace_id, locale)

    async def list_triggers(self, ctx: WorkspaceContext) -> list[TriggerOverview]:
        """Welle 5: Discovery-Liste aller Trigger im Workspace mit Playbook-Verweis.

        Quelle fuer MCP-Tool `list_triggers` und Frontend-Hinweise.
        """
        return await self._repo.list_triggers_with_playbooks(ctx.workspace_id)

    async def delete(self, ctx: WorkspaceContext, playbook_id: UUID) -> None:
        """Hard-Delete des Playbooks (ADR-0032).

        Editor-Gate. Blockiert mit 409, solange Personas das Playbook verlinken
        oder Eltern-Composites es einbetten (der 409-Body listet beide Quellen).
        404, wenn das Playbook nicht (mehr) existiert. Die FK-Kaskaden raeumen
        Versionen sowie ausgehende Resource-Links/Composition-Kanten beim DELETE
        selbst ab.
        """
        require_role(ctx, WorkspaceRole.editor)
        playbook = await self._repo.fetch(ctx.workspace_id, playbook_id)
        if playbook is None:
            raise _not_found()
        if self._usage_repo is None:  # pragma: no cover - im Prod immer gesetzt
            raise RuntimeError("PlaybookService.delete benoetigt ein UsageRepository.")
        personas = await self._usage_repo.list_playbook_usages(ctx.workspace_id, playbook_id)
        composites = await self._usage_repo.list_playbook_parent_composites(
            ctx.workspace_id, playbook_id
        )
        if personas or composites:
            raise _delete_blocked(personas, composites)
        deleted = await self._repo.delete(ctx.workspace_id, playbook_id)
        if not deleted:
            raise _not_found()
