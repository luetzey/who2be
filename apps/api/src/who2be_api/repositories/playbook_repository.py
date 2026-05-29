"""Persistenz fuer das Playbook-Aggregat (`playbook` + `playbook_version`).

Versionierung ueber eine History-Tabelle (ADR-0004). `type`, `tags` und
`triggers` werden aus dem Versions-Inhalt auf die `playbook`-Zeile
denormalisiert, damit das Listing ohne Join filtern kann (§3).

Phase 2.1a-2: Filter laufen ueber `workspace_id` statt `owner_id`. `owner_id`
bleibt als Audit-Spalte (`created_by`) und wird beim INSERT mitgeschrieben.

Phase 2.1b: Status-Felder (`current_status`, `has_pending_draft`) im SELECT;
`update` erzwingt Draft-on-Edit bei `active`-Current; `active_only=True`
filtert auf Active-Versionen — MCP-Pfad (Plan §2.1.C/D).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

import asyncpg

from who2be_models import (
    PlaybookContent,
    PlaybookRead,
    PlaybookVersionRead,
    VersionStatus,
)

_SELECT_CURRENT = """
    SELECT p.id, p.workspace_id, p.owner_id, p.name, p.current_version,
           p.type, p.tags, p.triggers, p.created_at, p.updated_at, pv.content,
           pv.status AS current_status,
           EXISTS (
               SELECT 1 FROM playbook_version dv
               WHERE dv.playbook_id = p.id AND dv.status = 'draft'
           ) AS has_pending_draft
    FROM playbook p
    JOIN playbook_version pv
      ON pv.playbook_id = p.id AND pv.version = p.current_version
"""

_SELECT_ACTIVE = """
    SELECT p.id, p.workspace_id, p.owner_id, p.name,
           pv.version AS current_version,
           p.type, p.tags, p.triggers, p.created_at, p.updated_at, pv.content,
           pv.status AS current_status,
           EXISTS (
               SELECT 1 FROM playbook_version dv
               WHERE dv.playbook_id = p.id AND dv.status = 'draft'
           ) AS has_pending_draft
    FROM playbook p
    JOIN playbook_version pv
      ON pv.playbook_id = p.id AND pv.status = 'active'
"""


def _escape_like(value: str) -> str:
    """Maskiert LIKE-Sonderzeichen, damit der Filter reiner Teilstring bleibt."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@dataclass(frozen=True)
class PlaybookUpdateOutcome:
    """Ergebnis eines `update`-Aufrufs (analog `PersonaUpdateOutcome`)."""

    playbook: PlaybookRead | None
    conflict: Literal["draft_exists"] | None = None


class PlaybookRepository(Protocol):
    """Service-seitige Abstraktion fuer den Playbook-Zugriff."""

    async def insert(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        name: str,
        content: PlaybookContent,
    ) -> PlaybookRead: ...

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        tag: str | None,
        trigger: str | None,
        limit: int,
        after: tuple[datetime, UUID] | None,
        active_only: bool = False,
    ) -> list[PlaybookRead]: ...

    async def fetch(
        self,
        workspace_id: UUID,
        playbook_id: UUID,
        active_only: bool = False,
    ) -> PlaybookRead | None: ...

    async def update(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        playbook_id: UUID,
        name: str | None,
        content: PlaybookContent,
    ) -> PlaybookUpdateOutcome: ...

    async def list_versions(
        self, workspace_id: UUID, playbook_id: UUID
    ) -> list[PlaybookVersionRead] | None: ...

    async def fetch_version(
        self, workspace_id: UUID, playbook_id: UUID, version: int
    ) -> PlaybookVersionRead | None: ...


class PgPlaybookRepository:
    """asyncpg-Implementierung von `PlaybookRepository`."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def insert(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        name: str,
        content: PlaybookContent,
    ) -> PlaybookRead:
        content_json = content.model_dump(mode="json")
        async with self._pool.acquire() as conn, conn.transaction():
            playbook = await conn.fetchrow(
                "INSERT INTO playbook (workspace_id, owner_id, name, type, tags, triggers) "
                "VALUES ($1, $2, $3, $4, $5, $6) "
                "RETURNING id, workspace_id, owner_id, name, current_version, type, tags, "
                "triggers, created_at, updated_at",
                workspace_id,
                owner_id,
                name,
                content.type,
                content.tags,
                content.triggers,
            )
            await conn.execute(
                "INSERT INTO playbook_version "
                "(playbook_id, version, content, status, created_by) "
                "VALUES ($1, $2, $3, $4, $5)",
                playbook["id"],
                playbook["current_version"],
                content_json,
                VersionStatus.draft.value,
                owner_id,
            )
        # Neue v1 startet als Draft (Phase 3-0, siehe Persona-Pendant fuer
        # Begruendung).
        return PlaybookRead.model_validate(
            {
                **dict(playbook),
                "content": content_json,
                "current_status": VersionStatus.draft,
                "has_pending_draft": True,
            }
        )

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        tag: str | None,
        trigger: str | None,
        limit: int,
        after: tuple[datetime, UUID] | None,
        active_only: bool = False,
    ) -> list[PlaybookRead]:
        select = _SELECT_ACTIVE if active_only else _SELECT_CURRENT
        trigger_pattern = _escape_like(trigger) if trigger is not None else None
        # Tag/Trigger-Filter und Keyset-Pagination teilen sich denselben
        # WHERE-Block; der Cursor-Pfad haengt einen weiteren Term an.
        if after is None:
            rows = await self._pool.fetch(
                f"{select} "
                "WHERE p.workspace_id = $1 "
                "AND ($2::text IS NULL OR $2 = ANY(p.tags)) "
                "AND ($3::text IS NULL OR "
                "     p.triggers ILIKE '%' || $3 || '%' ESCAPE '\\') "
                "ORDER BY p.created_at DESC, p.id DESC LIMIT $4",
                workspace_id,
                tag,
                trigger_pattern,
                limit,
            )
        else:
            rows = await self._pool.fetch(
                f"{select} "
                "WHERE p.workspace_id = $1 "
                "AND ($2::text IS NULL OR $2 = ANY(p.tags)) "
                "AND ($3::text IS NULL OR "
                "     p.triggers ILIKE '%' || $3 || '%' ESCAPE '\\') "
                "AND (p.created_at, p.id) < ($4, $5) "
                "ORDER BY p.created_at DESC, p.id DESC LIMIT $6",
                workspace_id,
                tag,
                trigger_pattern,
                after[0],
                after[1],
                limit,
            )
        return [PlaybookRead.model_validate(dict(row)) for row in rows]

    async def fetch(
        self,
        workspace_id: UUID,
        playbook_id: UUID,
        active_only: bool = False,
    ) -> PlaybookRead | None:
        select = _SELECT_ACTIVE if active_only else _SELECT_CURRENT
        row = await self._pool.fetchrow(
            f"{select} WHERE p.id = $1 AND p.workspace_id = $2",
            playbook_id,
            workspace_id,
        )
        return PlaybookRead.model_validate(dict(row)) if row is not None else None

    async def update(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        playbook_id: UUID,
        name: str | None,
        content: PlaybookContent,
    ) -> PlaybookUpdateOutcome:
        content_json = content.model_dump(mode="json")
        async with self._pool.acquire() as conn, conn.transaction():
            current = await conn.fetchrow(
                "SELECT p.current_version, pv.status "
                "FROM playbook p "
                "JOIN playbook_version pv "
                "  ON pv.playbook_id = p.id AND pv.version = p.current_version "
                "WHERE p.id = $1 AND p.workspace_id = $2 FOR UPDATE OF p",
                playbook_id,
                workspace_id,
            )
            if current is None:
                return PlaybookUpdateOutcome(playbook=None)
            existing_draft = await conn.fetchval(
                "SELECT 1 FROM playbook_version "
                "WHERE playbook_id = $1 AND status = 'draft'",
                playbook_id,
            )
            if existing_draft is not None:
                return PlaybookUpdateOutcome(playbook=None, conflict="draft_exists")
            next_version = current["current_version"] + 1
            new_status: VersionStatus
            if current["status"] == VersionStatus.active.value:
                new_status = VersionStatus.draft
            else:
                new_status = VersionStatus.inactive
            playbook = await conn.fetchrow(
                "UPDATE playbook "
                "SET current_version = $1, name = COALESCE($2, name), "
                "type = $3, tags = $4, triggers = $5, updated_at = now() "
                "WHERE id = $6 "
                "RETURNING id, workspace_id, owner_id, name, current_version, type, tags, "
                "triggers, created_at, updated_at",
                next_version,
                name,
                content.type,
                content.tags,
                content.triggers,
                playbook_id,
            )
            await conn.execute(
                "INSERT INTO playbook_version "
                "(playbook_id, version, content, status, created_by) "
                "VALUES ($1, $2, $3, $4, $5)",
                playbook_id,
                next_version,
                content_json,
                new_status.value,
                owner_id,
            )
        return PlaybookUpdateOutcome(
            playbook=PlaybookRead.model_validate(
                {
                    **dict(playbook),
                    "content": content_json,
                    "current_status": new_status,
                    "has_pending_draft": new_status == VersionStatus.draft,
                }
            )
        )

    async def list_versions(
        self, workspace_id: UUID, playbook_id: UUID
    ) -> list[PlaybookVersionRead] | None:
        owned = await self._pool.fetchval(
            "SELECT 1 FROM playbook WHERE id = $1 AND workspace_id = $2",
            playbook_id,
            workspace_id,
        )
        if owned is None:
            return None
        rows = await self._pool.fetch(
            "SELECT version, status, content, created_by, created_at "
            "FROM playbook_version WHERE playbook_id = $1 ORDER BY version DESC",
            playbook_id,
        )
        return [PlaybookVersionRead.model_validate(dict(row)) for row in rows]

    async def fetch_version(
        self, workspace_id: UUID, playbook_id: UUID, version: int
    ) -> PlaybookVersionRead | None:
        row = await self._pool.fetchrow(
            "SELECT pv.version, pv.status, pv.content, pv.created_by, pv.created_at "
            "FROM playbook_version pv "
            "JOIN playbook p ON p.id = pv.playbook_id "
            "WHERE p.id = $1 AND p.workspace_id = $2 AND pv.version = $3",
            playbook_id,
            workspace_id,
            version,
        )
        return PlaybookVersionRead.model_validate(dict(row)) if row is not None else None
