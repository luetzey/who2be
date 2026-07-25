"""Persistenz fuer das Playbook-Aggregat (`playbook` + `playbook_version`).

Versionierung ueber eine History-Tabelle (ADR-0004). `type`, `tags` und
`triggers` werden aus dem Versions-Inhalt auf die `playbook`-Zeile
denormalisiert, damit das Listing ohne Join filtern kann (§3).

Phase 2.1a-2: Filter laufen ueber `workspace_id` statt `owner_id`. `owner_id`
bleibt als Audit-Spalte (`created_by`) und wird beim INSERT mitgeschrieben.

Phase 2.1b: Status-Felder (`current_status`, `has_pending_draft`) im SELECT;
`update` erzwingt Draft-on-Edit bei `active`-Current; `active_only=True`
filtert auf Active-Versionen — MCP-Pfad (Plan §2.1.C/D).

„Ein Element, eine Sprache" (ADR-0045): `locale` ist ein Attribut der
`playbook`-Identitaets-Zeile. Reads sind locale-agnostisch (Current = globale
Max-Version mit Legacy-Tie-Break auf die Entity-Sprache; Active = per-entity
eindeutige `status='active'`-Row); `list_by_workspace` filtert optional auf
`playbook.locale`. Versions-Writes uebernehmen die Entity-Sprache;
`next_version` zaehlt global ueber alle locales. Die denormalisierten
Filterspalten (`type`, `tags`, `triggers`) bleiben entity-weit.
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
    PlaybookContent,
    PlaybookRead,
    PlaybookRef,
    PlaybookVersionRead,
    TriggerOverview,
    VersionStatus,
)


def _select_current() -> str:
    """Current-Read (locale-agnostisch): die global hoechste Version.

    Legacy-Tie-Break: Alt-Daten aus dem ADR-0027-Multi-Track koennen dieselbe
    Versionsnummer in zwei Sprachen tragen — bevorzugt wird deterministisch die
    Row in der Entity-Sprache. `current_version` ist auf die Versionsnummer der
    gelieferten Row aliased, damit `current_version` und `content` matchen.
    """
    return (
        "SELECT p.id, p.workspace_id, p.owner_id, p.name, "
        "pv.version AS current_version, "
        "p.type, p.tags, p.triggers, p.created_at, p.updated_at, p.is_managed, "
        "pv.content, p.locale, "
        "pv.status AS current_status, "
        "EXISTS ( "
        "    SELECT 1 FROM playbook_version dv "
        "    WHERE dv.playbook_id = p.id AND dv.status = 'draft' "
        ") AS has_pending_draft, "
        "EXISTS ( "
        "    SELECT 1 FROM playbook_composition c WHERE c.parent_id = p.id "
        ") AS is_composite "
        "FROM playbook p "
        "JOIN LATERAL ( "
        "    SELECT v.version, v.status, v.content FROM playbook_version v "
        "    WHERE v.playbook_id = p.id "
        "    ORDER BY v.version DESC, (v.locale = p.locale) DESC "
        "    LIMIT 1 "
        ") pv ON TRUE "
    )


def _select_active() -> str:
    """Active-Read: die per-entity eindeutige `status='active'`-Version."""
    return (
        "SELECT p.id, p.workspace_id, p.owner_id, p.name, "
        "pv.version AS current_version, "
        "p.type, p.tags, p.triggers, p.created_at, p.updated_at, p.is_managed, "
        "pv.content, p.locale, "
        "pv.status AS current_status, "
        "EXISTS ( "
        "    SELECT 1 FROM playbook_version dv "
        "    WHERE dv.playbook_id = p.id AND dv.status = 'draft' "
        ") AS has_pending_draft, "
        "EXISTS ( "
        "    SELECT 1 FROM playbook_composition c WHERE c.parent_id = p.id "
        ") AS is_composite "
        "FROM playbook p "
        "JOIN playbook_version pv ON pv.playbook_id = p.id "
        "  AND pv.status = 'active' "
    )


# Locked Current-Read fuer die Schreib-Pfade: globale Max-Version (+ Status der
# juengsten Row, Legacy-Tie-Break auf die Entity-Sprache). Sperre auf der
# Identitaets-Zeile; `next_version` = Ergebnis + 1 (globaler Zaehler).
_CURRENT_FOR_UPDATE = (
    "SELECT pv.version AS current_version, pv.status "
    "FROM playbook p "
    "JOIN LATERAL ( "
    "    SELECT v.version, v.status FROM playbook_version v "
    "    WHERE v.playbook_id = p.id "
    "    ORDER BY v.version DESC, (v.locale = p.locale) DESC "
    "    LIMIT 1 "
    ") pv ON TRUE "
    "WHERE p.id = $1 AND p.workspace_id = $2 FOR UPDATE OF p"
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
        locale: str,
    ) -> PlaybookRead: ...

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        tag: str | None,
        trigger: str | None,
        limit: int,
        after: tuple[datetime, UUID] | None,
        active_only: bool = False,
        locale: str | None = None,
        restrict_ids: list[UUID] | None = None,
    ) -> list[PlaybookRead]: ...

    async def fetch(
        self,
        workspace_id: UUID,
        playbook_id: UUID,
        active_only: bool = False,
        restrict_ids: list[UUID] | None = None,
    ) -> PlaybookRead | None: ...

    async def update(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        playbook_id: UUID,
        name: str | None,
        content: PlaybookContent,
        new_locale: str | None = None,
    ) -> PlaybookUpdateOutcome: ...

    async def upsert_draft(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        playbook_id: UUID,
        name: str | None,
        content: PlaybookContent,
        new_locale: str | None = None,
    ) -> PlaybookUpdateOutcome: ...

    async def restore_version(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        playbook_id: UUID,
        content: PlaybookContent,
    ) -> PlaybookUpdateOutcome: ...

    async def list_versions(
        self, workspace_id: UUID, playbook_id: UUID
    ) -> list[PlaybookVersionRead] | None: ...

    async def fetch_version(
        self, workspace_id: UUID, playbook_id: UUID, version: int
    ) -> PlaybookVersionRead | None: ...

    async def list_distinct_tags(
        self,
        workspace_id: UUID,
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
        locale: str,
    ) -> PlaybookRead:
        # „Ein Element, eine Sprache": die Entity-Zeile traegt die Sprache,
        # Draft-v1 uebernimmt sie. Die denormalisierten Filterspalten
        # (type/tags/triggers) sind entity-weit.
        content_json = content.model_dump(mode="json")
        async with self._pool.acquire() as conn, conn.transaction():
            # Welle 4: type="" ist erlaubter Draft-Zustand (Migration 0025 hat
            # den CHECK um '' erweitert). Direkt content.type uebergeben.
            playbook = await conn.fetchrow(
                "INSERT INTO playbook "
                "(workspace_id, owner_id, name, type, tags, triggers, locale) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7) "
                "RETURNING id, workspace_id, owner_id, name, current_version, type, tags, "
                "triggers, locale, created_at, updated_at",
                workspace_id,
                owner_id,
                name,
                content.type,
                content.tags,
                content.triggers,
                locale,
            )
            await conn.execute(
                "INSERT INTO playbook_version "
                "(playbook_id, version, content, status, created_by, locale) "
                "VALUES ($1, $2, $3, $4, $5, $6)",
                playbook["id"],
                playbook["current_version"],
                content_json,
                VersionStatus.draft.value,
                owner_id,
                locale,
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
        locale: str | None = None,
        restrict_ids: list[UUID] | None = None,
    ) -> list[PlaybookRead]:
        select = _select_active() if active_only else _select_current()
        trigger_pattern = _escape_like(trigger) if trigger is not None else None
        # Tag/Trigger-Filter und Keyset-Pagination teilen sich denselben
        # WHERE-Block; der Cursor-Pfad haengt einen weiteren Term an. `locale`
        # ist der optionale Sprachfilter auf die Entity-Sprache (NULL ⇒ alle).
        # `restrict_ids` (Read-Scoping `assigned`) ist der letzte Parameter:
        # NULL ⇒ keine Einschraenkung, leere Liste ⇒ keine Treffer.
        if after is None:
            rows = await self._pool.fetch(
                f"{select} "
                "WHERE p.workspace_id = $1 "
                "AND ($2::text IS NULL OR $2 = ANY(p.tags)) "
                "AND ($3::text IS NULL OR "
                "     p.triggers ILIKE '%' || $3 || '%' ESCAPE '\\') "
                "AND ($5::text IS NULL OR p.locale = $5) "
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
            rows = await self._pool.fetch(
                f"{select} "
                "WHERE p.workspace_id = $1 "
                "AND ($2::text IS NULL OR $2 = ANY(p.tags)) "
                "AND ($3::text IS NULL OR "
                "     p.triggers ILIKE '%' || $3 || '%' ESCAPE '\\') "
                "AND (p.created_at, p.id) < ($4, $5) "
                "AND ($7::text IS NULL OR p.locale = $7) "
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
        playbooks = [PlaybookRead.model_validate(dict(row)) for row in rows]
        return await self._attach_compose_children(playbooks)

    async def _attach_compose_children(self, playbooks: list[PlaybookRead]) -> list[PlaybookRead]:
        """WP-D2: Sub-Playbook-Refs fuer die Listen-Seite nachladen.

        EIN Batch-Select ueber `playbook_composition` fuer alle Composites der
        Seite (kein N+1) — laeuft NACH `_select_current`/`_select_active` und
        deckt damit beide Lese-Pfade ab. Nur id + name, geordnet nach
        `position` (Ausfuehrungssequenz, ADR-0024). Nicht-Composites behalten
        die leere Default-Liste des DTOs.
        """
        parent_ids = [playbook.id for playbook in playbooks if playbook.is_composite]
        if not parent_ids:
            return playbooks
        rows = await self._pool.fetch(
            "SELECT c.parent_id, child.id, child.name "
            "  FROM playbook_composition c "
            "  JOIN playbook child ON child.id = c.child_id "
            " WHERE c.parent_id = ANY($1::uuid[]) "
            " ORDER BY c.position ASC, child.name ASC",
            parent_ids,
        )
        by_parent: dict[UUID, list[PlaybookRef]] = {}
        for row in rows:
            by_parent.setdefault(row["parent_id"], []).append(
                PlaybookRef(id=row["id"], name=row["name"])
            )
        for playbook in playbooks:
            playbook.compose_children = by_parent.get(playbook.id, [])
        return playbooks

    async def fetch(
        self,
        workspace_id: UUID,
        playbook_id: UUID,
        active_only: bool = False,
        restrict_ids: list[UUID] | None = None,
    ) -> PlaybookRead | None:
        select = _select_active() if active_only else _select_current()
        row = await self._pool.fetchrow(
            f"{select} WHERE p.id = $1 AND p.workspace_id = $2 "
            "AND ($3::uuid[] IS NULL OR p.id = ANY($3))",
            playbook_id,
            workspace_id,
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
        new_locale: str | None = None,
    ) -> PlaybookUpdateOutcome:
        content_json = content.model_dump(mode="json")
        async with self._pool.acquire() as conn, conn.transaction():
            current = await conn.fetchrow(
                _CURRENT_FOR_UPDATE,
                playbook_id,
                workspace_id,
            )
            if current is None:
                return PlaybookUpdateOutcome(playbook=None)
            # Solange irgendein Draft existiert, blockiert PUT: der Caller soll
            # erst Promote/Discard durchspielen.
            existing_draft = await conn.fetchval(
                "SELECT 1 FROM playbook_version WHERE playbook_id = $1 AND status = 'draft'",
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
            # Filterspalten (type/tags/triggers) sind entity-weit und wandern
            # bei jedem Edit mit; ein gesetztes `new_locale` wechselt die
            # Entity-Sprache (Metadaten-Update).
            playbook = await conn.fetchrow(
                "UPDATE playbook "
                "SET current_version = $1, name = COALESCE($2, name), "
                "type = $3, tags = $4, triggers = $5, "
                "locale = COALESCE($7, locale), updated_at = now() "
                "WHERE id = $6 "
                "RETURNING id, workspace_id, owner_id, name, current_version, type, tags, "
                "triggers, locale, created_at, updated_at",
                next_version,
                name,
                content.type,
                content.tags,
                content.triggers,
                playbook_id,
                new_locale,
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
                playbook["locale"],
            )
        return PlaybookUpdateOutcome(
            playbook=PlaybookRead.model_validate(
                {
                    **dict(playbook),
                    "current_version": next_version,
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
        new_locale: str | None = None,
    ) -> PlaybookUpdateOutcome:
        """Auto-Save-Pfad fuer Playbook (PATCH `.../draft`).

        Semantik analog zu `PgPersonaRepository.upsert_draft`:
        - bestehender Draft → in-place Update (kein Versions-Increment).
        - kein Draft, current=active|inactive → neuer Draft v(n+1).
        - kein Draft, current=review → 409 (review_pending), Frontend
          verhindert das eigentlich.
        Denormalisierte Filterspalten (`type`, `tags`, `triggers`) wandern
        bei jedem Patch mit, sonst spiegelt die Liste den Draft-Inhalt nicht.
        """
        content_json = content.model_dump(mode="json")
        async with self._pool.acquire() as conn, conn.transaction():
            current = await conn.fetchrow(
                _CURRENT_FOR_UPDATE,
                playbook_id,
                workspace_id,
            )
            if current is None:
                return PlaybookUpdateOutcome(playbook=None)
            draft_version = await conn.fetchval(
                "SELECT version FROM playbook_version WHERE playbook_id = $1 AND status = 'draft'",
                playbook_id,
            )
            if draft_version is not None:
                playbook = await conn.fetchrow(
                    "UPDATE playbook "
                    "SET name = COALESCE($1, name), type = $2, tags = $3, "
                    "triggers = $4, locale = COALESCE($6, locale), updated_at = now() "
                    "WHERE id = $5 "
                    "RETURNING id, workspace_id, owner_id, name, current_version, "
                    "type, tags, triggers, locale, created_at, updated_at",
                    name,
                    content.type,
                    content.tags,
                    content.triggers,
                    playbook_id,
                    new_locale,
                )
                await conn.execute(
                    "UPDATE playbook_version SET content = $1, created_by = $2 "
                    "WHERE playbook_id = $3 AND version = $4 AND status = 'draft'",
                    content_json,
                    owner_id,
                    playbook_id,
                    draft_version,
                )
                return PlaybookUpdateOutcome(
                    playbook=PlaybookRead.model_validate(
                        {
                            **dict(playbook),
                            "current_version": draft_version,
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
                "SET current_version = $1, name = COALESCE($2, name), "
                "type = $3, tags = $4, triggers = $5, "
                "locale = COALESCE($7, locale), updated_at = now() "
                "WHERE id = $6 "
                "RETURNING id, workspace_id, owner_id, name, current_version, "
                "type, tags, triggers, locale, created_at, updated_at",
                next_version,
                name,
                content.type,
                content.tags,
                content.triggers,
                playbook_id,
                new_locale,
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
                playbook["locale"],
            )
        return PlaybookUpdateOutcome(
            playbook=PlaybookRead.model_validate(
                {
                    **dict(playbook),
                    "current_version": next_version,
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
    ) -> PlaybookUpdateOutcome:
        """Schreibt `content` (Snapshot einer fruehen Version) als neue Draft.

        Non-destruktiv (Track A §3.1): kein Pointer-Reset, sondern eine frische
        Draft-Version v(n+1) (globaler Zaehler). 409 (`draft_exists`), wenn
        bereits ein Draft offen ist — konsistent mit `update`/PUT-auf-Active. Der
        Name und die Entity-Sprache bleiben unveraendert; die denormalisierten
        Filterspalten wandern aus dem Snapshot-Content mit.
        """
        content_json = content.model_dump(mode="json")
        async with self._pool.acquire() as conn, conn.transaction():
            current = await conn.fetchrow(
                # Globale Max-Version als Scalar-Subquery — Postgres erlaubt
                # `FOR UPDATE` nicht zusammen mit `GROUP BY`. Sperre auf der
                # `playbook`-Identitaets-Zeile.
                "SELECT (SELECT max(v.version) FROM playbook_version v "
                "        WHERE v.playbook_id = p.id) AS current_version "
                "FROM playbook p "
                "WHERE p.id = $1 AND p.workspace_id = $2 "
                "FOR UPDATE",
                playbook_id,
                workspace_id,
            )
            if current is None or current["current_version"] is None:
                return PlaybookUpdateOutcome(playbook=None)
            existing_draft = await conn.fetchval(
                "SELECT 1 FROM playbook_version WHERE playbook_id = $1 AND status = 'draft'",
                playbook_id,
            )
            if existing_draft is not None:
                return PlaybookUpdateOutcome(playbook=None, conflict="draft_exists")
            next_version = current["current_version"] + 1
            playbook = await conn.fetchrow(
                "UPDATE playbook "
                "SET current_version = $1, "
                "type = $2, tags = $3, triggers = $4, updated_at = now() "
                "WHERE id = $5 "
                "RETURNING id, workspace_id, owner_id, name, current_version, type, tags, "
                "triggers, locale, created_at, updated_at",
                next_version,
                content.type,
                content.tags,
                content.triggers,
                playbook_id,
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
                playbook["locale"],
            )
        return PlaybookUpdateOutcome(
            playbook=PlaybookRead.model_validate(
                {
                    **dict(playbook),
                    "current_version": next_version,
                    "content": content_json,
                    "current_status": VersionStatus.draft,
                    "has_pending_draft": True,
                }
            )
        )

    async def list_versions(
        self, workspace_id: UUID, playbook_id: UUID
    ) -> list[PlaybookVersionRead] | None:
        return await self._list_versions(workspace_id, playbook_id)

    async def fetch_version(
        self, workspace_id: UUID, playbook_id: UUID, version: int
    ) -> PlaybookVersionRead | None:
        return await self._fetch_version(workspace_id, playbook_id, version)

    async def list_distinct_tags(
        self,
        workspace_id: UUID,
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

        Trigger sind kanonisch kommagetrennt in `playbook.triggers`
        denormalisiert (WP-D1: Modell-Validator + Migration 0063). Wir
        splitten in SQL via `regexp_split_to_array`+`unnest` — defensiv an
        `,` UND `;`, damit auch nicht-normalisierter Legacy-Bestand keine
        Riesen-Trigger liefert —, trimmen leere Eintraege und gruppieren in
        Python: `asyncpg` hat keinen praktischen Weg, JSON-Aggregate ohne
        weitere Decode-Logik zurueckzugeben.

        Sortierung explizit `COLLATE "C"` (Codepoint-Order wie Pythons
        `sorted()`): der API-Contract ist lexikografische Ordnung, aber
        Locale-Collations (z. B. `en_US.utf8`) gewichten `-`/Leerzeichen
        weich und ordnen etwa `agent-drift` vor `agent konfigurieren` —
        das Ergebnis hinge sonst von der DB-Locale ab.
        """
        rows = await self._pool.fetch(
            "SELECT p.id, p.name, trim(t.trigger) AS trigger "
            "  FROM playbook p, "
            "       unnest(regexp_split_to_array(coalesce(p.triggers, ''), '[,;]')) "
            "         AS t(trigger) "
            " WHERE p.workspace_id = $1 "
            "   AND trim(t.trigger) <> '' "
            ' ORDER BY trim(t.trigger) COLLATE "C" ASC, p.name COLLATE "C" ASC',
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
