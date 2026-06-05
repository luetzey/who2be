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

Content-i18n (ADR-0027, Stream D2): jede Version traegt ein `locale`-Kuerzel;
pro Sprache laeuft ein eigener Versions-Track. Die "aktuelle" Version einer
Sprache ist die hoechste `version` mit diesem `locale` (statt der einzelnen
`resource.current_version`-Spalte, die nur noch den Default-Locale-Track
`'de'` spiegelt). Alle Lese-/Schreib-Pfade nehmen `locale` (Default `'de'` =
Backward-Compat).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

import asyncpg

from who2be_models import (
    DEFAULT_LOCALE,
    ResourceContent,
    ResourceRead,
    ResourceVersionRead,
    VersionStatus,
)


def _select_current(locale_param: str) -> str:
    """Current-Read pro Sprache: hoechste Version des `locale`-Tracks.

    `locale_param` ist der asyncpg-Platzhalter (z. B. `"$3"`), der die Ziel-
    Sprache traegt — er erscheint mehrfach (JOIN + Max-Subquery + Draft-EXISTS).
    `current_version` wird auf die Versionsnummer dieser Sprache aliased, damit
    `current_version` und `content` in der Antwort matchen.
    """
    return (
        "SELECT r.id, r.workspace_id, r.owner_id, r.name, "
        "rv.version AS current_version, "
        "r.created_at, r.updated_at, rv.content, rv.locale, "
        "rv.status AS current_status, "
        "EXISTS ( "
        "    SELECT 1 FROM resource_version dv "
        f"    WHERE dv.resource_id = r.id AND dv.locale = {locale_param} AND dv.status = 'draft' "
        ") AS has_pending_draft "
        "FROM resource r "
        f"JOIN resource_version rv ON rv.resource_id = r.id AND rv.locale = {locale_param} "
        "  AND rv.version = ( "
        "      SELECT max(v.version) FROM resource_version v "
        f"      WHERE v.resource_id = r.id AND v.locale = {locale_param} "
        "  ) "
    )


def _select_active(locale_param: str) -> str:
    """Active-Read pro Sprache: die `status='active'`-Version des Tracks."""
    return (
        "SELECT r.id, r.workspace_id, r.owner_id, r.name, "
        "rv.version AS current_version, "
        "r.created_at, r.updated_at, rv.content, rv.locale, "
        "rv.status AS current_status, "
        "EXISTS ( "
        "    SELECT 1 FROM resource_version dv "
        f"    WHERE dv.resource_id = r.id AND dv.locale = {locale_param} AND dv.status = 'draft' "
        ") AS has_pending_draft "
        "FROM resource r "
        f"JOIN resource_version rv ON rv.resource_id = r.id AND rv.locale = {locale_param} "
        "  AND rv.status = 'active' "
    )


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

    async def list_distinct_tags(
        self, workspace_id: UUID, locale: str = DEFAULT_LOCALE
    ) -> list[str]: ...


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
        locales: list[str] | None = None,
    ) -> ResourceRead:
        # Content-i18n: pro gewaehlter Sprache eine eigene Draft-v1 (Copy der
        # Vorlage). Default `['de']` haelt Bestands-Aufrufer kompatibel.
        target_locales = locales or [DEFAULT_LOCALE]
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
            for loc in target_locales:
                await conn.execute(
                    "INSERT INTO resource_version "
                    "(resource_id, version, content, status, created_by, locale) "
                    "VALUES ($1, $2, $3, $4, $5, $6)",
                    resource["id"],
                    resource["current_version"],
                    content_json,
                    VersionStatus.draft.value,
                    owner_id,
                    loc,
                )
        # Neue v1 startet als Draft (Phase 3-0, siehe Persona-Pendant fuer
        # Begruendung). Die Antwort spiegelt die erste gewaehlte Sprache.
        return ResourceRead.model_validate(
            {
                **dict(resource),
                "content": content_json,
                "locale": target_locales[0],
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
        locale: str = DEFAULT_LOCALE,
        restrict_ids: list[UUID] | None = None,
    ) -> list[ResourceRead]:
        # Tag-Filter via jsonb-In-Query: kein denormalisierter Tag-Array auf
        # der resource-Zeile (laut Plan E3 Out-of-Scope); stattdessen direkt
        # aus content->tags im resource_version-Row. Bedingung:
        # `$tag = ANY(SELECT jsonb_array_elements_text(rv.content->'tags'))`.
        # `restrict_ids` (Read-Scoping `assigned`) ist der letzte Parameter:
        # NULL ⇒ keine Einschraenkung, leere Liste ⇒ keine Treffer.
        builder = _select_active if active_only else _select_current
        if after is None:
            select = builder("$4")
            rows = await self._pool.fetch(
                f"{select} WHERE r.workspace_id = $1 "
                "AND ($2::text IS NULL OR $2 = ANY("
                "    SELECT jsonb_array_elements_text(rv.content->'tags'))) "
                "AND ($5::uuid[] IS NULL OR r.id = ANY($5)) "
                "ORDER BY r.created_at DESC, r.id DESC LIMIT $3",
                workspace_id,
                tag,
                limit,
                locale,
                restrict_ids,
            )
        else:
            select = builder("$6")
            rows = await self._pool.fetch(
                f"{select} WHERE r.workspace_id = $1 "
                "AND ($2::text IS NULL OR $2 = ANY("
                "    SELECT jsonb_array_elements_text(rv.content->'tags'))) "
                "AND (r.created_at, r.id) < ($3, $4) "
                "AND ($7::uuid[] IS NULL OR r.id = ANY($7)) "
                "ORDER BY r.created_at DESC, r.id DESC LIMIT $5",
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
        self, workspace_id: UUID, locale: str = DEFAULT_LOCALE
    ) -> list[str]:
        # Track E3: Tags liegen denormalisiert in `resource_version.content->'tags'`
        # (kein Array-Spalte auf `resource`, anders als bei Playbooks). Wir
        # extrahieren DISTINCT-Tags aus der jeweils aktuellen Version pro Sprache
        # ueber denselben `_select_current`-Build wie der Tag-Filter — `tags` ist
        # im Modell `default_factory=list`, also stets ein (ggf. leeres) jsonb-Array.
        select = _select_current("$2")
        rows = await self._pool.fetch(
            f"SELECT DISTINCT tag FROM ( {select} WHERE r.workspace_id = $1 ) AS cur, "
            "jsonb_array_elements_text(cur.content->'tags') AS tag "
            "ORDER BY tag ASC",
            workspace_id,
            locale,
        )
        return [row["tag"] for row in rows]

    async def fetch(
        self,
        workspace_id: UUID,
        resource_id: UUID,
        active_only: bool = False,
        locale: str = DEFAULT_LOCALE,
        restrict_ids: list[UUID] | None = None,
    ) -> ResourceRead | None:
        builder = _select_active if active_only else _select_current
        select = builder("$3")
        row = await self._pool.fetchrow(
            f"{select} WHERE r.id = $1 AND r.workspace_id = $2 "
            "AND ($4::uuid[] IS NULL OR r.id = ANY($4))",
            resource_id,
            workspace_id,
            locale,
            restrict_ids,
        )
        return ResourceRead.model_validate(dict(row)) if row is not None else None

    async def update(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        resource_id: UUID,
        name: str | None,
        content: ResourceContent,
        locale: str = DEFAULT_LOCALE,
    ) -> ResourceUpdateOutcome:
        content_json = content.model_dump(mode="json")
        is_default = locale == DEFAULT_LOCALE
        async with self._pool.acquire() as conn, conn.transaction():
            current = await conn.fetchrow(
                "SELECT rv.version AS current_version, rv.status "
                "FROM resource r "
                "JOIN resource_version rv "
                "  ON rv.resource_id = r.id AND rv.locale = $3 "
                "  AND rv.version = ( "
                "      SELECT max(v.version) FROM resource_version v "
                "      WHERE v.resource_id = r.id AND v.locale = $3 "
                "  ) "
                "WHERE r.id = $1 AND r.workspace_id = $2 FOR UPDATE OF r",
                resource_id,
                workspace_id,
                locale,
            )
            if current is None:
                return ResourceUpdateOutcome(resource=None)
            existing_draft = await conn.fetchval(
                "SELECT 1 FROM resource_version "
                "WHERE resource_id = $1 AND locale = $2 AND status = 'draft'",
                resource_id,
                locale,
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
                "SET current_version = CASE WHEN $4 THEN $1 ELSE current_version END, "
                "name = COALESCE($2, name), updated_at = now() "
                "WHERE id = $3 "
                "RETURNING id, workspace_id, owner_id, name, current_version, "
                "created_at, updated_at",
                next_version,
                name,
                resource_id,
                is_default,
            )
            await conn.execute(
                "INSERT INTO resource_version "
                "(resource_id, version, content, status, created_by, locale) "
                "VALUES ($1, $2, $3, $4, $5, $6)",
                resource_id,
                next_version,
                content_json,
                new_status.value,
                owner_id,
                locale,
            )
        return ResourceUpdateOutcome(
            resource=ResourceRead.model_validate(
                {
                    **dict(resource),
                    "current_version": next_version,
                    "locale": locale,
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
        locale: str = DEFAULT_LOCALE,
    ) -> ResourceUpdateOutcome:
        """Auto-Save-Pfad fuer Resource (PATCH `.../draft`).

        Semantik wie `PgPersonaRepository.upsert_draft` — bestehender Draft
        (in dieser Sprache) wird in-place ueberschrieben, sonst entsteht eine
        neue Draft-Version. `current_version` wandert nur fuer den Default-
        Locale-Track mit.
        """
        content_json = content.model_dump(mode="json")
        is_default = locale == DEFAULT_LOCALE
        async with self._pool.acquire() as conn, conn.transaction():
            current = await conn.fetchrow(
                "SELECT rv.version AS current_version, rv.status "
                "FROM resource r "
                "JOIN resource_version rv "
                "  ON rv.resource_id = r.id AND rv.locale = $3 "
                "  AND rv.version = ( "
                "      SELECT max(v.version) FROM resource_version v "
                "      WHERE v.resource_id = r.id AND v.locale = $3 "
                "  ) "
                "WHERE r.id = $1 AND r.workspace_id = $2 FOR UPDATE OF r",
                resource_id,
                workspace_id,
                locale,
            )
            if current is None:
                return ResourceUpdateOutcome(resource=None)
            draft_version = await conn.fetchval(
                "SELECT version FROM resource_version "
                "WHERE resource_id = $1 AND locale = $2 AND status = 'draft'",
                resource_id,
                locale,
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
                    "WHERE resource_id = $3 AND locale = $4 AND version = $5",
                    content_json,
                    owner_id,
                    resource_id,
                    locale,
                    draft_version,
                )
                return ResourceUpdateOutcome(
                    resource=ResourceRead.model_validate(
                        {
                            **dict(resource),
                            "current_version": draft_version,
                            "locale": locale,
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
                "SET current_version = CASE WHEN $4 THEN $1 ELSE current_version END, "
                "name = COALESCE($2, name), updated_at = now() "
                "WHERE id = $3 "
                "RETURNING id, workspace_id, owner_id, name, current_version, "
                "created_at, updated_at",
                next_version,
                name,
                resource_id,
                is_default,
            )
            await conn.execute(
                "INSERT INTO resource_version "
                "(resource_id, version, content, status, created_by, locale) "
                "VALUES ($1, $2, $3, $4, $5, $6)",
                resource_id,
                next_version,
                content_json,
                VersionStatus.draft.value,
                owner_id,
                locale,
            )
        return ResourceUpdateOutcome(
            resource=ResourceRead.model_validate(
                {
                    **dict(resource),
                    "current_version": next_version,
                    "locale": locale,
                    "content": content_json,
                    "current_status": VersionStatus.draft,
                    "has_pending_draft": True,
                }
            )
        )

    async def restore_version(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        resource_id: UUID,
        content: ResourceContent,
        locale: str = DEFAULT_LOCALE,
    ) -> ResourceUpdateOutcome:
        """Schreibt `content` (Snapshot) als neue Draft-Version (Track A §3.1).

        Non-destruktiv: frische Draft v(n+1) im `locale`-Track, kein Pointer-
        Reset. 409 (`draft_exists`) bei bereits offenem Draft. Name bleibt
        unveraendert.
        """
        content_json = content.model_dump(mode="json")
        is_default = locale == DEFAULT_LOCALE
        async with self._pool.acquire() as conn, conn.transaction():
            current = await conn.fetchrow(
                # Per-locale Max-Version als Scalar-Subquery — Postgres erlaubt
                # `FOR UPDATE` nicht zusammen mit `GROUP BY`. Sperre auf der
                # `resource`-Identitaets-Zeile.
                "SELECT (SELECT max(v.version) FROM resource_version v "
                "        WHERE v.resource_id = r.id AND v.locale = $3) AS current_version "
                "FROM resource r "
                "WHERE r.id = $1 AND r.workspace_id = $2 "
                "FOR UPDATE",
                resource_id,
                workspace_id,
                locale,
            )
            if current is None or current["current_version"] is None:
                return ResourceUpdateOutcome(resource=None)
            existing_draft = await conn.fetchval(
                "SELECT 1 FROM resource_version "
                "WHERE resource_id = $1 AND locale = $2 AND status = 'draft'",
                resource_id,
                locale,
            )
            if existing_draft is not None:
                return ResourceUpdateOutcome(resource=None, conflict="draft_exists")
            next_version = current["current_version"] + 1
            resource = await conn.fetchrow(
                "UPDATE resource SET "
                "current_version = CASE WHEN $3 THEN $1 ELSE current_version END, "
                "updated_at = now() "
                "WHERE id = $2 "
                "RETURNING id, workspace_id, owner_id, name, current_version, "
                "created_at, updated_at",
                next_version,
                resource_id,
                is_default,
            )
            await conn.execute(
                "INSERT INTO resource_version "
                "(resource_id, version, content, status, created_by, locale) "
                "VALUES ($1, $2, $3, $4, $5, $6)",
                resource_id,
                next_version,
                content_json,
                VersionStatus.draft.value,
                owner_id,
                locale,
            )
        return ResourceUpdateOutcome(
            resource=ResourceRead.model_validate(
                {
                    **dict(resource),
                    "current_version": next_version,
                    "locale": locale,
                    "content": content_json,
                    "current_status": VersionStatus.draft,
                    "has_pending_draft": True,
                }
            )
        )

    async def list_versions(
        self, workspace_id: UUID, resource_id: UUID, locale: str = DEFAULT_LOCALE
    ) -> list[ResourceVersionRead] | None:
        owned = await self._pool.fetchval(
            "SELECT 1 FROM resource WHERE id = $1 AND workspace_id = $2",
            resource_id,
            workspace_id,
        )
        if owned is None:
            return None
        rows = await self._pool.fetch(
            "SELECT version, status, locale, content, created_by, created_at "
            "FROM resource_version WHERE resource_id = $1 AND locale = $2 "
            "ORDER BY version DESC",
            resource_id,
            locale,
        )
        return [ResourceVersionRead.model_validate(dict(row)) for row in rows]

    async def fetch_version(
        self, workspace_id: UUID, resource_id: UUID, version: int, locale: str = DEFAULT_LOCALE
    ) -> ResourceVersionRead | None:
        row = await self._pool.fetchrow(
            "SELECT rv.version, rv.status, rv.locale, rv.content, rv.created_by, rv.created_at "
            "FROM resource_version rv "
            "JOIN resource r ON r.id = rv.resource_id "
            "WHERE r.id = $1 AND r.workspace_id = $2 AND rv.version = $3 AND rv.locale = $4",
            resource_id,
            workspace_id,
            version,
            locale,
        )
        return ResourceVersionRead.model_validate(dict(row)) if row is not None else None
