"""Persistenz fuer das Playbook-Aggregat (`playbook` + `playbook_version`).

Versionierung ueber eine History-Tabelle (ADR-0004). `type`, `tags` und
`triggers` werden aus dem Versions-Inhalt auf die `playbook`-Zeile
denormalisiert, damit das Listing ohne Join filtern kann (§3).

Phase 2.1a-2: Filter laufen ueber `workspace_id` statt `owner_id`. `owner_id`
bleibt als Audit-Spalte (`created_by`) und wird beim INSERT mitgeschrieben.

Phase 2.1b: Status-Felder (`current_status`, `has_pending_draft`) im SELECT;
`update` erzwingt Draft-on-Edit bei `active`-Current; `active_only=True`
filtert auf Active-Versionen — MCP-Pfad (Plan §2.1.C/D).

Content-i18n (ADR-0027, Stream D2): jede Version traegt ein `locale`-Kuerzel;
pro Sprache laeuft ein eigener Versions-Track. Die "aktuelle" Version einer
Sprache ist die hoechste `version` mit diesem `locale` (statt der einzelnen
`playbook.current_version`-Spalte, die nur noch den Default-Locale-Track
`'de'` spiegelt). Alle Lese-/Schreib-Pfade nehmen `locale` (Default `'de'` =
Backward-Compat). Die denormalisierten Filterspalten (`type`, `tags`,
`triggers`) bleiben entity-weit auf der `playbook`-Zeile — nicht pro Sprache.
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
    PlaybookContent,
    PlaybookRead,
    PlaybookRef,
    PlaybookVersionRead,
    TriggerOverview,
    VersionStatus,
)


def _select_current(locale_param: str) -> str:
    """Current-Read pro Sprache: hoechste Version des `locale`-Tracks.

    `locale_param` ist der asyncpg-Platzhalter (z. B. `"$2"`), der die Ziel-
    Sprache traegt — er erscheint mehrfach (JOIN + Max-Subquery + Draft-EXISTS).
    `current_version` wird auf die Versionsnummer dieser Sprache aliased, damit
    `current_version` und `content` in der Antwort matchen.
    """
    return (
        "SELECT p.id, p.workspace_id, p.owner_id, p.name, "
        "pv.version AS current_version, "
        "p.type, p.tags, p.triggers, p.created_at, p.updated_at, pv.content, pv.locale, "
        "pv.status AS current_status, "
        "EXISTS ( "
        "    SELECT 1 FROM playbook_version dv "
        f"    WHERE dv.playbook_id = p.id AND dv.locale = {locale_param} AND dv.status = 'draft' "
        ") AS has_pending_draft, "
        "EXISTS ( "
        "    SELECT 1 FROM playbook_composition c WHERE c.parent_id = p.id "
        ") AS is_composite "
        "FROM playbook p "
        f"JOIN playbook_version pv ON pv.playbook_id = p.id AND pv.locale = {locale_param} "
        "  AND pv.version = ( "
        "      SELECT max(v.version) FROM playbook_version v "
        f"      WHERE v.playbook_id = p.id AND v.locale = {locale_param} "
        "  ) "
    )


def _select_active(locale_param: str) -> str:
    """Active-Read pro Sprache: die `status='active'`-Version des Tracks."""
    return (
        "SELECT p.id, p.workspace_id, p.owner_id, p.name, "
        "pv.version AS current_version, "
        "p.type, p.tags, p.triggers, p.created_at, p.updated_at, pv.content, pv.locale, "
        "pv.status AS current_status, "
        "EXISTS ( "
        "    SELECT 1 FROM playbook_version dv "
        f"    WHERE dv.playbook_id = p.id AND dv.locale = {locale_param} AND dv.status = 'draft' "
        ") AS has_pending_draft, "
        "EXISTS ( "
        "    SELECT 1 FROM playbook_composition c WHERE c.parent_id = p.id "
        ") AS is_composite "
        "FROM playbook p "
        f"JOIN playbook_version pv ON pv.playbook_id = p.id AND pv.locale = {locale_param} "
        "  AND pv.status = 'active' "
    )


def _escape_like(value: str) -> str:
    """Maskiert LIKE-Sonderzeichen, damit der Filter reiner Teilstring bleibt."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@dataclass(frozen=True)
class PlaybookUpdateOutcome:
    """Ergebnis eines `update`- oder `upsert_draft`-Aufrufs (analog Persona)."""

    playbook: PlaybookRead | None
    conflict: Literal["draft_exists", "review_pending"] | None = None


class PlaybookRepository(Protocol):
    """Service-seitige Abstraktion fuer den Playbook-Zugriff."""

    async def insert(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        name: str,
        content: PlaybookContent,
        locales: list[str] | None = None,
    ) -> PlaybookRead: ...

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        tag: str | None,
        trigger: str | None,
        limit: int,
        after: tuple[datetime, UUID] | None,
        active_only: bool = False,
        locale: str = DEFAULT_LOCALE,
        restrict_ids: list[UUID] | None = None,
    ) -> list[PlaybookRead]: ...

    async def fetch(
        self,
        workspace_id: UUID,
        playbook_id: UUID,
        active_only: bool = False,
        locale: str = DEFAULT_LOCALE,
        restrict_ids: list[UUID] | None = None,
    ) -> PlaybookRead | None: ...

    async def update(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        playbook_id: UUID,
        name: str | None,
        content: PlaybookContent,
        locale: str = DEFAULT_LOCALE,
    ) -> PlaybookUpdateOutcome: ...

    async def upsert_draft(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        playbook_id: UUID,
        name: str | None,
        content: PlaybookContent,
        locale: str = DEFAULT_LOCALE,
    ) -> PlaybookUpdateOutcome: ...

    async def restore_version(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        playbook_id: UUID,
        content: PlaybookContent,
        locale: str = DEFAULT_LOCALE,
    ) -> PlaybookUpdateOutcome: ...

    async def list_versions(
        self, workspace_id: UUID, playbook_id: UUID, locale: str = DEFAULT_LOCALE
    ) -> list[PlaybookVersionRead] | None: ...

    async def fetch_version(
        self, workspace_id: UUID, playbook_id: UUID, version: int, locale: str = DEFAULT_LOCALE
    ) -> PlaybookVersionRead | None: ...

    async def list_distinct_tags(
        self,
        workspace_id: UUID,
        locale: str = DEFAULT_LOCALE,
        restrict_ids: list[UUID] | None = None,
    ) -> list[str]: ...

    async def list_triggers_with_playbooks(self, workspace_id: UUID) -> list[TriggerOverview]: ...

    async def delete(self, workspace_id: UUID, playbook_id: UUID) -> bool: ...

    async def is_managed(self, workspace_id: UUID, entity_id: UUID) -> bool: ...


class PgPlaybookRepository(VersionedAggregateRepository[PlaybookRead, PlaybookVersionRead]):
    """asyncpg-Implementierung von `PlaybookRepository`.

    Teil-Migration auf den generischen Kern (Repo-Review STR-1c, Option B):
    `list_versions`/`fetch_version`/`delete` kommen aus
    `VersionedAggregateRepository`. `insert`/`update`/`upsert_draft`/
    `restore_version` sowie die Lese-Filter bleiben playbook-eigen — die
    denormalisierten Identitaets-Spalten (`type`/`tags`/`triggers`) und
    `is_composite` weichen vom generischen Schema ab.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        super().__init__(
            pool,
            AggregateTables("playbook", PlaybookRead, PlaybookVersionRead),
        )

    async def insert(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        name: str,
        content: PlaybookContent,
        locales: list[str] | None = None,
    ) -> PlaybookRead:
        # Content-i18n: pro gewaehlter Sprache eine eigene Draft-v1 (Copy der
        # Vorlage). Default `['de']` haelt Bestands-Aufrufer kompatibel. Die
        # denormalisierten Filterspalten (type/tags/triggers) sind entity-weit
        # und werden nur einmal auf der `playbook`-Zeile gesetzt.
        target_locales = locales or [DEFAULT_LOCALE]
        content_json = content.model_dump(mode="json")
        async with self._pool.acquire() as conn, conn.transaction():
            # Welle 4: type="" ist erlaubter Draft-Zustand (Migration 0025 hat
            # den CHECK um '' erweitert). Direkt content.type uebergeben.
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
            for loc in target_locales:
                await conn.execute(
                    "INSERT INTO playbook_version "
                    "(playbook_id, version, content, status, created_by, locale) "
                    "VALUES ($1, $2, $3, $4, $5, $6)",
                    playbook["id"],
                    playbook["current_version"],
                    content_json,
                    VersionStatus.draft.value,
                    owner_id,
                    loc,
                )
        # Neue v1 startet als Draft (Phase 3-0, siehe Persona-Pendant fuer
        # Begruendung). Die Antwort spiegelt die erste gewaehlte Sprache.
        return PlaybookRead.model_validate(
            {
                **dict(playbook),
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
        trigger: str | None,
        limit: int,
        after: tuple[datetime, UUID] | None,
        active_only: bool = False,
        locale: str = DEFAULT_LOCALE,
        restrict_ids: list[UUID] | None = None,
    ) -> list[PlaybookRead]:
        builder = _select_active if active_only else _select_current
        trigger_pattern = _escape_like(trigger) if trigger is not None else None
        # Tag/Trigger-Filter und Keyset-Pagination teilen sich denselben
        # WHERE-Block; der Cursor-Pfad haengt einen weiteren Term an. Der
        # `locale`-Platzhalter haengt hinten an die Parameterliste. `restrict_ids`
        # (Read-Scoping `assigned`) ist der letzte Parameter: NULL ⇒ keine
        # Einschraenkung, leere Liste ⇒ keine Treffer.
        if after is None:
            select = builder("$5")
            rows = await self._pool.fetch(
                f"{select} "
                "WHERE p.workspace_id = $1 "
                "AND ($2::text IS NULL OR $2 = ANY(p.tags)) "
                "AND ($3::text IS NULL OR "
                "     p.triggers ILIKE '%' || $3 || '%' ESCAPE '\\') "
                "AND ($6::uuid[] IS NULL OR p.id = ANY($6)) "
                "ORDER BY p.created_at DESC, p.id DESC LIMIT $4",
                workspace_id,
                tag,
                trigger_pattern,
                limit,
                locale,
                restrict_ids,
            )
        else:
            select = builder("$7")
            rows = await self._pool.fetch(
                f"{select} "
                "WHERE p.workspace_id = $1 "
                "AND ($2::text IS NULL OR $2 = ANY(p.tags)) "
                "AND ($3::text IS NULL OR "
                "     p.triggers ILIKE '%' || $3 || '%' ESCAPE '\\') "
                "AND (p.created_at, p.id) < ($4, $5) "
                "AND ($8::uuid[] IS NULL OR p.id = ANY($8)) "
                "ORDER BY p.created_at DESC, p.id DESC LIMIT $6",
                workspace_id,
                tag,
                trigger_pattern,
                after[0],
                after[1],
                limit,
                locale,
                restrict_ids,
            )
        return [PlaybookRead.model_validate(dict(row)) for row in rows]

    async def fetch(
        self,
        workspace_id: UUID,
        playbook_id: UUID,
        active_only: bool = False,
        locale: str = DEFAULT_LOCALE,
        restrict_ids: list[UUID] | None = None,
    ) -> PlaybookRead | None:
        builder = _select_active if active_only else _select_current
        select = builder("$3")
        row = await self._pool.fetchrow(
            f"{select} WHERE p.id = $1 AND p.workspace_id = $2 "
            "AND ($4::uuid[] IS NULL OR p.id = ANY($4))",
            playbook_id,
            workspace_id,
            locale,
            restrict_ids,
        )
        return PlaybookRead.model_validate(dict(row)) if row is not None else None

    async def update(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        playbook_id: UUID,
        name: str | None,
        content: PlaybookContent,
        locale: str = DEFAULT_LOCALE,
    ) -> PlaybookUpdateOutcome:
        content_json = content.model_dump(mode="json")
        is_default = locale == DEFAULT_LOCALE
        async with self._pool.acquire() as conn, conn.transaction():
            current = await conn.fetchrow(
                "SELECT pv.version AS current_version, pv.status "
                "FROM playbook p "
                "JOIN playbook_version pv "
                "  ON pv.playbook_id = p.id AND pv.locale = $3 "
                "  AND pv.version = ( "
                "      SELECT max(v.version) FROM playbook_version v "
                "      WHERE v.playbook_id = p.id AND v.locale = $3 "
                "  ) "
                "WHERE p.id = $1 AND p.workspace_id = $2 FOR UPDATE OF p",
                playbook_id,
                workspace_id,
                locale,
            )
            if current is None:
                return PlaybookUpdateOutcome(playbook=None)
            # Solange irgendein Draft (in dieser Sprache) existiert, blockiert
            # PUT: der Caller soll erst Promote/Discard durchspielen.
            existing_draft = await conn.fetchval(
                "SELECT 1 FROM playbook_version "
                "WHERE playbook_id = $1 AND locale = $2 AND status = 'draft'",
                playbook_id,
                locale,
            )
            if existing_draft is not None:
                return PlaybookUpdateOutcome(playbook=None, conflict="draft_exists")
            next_version = current["current_version"] + 1
            new_status: VersionStatus
            if current["status"] == VersionStatus.active.value:
                new_status = VersionStatus.draft
            else:
                new_status = VersionStatus.inactive
            # `current_version` auf der Identitaets-Zeile spiegelt nur den
            # Default-Locale-Track; Filterspalten (type/tags/triggers) sind
            # entity-weit und wandern bei jedem Edit mit.
            playbook = await conn.fetchrow(
                "UPDATE playbook "
                "SET current_version = CASE WHEN $7 THEN $1 ELSE current_version END, "
                "name = COALESCE($2, name), "
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
                is_default,
            )
            await conn.execute(
                "INSERT INTO playbook_version "
                "(playbook_id, version, content, status, created_by, locale) "
                "VALUES ($1, $2, $3, $4, $5, $6)",
                playbook_id,
                next_version,
                content_json,
                new_status.value,
                owner_id,
                locale,
            )
        return PlaybookUpdateOutcome(
            playbook=PlaybookRead.model_validate(
                {
                    **dict(playbook),
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
        playbook_id: UUID,
        name: str | None,
        content: PlaybookContent,
        locale: str = DEFAULT_LOCALE,
    ) -> PlaybookUpdateOutcome:
        """Auto-Save-Pfad fuer Playbook (PATCH `.../draft`).

        Semantik analog zu `PgPersonaRepository.upsert_draft`, jeweils pro
        Sprache:
        - bestehender Draft → in-place Update (kein Versions-Increment).
        - kein Draft, current=active|inactive → neuer Draft v(n+1).
        - kein Draft, current=review → 409 (review_pending), Frontend
          verhindert das eigentlich.
        Denormalisierte Filterspalten (`type`, `tags`, `triggers`) wandern
        bei jedem Patch mit, sonst spiegelt die Liste den Draft-Inhalt nicht.
        """
        content_json = content.model_dump(mode="json")
        is_default = locale == DEFAULT_LOCALE
        async with self._pool.acquire() as conn, conn.transaction():
            current = await conn.fetchrow(
                "SELECT pv.version AS current_version, pv.status "
                "FROM playbook p "
                "JOIN playbook_version pv "
                "  ON pv.playbook_id = p.id AND pv.locale = $3 "
                "  AND pv.version = ( "
                "      SELECT max(v.version) FROM playbook_version v "
                "      WHERE v.playbook_id = p.id AND v.locale = $3 "
                "  ) "
                "WHERE p.id = $1 AND p.workspace_id = $2 FOR UPDATE OF p",
                playbook_id,
                workspace_id,
                locale,
            )
            if current is None:
                return PlaybookUpdateOutcome(playbook=None)
            draft_version = await conn.fetchval(
                "SELECT version FROM playbook_version "
                "WHERE playbook_id = $1 AND locale = $2 AND status = 'draft'",
                playbook_id,
                locale,
            )
            if draft_version is not None:
                playbook = await conn.fetchrow(
                    "UPDATE playbook "
                    "SET name = COALESCE($1, name), type = $2, tags = $3, "
                    "triggers = $4, updated_at = now() "
                    "WHERE id = $5 "
                    "RETURNING id, workspace_id, owner_id, name, current_version, "
                    "type, tags, triggers, created_at, updated_at",
                    name,
                    content.type,
                    content.tags,
                    content.triggers,
                    playbook_id,
                )
                await conn.execute(
                    "UPDATE playbook_version SET content = $1, created_by = $2 "
                    "WHERE playbook_id = $3 AND locale = $4 AND version = $5",
                    content_json,
                    owner_id,
                    playbook_id,
                    locale,
                    draft_version,
                )
                return PlaybookUpdateOutcome(
                    playbook=PlaybookRead.model_validate(
                        {
                            **dict(playbook),
                            "current_version": draft_version,
                            "locale": locale,
                            "content": content_json,
                            "current_status": VersionStatus.draft,
                            "has_pending_draft": True,
                        }
                    )
                )
            if current["status"] == VersionStatus.review.value:
                return PlaybookUpdateOutcome(playbook=None, conflict="review_pending")
            next_version = current["current_version"] + 1
            playbook = await conn.fetchrow(
                "UPDATE playbook "
                "SET current_version = CASE WHEN $7 THEN $1 ELSE current_version END, "
                "name = COALESCE($2, name), "
                "type = $3, tags = $4, triggers = $5, updated_at = now() "
                "WHERE id = $6 "
                "RETURNING id, workspace_id, owner_id, name, current_version, "
                "type, tags, triggers, created_at, updated_at",
                next_version,
                name,
                content.type,
                content.tags,
                content.triggers,
                playbook_id,
                is_default,
            )
            await conn.execute(
                "INSERT INTO playbook_version "
                "(playbook_id, version, content, status, created_by, locale) "
                "VALUES ($1, $2, $3, $4, $5, $6)",
                playbook_id,
                next_version,
                content_json,
                VersionStatus.draft.value,
                owner_id,
                locale,
            )
        return PlaybookUpdateOutcome(
            playbook=PlaybookRead.model_validate(
                {
                    **dict(playbook),
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
        playbook_id: UUID,
        content: PlaybookContent,
        locale: str = DEFAULT_LOCALE,
    ) -> PlaybookUpdateOutcome:
        """Schreibt `content` (Snapshot einer fruehen Version) als neue Draft.

        Non-destruktiv (Track A §3.1): kein Pointer-Reset, sondern eine frische
        Draft-Version v(n+1) im `locale`-Track. 409 (`draft_exists`), wenn
        bereits ein Draft offen ist — konsistent mit `update`/PUT-auf-Active. Der
        Name bleibt unveraendert (Name ist nicht Teil des versionierten
        Contents); die denormalisierten Filterspalten wandern aus dem
        Snapshot-Content mit.
        """
        content_json = content.model_dump(mode="json")
        is_default = locale == DEFAULT_LOCALE
        async with self._pool.acquire() as conn, conn.transaction():
            current = await conn.fetchrow(
                # Per-locale Max-Version als Scalar-Subquery — Postgres erlaubt
                # `FOR UPDATE` nicht zusammen mit `GROUP BY`. Sperre auf der
                # `playbook`-Identitaets-Zeile.
                "SELECT (SELECT max(v.version) FROM playbook_version v "
                "        WHERE v.playbook_id = p.id AND v.locale = $3) AS current_version "
                "FROM playbook p "
                "WHERE p.id = $1 AND p.workspace_id = $2 "
                "FOR UPDATE",
                playbook_id,
                workspace_id,
                locale,
            )
            if current is None or current["current_version"] is None:
                return PlaybookUpdateOutcome(playbook=None)
            existing_draft = await conn.fetchval(
                "SELECT 1 FROM playbook_version "
                "WHERE playbook_id = $1 AND locale = $2 AND status = 'draft'",
                playbook_id,
                locale,
            )
            if existing_draft is not None:
                return PlaybookUpdateOutcome(playbook=None, conflict="draft_exists")
            next_version = current["current_version"] + 1
            playbook = await conn.fetchrow(
                "UPDATE playbook "
                "SET current_version = CASE WHEN $6 THEN $1 ELSE current_version END, "
                "type = $2, tags = $3, triggers = $4, updated_at = now() "
                "WHERE id = $5 "
                "RETURNING id, workspace_id, owner_id, name, current_version, type, tags, "
                "triggers, created_at, updated_at",
                next_version,
                content.type,
                content.tags,
                content.triggers,
                playbook_id,
                is_default,
            )
            await conn.execute(
                "INSERT INTO playbook_version "
                "(playbook_id, version, content, status, created_by, locale) "
                "VALUES ($1, $2, $3, $4, $5, $6)",
                playbook_id,
                next_version,
                content_json,
                VersionStatus.draft.value,
                owner_id,
                locale,
            )
        return PlaybookUpdateOutcome(
            playbook=PlaybookRead.model_validate(
                {
                    **dict(playbook),
                    "current_version": next_version,
                    "locale": locale,
                    "content": content_json,
                    "current_status": VersionStatus.draft,
                    "has_pending_draft": True,
                }
            )
        )

    async def list_versions(
        self, workspace_id: UUID, playbook_id: UUID, locale: str = DEFAULT_LOCALE
    ) -> list[PlaybookVersionRead] | None:
        return await self._list_versions(workspace_id, playbook_id, locale)

    async def fetch_version(
        self, workspace_id: UUID, playbook_id: UUID, version: int, locale: str = DEFAULT_LOCALE
    ) -> PlaybookVersionRead | None:
        return await self._fetch_version(workspace_id, playbook_id, version, locale)

    async def list_distinct_tags(
        self,
        workspace_id: UUID,
        locale: str = DEFAULT_LOCALE,
        restrict_ids: list[UUID] | None = None,
    ) -> list[str]:
        """DISTINCT alle Tags des Workspaces, lexikografisch sortiert.

        Quelle ist die denormalisierte `playbook.tags`-Spalte; das deckt auch
        Playbooks ohne aktuelle Version ab. Cross-Workspace-Filter ueber
        `workspace_id` ist hier essenziell — Tags eines anderen Workspaces
        wuerden sonst durchschlagen (siehe `test_playbook_tags`).

        `restrict_ids` (Read-Scoping `assigned`) begrenzt die Tag-Menge auf die
        sichtbaren Playbooks: NULL ⇒ keine Einschraenkung, leere Liste ⇒ keine
        Treffer. Sonst leakt ein `assigned`-Agent ueber den Tag-Picker die Tags
        nicht zugewiesener Playbooks (LOW-1).

        `locale` steht nur fuer Protocol-Kompatibilitaet in der Signatur: Tags
        liegen entity-weit/denormalisiert auf `playbook.tags`, nicht pro Sprache
        — der Parameter wird daher bewusst nicht gefiltert.
        """
        rows = await self._pool.fetch(
            "SELECT DISTINCT tag "
            "FROM playbook, unnest(tags) AS tag "
            "WHERE workspace_id = $1 "
            "AND ($2::uuid[] IS NULL OR id = ANY($2)) "
            "ORDER BY tag ASC",
            workspace_id,
            restrict_ids,
        )
        return [row["tag"] for row in rows]

    async def list_triggers_with_playbooks(self, workspace_id: UUID) -> list[TriggerOverview]:
        """Welle 5: Discovery-Aggregat fuer den `list_triggers`-MCP-Tool.

        Trigger sind heute kommagetrennt in `playbook.triggers` denormalisiert.
        Wir splitten in SQL via `string_to_array`+`unnest`, trimmen leere
        Eintraege und gruppieren in Python — `asyncpg` hat keinen praktischen
        Weg, JSON-Aggregate ohne weitere Decode-Logik zurueckzugeben.
        """
        rows = await self._pool.fetch(
            "SELECT p.id, p.name, trim(t.trigger) AS trigger "
            "  FROM playbook p, "
            "       unnest(string_to_array(coalesce(p.triggers, ''), ',')) AS t(trigger) "
            " WHERE p.workspace_id = $1 "
            "   AND trim(t.trigger) <> '' "
            " ORDER BY trim(t.trigger) ASC, p.name ASC",
            workspace_id,
        )
        bucket: dict[str, list[PlaybookRef]] = {}
        for row in rows:
            bucket.setdefault(row["trigger"], []).append(
                PlaybookRef(id=row["id"], name=row["name"])
            )
        return [
            TriggerOverview(trigger=trigger, playbooks=playbooks)
            for trigger, playbooks in bucket.items()
        ]

    async def delete(self, workspace_id: UUID, playbook_id: UUID) -> bool:
        """Hard-Delete der Identitaets-Zeile (ADR-0032), workspace-scoped.

        FK-Kaskaden (0003 `playbook_version`, 0016 `playbook_resource_link`,
        0028 `playbook_composition` parent+child — alle ON DELETE CASCADE) raeumen
        Versionen und ausgehende Links/Composition-Kanten; eingehende Referenzen
        (verlinkende Personas, Eltern-Composites) faengt der Service vorab als
        409 ab.
        """
        return await self._delete(workspace_id, playbook_id)
