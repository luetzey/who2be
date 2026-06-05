"""Persistenz fuer das Persona-Aggregat (`persona` + `persona_version`).

Versionierung ueber eine History-Tabelle (ADR-0004): `insert` und `update`
schreiben Identitaets-Zeile und Versions-Snapshot in einer Transaktion.
Verantwortung: SQL + Row↔Model-Mapping, keine Geschaeftsregeln.

Phase 2.1a-2: Filter laufen ueber `workspace_id` statt `owner_id`. `owner_id`
bleibt als Audit-Spalte (`created_by`) und wird beim INSERT mitgeschrieben.

Phase 2.1b: Status-Felder (`current_status`, `has_pending_draft`) werden im
SELECT-Pfad mitgelesen. `update` erzwingt Draft-on-Edit, wenn die aktuelle
Version `active` ist (Plan §2.1.C). `active_only=True` filtert in den
Lese-Pfaden auf `status='active'` und liefert die Active-Version als
Current — Pfad fuer den MCP-Server (Plan §2.1.D).

Content-i18n (ADR-0027, Stream D2): jede Version traegt ein `locale`-Kuerzel;
pro Sprache laeuft ein eigener Versions-Track. Die "aktuelle" Version einer
Sprache ist die hoechste `version` mit diesem `locale` (statt der einzelnen
`persona.current_version`-Spalte, die nur noch den Default-Locale-Track
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
    PersonaRead,
    PersonaVersionContent,
    PersonaVersionRead,
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
        "SELECT p.id, p.workspace_id, p.owner_id, p.name, "
        "pv.version AS current_version, "
        "p.created_at, p.updated_at, pv.content, pv.locale, "
        "pv.status AS current_status, "
        "EXISTS ( "
        "    SELECT 1 FROM persona_version dv "
        f"    WHERE dv.persona_id = p.id AND dv.locale = {locale_param} AND dv.status = 'draft' "
        ") AS has_pending_draft "
        "FROM persona p "
        f"JOIN persona_version pv ON pv.persona_id = p.id AND pv.locale = {locale_param} "
        "  AND pv.version = ( "
        "      SELECT max(v.version) FROM persona_version v "
        f"      WHERE v.persona_id = p.id AND v.locale = {locale_param} "
        "  ) "
    )


def _select_active(locale_param: str) -> str:
    """Active-Read pro Sprache: die `status='active'`-Version des Tracks."""
    return (
        "SELECT p.id, p.workspace_id, p.owner_id, p.name, "
        "pv.version AS current_version, "
        "p.created_at, p.updated_at, pv.content, pv.locale, "
        "pv.status AS current_status, "
        "EXISTS ( "
        "    SELECT 1 FROM persona_version dv "
        f"    WHERE dv.persona_id = p.id AND dv.locale = {locale_param} AND dv.status = 'draft' "
        ") AS has_pending_draft "
        "FROM persona p "
        f"JOIN persona_version pv ON pv.persona_id = p.id AND pv.locale = {locale_param} "
        "  AND pv.status = 'active' "
    )


@dataclass(frozen=True)
class PersonaUpdateOutcome:
    """Ergebnis eines `update`- oder `upsert_draft`-Aufrufs.

    `conflict='draft_exists'` markiert den PUT-Pfad bei bereits offenem Draft;
    `conflict='review_pending'` markiert den PATCH-Pfad gegen eine Review-
    Version (auto-save darf einen Review-Snapshot nicht ueberschreiben). In
    beiden Faellen ist `persona=None`. `conflict=None` und `persona=None`
    heisst "nicht gefunden" (→ 404).
    """

    persona: PersonaRead | None
    conflict: Literal["draft_exists", "review_pending"] | None = None


class PersonaRepository(Protocol):
    """Service-seitige Abstraktion fuer den Persona-Zugriff."""

    async def insert(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        name: str,
        content: PersonaVersionContent,
        locales: list[str] | None = None,
    ) -> PersonaRead: ...

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        limit: int,
        after: tuple[datetime, UUID] | None,
        active_only: bool = False,
        locale: str = DEFAULT_LOCALE,
    ) -> list[PersonaRead]: ...

    async def fetch(
        self,
        workspace_id: UUID,
        persona_id: UUID,
        active_only: bool = False,
        locale: str = DEFAULT_LOCALE,
    ) -> PersonaRead | None: ...

    async def update(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        persona_id: UUID,
        name: str | None,
        content: PersonaVersionContent,
        locale: str = DEFAULT_LOCALE,
    ) -> PersonaUpdateOutcome: ...

    async def upsert_draft(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        persona_id: UUID,
        name: str | None,
        content: PersonaVersionContent,
        locale: str = DEFAULT_LOCALE,
    ) -> PersonaUpdateOutcome: ...

    async def restore_version(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        persona_id: UUID,
        content: PersonaVersionContent,
        locale: str = DEFAULT_LOCALE,
    ) -> PersonaUpdateOutcome: ...

    async def list_versions(
        self, workspace_id: UUID, persona_id: UUID, locale: str = DEFAULT_LOCALE
    ) -> list[PersonaVersionRead] | None: ...

    async def fetch_version(
        self, workspace_id: UUID, persona_id: UUID, version: int, locale: str = DEFAULT_LOCALE
    ) -> PersonaVersionRead | None: ...

    async def list_distinct_tags(
        self, workspace_id: UUID, locale: str = DEFAULT_LOCALE
    ) -> list[str]: ...


class PgPersonaRepository:
    """asyncpg-Implementierung von `PersonaRepository`."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def insert(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        name: str,
        content: PersonaVersionContent,
        locales: list[str] | None = None,
    ) -> PersonaRead:
        # Content-i18n: pro gewaehlter Sprache eine eigene Draft-v1 (Copy der
        # Vorlage). Default `['de']` haelt Bestands-Aufrufer kompatibel.
        target_locales = locales or [DEFAULT_LOCALE]
        content_json = content.model_dump(mode="json")
        async with self._pool.acquire() as conn, conn.transaction():
            persona = await conn.fetchrow(
                "INSERT INTO persona (workspace_id, owner_id, name) "
                "VALUES ($1, $2, $3) "
                "RETURNING id, workspace_id, owner_id, name, current_version, "
                "created_at, updated_at",
                workspace_id,
                owner_id,
                name,
            )
            for loc in target_locales:
                await conn.execute(
                    "INSERT INTO persona_version "
                    "(persona_id, version, content, status, created_by, locale) "
                    "VALUES ($1, $2, $3, $4, $5, $6)",
                    persona["id"],
                    persona["current_version"],
                    content_json,
                    VersionStatus.draft.value,
                    owner_id,
                    loc,
                )
        # Neue v1 startet als Draft (Phase 3-0): die UI rendert sofort die
        # Status-Action-Bar, MCP-Reads ueberspringen sie bis Promotion. Die
        # Antwort spiegelt die erste gewaehlte Sprache.
        return PersonaRead.model_validate(
            {
                **dict(persona),
                "content": content_json,
                "locale": target_locales[0],
                "current_status": VersionStatus.draft,
                "has_pending_draft": True,
            }
        )

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        limit: int,
        after: tuple[datetime, UUID] | None,
        active_only: bool = False,
        locale: str = DEFAULT_LOCALE,
    ) -> list[PersonaRead]:
        builder = _select_active if active_only else _select_current
        # Tie-Breaker auf `id` haelt die Sortierung stabil, wenn zwei Rows
        # auf die Microsekunde gleichzeitig angelegt wurden.
        if after is None:
            select = builder("$3")
            rows = await self._pool.fetch(
                f"{select} WHERE p.workspace_id = $1 "
                "ORDER BY p.created_at DESC, p.id DESC LIMIT $2",
                workspace_id,
                limit,
                locale,
            )
        else:
            select = builder("$5")
            rows = await self._pool.fetch(
                f"{select} WHERE p.workspace_id = $1 "
                "AND (p.created_at, p.id) < ($2, $3) "
                "ORDER BY p.created_at DESC, p.id DESC LIMIT $4",
                workspace_id,
                after[0],
                after[1],
                limit,
                locale,
            )
        return [PersonaRead.model_validate(dict(row)) for row in rows]

    async def fetch(
        self,
        workspace_id: UUID,
        persona_id: UUID,
        active_only: bool = False,
        locale: str = DEFAULT_LOCALE,
    ) -> PersonaRead | None:
        builder = _select_active if active_only else _select_current
        select = builder("$3")
        row = await self._pool.fetchrow(
            f"{select} WHERE p.id = $1 AND p.workspace_id = $2",
            persona_id,
            workspace_id,
            locale,
        )
        return PersonaRead.model_validate(dict(row)) if row is not None else None

    async def update(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        persona_id: UUID,
        name: str | None,
        content: PersonaVersionContent,
        locale: str = DEFAULT_LOCALE,
    ) -> PersonaUpdateOutcome:
        content_json = content.model_dump(mode="json")
        is_default = locale == DEFAULT_LOCALE
        async with self._pool.acquire() as conn, conn.transaction():
            current = await conn.fetchrow(
                "SELECT pv.version AS current_version, pv.status "
                "FROM persona p "
                "JOIN persona_version pv "
                "  ON pv.persona_id = p.id AND pv.locale = $3 "
                "  AND pv.version = ( "
                "      SELECT max(v.version) FROM persona_version v "
                "      WHERE v.persona_id = p.id AND v.locale = $3 "
                "  ) "
                "WHERE p.id = $1 AND p.workspace_id = $2 FOR UPDATE OF p",
                persona_id,
                workspace_id,
                locale,
            )
            if current is None:
                return PersonaUpdateOutcome(persona=None)
            # Solange irgendein Draft (in dieser Sprache) existiert, blockiert
            # PUT: der Caller soll erst Promote/Discard durchspielen.
            existing_draft = await conn.fetchval(
                "SELECT 1 FROM persona_version "
                "WHERE persona_id = $1 AND locale = $2 AND status = 'draft'",
                persona_id,
                locale,
            )
            if existing_draft is not None:
                return PersonaUpdateOutcome(persona=None, conflict="draft_exists")
            next_version = current["current_version"] + 1
            new_status: VersionStatus
            if current["status"] == VersionStatus.active.value:
                # Active-Version bleibt unangetastet; neue Version startet als
                # Draft (Plan §2.1.C — "Active-Version bleibt unangetastet").
                new_status = VersionStatus.draft
            else:
                # Bestandsverhalten: neue Version uebernimmt DB-Default
                # `'inactive'`. Status-Wechsel laeuft separat ueber die
                # Transition-API.
                new_status = VersionStatus.inactive
            persona = await conn.fetchrow(
                "UPDATE persona "
                "SET current_version = CASE WHEN $4 THEN $1 ELSE current_version END, "
                "name = COALESCE($2, name), updated_at = now() "
                "WHERE id = $3 "
                "RETURNING id, workspace_id, owner_id, name, current_version, "
                "created_at, updated_at",
                next_version,
                name,
                persona_id,
                is_default,
            )
            await conn.execute(
                "INSERT INTO persona_version "
                "(persona_id, version, content, status, created_by, locale) "
                "VALUES ($1, $2, $3, $4, $5, $6)",
                persona_id,
                next_version,
                content_json,
                new_status.value,
                owner_id,
                locale,
            )
        return PersonaUpdateOutcome(
            persona=PersonaRead.model_validate(
                {
                    **dict(persona),
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
        persona_id: UUID,
        name: str | None,
        content: PersonaVersionContent,
        locale: str = DEFAULT_LOCALE,
    ) -> PersonaUpdateOutcome:
        """Auto-Save-Pfad (PATCH `.../draft`).

        Verhalten (jeweils pro Sprache):
        - Existiert ein Draft, wird die Draft-Row in-place ueberschrieben —
          kein Versions-Increment. Active bleibt unangetastet.
        - Existiert kein Draft, wird ein neuer Draft v(n+1) angelegt.
        - Edge-Case `current_status='review'` ohne offenen Draft: 409.
        """
        content_json = content.model_dump(mode="json")
        is_default = locale == DEFAULT_LOCALE
        async with self._pool.acquire() as conn, conn.transaction():
            current = await conn.fetchrow(
                "SELECT pv.version AS current_version, pv.status "
                "FROM persona p "
                "JOIN persona_version pv "
                "  ON pv.persona_id = p.id AND pv.locale = $3 "
                "  AND pv.version = ( "
                "      SELECT max(v.version) FROM persona_version v "
                "      WHERE v.persona_id = p.id AND v.locale = $3 "
                "  ) "
                "WHERE p.id = $1 AND p.workspace_id = $2 FOR UPDATE OF p",
                persona_id,
                workspace_id,
                locale,
            )
            if current is None:
                return PersonaUpdateOutcome(persona=None)
            draft_version = await conn.fetchval(
                "SELECT version FROM persona_version "
                "WHERE persona_id = $1 AND locale = $2 AND status = 'draft'",
                persona_id,
                locale,
            )
            if draft_version is not None:
                persona = await conn.fetchrow(
                    "UPDATE persona "
                    "SET name = COALESCE($1, name), updated_at = now() "
                    "WHERE id = $2 "
                    "RETURNING id, workspace_id, owner_id, name, current_version, "
                    "created_at, updated_at",
                    name,
                    persona_id,
                )
                await conn.execute(
                    "UPDATE persona_version SET content = $1, created_by = $2 "
                    "WHERE persona_id = $3 AND locale = $4 AND version = $5",
                    content_json,
                    owner_id,
                    persona_id,
                    locale,
                    draft_version,
                )
                return PersonaUpdateOutcome(
                    persona=PersonaRead.model_validate(
                        {
                            **dict(persona),
                            "current_version": draft_version,
                            "locale": locale,
                            "content": content_json,
                            "current_status": VersionStatus.draft,
                            "has_pending_draft": True,
                        }
                    )
                )
            if current["status"] == VersionStatus.review.value:
                return PersonaUpdateOutcome(persona=None, conflict="review_pending")
            next_version = current["current_version"] + 1
            persona = await conn.fetchrow(
                "UPDATE persona "
                "SET current_version = CASE WHEN $4 THEN $1 ELSE current_version END, "
                "name = COALESCE($2, name), updated_at = now() "
                "WHERE id = $3 "
                "RETURNING id, workspace_id, owner_id, name, current_version, "
                "created_at, updated_at",
                next_version,
                name,
                persona_id,
                is_default,
            )
            await conn.execute(
                "INSERT INTO persona_version "
                "(persona_id, version, content, status, created_by, locale) "
                "VALUES ($1, $2, $3, $4, $5, $6)",
                persona_id,
                next_version,
                content_json,
                VersionStatus.draft.value,
                owner_id,
                locale,
            )
        return PersonaUpdateOutcome(
            persona=PersonaRead.model_validate(
                {
                    **dict(persona),
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
        persona_id: UUID,
        content: PersonaVersionContent,
        locale: str = DEFAULT_LOCALE,
    ) -> PersonaUpdateOutcome:
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
                # `FOR UPDATE` nicht zusammen mit `GROUP BY`. Die Sperre liegt
                # auf der Identitaets-Zeile `persona`; current_version ist NULL,
                # wenn fuer die Sprache (noch) keine Version existiert.
                "SELECT (SELECT max(v.version) FROM persona_version v "
                "        WHERE v.persona_id = p.id AND v.locale = $3) AS current_version "
                "FROM persona p "
                "WHERE p.id = $1 AND p.workspace_id = $2 "
                "FOR UPDATE",
                persona_id,
                workspace_id,
                locale,
            )
            if current is None or current["current_version"] is None:
                return PersonaUpdateOutcome(persona=None)
            existing_draft = await conn.fetchval(
                "SELECT 1 FROM persona_version "
                "WHERE persona_id = $1 AND locale = $2 AND status = 'draft'",
                persona_id,
                locale,
            )
            if existing_draft is not None:
                return PersonaUpdateOutcome(persona=None, conflict="draft_exists")
            next_version = current["current_version"] + 1
            persona = await conn.fetchrow(
                "UPDATE persona SET "
                "current_version = CASE WHEN $3 THEN $1 ELSE current_version END, "
                "updated_at = now() "
                "WHERE id = $2 "
                "RETURNING id, workspace_id, owner_id, name, current_version, "
                "created_at, updated_at",
                next_version,
                persona_id,
                is_default,
            )
            await conn.execute(
                "INSERT INTO persona_version "
                "(persona_id, version, content, status, created_by, locale) "
                "VALUES ($1, $2, $3, $4, $5, $6)",
                persona_id,
                next_version,
                content_json,
                VersionStatus.draft.value,
                owner_id,
                locale,
            )
        return PersonaUpdateOutcome(
            persona=PersonaRead.model_validate(
                {
                    **dict(persona),
                    "current_version": next_version,
                    "locale": locale,
                    "content": content_json,
                    "current_status": VersionStatus.draft,
                    "has_pending_draft": True,
                }
            )
        )

    async def list_versions(
        self, workspace_id: UUID, persona_id: UUID, locale: str = DEFAULT_LOCALE
    ) -> list[PersonaVersionRead] | None:
        owned = await self._pool.fetchval(
            "SELECT 1 FROM persona WHERE id = $1 AND workspace_id = $2",
            persona_id,
            workspace_id,
        )
        if owned is None:
            return None
        rows = await self._pool.fetch(
            "SELECT version, status, locale, content, created_by, created_at "
            "FROM persona_version WHERE persona_id = $1 AND locale = $2 "
            "ORDER BY version DESC",
            persona_id,
            locale,
        )
        return [PersonaVersionRead.model_validate(dict(row)) for row in rows]

    async def fetch_version(
        self, workspace_id: UUID, persona_id: UUID, version: int, locale: str = DEFAULT_LOCALE
    ) -> PersonaVersionRead | None:
        row = await self._pool.fetchrow(
            "SELECT pv.version, pv.status, pv.locale, pv.content, pv.created_by, pv.created_at "
            "FROM persona_version pv "
            "JOIN persona p ON p.id = pv.persona_id "
            "WHERE p.id = $1 AND p.workspace_id = $2 AND pv.version = $3 AND pv.locale = $4",
            persona_id,
            workspace_id,
            version,
            locale,
        )
        return PersonaVersionRead.model_validate(dict(row)) if row is not None else None

    async def list_distinct_tags(
        self, workspace_id: UUID, locale: str = DEFAULT_LOCALE
    ) -> list[str]:
        """DISTINCT alle Persona-Tags des Workspaces, lexikografisch sortiert.

        Persona-Tags liegen — anders als bei Playbooks — nicht denormalisiert
        auf der Identitaets-Zeile, sondern im JSON der aktuellen Version
        (`persona_version.content->'tags'`). Wir lesen daher per Lateral-Join
        ueber die Current-Version (= hoechste Version des `locale`-Tracks) jeder
        Persona im Workspace. Historische Versions-Snapshots tragen nicht bei.
        Cross-Workspace-Isolation ueber den `workspace_id`-Filter.
        """
        rows = await self._pool.fetch(
            "SELECT DISTINCT tag "
            "FROM persona p "
            "JOIN persona_version pv "
            "  ON pv.persona_id = p.id AND pv.locale = $2 "
            "  AND pv.version = ( "
            "      SELECT max(v.version) FROM persona_version v "
            "      WHERE v.persona_id = p.id AND v.locale = $2 "
            "  ) "
            "CROSS JOIN LATERAL jsonb_array_elements_text(pv.content->'tags') AS tag "
            "WHERE p.workspace_id = $1 "
            "ORDER BY tag ASC",
            workspace_id,
            locale,
        )
        return [row["tag"] for row in rows]
