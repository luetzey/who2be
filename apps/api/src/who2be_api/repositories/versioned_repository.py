"""Generische Basis fuer versionierte Aggregat-Repositories (Repo-Review STR-1).

`persona`/`playbook`/`resource` teilen denselben Versionierungs-Kern:
History-Tabelle (ADR-0004), Status pro Version (ADR-0020). Bisher lag dieser
Kern dreimal nahezu identisch in den drei Repos (~1.960 Z.). Diese Basis haelt
ihn EINMAL; die Repos werden duenne Subklassen, die nur ihre entity-
spezifischen Lesepfade (Filter/Tags/Triggers) und — fuer typisierte
Rueckgaben — die `update`/`upsert_draft`/`restore_version`-Wrapper ergaenzen.

„Ein Element, eine Sprache" (ADR-0045, Plan 2026-07-24): `locale` lebt auf der
Identitaets-Zeile — Reads sind locale-agnostisch (die aktive Version ist die
per-entity eindeutige `status='active'`-Row, die aktuelle die globale
Max-Version), Versions-Writes uebernehmen die Entity-Sprache, und
`next_version` wird GLOBAL ueber alle locales berechnet (Legacy-Daten aus dem
ADR-0027-Multi-Track koennen z. B. DE-v1 UND EN-v1 tragen — der Tie-Break
`ORDER BY version DESC, (locale = e.locale) DESC` haelt solche Reads
deterministisch). Ein gesetztes Update-`locale` ist ein Metadaten-Update der
Entity-Sprache; die Versions-Historie behaelt ihre alten locale-Werte.

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

from who2be_api.core.entity_sql import safe_entity
from who2be_models import VersionStatus

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
    # `has_slug=True` blendet eine workspace-eindeutige Identitaets-Spalte in
    # alle Lese-/Schreib-Pfade ein (Resource: `slug`; ExternalTool: `alias` —
    # `slug_column` waehlt den physischen Spaltennamen, Persona/Playbook haben
    # keine).
    has_slug: bool = False
    slug_column: str = "slug"
    version_table: str = field(init=False)
    fk: str = field(init=False)

    def __post_init__(self) -> None:
        # Defense-in-Depth: nur bekannte Inhalts-Tabellen als SQL-Identifier.
        safe_entity(self.entity)
        if self.has_slug and self.slug_column not in {"slug", "alias"}:
            raise ValueError(f"Unbekannte Slug-Spalte: {self.slug_column!r}")
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
        """`e.<slug_column>, ` fuer slug-fuehrende Aggregate, sonst leer."""
        return f"e.{self._t.slug_column}, " if self._t.has_slug else ""

    def _returning_cols(self) -> str:
        """Identitaets-RETURNING-Spalten (inkl. Slug-Spalte bei slug-Aggregaten)."""
        slug = f"{self._t.slug_column}, " if self._t.has_slug else ""
        return (
            f"id, workspace_id, owner_id, name, {slug}locale, "
            "current_version, created_at, updated_at"
        )

    # --- SELECT-Bausteine (von Subklassen-fetch/list eingebettet) ------------

    def _select_current(self) -> str:
        """Current-Read (locale-agnostisch): die global hoechste Version.

        Legacy-Tie-Break: Alt-Daten aus dem ADR-0027-Multi-Track koennen
        dieselbe Versionsnummer in zwei Sprachen tragen — bevorzugt wird
        deterministisch die Row in der Entity-Sprache.
        """
        e, ev, fk = self._t.entity, self._t.version_table, self._t.fk
        return (
            f"SELECT e.id, e.workspace_id, e.owner_id, e.name, {self._slug_select()}e.is_managed, "
            "ev.version AS current_version, "
            "e.created_at, e.updated_at, ev.content, e.locale, "
            "ev.status AS current_status, "
            "EXISTS ( "
            f"    SELECT 1 FROM {ev} dv "
            f"    WHERE dv.{fk} = e.id AND dv.status = 'draft' "
            ") AS has_pending_draft "
            f"FROM {e} e "
            "JOIN LATERAL ( "
            f"    SELECT v.version, v.status, v.content FROM {ev} v "
            f"    WHERE v.{fk} = e.id "
            "    ORDER BY v.version DESC, (v.locale = e.locale) DESC "
            "    LIMIT 1 "
            ") ev ON TRUE "
        )

    def _select_active(self) -> str:
        """Active-Read: die per-entity eindeutige `status='active'`-Version."""
        e, ev, fk = self._t.entity, self._t.version_table, self._t.fk
        return (
            f"SELECT e.id, e.workspace_id, e.owner_id, e.name, {self._slug_select()}e.is_managed, "
            "ev.version AS current_version, "
            "e.created_at, e.updated_at, ev.content, e.locale, "
            "ev.status AS current_status, "
            "EXISTS ( "
            f"    SELECT 1 FROM {ev} dv "
            f"    WHERE dv.{fk} = e.id AND dv.status = 'draft' "
            ") AS has_pending_draft "
            f"FROM {e} e "
            f"JOIN {ev} ev ON ev.{fk} = e.id AND ev.status = 'active' "
        )

    def _build(self, row: asyncpg.Record, **overrides: object) -> TRead:
        """Row + Overrides → Read-Model (zentralisiert das `model_validate`)."""
        return self._t.read_model.model_validate({**dict(row), **overrides})

    def _current_version_sql(self) -> str:
        """Locked Current-Read fuer die Schreib-Pfade: globale Max-Version.

        Die Sperre liegt auf der Identitaets-Zeile (`FOR UPDATE OF e`);
        `next_version` = Ergebnis + 1 (globaler Zaehler ueber alle locales).
        """
        e, ev, fk = self._t.entity, self._t.version_table, self._t.fk
        return (
            "SELECT ev.version AS current_version, ev.status "
            f"FROM {e} e "
            "JOIN LATERAL ( "
            f"    SELECT v.version, v.status FROM {ev} v "
            f"    WHERE v.{fk} = e.id "
            "    ORDER BY v.version DESC, (v.locale = e.locale) DESC "
            "    LIMIT 1 "
            ") ev ON TRUE "
            "WHERE e.id = $1 AND e.workspace_id = $2 FOR UPDATE OF e"
        )

    # --- Schreib-Kern (identisch ueber alle Aggregate) -----------------------

    async def _insert(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        name: str,
        content: BaseModel,
        locale: str,
        slug: str | None = None,
    ) -> TRead:
        """Legt die Identitaets-Zeile (inkl. Entity-Sprache) + Draft-v1 an."""
        content_json = content.model_dump(mode="json")
        e, ev, fk = self._t.entity, self._t.version_table, self._t.fk
        async with self._pool.acquire() as conn, conn.transaction():
            if self._t.has_slug:
                # Die Slug-Spalte ist bei slug-fuehrenden Aggregaten Pflicht (der
                # Service leitet sie aus dem Namen ab); der partielle
                # UNIQUE-Index (workspace_id, <slug_column>) meldet Kollisionen
                # als asyncpg.UniqueViolationError.
                row = await conn.fetchrow(
                    f"INSERT INTO {e} (workspace_id, owner_id, name, locale, "
                    f"{self._t.slug_column}) "
                    "VALUES ($1, $2, $3, $4, $5) "
                    f"RETURNING {self._returning_cols()}",
                    workspace_id,
                    owner_id,
                    name,
                    locale,
                    slug,
                )
            else:
                row = await conn.fetchrow(
                    f"INSERT INTO {e} (workspace_id, owner_id, name, locale) "
                    "VALUES ($1, $2, $3, $4) "
                    f"RETURNING {self._returning_cols()}",
                    workspace_id,
                    owner_id,
                    name,
                    locale,
                )
            await conn.execute(
                f"INSERT INTO {ev} "
                f"({fk}, version, content, status, created_by, locale) "
                "VALUES ($1, $2, $3, $4, $5, $6)",
                row["id"],
                row["current_version"],
                content_json,
                VersionStatus.draft.value,
                owner_id,
                locale,
            )
        # Neue v1 startet als Draft (Phase 3-0): die UI rendert sofort die
        # Status-Action-Bar, MCP-Reads ueberspringen sie bis Promotion.
        return self._build(
            row,
            content=content_json,
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
        new_locale: str | None = None,
    ) -> tuple[TRead | None, WriteConflict | None]:
        """PUT-Pfad: neue Version. Active bleibt unangetastet (→ neuer Draft).

        Blockiert mit `draft_exists`, solange irgendein Draft offen ist.
        `new_locale` (gesetzt) wechselt die Entity-Sprache (Metadaten-Update);
        die neue Versions-Row uebernimmt die (ggf. neue) Entity-Sprache.
        """
        content_json = content.model_dump(mode="json")
        e, ev, fk = self._t.entity, self._t.version_table, self._t.fk
        async with self._pool.acquire() as conn, conn.transaction():
            current = await conn.fetchrow(
                self._current_version_sql(),
                entity_id,
                workspace_id,
            )
            if current is None:
                return None, None
            existing_draft = await conn.fetchval(
                f"SELECT 1 FROM {ev} WHERE {fk} = $1 AND status = 'draft'",
                entity_id,
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
                "SET current_version = $1, name = COALESCE($2, name), "
                "locale = COALESCE($4, locale), updated_at = now() "
                "WHERE id = $3 "
                f"RETURNING {self._returning_cols()}",
                next_version,
                name,
                entity_id,
                new_locale,
            )
            assert row is not None
            await conn.execute(
                f"INSERT INTO {ev} "
                f"({fk}, version, content, status, created_by, locale) "
                "VALUES ($1, $2, $3, $4, $5, $6)",
                entity_id,
                next_version,
                content_json,
                new_status.value,
                owner_id,
                row["locale"],
            )
        built = self._build(
            row,
            current_version=next_version,
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
        new_locale: str | None = None,
    ) -> tuple[TRead | None, WriteConflict | None]:
        """Auto-Save-Pfad (PATCH `.../draft`).

        - Existiert ein Draft, wird die Draft-Row in-place ueberschrieben —
          kein Versions-Increment. Active bleibt unangetastet.
        - Existiert kein Draft, wird ein neuer Draft v(n+1) angelegt.
        - Edge-Case `current_status='review'` ohne offenen Draft: `review_pending`.
        `new_locale` wechselt die Entity-Sprache (Metadaten-Update).
        """
        content_json = content.model_dump(mode="json")
        e, ev, fk = self._t.entity, self._t.version_table, self._t.fk
        async with self._pool.acquire() as conn, conn.transaction():
            current = await conn.fetchrow(
                self._current_version_sql(),
                entity_id,
                workspace_id,
            )
            if current is None:
                return None, None
            draft_version = await conn.fetchval(
                f"SELECT version FROM {ev} WHERE {fk} = $1 AND status = 'draft'",
                entity_id,
            )
            if draft_version is not None:
                row = await conn.fetchrow(
                    f"UPDATE {e} "
                    "SET name = COALESCE($1, name), locale = COALESCE($3, locale), "
                    "updated_at = now() "
                    "WHERE id = $2 "
                    f"RETURNING {self._returning_cols()}",
                    name,
                    entity_id,
                    new_locale,
                )
                await conn.execute(
                    f"UPDATE {ev} SET content = $1, created_by = $2 "
                    f"WHERE {fk} = $3 AND version = $4 AND status = 'draft'",
                    content_json,
                    owner_id,
                    entity_id,
                    draft_version,
                )
                built = self._build(
                    row,
                    current_version=draft_version,
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
                "SET current_version = $1, name = COALESCE($2, name), "
                "locale = COALESCE($4, locale), updated_at = now() "
                "WHERE id = $3 "
                f"RETURNING {self._returning_cols()}",
                next_version,
                name,
                entity_id,
                new_locale,
            )
            assert row is not None
            await conn.execute(
                f"INSERT INTO {ev} "
                f"({fk}, version, content, status, created_by, locale) "
                "VALUES ($1, $2, $3, $4, $5, $6)",
                entity_id,
                next_version,
                content_json,
                VersionStatus.draft.value,
                owner_id,
                row["locale"],
            )
        built = self._build(
            row,
            current_version=next_version,
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
    ) -> tuple[TRead | None, WriteConflict | None]:
        """Schreibt `content` (Snapshot) als neue Draft-Version (Track A §3.1).

        Non-destruktiv: frische Draft v(n+1) (globaler Zaehler), kein Pointer-
        Reset. `draft_exists` bei bereits offenem Draft. Name und Entity-Sprache
        bleiben unveraendert; die neue Row traegt die Entity-Sprache.
        """
        content_json = content.model_dump(mode="json")
        e, ev, fk = self._t.entity, self._t.version_table, self._t.fk
        async with self._pool.acquire() as conn, conn.transaction():
            current = await conn.fetchrow(
                # Globale Max-Version als Scalar-Subquery — Postgres erlaubt
                # `FOR UPDATE` nicht zusammen mit `GROUP BY`. Die Sperre liegt
                # auf der Identitaets-Zeile; current_version ist NULL, wenn
                # (theoretisch) keine Version existiert.
                f"SELECT (SELECT max(v.version) FROM {ev} v "
                f"        WHERE v.{fk} = e.id) AS current_version "
                f"FROM {e} e "
                "WHERE e.id = $1 AND e.workspace_id = $2 "
                "FOR UPDATE",
                entity_id,
                workspace_id,
            )
            if current is None or current["current_version"] is None:
                return None, None
            existing_draft = await conn.fetchval(
                f"SELECT 1 FROM {ev} WHERE {fk} = $1 AND status = 'draft'",
                entity_id,
            )
            if existing_draft is not None:
                return None, "draft_exists"
            next_version = current["current_version"] + 1
            row = await conn.fetchrow(
                f"UPDATE {e} SET "
                "current_version = $1, updated_at = now() "
                "WHERE id = $2 "
                f"RETURNING {self._returning_cols()}",
                next_version,
                entity_id,
            )
            assert row is not None
            await conn.execute(
                f"INSERT INTO {ev} "
                f"({fk}, version, content, status, created_by, locale) "
                "VALUES ($1, $2, $3, $4, $5, $6)",
                entity_id,
                next_version,
                content_json,
                VersionStatus.draft.value,
                owner_id,
                row["locale"],
            )
        built = self._build(
            row,
            current_version=next_version,
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
        self, workspace_id: UUID, entity_id: UUID
    ) -> list[TVersionRead] | None:
        """Alle Versions-Snapshots (locale-agnostisch, neueste zuerst).

        Legacy-Rows mit gleicher Versionsnummer in zwei Sprachen erscheinen
        beide (Historie); Tie-Break auf `locale` haelt die Ordnung stabil.
        """
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
            f"FROM {ev} WHERE {fk} = $1 "
            "ORDER BY version DESC, locale ASC",
            entity_id,
        )
        return [self._t.version_read_model.model_validate(dict(row)) for row in rows]

    async def _fetch_version(
        self, workspace_id: UUID, entity_id: UUID, version: int
    ) -> TVersionRead | None:
        """Ein Versions-Snapshot nach Nummer — bei Legacy-Duplikaten (DE-v1 UND
        EN-v1) gewinnt deterministisch die Row in der Entity-Sprache."""
        e, ev, fk = self._t.entity, self._t.version_table, self._t.fk
        row = await self._pool.fetchrow(
            "SELECT ev.version, ev.status, ev.locale, ev.content, ev.created_by, ev.created_at "
            f"FROM {ev} ev "
            f"JOIN {e} e ON e.id = ev.{fk} "
            "WHERE e.id = $1 AND e.workspace_id = $2 AND ev.version = $3 "
            "ORDER BY (ev.locale = e.locale) DESC "
            "LIMIT 1",
            entity_id,
            workspace_id,
            version,
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
