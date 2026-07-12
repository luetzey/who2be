"""Generische Basis fuer versionierte Aggregat-Repositories (Repo-Review STR-1).

`persona`/`playbook`/`resource` teilen denselben Versionierungs-Kern:
History-Tabelle (ADR-0004), Status pro Version (ADR-0020), pro-Sprache-Tracks
(ADR-0027). Bisher lag dieser Kern dreimal nahezu identisch in den drei
Repos (~1.960 Z.). Diese Basis haelt ihn EINMAL; die Repos werden duenne
Subklassen, die nur ihre entity-spezifischen Lesepfade (Filter/Tags/Triggers)
und — fuer typisierte Rueckgaben — die `update`/`upsert_draft`/`restore_version`-
Wrapper ergaenzen.

Die Tabellennamen werden aus `AggregateTables.entity` abgeleitet und beim
Konstruieren gegen die geteilte `entity_sql`-Whitelist geprueft (Zero-Trust;
die f-String-Interpolation nimmt nie Nutzereingaben — `entity` ist immer ein
internes Literal aus der Subklasse).

Aliase im generierten SQL sind fix: `e` (Identitaet), `ev` (Version), `dv`/`v`
(Subquery-Aliase). Subklassen-SQL, das die `_select_*`-Bausteine einbettet,
muss dieselben Aliase verwenden.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, Literal, TypeVar
from uuid import UUID

import asyncpg
from pydantic import BaseModel

from who2be_api.services.entity_sql import safe_entity
from who2be_models import DEFAULT_LOCALE, VersionStatus

TRead = TypeVar("TRead", bound=BaseModel)
TVersionRead = TypeVar("TVersionRead", bound=BaseModel)

# Schreib-Konflikt aus dem Draft-Workflow: `draft_exists` blockiert PUT/Restore
# bei bereits offenem Draft, `review_pending` blockiert den Auto-Save gegen eine
# Review-Version. Beide werden vom Service in einen 409 uebersetzt.
WriteConflict = Literal["draft_exists", "review_pending"]


@dataclass(frozen=True)
class AggregateTables(Generic[TRead, TVersionRead]):
    """Tabellen-/Modell-Konfiguration eines versionierten Aggregats.

    `entity` (z. B. `"persona"`) bestimmt Identitaets-Tabelle, Versions-Tabelle
    (`{entity}_version`) und FK-Spalte (`{entity}_id`). `read_model` /
    `version_read_model` sind die Pydantic-Klassen fuer das Row→Model-Mapping.
    """

    entity: str
    read_model: type[TRead]
    version_read_model: type[TVersionRead]
    # `has_slug=True` blendet die workspace-eindeutige `slug`-Spalte in alle
    # Lese-/Schreib-Pfade ein (nur Resource; Persona/Playbook haben keine).
    has_slug: bool = False
    version_table: str = field(init=False)
    fk: str = field(init=False)

    def __post_init__(self) -> None:
        # Defense-in-Depth: nur bekannte Inhalts-Tabellen als SQL-Identifier.
        safe_entity(self.entity)
        object.__setattr__(self, "version_table", f"{self.entity}_version")
        object.__setattr__(self, "fk", f"{self.entity}_id")


class VersionedAggregateRepository(Generic[TRead, TVersionRead]):
    """Identischer CRUD-/Versionierungs-Kern fuer persona/playbook/resource.

    Subklassen rufen `super().__init__(pool, AggregateTables(...))` und ergaenzen
    die entity-spezifischen Methoden (`fetch`, `list_by_workspace`,
    `list_distinct_tags`) sowie die typisierten `update`/`upsert_draft`/
    `restore_version`-Wrapper um die `_update`/`_upsert_draft`/`_restore_version`-
    Kerne (die ein `(read_model | None, conflict)`-Tupel liefern).
    """

    def __init__(self, pool: asyncpg.Pool, tables: AggregateTables[TRead, TVersionRead]) -> None:
        self._pool = pool
        self._t = tables

    # --- Slug-aware Spalten-Bausteine ----------------------------------------

    def _slug_select(self) -> str:
        """`e.slug, ` fuer slug-fuehrende Aggregate, sonst leer."""
        return "e.slug, " if self._t.has_slug else ""

    def _returning_cols(self) -> str:
        """Identitaets-RETURNING-Spalten (inkl. `slug` bei slug-Aggregaten)."""
        slug = "slug, " if self._t.has_slug else ""
        return f"id, workspace_id, owner_id, name, {slug}current_version, created_at, updated_at"

    # --- SELECT-Bausteine (von Subklassen-fetch/list eingebettet) ------------

    def _select_current(self, locale_param: str) -> str:
        """Current-Read pro Sprache: hoechste Version des `locale`-Tracks.

        `locale_param` ist der asyncpg-Platzhalter (z. B. `"$3"`), der die Ziel-
        Sprache traegt; er erscheint mehrfach (JOIN + Max-Subquery + Draft-EXISTS).
        """
        e, ev, fk = self._t.entity, self._t.version_table, self._t.fk
        return (
            f"SELECT e.id, e.workspace_id, e.owner_id, e.name, {self._slug_select()}e.is_managed, "
            "ev.version AS current_version, "
            "e.created_at, e.updated_at, ev.content, ev.locale, "
            "ev.status AS current_status, "
            "EXISTS ( "
            f"    SELECT 1 FROM {ev} dv "
            f"    WHERE dv.{fk} = e.id AND dv.locale = {locale_param} AND dv.status = 'draft' "
            ") AS has_pending_draft "
            f"FROM {e} e "
            f"JOIN {ev} ev ON ev.{fk} = e.id AND ev.locale = {locale_param} "
            "  AND ev.version = ( "
            f"      SELECT max(v.version) FROM {ev} v "
            f"      WHERE v.{fk} = e.id AND v.locale = {locale_param} "
            "  ) "
        )

    def _select_active(self, locale_param: str) -> str:
        """Active-Read pro Sprache: die `status='active'`-Version des Tracks."""
        e, ev, fk = self._t.entity, self._t.version_table, self._t.fk
        return (
            f"SELECT e.id, e.workspace_id, e.owner_id, e.name, {self._slug_select()}e.is_managed, "
            "ev.version AS current_version, "
            "e.created_at, e.updated_at, ev.content, ev.locale, "
            "ev.status AS current_status, "
            "EXISTS ( "
            f"    SELECT 1 FROM {ev} dv "
            f"    WHERE dv.{fk} = e.id AND dv.locale = {locale_param} AND dv.status = 'draft' "
            ") AS has_pending_draft "
            f"FROM {e} e "
            f"JOIN {ev} ev ON ev.{fk} = e.id AND ev.locale = {locale_param} "
            "  AND ev.status = 'active' "
        )

    def _build(self, row: asyncpg.Record, **overrides: object) -> TRead:
        """Row + Overrides → Read-Model (zentralisiert das `model_validate`)."""
        return self._t.read_model.model_validate({**dict(row), **overrides})

    # --- Schreib-Kern (identisch ueber alle Aggregate) -----------------------

    async def _insert(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        name: str,
        content: BaseModel,
        locales: list[str] | None = None,
        slug: str | None = None,
    ) -> TRead:
        # Content-i18n: pro gewaehlter Sprache eine eigene Draft-v1 (Copy der
        # Vorlage). Default `['de']` haelt Bestands-Aufrufer kompatibel.
        target_locales = locales or [DEFAULT_LOCALE]
        content_json = content.model_dump(mode="json")
        e, ev, fk = self._t.entity, self._t.version_table, self._t.fk
        async with self._pool.acquire() as conn, conn.transaction():
            if self._t.has_slug:
                # `slug` ist bei slug-fuehrenden Aggregaten Pflicht (der Service
                # leitet ihn aus dem Namen ab); die UNIQUE(workspace_id, slug)
                # meldet Kollisionen als asyncpg.UniqueViolationError.
                row = await conn.fetchrow(
                    f"INSERT INTO {e} (workspace_id, owner_id, name, slug) "
                    "VALUES ($1, $2, $3, $4) "
                    f"RETURNING {self._returning_cols()}",
                    workspace_id,
                    owner_id,
                    name,
                    slug,
                )
            else:
                row = await conn.fetchrow(
                    f"INSERT INTO {e} (workspace_id, owner_id, name) "
                    "VALUES ($1, $2, $3) "
                    f"RETURNING {self._returning_cols()}",
                    workspace_id,
                    owner_id,
                    name,
                )
            for loc in target_locales:
                await conn.execute(
                    f"INSERT INTO {ev} "
                    f"({fk}, version, content, status, created_by, locale) "
                    "VALUES ($1, $2, $3, $4, $5, $6)",
                    row["id"],
                    row["current_version"],
                    content_json,
                    VersionStatus.draft.value,
                    owner_id,
                    loc,
                )
        # Neue v1 startet als Draft (Phase 3-0): die UI rendert sofort die
        # Status-Action-Bar, MCP-Reads ueberspringen sie bis Promotion. Die
        # Antwort spiegelt die erste gewaehlte Sprache.
        return self._build(
            row,
            content=content_json,
            locale=target_locales[0],
            current_status=VersionStatus.draft,
            has_pending_draft=True,
        )

    async def _update(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        entity_id: UUID,
        name: str | None,
        content: BaseModel,
        locale: str,
    ) -> tuple[TRead | None, WriteConflict | None]:
        """PUT-Pfad: neue Version. Active bleibt unangetastet (→ neuer Draft).

        Blockiert mit `draft_exists`, solange irgendein Draft des Tracks offen ist.
        """
        content_json = content.model_dump(mode="json")
        is_default = locale == DEFAULT_LOCALE
        e, ev, fk = self._t.entity, self._t.version_table, self._t.fk
        async with self._pool.acquire() as conn, conn.transaction():
            current = await conn.fetchrow(
                "SELECT ev.version AS current_version, ev.status "
                f"FROM {e} e "
                f"JOIN {ev} ev "
                f"  ON ev.{fk} = e.id AND ev.locale = $3 "
                "  AND ev.version = ( "
                f"      SELECT max(v.version) FROM {ev} v "
                f"      WHERE v.{fk} = e.id AND v.locale = $3 "
                "  ) "
                "WHERE e.id = $1 AND e.workspace_id = $2 FOR UPDATE OF e",
                entity_id,
                workspace_id,
                locale,
            )
            if current is None:
                return None, None
            existing_draft = await conn.fetchval(
                f"SELECT 1 FROM {ev} WHERE {fk} = $1 AND locale = $2 AND status = 'draft'",
                entity_id,
                locale,
            )
            if existing_draft is not None:
                return None, "draft_exists"
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
            row = await conn.fetchrow(
                f"UPDATE {e} "
                "SET current_version = CASE WHEN $4 THEN $1 ELSE current_version END, "
                "name = COALESCE($2, name), updated_at = now() "
                "WHERE id = $3 "
                f"RETURNING {self._returning_cols()}",
                next_version,
                name,
                entity_id,
                is_default,
            )
            await conn.execute(
                f"INSERT INTO {ev} "
                f"({fk}, version, content, status, created_by, locale) "
                "VALUES ($1, $2, $3, $4, $5, $6)",
                entity_id,
                next_version,
                content_json,
                new_status.value,
                owner_id,
                locale,
            )
        built = self._build(
            row,
            current_version=next_version,
            locale=locale,
            content=content_json,
            current_status=new_status,
            has_pending_draft=new_status == VersionStatus.draft,
        )
        return built, None

    async def _upsert_draft(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        entity_id: UUID,
        name: str | None,
        content: BaseModel,
        locale: str,
    ) -> tuple[TRead | None, WriteConflict | None]:
        """Auto-Save-Pfad (PATCH `.../draft`), jeweils pro Sprache.

        - Existiert ein Draft, wird die Draft-Row in-place ueberschrieben —
          kein Versions-Increment. Active bleibt unangetastet.
        - Existiert kein Draft, wird ein neuer Draft v(n+1) angelegt.
        - Edge-Case `current_status='review'` ohne offenen Draft: `review_pending`.
        """
        content_json = content.model_dump(mode="json")
        is_default = locale == DEFAULT_LOCALE
        e, ev, fk = self._t.entity, self._t.version_table, self._t.fk
        async with self._pool.acquire() as conn, conn.transaction():
            current = await conn.fetchrow(
                "SELECT ev.version AS current_version, ev.status "
                f"FROM {e} e "
                f"JOIN {ev} ev "
                f"  ON ev.{fk} = e.id AND ev.locale = $3 "
                "  AND ev.version = ( "
                f"      SELECT max(v.version) FROM {ev} v "
                f"      WHERE v.{fk} = e.id AND v.locale = $3 "
                "  ) "
                "WHERE e.id = $1 AND e.workspace_id = $2 FOR UPDATE OF e",
                entity_id,
                workspace_id,
                locale,
            )
            if current is None:
                return None, None
            draft_version = await conn.fetchval(
                f"SELECT version FROM {ev} WHERE {fk} = $1 AND locale = $2 AND status = 'draft'",
                entity_id,
                locale,
            )
            if draft_version is not None:
                row = await conn.fetchrow(
                    f"UPDATE {e} "
                    "SET name = COALESCE($1, name), updated_at = now() "
                    "WHERE id = $2 "
                    f"RETURNING {self._returning_cols()}",
                    name,
                    entity_id,
                )
                await conn.execute(
                    f"UPDATE {ev} SET content = $1, created_by = $2 "
                    f"WHERE {fk} = $3 AND locale = $4 AND version = $5",
                    content_json,
                    owner_id,
                    entity_id,
                    locale,
                    draft_version,
                )
                built = self._build(
                    row,
                    current_version=draft_version,
                    locale=locale,
                    content=content_json,
                    current_status=VersionStatus.draft,
                    has_pending_draft=True,
                )
                return built, None
            if current["status"] == VersionStatus.review.value:
                return None, "review_pending"
            next_version = current["current_version"] + 1
            row = await conn.fetchrow(
                f"UPDATE {e} "
                "SET current_version = CASE WHEN $4 THEN $1 ELSE current_version END, "
                "name = COALESCE($2, name), updated_at = now() "
                "WHERE id = $3 "
                f"RETURNING {self._returning_cols()}",
                next_version,
                name,
                entity_id,
                is_default,
            )
            await conn.execute(
                f"INSERT INTO {ev} "
                f"({fk}, version, content, status, created_by, locale) "
                "VALUES ($1, $2, $3, $4, $5, $6)",
                entity_id,
                next_version,
                content_json,
                VersionStatus.draft.value,
                owner_id,
                locale,
            )
        built = self._build(
            row,
            current_version=next_version,
            locale=locale,
            content=content_json,
            current_status=VersionStatus.draft,
            has_pending_draft=True,
        )
        return built, None

    async def _restore_version(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        entity_id: UUID,
        content: BaseModel,
        locale: str,
    ) -> tuple[TRead | None, WriteConflict | None]:
        """Schreibt `content` (Snapshot) als neue Draft-Version (Track A §3.1).

        Non-destruktiv: frische Draft v(n+1) im `locale`-Track, kein Pointer-
        Reset. `draft_exists` bei bereits offenem Draft. Name bleibt unveraendert.
        """
        content_json = content.model_dump(mode="json")
        is_default = locale == DEFAULT_LOCALE
        e, ev, fk = self._t.entity, self._t.version_table, self._t.fk
        async with self._pool.acquire() as conn, conn.transaction():
            current = await conn.fetchrow(
                # Per-locale Max-Version als Scalar-Subquery — Postgres erlaubt
                # `FOR UPDATE` nicht zusammen mit `GROUP BY`. Die Sperre liegt
                # auf der Identitaets-Zeile; current_version ist NULL, wenn fuer
                # die Sprache (noch) keine Version existiert.
                f"SELECT (SELECT max(v.version) FROM {ev} v "
                f"        WHERE v.{fk} = e.id AND v.locale = $3) AS current_version "
                f"FROM {e} e "
                "WHERE e.id = $1 AND e.workspace_id = $2 "
                "FOR UPDATE",
                entity_id,
                workspace_id,
                locale,
            )
            if current is None or current["current_version"] is None:
                return None, None
            existing_draft = await conn.fetchval(
                f"SELECT 1 FROM {ev} WHERE {fk} = $1 AND locale = $2 AND status = 'draft'",
                entity_id,
                locale,
            )
            if existing_draft is not None:
                return None, "draft_exists"
            next_version = current["current_version"] + 1
            row = await conn.fetchrow(
                f"UPDATE {e} SET "
                "current_version = CASE WHEN $3 THEN $1 ELSE current_version END, "
                "updated_at = now() "
                "WHERE id = $2 "
                f"RETURNING {self._returning_cols()}",
                next_version,
                entity_id,
                is_default,
            )
            await conn.execute(
                f"INSERT INTO {ev} "
                f"({fk}, version, content, status, created_by, locale) "
                "VALUES ($1, $2, $3, $4, $5, $6)",
                entity_id,
                next_version,
                content_json,
                VersionStatus.draft.value,
                owner_id,
                locale,
            )
        built = self._build(
            row,
            current_version=next_version,
            locale=locale,
            content=content_json,
            current_status=VersionStatus.draft,
            has_pending_draft=True,
        )
        return built, None

    # --- Managed-Lock + Versions-Lesepfade + Delete (identisch) --------------

    async def is_managed(self, workspace_id: UUID, entity_id: UUID) -> bool:
        """True, wenn das Aggregat vom System verwaltet ist (Builder-Lock)."""
        val = await self._pool.fetchval(
            f"SELECT is_managed FROM {self._t.entity} WHERE id = $1 AND workspace_id = $2",
            entity_id,
            workspace_id,
        )
        return bool(val)

    async def _list_versions(
        self, workspace_id: UUID, entity_id: UUID, locale: str = DEFAULT_LOCALE
    ) -> list[TVersionRead] | None:
        e, ev, fk = self._t.entity, self._t.version_table, self._t.fk
        owned = await self._pool.fetchval(
            f"SELECT 1 FROM {e} WHERE id = $1 AND workspace_id = $2",
            entity_id,
            workspace_id,
        )
        if owned is None:
            return None
        rows = await self._pool.fetch(
            "SELECT version, status, locale, content, created_by, created_at "
            f"FROM {ev} WHERE {fk} = $1 AND locale = $2 "
            "ORDER BY version DESC",
            entity_id,
            locale,
        )
        return [self._t.version_read_model.model_validate(dict(row)) for row in rows]

    async def _fetch_version(
        self, workspace_id: UUID, entity_id: UUID, version: int, locale: str = DEFAULT_LOCALE
    ) -> TVersionRead | None:
        e, ev, fk = self._t.entity, self._t.version_table, self._t.fk
        row = await self._pool.fetchrow(
            "SELECT ev.version, ev.status, ev.locale, ev.content, ev.created_by, ev.created_at "
            f"FROM {ev} ev "
            f"JOIN {e} e ON e.id = ev.{fk} "
            "WHERE e.id = $1 AND e.workspace_id = $2 AND ev.version = $3 AND ev.locale = $4",
            entity_id,
            workspace_id,
            version,
            locale,
        )
        if row is None:
            return None
        return self._t.version_read_model.model_validate(dict(row))

    async def _delete(self, workspace_id: UUID, entity_id: UUID) -> bool:
        """Hard-Delete der Identitaets-Zeile (ADR-0032), workspace-scoped.

        Die FK-Kaskaden raeumen Versionen und ausgehende Links automatisch ab;
        eingehende Referenzen werden im Service vorab als 409 abgefangen.
        """
        e = self._t.entity
        async with self._pool.acquire() as conn, conn.transaction():
            result = await conn.execute(
                f"DELETE FROM {e} WHERE id = $1 AND workspace_id = $2",
                entity_id,
                workspace_id,
            )
        # asyncpg gibt "DELETE <n>" zurueck; n=0 wenn nichts geloescht wurde.
        return bool(result.split()[-1] != "0")
