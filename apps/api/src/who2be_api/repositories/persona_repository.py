"""Persistenz fuer das Persona-Aggregat (`persona` + `persona_version`).

Der versionierte CRUD-Kern (insert/update/upsert_draft/restore/list/fetch_version/
delete) lebt in `VersionedAggregateRepository` (Repo-Review STR-1) — gemeinsam mit
Playbook und Resource. Diese Klasse ist die duenne Persona-Subklasse: sie bindet
die Tabellen-Config, wrappt die generischen Kerne in die typisierten Persona-
Signaturen (`PersonaUpdateOutcome`) und ergaenzt die entity-spezifischen
Lesepfade (`fetch`, `list_by_workspace`, `list_distinct_tags`).

Versionierung ueber eine History-Tabelle (ADR-0004); Status pro Version
(ADR-0020); Workspace-Isolation ueber `workspace_id` (ADR-0019). Content-i18n
(ADR-0027): jede Version traegt ein `locale`-Kuerzel, pro Sprache ein eigener
Versions-Track; die "aktuelle" Version einer Sprache ist die hoechste `version`
dieses `locale`. `active_only=True` filtert die Lesepfade auf `status='active'`
(MCP-Pfad, Plan §2.1.D).
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
    PersonaRead,
    PersonaVersionContent,
    PersonaVersionRead,
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

    async def delete(self, workspace_id: UUID, persona_id: UUID) -> bool: ...

    async def is_managed(self, workspace_id: UUID, entity_id: UUID) -> bool: ...


class PgPersonaRepository(VersionedAggregateRepository[PersonaRead, PersonaVersionRead]):
    """asyncpg-Implementierung von `PersonaRepository` auf dem generischen Kern."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        super().__init__(
            pool,
            AggregateTables("persona", PersonaRead, PersonaVersionRead),
        )

    # --- Generischer Kern, in die Persona-Signaturen gewrappt ----------------

    async def insert(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        name: str,
        content: PersonaVersionContent,
        locales: list[str] | None = None,
    ) -> PersonaRead:
        return await self._insert(workspace_id, owner_id, name, content, locales)

    async def update(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        persona_id: UUID,
        name: str | None,
        content: PersonaVersionContent,
        locale: str = DEFAULT_LOCALE,
    ) -> PersonaUpdateOutcome:
        persona, conflict = await self._update(
            workspace_id, owner_id, persona_id, name, content, locale
        )
        return PersonaUpdateOutcome(persona=persona, conflict=conflict)

    async def upsert_draft(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        persona_id: UUID,
        name: str | None,
        content: PersonaVersionContent,
        locale: str = DEFAULT_LOCALE,
    ) -> PersonaUpdateOutcome:
        persona, conflict = await self._upsert_draft(
            workspace_id, owner_id, persona_id, name, content, locale
        )
        return PersonaUpdateOutcome(persona=persona, conflict=conflict)

    async def restore_version(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        persona_id: UUID,
        content: PersonaVersionContent,
        locale: str = DEFAULT_LOCALE,
    ) -> PersonaUpdateOutcome:
        persona, conflict = await self._restore_version(
            workspace_id, owner_id, persona_id, content, locale
        )
        return PersonaUpdateOutcome(persona=persona, conflict=conflict)

    async def list_versions(
        self, workspace_id: UUID, persona_id: UUID, locale: str = DEFAULT_LOCALE
    ) -> list[PersonaVersionRead] | None:
        return await self._list_versions(workspace_id, persona_id, locale)

    async def fetch_version(
        self, workspace_id: UUID, persona_id: UUID, version: int, locale: str = DEFAULT_LOCALE
    ) -> PersonaVersionRead | None:
        return await self._fetch_version(workspace_id, persona_id, version, locale)

    async def delete(self, workspace_id: UUID, persona_id: UUID) -> bool:
        return await self._delete(workspace_id, persona_id)

    # --- Entity-spezifische Lesepfade ----------------------------------------

    async def fetch(
        self,
        workspace_id: UUID,
        persona_id: UUID,
        active_only: bool = False,
        locale: str = DEFAULT_LOCALE,
    ) -> PersonaRead | None:
        builder = self._select_active if active_only else self._select_current
        select = builder("$3")
        row = await self._pool.fetchrow(
            f"{select} WHERE e.id = $1 AND e.workspace_id = $2",
            persona_id,
            workspace_id,
            locale,
        )
        return PersonaRead.model_validate(dict(row)) if row is not None else None

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        limit: int,
        after: tuple[datetime, UUID] | None,
        active_only: bool = False,
        locale: str = DEFAULT_LOCALE,
    ) -> list[PersonaRead]:
        builder = self._select_active if active_only else self._select_current
        # Tie-Breaker auf `id` haelt die Sortierung stabil, wenn zwei Rows
        # auf die Microsekunde gleichzeitig angelegt wurden.
        if after is None:
            select = builder("$3")
            rows = await self._pool.fetch(
                f"{select} WHERE e.workspace_id = $1 "
                "ORDER BY e.created_at DESC, e.id DESC LIMIT $2",
                workspace_id,
                limit,
                locale,
            )
        else:
            select = builder("$5")
            rows = await self._pool.fetch(
                f"{select} WHERE e.workspace_id = $1 "
                "AND (e.created_at, e.id) < ($2, $3) "
                "ORDER BY e.created_at DESC, e.id DESC LIMIT $4",
                workspace_id,
                after[0],
                after[1],
                limit,
                locale,
            )
        return [PersonaRead.model_validate(dict(row)) for row in rows]

    async def list_distinct_tags(
        self, workspace_id: UUID, locale: str = DEFAULT_LOCALE
    ) -> list[str]:
        """DISTINCT alle Persona-Tags des Workspaces, lexikografisch sortiert.

        Persona-Tags liegen — anders als bei Playbooks — nicht denormalisiert
        auf der Identitaets-Zeile, sondern im JSON der aktuellen Version
        (`persona_version.content->'tags'`). Wir lesen daher per Lateral-Join
        ueber die Current-Version (= hoechste Version des `locale`-Tracks) jeder
        Persona im Workspace. Historische Versions-Snapshots tragen nicht bei.
        """
        rows = await self._pool.fetch(
            "SELECT DISTINCT tag "
            "FROM persona e "
            "JOIN persona_version ev "
            "  ON ev.persona_id = e.id AND ev.locale = $2 "
            "  AND ev.version = ( "
            "      SELECT max(v.version) FROM persona_version v "
            "      WHERE v.persona_id = e.id AND v.locale = $2 "
            "  ) "
            "CROSS JOIN LATERAL jsonb_array_elements_text(ev.content->'tags') AS tag "
            "WHERE e.workspace_id = $1 "
            "ORDER BY tag ASC",
            workspace_id,
            locale,
        )
        return [row["tag"] for row in rows]
