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
from who2be_api.services.placeholders import RenderContext, render_template_body
from who2be_api.services.playbook_body_pills import extract_pills
from who2be_api.services.playbook_composition_service import PlaybookCompositionService
from who2be_api.services.playbook_resource_link_service import PlaybookResourceLinkService
from who2be_models import (
    PlaybookCompositionLinkSet,
    PlaybookContent,
    PlaybookCreate,
    PlaybookRead,
    PlaybookUpdate,
    PlaybookVersionRead,
    ResourceLinkSet,
    TriggerOverview,
    WorkspaceRole,
    encode_cursor,
)


class PlaybookRenderResponse(BaseModel):
    """Antwort des Render-Endpoints: expandierter Body + offene Placeholder-Keys.

    Spiegelt den Agent-Render-Vertrag: `body_rendered` ist der Plain-Text-Output
    von `render_template_body`; bei `body_format='plain'` der rohe Body. `unresolved`
    listet deduplizierte, lexikografisch sortierte Miss-Keys.
    """

    body_rendered: str
    unresolved: list[str]


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


def _review_conflict() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            "Diese Version steht in der Review — Auto-Save ist deaktiviert. "
            "Lehne die Review erst ab, bevor du weiter editierst."
        ),
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
    ) -> None:
        self._repo = playbook_repo
        self._pool = pool
        self._composition_service = composition_service
        self._resource_link_service = resource_link_service

    async def create(self, ctx: WorkspaceContext, data: PlaybookCreate) -> PlaybookRead:
        require_role(ctx, WorkspaceRole.editor)
        playbook = await self._repo.insert(
            ctx.workspace_id, ctx.user_id, data.name, data.content
        )
        await self._sync_body_pills(ctx, playbook.id, data.content)
        return playbook

    async def render(
        self, ctx: WorkspaceContext, playbook_id: UUID
    ) -> PlaybookRenderResponse:
        """Expandiert den Playbook-Body durch den Placeholder-Renderer (B5).

        Bei `body_format != 'blocknote'` liefert `render_template_body` den rohen
        Body unveraendert zurueck (Z.61-62 im Renderer). MCP nutzt diesen Endpoint,
        da der MCP-Prozess keinen DB-Zugriff hat.
        """
        playbook = await self.get(ctx, playbook_id)
        render_ctx = RenderContext(
            workspace_id=ctx.workspace_id,
            persona_id=None,
            now=datetime.now(UTC),
        )
        async with self._pool.acquire() as conn:
            body_rendered, unresolved = await render_template_body(
                playbook.content.body,
                playbook.content.body_format,
                render_ctx,
                conn,
            )
        return PlaybookRenderResponse(body_rendered=body_rendered, unresolved=unresolved)

    async def _sync_body_pills(
        self, ctx: WorkspaceContext, playbook_id: UUID, content: PlaybookContent
    ) -> None:
        """Save-Sync „Body treibt" (B3): extrahiert Inline-Pills und synct sie.

        Laeuft NUR bei `body_format=='blocknote'`. 'plain'-Bodies bleiben komplett
        unangetastet (Composition-/Resource-Link-Tabellen werden nicht beruehrt).

        Delegiert an die Services (nicht die Repos), damit Dedup, Self-Ref-Filter,
        Zyklus-Guard und Heading-Anker-Validierung greifen. Ein Zyklus (→ 409) oder
        ungueltiger Block-Anker (→ 422) propagiert als HTTPException nach oben.
        """
        if content.body_format != "blocknote":
            return
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
        await self._sync_body_pills(ctx, outcome.playbook.id, data.content)
        return outcome.playbook

    async def update_draft(
        self, ctx: WorkspaceContext, playbook_id: UUID, data: PlaybookUpdate
    ) -> PlaybookRead:
        """Auto-Save-Pfad (PATCH `.../draft`) — upsertet die Draft-Version."""
        require_role(ctx, WorkspaceRole.editor)
        outcome = await self._repo.upsert_draft(
            ctx.workspace_id, ctx.user_id, playbook_id, data.name, data.content
        )
        if outcome.conflict == "review_pending":
            raise _review_conflict()
        if outcome.playbook is None:
            raise _not_found()
        await self._sync_body_pills(ctx, outcome.playbook.id, data.content)
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

    async def list_triggers(self, ctx: WorkspaceContext) -> list[TriggerOverview]:
        """Welle 5: Discovery-Liste aller Trigger im Workspace mit Playbook-Verweis.

        Quelle fuer MCP-Tool `list_triggers` und Frontend-Hinweise.
        """
        return await self._repo.list_triggers_with_playbooks(ctx.workspace_id)
