"""Persistenz fuer das SystemPromptTemplate-Aggregat.

Versionierung ueber eine History-Tabelle (ADR-0004); Aufbau und Verhalten
spiegeln `PersonaRepository`. Mandantenschluessel ist `workspace_id`
(siehe Migration 0022); `owner_id` bleibt Audit-Spalte.

Phase 3 Runde 3: Template-Reads filtern KEIN active_only mehr nach
`is_api_token` — Templates werden nur ueber den Render-Endpoint vom
API-Token-Pfad konsumiert und der Render-Service waehlt selbst die Active-
Version. Die Default-Such- und List-Reads liefern daher immer die aktuelle
Version (analog zur Persona-/Playbook-`active_only`-Logik wuerde sonst der
Render-Endpoint nichts mehr finden, solange das Template noch im Draft ist).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Protocol
from uuid import UUID

import asyncpg

from who2be_models import (
    SystemPromptTemplateContent,
    SystemPromptTemplateRead,
    SystemPromptTemplateVersionRead,
    VersionStatus,
)

# Identitaets-Zeile + Inhalt der aktuellen Version (analog Persona).
# Track B (Nur-BlockNote): `body_format` ist entfallen — der Body ist immer
# BlockNote-JSON.
_SELECT_CURRENT = """
    SELECT t.id, t.workspace_id, t.owner_id, t.name, t.slug,
           t.is_managed, t.current_version,
           t.created_at, t.updated_at, tv.content, tv.locale,
           tv.status AS current_status,
           EXISTS (
               SELECT 1 FROM system_prompt_template_version dv
               WHERE dv.template_id = t.id AND dv.status = 'draft'
           ) AS has_pending_draft
    FROM system_prompt_template t
    JOIN system_prompt_template_version tv
      ON tv.template_id = t.id AND tv.version = t.current_version
"""


@dataclass(frozen=True)
class SystemPromptTemplateUpdateOutcome:
    """Ergebnis eines `update`-Aufrufs (analog `PersonaUpdateOutcome`)."""

    template: SystemPromptTemplateRead | None
    conflict: Literal["draft_exists"] | None = None


class SystemPromptTemplateRepository(Protocol):
    """Service-seitige Abstraktion."""

    async def insert(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        name: str,
        slug: str,
        content: SystemPromptTemplateContent,
    ) -> SystemPromptTemplateRead: ...

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        limit: int,
        after: tuple[datetime, UUID] | None,
    ) -> list[SystemPromptTemplateRead]: ...

    async def fetch(
        self, workspace_id: UUID, template_id: UUID
    ) -> SystemPromptTemplateRead | None: ...

    async def fetch_active_content(
        self, workspace_id: UUID, template_id: UUID
    ) -> SystemPromptTemplateContent | None: ...

    async def update(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        template_id: UUID,
        name: str | None,
        content: SystemPromptTemplateContent,
    ) -> SystemPromptTemplateUpdateOutcome: ...

    async def restore_version(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        template_id: UUID,
        content: SystemPromptTemplateContent,
    ) -> SystemPromptTemplateUpdateOutcome: ...

    async def list_versions(
        self, workspace_id: UUID, template_id: UUID
    ) -> list[SystemPromptTemplateVersionRead] | None: ...

    async def fetch_version(
        self, workspace_id: UUID, template_id: UUID, version: int
    ) -> SystemPromptTemplateVersionRead | None: ...

    async def is_managed(self, workspace_id: UUID, template_id: UUID) -> bool: ...


def _row_to_read(row: dict[str, Any]) -> SystemPromptTemplateRead:
    """Wandelt eine SELECT-Row in ein Read-Modell — `content` als jsonb-dict."""
    return SystemPromptTemplateRead.model_validate(row)


class PgSystemPromptTemplateRepository:
    """asyncpg-Implementierung."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def is_managed(self, workspace_id: UUID, template_id: UUID) -> bool:
        val = await self._pool.fetchval(
            "SELECT is_managed FROM system_prompt_template WHERE id = $1 AND workspace_id = $2",
            template_id,
            workspace_id,
        )
        return bool(val)

    async def insert(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        name: str,
        slug: str,
        content: SystemPromptTemplateContent,
    ) -> SystemPromptTemplateRead:
        content_json = content.model_dump(mode="json")
        async with self._pool.acquire() as conn, conn.transaction():
            template = await conn.fetchrow(
                "INSERT INTO system_prompt_template "
                "(workspace_id, owner_id, name, slug) "
                "VALUES ($1, $2, $3, $4) "
                "RETURNING id, workspace_id, owner_id, name, slug, "
                "current_version, created_at, updated_at",
                workspace_id,
                owner_id,
                name,
                slug,
            )
            await conn.execute(
                "INSERT INTO system_prompt_template_version "
                "(template_id, version, content, status, created_by) "
                "VALUES ($1, $2, $3, $4, $5)",
                template["id"],
                template["current_version"],
                content_json,
                VersionStatus.draft.value,
                owner_id,
            )
        return SystemPromptTemplateRead.model_validate(
            {
                **dict(template),
                "content": content_json,
                "current_status": VersionStatus.draft,
                "has_pending_draft": True,
            }
        )

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        limit: int,
        after: tuple[datetime, UUID] | None,
    ) -> list[SystemPromptTemplateRead]:
        if after is None:
            rows = await self._pool.fetch(
                f"{_SELECT_CURRENT} WHERE t.workspace_id = $1 "
                "ORDER BY t.created_at DESC, t.id DESC LIMIT $2",
                workspace_id,
                limit,
            )
        else:
            rows = await self._pool.fetch(
                f"{_SELECT_CURRENT} WHERE t.workspace_id = $1 "
                "AND (t.created_at, t.id) < ($2, $3) "
                "ORDER BY t.created_at DESC, t.id DESC LIMIT $4",
                workspace_id,
                after[0],
                after[1],
                limit,
            )
        return [_row_to_read(dict(row)) for row in rows]

    async def fetch(self, workspace_id: UUID, template_id: UUID) -> SystemPromptTemplateRead | None:
        row = await self._pool.fetchrow(
            f"{_SELECT_CURRENT} WHERE t.id = $1 AND t.workspace_id = $2",
            template_id,
            workspace_id,
        )
        return _row_to_read(dict(row)) if row is not None else None

    async def fetch_active_content(
        self, workspace_id: UUID, template_id: UUID
    ) -> SystemPromptTemplateContent | None:
        """Liefert den Inhalt der Active-Version (oder None, falls keine).

        Wird vom Render-Service genutzt: rendere nur, wenn das Template eine
        publizierte Version hat — ungeprueftes Draft-Material soll nicht aus
        Versehen in einen externen LLM-Chat kopiert werden.
        """
        row = await self._pool.fetchrow(
            "SELECT tv.content FROM system_prompt_template_version tv "
            "JOIN system_prompt_template t ON t.id = tv.template_id "
            "WHERE t.id = $1 AND t.workspace_id = $2 AND tv.status = 'active'",
            template_id,
            workspace_id,
        )
        if row is None:
            return None
        return SystemPromptTemplateContent.model_validate(row["content"])

    async def update(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        template_id: UUID,
        name: str | None,
        content: SystemPromptTemplateContent,
    ) -> SystemPromptTemplateUpdateOutcome:
        content_json = content.model_dump(mode="json")
        async with self._pool.acquire() as conn, conn.transaction():
            current = await conn.fetchrow(
                "SELECT t.current_version, tv.status "
                "FROM system_prompt_template t "
                "JOIN system_prompt_template_version tv "
                "  ON tv.template_id = t.id AND tv.version = t.current_version "
                "WHERE t.id = $1 AND t.workspace_id = $2 FOR UPDATE OF t",
                template_id,
                workspace_id,
            )
            if current is None:
                return SystemPromptTemplateUpdateOutcome(template=None)
            existing_draft = await conn.fetchval(
                "SELECT 1 FROM system_prompt_template_version "
                "WHERE template_id = $1 AND status = 'draft'",
                template_id,
            )
            if existing_draft is not None:
                return SystemPromptTemplateUpdateOutcome(template=None, conflict="draft_exists")
            next_version = current["current_version"] + 1
            new_status: VersionStatus
            if current["status"] == VersionStatus.active.value:
                new_status = VersionStatus.draft
            else:
                new_status = VersionStatus.inactive
            template = await conn.fetchrow(
                "UPDATE system_prompt_template "
                "SET current_version = $1, name = COALESCE($2, name), "
                "    updated_at = now() "
                "WHERE id = $3 "
                "RETURNING id, workspace_id, owner_id, name, slug, "
                "current_version, created_at, updated_at",
                next_version,
                name,
                template_id,
            )
            await conn.execute(
                "INSERT INTO system_prompt_template_version "
                "(template_id, version, content, status, created_by) "
                "VALUES ($1, $2, $3, $4, $5)",
                template_id,
                next_version,
                content_json,
                new_status.value,
                owner_id,
            )
        return SystemPromptTemplateUpdateOutcome(
            template=SystemPromptTemplateRead.model_validate(
                {
                    **dict(template),
                    "content": content_json,
                    "current_status": new_status,
                    "has_pending_draft": new_status == VersionStatus.draft,
                }
            )
        )

    async def restore_version(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        template_id: UUID,
        content: SystemPromptTemplateContent,
    ) -> SystemPromptTemplateUpdateOutcome:
        """Schreibt `content` (Snapshot) als neue Draft-Version (Track A §3.1).

        Non-destruktiv: frische Draft v(n+1), kein Pointer-Reset. 409
        (`draft_exists`) bei bereits offenem Draft. Name und Slug bleiben
        unveraendert.
        """
        content_json = content.model_dump(mode="json")
        async with self._pool.acquire() as conn, conn.transaction():
            current = await conn.fetchrow(
                "SELECT current_version FROM system_prompt_template "
                "WHERE id = $1 AND workspace_id = $2 FOR UPDATE",
                template_id,
                workspace_id,
            )
            if current is None:
                return SystemPromptTemplateUpdateOutcome(template=None)
            existing_draft = await conn.fetchval(
                "SELECT 1 FROM system_prompt_template_version "
                "WHERE template_id = $1 AND status = 'draft'",
                template_id,
            )
            if existing_draft is not None:
                return SystemPromptTemplateUpdateOutcome(template=None, conflict="draft_exists")
            next_version = current["current_version"] + 1
            template = await conn.fetchrow(
                "UPDATE system_prompt_template "
                "SET current_version = $1, updated_at = now() "
                "WHERE id = $2 "
                "RETURNING id, workspace_id, owner_id, name, slug, "
                "current_version, created_at, updated_at",
                next_version,
                template_id,
            )
            await conn.execute(
                "INSERT INTO system_prompt_template_version "
                "(template_id, version, content, status, created_by) "
                "VALUES ($1, $2, $3, $4, $5)",
                template_id,
                next_version,
                content_json,
                VersionStatus.draft.value,
                owner_id,
            )
        return SystemPromptTemplateUpdateOutcome(
            template=SystemPromptTemplateRead.model_validate(
                {
                    **dict(template),
                    "content": content_json,
                    "current_status": VersionStatus.draft,
                    "has_pending_draft": True,
                }
            )
        )

    async def list_versions(
        self, workspace_id: UUID, template_id: UUID
    ) -> list[SystemPromptTemplateVersionRead] | None:
        owned = await self._pool.fetchval(
            "SELECT 1 FROM system_prompt_template WHERE id = $1 AND workspace_id = $2",
            template_id,
            workspace_id,
        )
        if owned is None:
            return None
        rows = await self._pool.fetch(
            "SELECT version, status, locale, content, created_by, created_at "
            "FROM system_prompt_template_version WHERE template_id = $1 "
            "ORDER BY version DESC",
            template_id,
        )
        return [SystemPromptTemplateVersionRead.model_validate(dict(row)) for row in rows]

    async def fetch_version(
        self, workspace_id: UUID, template_id: UUID, version: int
    ) -> SystemPromptTemplateVersionRead | None:
        row = await self._pool.fetchrow(
            "SELECT tv.version, tv.status, tv.locale, tv.content, tv.created_by, tv.created_at "
            "FROM system_prompt_template_version tv "
            "JOIN system_prompt_template t ON t.id = tv.template_id "
            "WHERE t.id = $1 AND t.workspace_id = $2 AND tv.version = $3",
            template_id,
            workspace_id,
            version,
        )
        return (
            SystemPromptTemplateVersionRead.model_validate(dict(row)) if row is not None else None
        )
