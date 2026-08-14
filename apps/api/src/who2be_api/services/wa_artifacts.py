"""Geschaeftslogik fuer WorkArea-Artifacts (ADR-0047, WP4 — Spec A+E).

Schreibpfad-Gates (Security-Review 2026-08-13 H1, Muster
`resource_service.create`): IMMER zuerst `require_role(editor)` — die Rolle
ist auch bei agent-gebundenen Tokens am Token gepinnt —, danach
`require_capability(workarea_write)` + `require_write_rate` (fuer Menschen
No-Ops); beide zusaetzlich `ensure_area_access(write)` auf der Ziel-Area.
Reads filtern ueber
`readable_area_ids` IN der Repo-SQL — ein nicht lesbares Artifact ist von
einem nicht existierenden nicht unterscheidbar (404, kein Existenz-Leak).

Nebenlaeufigkeit (Entscheidung 3.3): `append` ist lockfrei (atomares
``content || $blocks, rev+1`` im Repo), `patch` optimistisch
(``WHERE rev = expected_rev`` → 409 `rev_conflict` mit aktueller rev im
detail). Jeder Content-Write synchronisiert die Passagen
(`wa_chunks.sync_artifact_chunks`) in DERSELBEN Transaktion; beim Delete
raeumt der FK ON DELETE CASCADE (0076) die Chunks ab.

ARC-3: kein SQL, keine HTTPException — nur `ApiGateError`, Repos und die
Helper aus `core/workarea_scope`. Transaktionssteuerung (`pool.acquire` +
`conn.transaction`) liegt bewusst hier (Muster `version_status`).
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import status

from who2be_api.core.errors import ApiGateError
from who2be_api.core.security import (
    WorkspaceContext,
    require_capability,
    require_role,
    require_write_rate,
)
from who2be_api.core.workarea_scope import (
    agent_not_found,
    artifact_not_found,
    ensure_area_access,
    readable_area_ids,
)
from who2be_api.repositories.wa_artifact_repository import WaArtifactRepository
from who2be_api.repositories.work_area_repository import WorkAreaRepository
from who2be_api.repositories.workspace_repository import WorkspaceRepository
from who2be_api.services.content_locale import resolve_content_locale
from who2be_api.services.wa_blocks import apply_patch, render_markdown, split_markdown
from who2be_api.services.wa_chunks import sync_artifact_chunks
from who2be_models import (
    AgentCapability,
    ArtifactAppend,
    ArtifactCreate,
    ArtifactMarkdown,
    ArtifactPatch,
    ArtifactRead,
    ArtifactType,
    DocBlock,
    WorkAreaGrantLevel,
    WorkspaceRole,
)
from who2be_models.workarea import INGEST_MAX_BLOCKS


def _anchor_unresolvable(anchor: str) -> ApiGateError:
    return ApiGateError(
        status=status.HTTP_422_UNPROCESSABLE_CONTENT,
        reason="anchor_unresolvable",
        actionable_by="agent",
        detail=(
            f"Der Anker '{anchor}' existiert in diesem Artifact nicht. "
            "Artifact erneut lesen — die Anker stehen als [#block_id] im Markdown."
        ),
    )


def _rev_conflict(expected_rev: int, current_rev: int) -> ApiGateError:
    return ApiGateError(
        status=status.HTTP_409_CONFLICT,
        reason="rev_conflict",
        actionable_by="agent",
        detail=(
            f"Veraltete Revision: expected_rev={expected_rev}, aktuelle rev={current_rev}. "
            "Artifact erneut lesen und den Patch auf die aktuelle rev aufsetzen."
        ),
    )


def _too_many_blocks() -> ApiGateError:
    """413 fuer einen Append ueber das kumulative Block-Limit (M7).

    Reason ist bewusst das bestehende `ingest_too_large`: es ist DERSELBE
    Block-Cap derselben Schutzfamilie (geteilte Konstante `INGEST_MAX_BLOCKS`,
    H3b), 413 ist der semantisch korrekte Status („Inhalt zu gross") und die
    Taxonomie bleibt geschlossen — ein neuer Reason fuer denselben Sachverhalt
    waere Vokabular ohne Not.
    """
    return ApiGateError(
        status=status.HTTP_413_CONTENT_TOO_LARGE,
        reason="ingest_too_large",
        actionable_by="agent",
        detail=(
            f"Der Append wuerde das Block-Limit von {INGEST_MAX_BLOCKS} Bloecken "
            "pro Artifact ueberschreiten — Inhalt kuerzen oder ein neues "
            "Artifact anlegen."
        ),
    )


class WaArtifactService:
    """Artifact-CRUD + Block-Operationen ueber den WorkArea-Repos."""

    def __init__(
        self,
        pool: asyncpg.Pool,
        artifact_repo: WaArtifactRepository,
        area_repo: WorkAreaRepository,
        workspace_repo: WorkspaceRepository | None = None,
    ) -> None:
        self._pool = pool
        self._artifacts = artifact_repo
        self._areas = area_repo
        self._workspaces = workspace_repo

    # ------------------------------------------------------------------ Gates

    def _require_write(self, ctx: WorkspaceContext) -> None:
        """Schreib-Gate (H1, Muster `resource_service.create`): IMMER zuerst
        `require_role(editor)` — die Rolle ist auch bei agent-gebundenen
        Tokens am Token gepinnt (ein viewer-Token schreibt nie) —, danach
        Capability + Rate (fuer Menschen/JWT No-Ops)."""
        require_role(ctx, WorkspaceRole.editor)
        require_capability(ctx, AgentCapability.workarea_write)
        require_write_rate(ctx)

    async def _require_writable_area(self, ctx: WorkspaceContext, area_id: UUID) -> None:
        await ensure_area_access(self._pool, ctx, area_id, WorkAreaGrantLevel.write)

    def _actor(self, ctx: WorkspaceContext) -> UUID:
        """Akteur-UUID fuer `updated_by`: der gebundene Agent, sonst der Mensch."""
        return ctx.agent_id if ctx.agent_id is not None else ctx.user_id

    async def _locale(self, ctx: WorkspaceContext) -> str:
        """Chunk-Sprache = Workspace-Content-Sprache (einfachster Bestandsweg,
        `resolve_content_locale` ohne expliziten Wunsch — Artifacts tragen
        kein eigenes locale-Feld)."""
        return await resolve_content_locale(self._workspaces, ctx.workspace_id, None)

    async def _readable(
        self, ctx: WorkspaceContext, artifact_id: UUID, *, include_blocks: bool
    ) -> ArtifactRead:
        """Artifact im Lese-Scope des Aufrufers — sonst 404 (kein Existenz-Leak)."""
        restrict = await readable_area_ids(self._pool, ctx)
        artifact = await self._artifacts.get(
            self._pool,
            ctx.workspace_id,
            artifact_id,
            restrict_area_ids=restrict,
            include_blocks=include_blocks,
        )
        if artifact is None:
            raise artifact_not_found()
        return artifact

    # ------------------------------------------------------------------ Writes

    async def create(
        self, ctx: WorkspaceContext, area_id: UUID | None, data: ArtifactCreate
    ) -> ArtifactRead:
        """Legt ein doc-Artifact an; `area_id=None` = private Area des Agenten.

        Der Router hat den Menschen-ohne-Area-Fall bereits mit 422 abgewiesen
        (Menschen haben keine private Area); hier verbleibt der defensive
        404-Pfad fuer einen parallel geloeschten Agenten.
        """
        self._require_write(ctx)
        if area_id is None:
            if ctx.agent_id is None:
                raise agent_not_found()
            private = await self._areas.get_or_create_private_area(ctx.workspace_id, ctx.agent_id)
            if private is None:
                raise agent_not_found()
            area_id = private.id
        await self._require_writable_area(ctx, area_id)

        blocks = split_markdown(data.content_md)
        locale = await self._locale(ctx)
        async with self._pool.acquire() as conn, conn.transaction():
            created = await self._artifacts.insert_doc(
                conn,
                ctx.workspace_id,
                area_id,
                title=data.title,
                occurred_at=data.occurred_at,
                occurred_precision=data.occurred_precision.value,
                sensitivity=data.sensitivity.value,
                source_system=data.source_system,
                source_url=data.source_url,
                fetched_at=data.fetched_at,
                blocks=blocks,
                updated_by=self._actor(ctx),
            )
            await sync_artifact_chunks(
                conn,
                workspace_id=ctx.workspace_id,
                artifact_id=created.id,
                area_id=area_id,
                blocks=blocks,
                locale=locale,
            )
        return created

    async def append(
        self, ctx: WorkspaceContext, artifact_id: UUID, data: ArtifactAppend
    ) -> ArtifactRead:
        """Lockfreies Anhaengen: beide nebenlaeufigen Appends gewinnen (rev+2)."""
        existing = await self._readable(ctx, artifact_id, include_blocks=True)
        self._require_write(ctx)
        await self._require_writable_area(ctx, existing.area_id)

        existing_ids = {b.block_id for b in existing.blocks or []}
        new_blocks = split_markdown(data.content_md, existing_ids)
        locale = await self._locale(ctx)
        async with self._pool.acquire() as conn, conn.transaction():
            updated = await self._artifacts.append_blocks(
                conn, ctx.workspace_id, artifact_id, new_blocks, self._actor(ctx)
            )
            if updated is None:
                # 0 Rows: entweder verschwunden/kein doc-Artifact (→ 404) oder
                # das SQL-Praedikat des kumulativen Block-Caps hat gegriffen
                # (M7 → 413) — Exists-Nachlese unterscheidet die Faelle.
                still_there = await self._artifacts.get(
                    conn,
                    ctx.workspace_id,
                    artifact_id,
                    restrict_area_ids=None,
                    include_blocks=False,
                )
                if still_there is None or still_there.type != ArtifactType.doc:
                    raise artifact_not_found()
                raise _too_many_blocks()
            await sync_artifact_chunks(
                conn,
                workspace_id=ctx.workspace_id,
                artifact_id=artifact_id,
                area_id=updated.area_id,
                blocks=updated.blocks or [],
                locale=locale,
            )
        return updated

    async def patch(
        self, ctx: WorkspaceContext, artifact_id: UUID, data: ArtifactPatch
    ) -> ArtifactRead:
        """Optimistisches Block-Edit (replace/insert_after/delete am Anker)."""
        existing = await self._readable(ctx, artifact_id, include_blocks=True)
        self._require_write(ctx)
        await self._require_writable_area(ctx, existing.area_id)
        if existing.rev != data.expected_rev:
            # Fast-Fail auf dem gelesenen Stand; das SQL-Praedikat
            # `WHERE rev = expected_rev` faengt das Rennen dazwischen.
            raise _rev_conflict(data.expected_rev, existing.rev)

        blocks = existing.blocks or []
        existing_ids = {b.block_id for b in blocks}
        replacement: list[DocBlock] = []
        if data.op != "delete":
            replacement = split_markdown(data.content_md or "", existing_ids)
        new_content = apply_patch(blocks, data.anchor, data.op, replacement)
        if new_content is None:
            raise _anchor_unresolvable(data.anchor)

        locale = await self._locale(ctx)
        async with self._pool.acquire() as conn, conn.transaction():
            updated, current_rev = await self._artifacts.patch_blocks(
                conn,
                ctx.workspace_id,
                artifact_id,
                data.expected_rev,
                new_content,
                self._actor(ctx),
            )
            if updated is None:
                if current_rev is None:
                    raise artifact_not_found()
                raise _rev_conflict(data.expected_rev, current_rev)
            await sync_artifact_chunks(
                conn,
                workspace_id=ctx.workspace_id,
                artifact_id=artifact_id,
                area_id=updated.area_id,
                blocks=updated.blocks or [],
                locale=locale,
            )
        return updated

    async def delete(self, ctx: WorkspaceContext, artifact_id: UUID) -> None:
        """Loescht Artifact + Passagen (Chunks via FK CASCADE, s. Modul-Kopf)."""
        existing = await self._readable(ctx, artifact_id, include_blocks=False)
        self._require_write(ctx)
        await self._require_writable_area(ctx, existing.area_id)
        async with self._pool.acquire() as conn, conn.transaction():
            if not await self._artifacts.delete(conn, ctx.workspace_id, artifact_id):
                raise artifact_not_found()

    # ------------------------------------------------------------------- Reads

    async def read(
        self, ctx: WorkspaceContext, artifact_id: UUID, anchor: str | None
    ) -> ArtifactMarkdown:
        """Markdown-Read mit ``[#block_id]``-Ankern; `anchor` liefert NUR den Block."""
        artifact = await self._readable(ctx, artifact_id, include_blocks=True)
        blocks = artifact.blocks or []
        if anchor is not None:
            block = next((b for b in blocks if b.block_id == anchor), None)
            if block is None:
                raise _anchor_unresolvable(anchor)
            blocks = [block]
        return ArtifactMarkdown(
            artifact_id=artifact.id,
            title=artifact.title,
            rev=artifact.rev,
            markdown=render_markdown(blocks, with_anchors=True),
        )

    async def list_for_area(self, ctx: WorkspaceContext, area_id: UUID) -> list[ArtifactRead]:
        """Artifacts einer Area (Metadaten); fehlender Read-Grant → 404."""
        await ensure_area_access(self._pool, ctx, area_id, WorkAreaGrantLevel.read)
        return await self._artifacts.list_for_area(self._pool, ctx.workspace_id, area_id)
