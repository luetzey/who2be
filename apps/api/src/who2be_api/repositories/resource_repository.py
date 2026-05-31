"""Persistenz fuer das Resource-Aggregat (`resource` + `resource_version`).

Versionierung ueber eine History-Tabelle (ADR-0004), Status pro Version
(ADR-0020), Workspace-Isolation ueber `workspace_id` (ADR-0019). Aufbau
identisch zum Playbook-Repository.

Tag-Filter (E3): Resources haben keine denormalisierte Tag-Spalte; der Filter
laueft ueber `resource_version.content` (jsonb-In-Query) mit dem Ausdruck
`$tag = ANY(SELECT jsonb_array_elements_text(rv.content->'tags'))`.
Kein GIN-Index — ausreichend fuer initiale Last (laut Plan Out-of-Scope).

`active_only=True` liefert die Active-Version statt der Current-Version
(MCP-Pfad). `update` erzwingt Draft-on-Edit bei `active`-Current.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

import asyncpg

from who2be_models import ResourceContent, ResourceRead, ResourceVersionRead, VersionStatus

_SELECT_CURRENT = """
    SELECT r.id, r.workspace_id, r.owner_id, r.name, r.current_version,
           r.created_at, r.updated_at, rv.content,
           rv.status AS current_status,
           EXISTS (
               SELECT 1 FROM resource_version dv
               WHERE dv.resource_id = r.id AND dv.status = 'draft'
           ) AS has_pending_draft
    FROM resource r
    JOIN resource_version rv
      ON rv.resource_id = r.id AND rv.version = r.current_version
"""

_SELECT_ACTIVE = """
    SELECT r.id, r.workspace_id, r.owner_id, r.name,
           rv.version AS current_version,
           r.created_at, r.updated_at, rv.content,
           rv.status AS current_status,
           EXISTS (
               SELECT 1 FROM resource_version dv
               WHERE dv.resource_id = r.id AND dv.status = 'draft'
           ) AS has_pending_draft
    FROM resource r
    JOIN resource_version rv
      ON rv.resource_id = r.id AND rv.status = 'active'
"""


@dataclass(frozen=True)
class ResourceUpdateOutcome:
    """Ergebnis eines `update`- oder `upsert_draft`-Aufrufs (analog Persona)."""

    resource: ResourceRead | None
    conflict: Literal["draft_exists", "review_pending"] | None = None


class ResourceRepository(Protocol):
    """Service-seitige Abstraktion fuer den Resource-Zugriff."""

    async def insert(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        name: str,
        content: ResourceContent,
    ) -> ResourceRead: ...

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        tag: str | None,
        limit: int,
        after: tuple[datetime, UUID] | None,
        active_only: bool = False,
    ) -> list[ResourceRead]: ...

    async def fetch(
        self,
        workspace_id: UUID,
        resource_id: UUID,
        active_only: bool = False,
    ) -> ResourceRead | None: ...

    async def update(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        resource_id: UUID,
        name: str | None,
        content: ResourceContent,
    ) -> ResourceUpdateOutcome: ...

    async def upsert_draft(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        resource_id: UUID,
        name: str | None,
        content: ResourceContent,
    ) -> ResourceUpdateOutcome: ...

    async def list_versions(
        self, workspace_id: UUID, resource_id: UUID
    ) -> list[ResourceVersionRead] | None: ...

    async def fetch_version(
        self, workspace_id: UUID, resource_id: UUID, version: int
    ) -> ResourceVersionRead | None: ...


class PgResourceRepository:
    """asyncpg-Implementierung von `ResourceRepository`."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def insert(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        name: str,
        content: ResourceContent,
    ) -> ResourceRead:
        content_json = content.model_dump(mode="json")
        async with self._pool.acquire() as conn, conn.transaction():
            resource = await conn.fetchrow(
                "INSERT INTO resource (workspace_id, owner_id, name) "
                "VALUES ($1, $2, $3) "
                "RETURNING id, workspace_id, owner_id, name, current_version, "
                "created_at, updated_at",
                workspace_id,
                owner_id,
                name,
            )
            await conn.execute(
                "INSERT INTO resource_version "
                "(resource_id, version, content, status, created_by) "
                "VALUES ($1, $2, $3, $4, $5)",
                resource["id"],
                resource["current_version"],
                content_json,
                VersionStatus.draft.value,
                owner_id,
            )
        # Neue v1 startet als Draft (Phase 3-0, siehe Persona-Pendant fuer
        # Begruendung).
        return ResourceRead.model_validate(
            {
                **dict(resource),
                "content": content_json,
                "current_status": VersionStatus.draft,
                "has_pending_draft": True,
            }
        )

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        tag: str | None,
        limit: int,
        after: tuple[datetime, UUID] | None,
        active_only: bool = False,
    ) -> list[ResourceRead]:
        # Tag-Filter via jsonb-In-Query: kein denormalisierter Tag-Array auf
        # der resource-Zeile (laut Plan E3 Out-of-Scope); stattdessen direkt
        # aus content->tags im resource_version-Row. Bedingung:
        # `$tag = ANY(SELECT jsonb_array_elements_text(rv.content->'tags'))`.
        select = _SELECT_ACTIVE if active_only else _SELECT_CURRENT
        if after is None:
            rows = await self._pool.fetch(
                f"{select} WHERE r.workspace_id = $1 "
                "AND ($2::text IS NULL OR $2 = ANY("
                "    SELECT jsonb_array_elements_text(rv.content->'tags'))) "
                "ORDER BY r.created_at DESC, r.id DESC LIMIT $3",
                workspace_id,
                tag,
                limit,
            )
        else:
            rows = await self._pool.fetch(
                f"{select} WHERE r.workspace_id = $1 "
                "AND ($2::text IS NULL OR $2 = ANY("
                "    SELECT jsonb_array_elements_text(rv.content->'tags'))) "
                "AND (r.created_at, r.id) < ($3, $4) "
                "ORDER BY r.created_at DESC, r.id DESC LIMIT $5",
                workspace_id,
                tag,
                after[0],
                after[1],
                limit,
            )
        return [ResourceRead.model_validate(dict(row)) for row in rows]

    async def fetch(
        self,
        workspace_id: UUID,
        resource_id: UUID,
        active_only: bool = False,
    ) -> ResourceRead | None:
        select = _SELECT_ACTIVE if active_only else _SELECT_CURRENT
        row = await self._pool.fetchrow(
            f"{select} WHERE r.id = $1 AND r.workspace_id = $2",
            resource_id,
            workspace_id,
        )
        return ResourceRead.model_validate(dict(row)) if row is not None else None

    async def update(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        resource_id: UUID,
        name: str | None,
        content: ResourceContent,
    ) -> ResourceUpdateOutcome:
        content_json = content.model_dump(mode="json")
        async with self._pool.acquire() as conn, conn.transaction():
            current = await conn.fetchrow(
                "SELECT r.current_version, rv.status "
                "FROM resource r "
                "JOIN resource_version rv "
                "  ON rv.resource_id = r.id AND rv.version = r.current_version "
                "WHERE r.id = $1 AND r.workspace_id = $2 FOR UPDATE OF r",
                resource_id,
                workspace_id,
            )
            if current is None:
                return ResourceUpdateOutcome(resource=None)
            existing_draft = await conn.fetchval(
                "SELECT 1 FROM resource_version WHERE resource_id = $1 AND status = 'draft'",
                resource_id,
            )
            if existing_draft is not None:
                return ResourceUpdateOutcome(resource=None, conflict="draft_exists")
            next_version = current["current_version"] + 1
            new_status: VersionStatus
            if current["status"] == VersionStatus.active.value:
                new_status = VersionStatus.draft
            else:
                new_status = VersionStatus.inactive
            resource = await conn.fetchrow(
                "UPDATE resource "
                "SET current_version = $1, name = COALESCE($2, name), updated_at = now() "
                "WHERE id = $3 "
                "RETURNING id, workspace_id, owner_id, name, current_version, "
                "created_at, updated_at",
                next_version,
                name,
                resource_id,
            )
            await conn.execute(
                "INSERT INTO resource_version "
                "(resource_id, version, content, status, created_by) "
                "VALUES ($1, $2, $3, $4, $5)",
                resource_id,
                next_version,
                content_json,
                new_status.value,
                owner_id,
            )
        return ResourceUpdateOutcome(
            resource=ResourceRead.model_validate(
                {
                    **dict(resource),
                    "content": content_json,
                    "current_status": new_status,
                    "has_pending_draft": new_status == VersionStatus.draft,
                }
            )
        )

    async def upsert_draft(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        resource_id: UUID,
        name: str | None,
        content: ResourceContent,
    ) -> ResourceUpdateOutcome:
        """Auto-Save-Pfad fuer Resource (PATCH `.../draft`).

        Semantik wie `PgPersonaRepository.upsert_draft` — bestehender Draft
        wird in-place ueberschrieben, sonst entsteht eine neue Draft-Version.
        """
        content_json = content.model_dump(mode="json")
        async with self._pool.acquire() as conn, conn.transaction():
            current = await conn.fetchrow(
                "SELECT r.current_version, rv.status "
                "FROM resource r "
                "JOIN resource_version rv "
                "  ON rv.resource_id = r.id AND rv.version = r.current_version "
                "WHERE r.id = $1 AND r.workspace_id = $2 FOR UPDATE OF r",
                resource_id,
                workspace_id,
            )
            if current is None:
                return ResourceUpdateOutcome(resource=None)
            draft_version = await conn.fetchval(
                "SELECT version FROM resource_version WHERE resource_id = $1 AND status = 'draft'",
                resource_id,
            )
            if draft_version is not None:
                resource = await conn.fetchrow(
                    "UPDATE resource "
                    "SET name = COALESCE($1, name), updated_at = now() "
                    "WHERE id = $2 "
                    "RETURNING id, workspace_id, owner_id, name, current_version, "
                    "created_at, updated_at",
                    name,
                    resource_id,
                )
                await conn.execute(
                    "UPDATE resource_version SET content = $1, created_by = $2 "
                    "WHERE resource_id = $3 AND version = $4",
                    content_json,
                    owner_id,
                    resource_id,
                    draft_version,
                )
                return ResourceUpdateOutcome(
                    resource=ResourceRead.model_validate(
                        {
                            **dict(resource),
                            "content": content_json,
                            "current_status": VersionStatus.draft,
                            "has_pending_draft": True,
                        }
                    )
                )
            if current["status"] == VersionStatus.review.value:
                return ResourceUpdateOutcome(resource=None, conflict="review_pending")
            next_version = current["current_version"] + 1
            resource = await conn.fetchrow(
                "UPDATE resource "
                "SET current_version = $1, name = COALESCE($2, name), "
                "updated_at = now() "
                "WHERE id = $3 "
                "RETURNING id, workspace_id, owner_id, name, current_version, "
                "created_at, updated_at",
                next_version,
                name,
                resource_id,
            )
            await conn.execute(
                "INSERT INTO resource_version "
                "(resource_id, version, content, status, created_by) "
                "VALUES ($1, $2, $3, $4, $5)",
                resource_id,
                next_version,
                content_json,
                VersionStatus.draft.value,
                owner_id,
            )
        return ResourceUpdateOutcome(
            resource=ResourceRead.model_validate(
                {
                    **dict(resource),
                    "content": content_json,
                    "current_status": VersionStatus.draft,
                    "has_pending_draft": True,
                }
            )
        )

    async def list_versions(
        self, workspace_id: UUID, resource_id: UUID
    ) -> list[ResourceVersionRead] | None:
        owned = await self._pool.fetchval(
            "SELECT 1 FROM resource WHERE id = $1 AND workspace_id = $2",
            resource_id,
            workspace_id,
        )
        if owned is None:
            return None
        rows = await self._pool.fetch(
            "SELECT version, status, content, created_by, created_at "
            "FROM resource_version WHERE resource_id = $1 ORDER BY version DESC",
            resource_id,
        )
        return [ResourceVersionRead.model_validate(dict(row)) for row in rows]

    async def fetch_version(
        self, workspace_id: UUID, resource_id: UUID, version: int
    ) -> ResourceVersionRead | None:
        row = await self._pool.fetchrow(
            "SELECT rv.version, rv.status, rv.content, rv.created_by, rv.created_at "
            "FROM resource_version rv "
            "JOIN resource r ON r.id = rv.resource_id "
            "WHERE r.id = $1 AND r.workspace_id = $2 AND rv.version = $3",
            resource_id,
            workspace_id,
            version,
        )
        return ResourceVersionRead.model_validate(dict(row)) if row is not None else None
