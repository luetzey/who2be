"""Persistenz fuer das Resource-Aggregat (`resource` + `resource_version`).

Der versionierte CRUD-Kern (insert/update/upsert_draft/restore/list_versions/
fetch_version/delete) lebt in `VersionedAggregateRepository` (Repo-Review STR-1) —
byte-identisch geteilt mit Persona/Playbook. Diese Klasse ist die duenne
Resource-Subklasse: Tabellen-Config + typisierte Wrapper (`ResourceUpdateOutcome`)
+ die entity-spezifischen Lesepfade.

Resource-Besonderheiten:
- **Tag-Filter (E3):** Resources haben keine denormalisierte Tag-Spalte; der
  Filter laeuft ueber `resource_version.content` (jsonb-In-Query) mit
  `$tag = ANY(SELECT jsonb_array_elements_text(ev.content->'tags'))`.
- **`restrict_ids` (Read-Scoping `assigned`):** `fetch`/`list_by_workspace`
  akzeptieren eine Whitelist von IDs (NULL ⇒ keine Einschraenkung, leere Liste ⇒
  keine Treffer).

Versionierung ueber History-Tabelle (ADR-0004), Status pro Version (ADR-0020),
Workspace-Isolation (ADR-0019), Content-i18n pro Sprache (ADR-0027).
`active_only=True` liefert die Active-Version statt der Current-Version (MCP-Pfad).
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
    DEFAULT_LOCALE,
    ResourceContent,
    ResourceRead,
    ResourceVersionRead,
    SubResourceRead,
)


@dataclass(frozen=True)
class ResourceListCounts:
    """Denormalisierte List-Card-Pills einer Resource (Batch-Aggregat).

    `playbook_link_count` = Anzahl der DISTINCT Playbooks, die (ueber
    `playbook_resource_link`) auf die Resource zeigen; `sub_resource_count` =
    Anzahl der ueber `resource_composition` eingebetteten/verlinkten
    Sub-Resources (parent_id = id).
    """

    playbook_link_count: int
    sub_resource_count: int


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
        locales: list[str] | None = None,
        slug: str | None = None,
    ) -> ResourceRead: ...

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        tag: str | None,
        limit: int,
        after: tuple[datetime, UUID] | None,
        active_only: bool = False,
        locale: str = DEFAULT_LOCALE,
        restrict_ids: list[UUID] | None = None,
    ) -> list[ResourceRead]: ...

    async def fetch(
        self,
        workspace_id: UUID,
        resource_id: UUID,
        active_only: bool = False,
        locale: str = DEFAULT_LOCALE,
        restrict_ids: list[UUID] | None = None,
    ) -> ResourceRead | None: ...

    async def update(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        resource_id: UUID,
        name: str | None,
        content: ResourceContent,
        locale: str = DEFAULT_LOCALE,
    ) -> ResourceUpdateOutcome: ...

    async def upsert_draft(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        resource_id: UUID,
        name: str | None,
        content: ResourceContent,
        locale: str = DEFAULT_LOCALE,
    ) -> ResourceUpdateOutcome: ...

    async def restore_version(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        resource_id: UUID,
        content: ResourceContent,
        locale: str = DEFAULT_LOCALE,
    ) -> ResourceUpdateOutcome: ...

    async def list_versions(
        self, workspace_id: UUID, resource_id: UUID, locale: str = DEFAULT_LOCALE
    ) -> list[ResourceVersionRead] | None: ...

    async def fetch_version(
        self, workspace_id: UUID, resource_id: UUID, version: int, locale: str = DEFAULT_LOCALE
    ) -> ResourceVersionRead | None: ...

    async def delete(self, workspace_id: UUID, resource_id: UUID) -> bool: ...

    async def is_managed(self, workspace_id: UUID, entity_id: UUID) -> bool: ...

    async def list_distinct_tags(
        self,
        workspace_id: UUID,
        locale: str = DEFAULT_LOCALE,
        restrict_ids: list[UUID] | None = None,
    ) -> list[str]: ...

    async def list_counts(
        self, workspace_id: UUID, resource_ids: list[UUID]
    ) -> dict[UUID, ResourceListCounts]: ...

    async def list_sub_resource_children(
        self,
        workspace_id: UUID,
        resource_ids: list[UUID],
        locale: str = DEFAULT_LOCALE,
    ) -> dict[UUID, list[SubResourceRead]]: ...


class PgResourceRepository(VersionedAggregateRepository[ResourceRead, ResourceVersionRead]):
    """asyncpg-Implementierung von `ResourceRepository` auf dem generischen Kern."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        super().__init__(
            pool,
            # `has_slug=True`: Resources tragen — wie SystemPromptTemplates —
            # einen workspace-eindeutigen Slug (Migration 0064).
            AggregateTables("resource", ResourceRead, ResourceVersionRead, has_slug=True),
        )

    # --- Generischer Kern, in die Resource-Signaturen gewrappt ---------------

    async def insert(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        name: str,
        content: ResourceContent,
        locales: list[str] | None = None,
        slug: str | None = None,
    ) -> ResourceRead:
        return await self._insert(workspace_id, owner_id, name, content, locales, slug=slug)

    async def update(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        resource_id: UUID,
        name: str | None,
        content: ResourceContent,
        locale: str = DEFAULT_LOCALE,
    ) -> ResourceUpdateOutcome:
        resource, conflict = await self._update(
            workspace_id, owner_id, resource_id, name, content, locale
        )
        return ResourceUpdateOutcome(resource=resource, conflict=conflict)

    async def upsert_draft(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        resource_id: UUID,
        name: str | None,
        content: ResourceContent,
        locale: str = DEFAULT_LOCALE,
    ) -> ResourceUpdateOutcome:
        resource, conflict = await self._upsert_draft(
            workspace_id, owner_id, resource_id, name, content, locale
        )
        return ResourceUpdateOutcome(resource=resource, conflict=conflict)

    async def restore_version(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        resource_id: UUID,
        content: ResourceContent,
        locale: str = DEFAULT_LOCALE,
    ) -> ResourceUpdateOutcome:
        resource, conflict = await self._restore_version(
            workspace_id, owner_id, resource_id, content, locale
        )
        return ResourceUpdateOutcome(resource=resource, conflict=conflict)

    async def list_versions(
        self, workspace_id: UUID, resource_id: UUID, locale: str = DEFAULT_LOCALE
    ) -> list[ResourceVersionRead] | None:
        return await self._list_versions(workspace_id, resource_id, locale)

    async def fetch_version(
        self, workspace_id: UUID, resource_id: UUID, version: int, locale: str = DEFAULT_LOCALE
    ) -> ResourceVersionRead | None:
        return await self._fetch_version(workspace_id, resource_id, version, locale)

    async def delete(self, workspace_id: UUID, resource_id: UUID) -> bool:
        return await self._delete(workspace_id, resource_id)

    # --- Entity-spezifische Lesepfade (Tag-Filter + restrict_ids) ------------

    async def fetch(
        self,
        workspace_id: UUID,
        resource_id: UUID,
        active_only: bool = False,
        locale: str = DEFAULT_LOCALE,
        restrict_ids: list[UUID] | None = None,
    ) -> ResourceRead | None:
        builder = self._select_active if active_only else self._select_current
        select = builder("$3")
        row = await self._pool.fetchrow(
            f"{select} WHERE e.id = $1 AND e.workspace_id = $2 "
            "AND ($4::uuid[] IS NULL OR e.id = ANY($4))",
            resource_id,
            workspace_id,
            locale,
            restrict_ids,
        )
        return ResourceRead.model_validate(dict(row)) if row is not None else None

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        tag: str | None,
        limit: int,
        after: tuple[datetime, UUID] | None,
        active_only: bool = False,
        locale: str = DEFAULT_LOCALE,
        restrict_ids: list[UUID] | None = None,
    ) -> list[ResourceRead]:
        # Tag-Filter via jsonb-In-Query auf `ev.content->'tags'` (kein
        # denormalisierter Tag-Array). `restrict_ids` (Read-Scoping `assigned`):
        # NULL ⇒ keine Einschraenkung, leere Liste ⇒ keine Treffer.
        builder = self._select_active if active_only else self._select_current
        if after is None:
            select = builder("$4")
            rows = await self._pool.fetch(
                f"{select} WHERE e.workspace_id = $1 "
                "AND ($2::text IS NULL OR $2 = ANY("
                "    SELECT jsonb_array_elements_text(ev.content->'tags'))) "
                "AND ($5::uuid[] IS NULL OR e.id = ANY($5)) "
                "ORDER BY e.created_at DESC, e.id DESC LIMIT $3",
                workspace_id,
                tag,
                limit,
                locale,
                restrict_ids,
            )
        else:
            select = builder("$6")
            rows = await self._pool.fetch(
                f"{select} WHERE e.workspace_id = $1 "
                "AND ($2::text IS NULL OR $2 = ANY("
                "    SELECT jsonb_array_elements_text(ev.content->'tags'))) "
                "AND (e.created_at, e.id) < ($3, $4) "
                "AND ($7::uuid[] IS NULL OR e.id = ANY($7)) "
                "ORDER BY e.created_at DESC, e.id DESC LIMIT $5",
                workspace_id,
                tag,
                after[0],
                after[1],
                limit,
                locale,
                restrict_ids,
            )
        return [ResourceRead.model_validate(dict(row)) for row in rows]

    async def list_distinct_tags(
        self,
        workspace_id: UUID,
        locale: str = DEFAULT_LOCALE,
        restrict_ids: list[UUID] | None = None,
    ) -> list[str]:
        # Track E3: Tags liegen denormalisiert in `resource_version.content->'tags'`
        # (keine Array-Spalte auf `resource`, anders als bei Playbooks). DISTINCT
        # ueber die jeweils aktuelle Version pro Sprache (`_select_current`).
        # `restrict_ids` (Read-Scoping `assigned`) begrenzt auf die sichtbaren
        # Resources: NULL ⇒ keine Einschraenkung, leere Liste ⇒ keine Treffer —
        # sonst leakt ein `assigned`-Agent fremde Tags ueber den Picker (LOW-1).
        select = self._select_current("$2")
        rows = await self._pool.fetch(
            f"SELECT DISTINCT tag FROM ( {select} WHERE e.workspace_id = $1 "
            "AND ($3::uuid[] IS NULL OR e.id = ANY($3)) ) AS cur, "
            "jsonb_array_elements_text(cur.content->'tags') AS tag "
            "ORDER BY tag ASC",
            workspace_id,
            locale,
            restrict_ids,
        )
        return [row["tag"] for row in rows]

    async def list_counts(
        self, workspace_id: UUID, resource_ids: list[UUID]
    ) -> dict[UUID, ResourceListCounts]:
        """Batch-Aggregat fuer die List-Card-Pills (ein Roundtrip, kein N+1).

        Set-basierter Join ueber `= ANY($2)`: DISTINCT-Playbook-Anzahl
        (`playbook_resource_link`) und Sub-Resource-Anzahl
        (`resource_composition`, parent_id = id) fuer alle uebergebenen Resources
        auf einmal. Leere ID-Liste => {}.
        """
        if not resource_ids:
            return {}
        rows = await self._pool.fetch(
            "SELECT r.id AS resource_id, "
            "       COALESCE(pl.cnt, 0)::int AS playbook_link_count, "
            "       COALESCE(sc.cnt, 0)::int AS sub_resource_count "
            "FROM resource r "
            "LEFT JOIN ( "
            "    SELECT resource_id, COUNT(DISTINCT playbook_id) AS cnt "
            "    FROM playbook_resource_link GROUP BY resource_id "
            ") pl ON pl.resource_id = r.id "
            "LEFT JOIN ( "
            "    SELECT parent_id, COUNT(*) AS cnt "
            "    FROM resource_composition GROUP BY parent_id "
            ") sc ON sc.parent_id = r.id "
            "WHERE r.workspace_id = $1 AND r.id = ANY($2)",
            workspace_id,
            resource_ids,
        )
        return {
            row["resource_id"]: ResourceListCounts(
                playbook_link_count=row["playbook_link_count"],
                sub_resource_count=row["sub_resource_count"],
            )
            for row in rows
        }

    async def list_sub_resource_children(
        self,
        workspace_id: UUID,
        resource_ids: list[UUID],
        locale: str = DEFAULT_LOCALE,
    ) -> dict[UUID, list[SubResourceRead]]:
        """Direkte Sub-Resource-Kinder je Parent als Summary (ein Roundtrip).

        Spiegelt `PgPlaybookRepository._attach_compose_children`: EIN Batch-Select
        ueber `resource_composition` fuer alle Parents der Seite (kein N+1). Je
        Kind traegt die Summary `id`, `name` sowie `status`/`version` der
        aktuellen Version des `locale`-Tracks — genug, damit die aufklappbare
        List-Karte den Kind-Stand ohne Extra-Fetch zeigt. DISTINCT ueber
        (parent, child): ein Kind mit mehreren Composition-Kanten (resource +
        block) erscheint genau einmal, geordnet nach kleinster `position`.
        """
        if not resource_ids:
            return {}
        rows = await self._pool.fetch(
            "SELECT parent_id, child_id, name, version, status FROM ( "
            "  SELECT DISTINCT ON (rc.parent_id, c.id) "
            "         rc.parent_id, c.id AS child_id, c.name, "
            "         cv.version, cv.status, rc.position "
            "    FROM resource_composition rc "
            "    JOIN resource c ON c.id = rc.child_id "
            "    JOIN resource_version cv "
            "      ON cv.resource_id = c.id AND cv.locale = $2 "
            "     AND cv.version = ( "
            "         SELECT max(v.version) FROM resource_version v "
            "         WHERE v.resource_id = c.id AND v.locale = $2 "
            "     ) "
            "   WHERE rc.workspace_id = $1 AND rc.parent_id = ANY($3::uuid[]) "
            "   ORDER BY rc.parent_id, c.id, rc.position ASC "
            ") t "
            "ORDER BY t.parent_id, t.position ASC, t.name ASC",
            workspace_id,
            locale,
            resource_ids,
        )
        by_parent: dict[UUID, list[SubResourceRead]] = {}
        for row in rows:
            by_parent.setdefault(row["parent_id"], []).append(
                SubResourceRead.model_validate(
                    {
                        "id": row["child_id"],
                        "name": row["name"],
                        "status": row["status"],
                        "version": row["version"],
                    }
                )
            )
        return by_parent
