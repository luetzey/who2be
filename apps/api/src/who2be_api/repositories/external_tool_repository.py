"""Persistenz fuer das ExternalTool-Aggregat (`external_tool` + `external_tool_version`).

Der versionierte CRUD-Kern (insert/update/upsert_draft/restore/list_versions/
fetch_version/delete) lebt in `VersionedAggregateRepository` (Repo-Review STR-1) —
geteilt mit Persona/Playbook/Resource. Diese Klasse ist die duenne ExternalTool-
Subklasse: Tabellen-Config + typisierte Wrapper (`ExternalToolUpdateOutcome`) +
die zwei entity-spezifischen Lesepfade (`fetch`/`list_by_workspace`).

Anders als Resource hat ExternalTool (WP-1) weder Tag-Filter-Query noch
Read-Scoping (`restrict_ids`) noch List-Card-Pills — beides ist WP-3/WP-5-Scope
(Policy-Domain `external_tool`, Reverse-Lookups). `has_slug=True` mit
`slug_column="alias"` blendet die workspace-eindeutige `alias`-Spalte
(Migration 0065) ein — spiegelt Resources `slug`, nur unter anderem Namen
(Blueprint: „Alias liegt auf dem Aggregat wie Template-Slug").

Versionierung ueber History-Tabelle (ADR-0004), Status pro Version (ADR-0020),
Workspace-Isolation (ADR-0019). „Ein Element, eine Sprache" (ADR-0045):
`locale` liegt auf der `external_tool`-Identitaets-Zeile, Reads sind
locale-agnostisch, `list_by_workspace` filtert optional auf die Entity-Sprache.
`active_only=True` liefert die Active-Version statt der Current-Version.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

import asyncpg

from who2be_api.repositories.versioned_repository import (
    AggregateTables,
    VersionedAggregateRepository,
)
from who2be_models import (
    ExternalToolContent,
    ExternalToolRead,
    ExternalToolVersionRead,
)


@dataclass(frozen=True)
class ExternalToolUpdateOutcome:
    """Ergebnis eines `update`- oder `upsert_draft`-Aufrufs (analog Resource)."""

    tool: ExternalToolRead | None
    conflict: Literal["draft_exists", "review_pending"] | None = None


class ExternalToolRepository(Protocol):
    """Service-seitige Abstraktion fuer den ExternalTool-Zugriff."""

    async def insert(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        name: str,
        content: ExternalToolContent,
        locale: str,
        alias: str | None = None,
    ) -> ExternalToolRead: ...

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        limit: int,
        after: tuple[datetime, UUID] | None,
        active_only: bool = False,
        locale: str | None = None,
    ) -> list[ExternalToolRead]: ...

    async def fetch(
        self,
        workspace_id: UUID,
        tool_id: UUID,
        active_only: bool = False,
    ) -> ExternalToolRead | None: ...

    async def update(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        tool_id: UUID,
        name: str | None,
        content: ExternalToolContent,
        new_locale: str | None = None,
    ) -> ExternalToolUpdateOutcome: ...

    async def upsert_draft(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        tool_id: UUID,
        name: str | None,
        content: ExternalToolContent,
        new_locale: str | None = None,
    ) -> ExternalToolUpdateOutcome: ...

    async def restore_version(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        tool_id: UUID,
        content: ExternalToolContent,
    ) -> ExternalToolUpdateOutcome: ...

    async def list_versions(
        self, workspace_id: UUID, tool_id: UUID
    ) -> list[ExternalToolVersionRead] | None: ...

    async def fetch_version(
        self, workspace_id: UUID, tool_id: UUID, version: int
    ) -> ExternalToolVersionRead | None: ...

    async def delete(self, workspace_id: UUID, tool_id: UUID) -> bool: ...

    async def is_managed(self, workspace_id: UUID, entity_id: UUID) -> bool: ...


class PgExternalToolRepository(
    VersionedAggregateRepository[ExternalToolRead, ExternalToolVersionRead]
):
    """asyncpg-Implementierung von `ExternalToolRepository` auf dem generischen Kern."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        super().__init__(
            pool,
            AggregateTables(
                "external_tool",
                ExternalToolRead,
                ExternalToolVersionRead,
                has_slug=True,
                slug_column="alias",
            ),
        )

    # --- Generischer Kern, in die ExternalTool-Signaturen gewrappt -----------

    async def insert(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        name: str,
        content: ExternalToolContent,
        locale: str,
        alias: str | None = None,
    ) -> ExternalToolRead:
        return await self._insert(workspace_id, owner_id, name, content, locale, slug=alias)

    async def update(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        tool_id: UUID,
        name: str | None,
        content: ExternalToolContent,
        new_locale: str | None = None,
    ) -> ExternalToolUpdateOutcome:
        tool, conflict = await self._update(
            workspace_id, owner_id, tool_id, name, content, new_locale
        )
        return ExternalToolUpdateOutcome(tool=tool, conflict=conflict)

    async def upsert_draft(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        tool_id: UUID,
        name: str | None,
        content: ExternalToolContent,
        new_locale: str | None = None,
    ) -> ExternalToolUpdateOutcome:
        tool, conflict = await self._upsert_draft(
            workspace_id, owner_id, tool_id, name, content, new_locale
        )
        return ExternalToolUpdateOutcome(tool=tool, conflict=conflict)

    async def restore_version(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        tool_id: UUID,
        content: ExternalToolContent,
    ) -> ExternalToolUpdateOutcome:
        tool, conflict = await self._restore_version(workspace_id, owner_id, tool_id, content)
        return ExternalToolUpdateOutcome(tool=tool, conflict=conflict)

    async def list_versions(
        self, workspace_id: UUID, tool_id: UUID
    ) -> list[ExternalToolVersionRead] | None:
        return await self._list_versions(workspace_id, tool_id)

    async def fetch_version(
        self, workspace_id: UUID, tool_id: UUID, version: int
    ) -> ExternalToolVersionRead | None:
        return await self._fetch_version(workspace_id, tool_id, version)

    async def delete(self, workspace_id: UUID, tool_id: UUID) -> bool:
        return await self._delete(workspace_id, tool_id)

    # --- Entity-spezifische Lesepfade -----------------------------------------

    async def fetch(
        self,
        workspace_id: UUID,
        tool_id: UUID,
        active_only: bool = False,
    ) -> ExternalToolRead | None:
        builder = self._select_active if active_only else self._select_current
        select = builder()
        row = await self._pool.fetchrow(
            f"{select} WHERE e.id = $1 AND e.workspace_id = $2",
            tool_id,
            workspace_id,
        )
        return ExternalToolRead.model_validate(dict(row)) if row is not None else None

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        limit: int,
        after: tuple[datetime, UUID] | None,
        active_only: bool = False,
        locale: str | None = None,
    ) -> list[ExternalToolRead]:
        builder = self._select_active if active_only else self._select_current
        select = builder()
        if after is None:
            rows = await self._pool.fetch(
                f"{select} WHERE e.workspace_id = $1 "
                "AND ($3::text IS NULL OR e.locale = $3) "
                "ORDER BY e.created_at DESC, e.id DESC LIMIT $2",
                workspace_id,
                limit,
                locale,
            )
        else:
            rows = await self._pool.fetch(
                f"{select} WHERE e.workspace_id = $1 "
                "AND (e.created_at, e.id) < ($2, $3) "
                "AND ($5::text IS NULL OR e.locale = $5) "
                "ORDER BY e.created_at DESC, e.id DESC LIMIT $4",
                workspace_id,
                after[0],
                after[1],
                limit,
                locale,
            )
        return [ExternalToolRead.model_validate(dict(row)) for row in rows]
