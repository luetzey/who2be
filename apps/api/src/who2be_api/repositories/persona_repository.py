"""Persistenz fuer das Persona-Aggregat (`persona` + `persona_version`).

Der versionierte CRUD-Kern (insert/update/upsert_draft/restore/list/fetch_version/
delete) lebt in `VersionedAggregateRepository` (Repo-Review STR-1) — gemeinsam mit
Playbook und Resource. Diese Klasse ist die duenne Persona-Subklasse: sie bindet
die Tabellen-Config, wrappt die generischen Kerne in die typisierten Persona-
Signaturen (`PersonaUpdateOutcome`) und ergaenzt die entity-spezifischen
Lesepfade (`fetch`, `list_by_workspace`, `list_distinct_tags`).

Versionierung ueber eine History-Tabelle (ADR-0004); Status pro Version
(ADR-0020); Workspace-Isolation ueber `workspace_id` (ADR-0019). „Ein Element,
eine Sprache" (ADR-0045): `locale` ist ein Attribut der Identitaets-Zeile —
Reads sind locale-agnostisch, `list_by_workspace` filtert optional auf die
Entity-Sprache. `active_only=True` filtert die Lesepfade auf `status='active'`
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
    PersonaRead,
    PersonaVersionContent,
    PersonaVersionRead,
)


@dataclass(frozen=True)
class PersonaListCounts:
    """Denormalisierte List-Card-Pills einer Persona (Batch-Aggregat).

    `playbook_count` = Anzahl der ueber `persona_playbook` verknuepften
    Playbooks; `agent_count` = Anzahl der Agenten mit `agent.persona_id = id`.
    """

    playbook_count: int
    agent_count: int


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
        locale: str,
    ) -> PersonaRead: ...

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        limit: int,
        after: tuple[datetime, UUID] | None,
        active_only: bool = False,
        locale: str | None = None,
        restrict_ids: list[UUID] | None = None,
        name: str | None = None,
    ) -> list[PersonaRead]: ...

    async def fetch(
        self,
        workspace_id: UUID,
        persona_id: UUID,
        active_only: bool = False,
    ) -> PersonaRead | None: ...

    async def update(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        persona_id: UUID,
        name: str | None,
        content: PersonaVersionContent,
        new_locale: str | None = None,
    ) -> PersonaUpdateOutcome: ...

    async def upsert_draft(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        persona_id: UUID,
        name: str | None,
        content: PersonaVersionContent,
        new_locale: str | None = None,
    ) -> PersonaUpdateOutcome: ...

    async def restore_version(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        persona_id: UUID,
        content: PersonaVersionContent,
    ) -> PersonaUpdateOutcome: ...

    async def list_versions(
        self, workspace_id: UUID, persona_id: UUID
    ) -> list[PersonaVersionRead] | None: ...

    async def fetch_version(
        self, workspace_id: UUID, persona_id: UUID, version: int
    ) -> PersonaVersionRead | None: ...

    async def list_distinct_tags(self, workspace_id: UUID) -> list[str]: ...

    async def list_counts(
        self, workspace_id: UUID, persona_ids: list[UUID]
    ) -> dict[UUID, PersonaListCounts]: ...

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
        locale: str,
    ) -> PersonaRead:
        return await self._insert(workspace_id, owner_id, name, content, locale)

    async def update(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        persona_id: UUID,
        name: str | None,
        content: PersonaVersionContent,
        new_locale: str | None = None,
    ) -> PersonaUpdateOutcome:
        persona, conflict = await self._update(
            workspace_id, owner_id, persona_id, name, content, new_locale
        )
        return PersonaUpdateOutcome(persona=persona, conflict=conflict)

    async def upsert_draft(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        persona_id: UUID,
        name: str | None,
        content: PersonaVersionContent,
        new_locale: str | None = None,
    ) -> PersonaUpdateOutcome:
        persona, conflict = await self._upsert_draft(
            workspace_id, owner_id, persona_id, name, content, new_locale
        )
        return PersonaUpdateOutcome(persona=persona, conflict=conflict)

    async def restore_version(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        persona_id: UUID,
        content: PersonaVersionContent,
    ) -> PersonaUpdateOutcome:
        persona, conflict = await self._restore_version(workspace_id, owner_id, persona_id, content)
        return PersonaUpdateOutcome(persona=persona, conflict=conflict)

    async def list_versions(
        self, workspace_id: UUID, persona_id: UUID
    ) -> list[PersonaVersionRead] | None:
        return await self._list_versions(workspace_id, persona_id)

    async def fetch_version(
        self, workspace_id: UUID, persona_id: UUID, version: int
    ) -> PersonaVersionRead | None:
        return await self._fetch_version(workspace_id, persona_id, version)

    async def delete(self, workspace_id: UUID, persona_id: UUID) -> bool:
        return await self._delete(workspace_id, persona_id)

    # --- Entity-spezifische Lesepfade ----------------------------------------

    async def fetch(
        self,
        workspace_id: UUID,
        persona_id: UUID,
        active_only: bool = False,
    ) -> PersonaRead | None:
        builder = self._select_active if active_only else self._select_current
        select = builder()
        row = await self._pool.fetchrow(
            f"{select} WHERE e.id = $1 AND e.workspace_id = $2",
            persona_id,
            workspace_id,
        )
        return PersonaRead.model_validate(dict(row)) if row is not None else None

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        limit: int,
        after: tuple[datetime, UUID] | None,
        active_only: bool = False,
        locale: str | None = None,
        restrict_ids: list[UUID] | None = None,
        name: str | None = None,
    ) -> list[PersonaRead]:
        builder = self._select_active if active_only else self._select_current
        select = builder()
        # Tie-Breaker auf `id` haelt die Sortierung stabil, wenn zwei Rows
        # auf die Microsekunde gleichzeitig angelegt wurden. `locale` ist der
        # optionale Sprachfilter auf die Entity-Sprache (NULL ⇒ alle Sprachen).
        # `restrict_ids` (z. B. `?agent=`-Listenfilter, WP-B): NULL ⇒ keine
        # Einschraenkung, leere Liste ⇒ keine Treffer — gleiche Mechanik wie
        # bei Playbook/Resource.
        # `name` ist der EXAKTE Namensfilter (Issue #415). Bewusst kein
        # `ILIKE`: der Filter bedient einen Aufloesungs-Pfad (`get_persona`
        # per Name), und der verglich bisher mit `==` — unscharf zu matchen
        # waere eine stille Verhaltensaenderung. Der Name ist NICHT unique
        # (dieselbe Persona kann in `de` und `en` existieren, ADR-0045),
        # deshalb bleibt die Sortierung massgeblich fuer den Treffer.
        if after is None:
            rows = await self._pool.fetch(
                f"{select} WHERE e.workspace_id = $1 "
                "AND ($3::text IS NULL OR e.locale = $3) "
                "AND ($4::uuid[] IS NULL OR e.id = ANY($4)) "
                "AND ($5::text IS NULL OR e.name = $5) "
                "ORDER BY e.created_at DESC, e.id DESC LIMIT $2",
                workspace_id,
                limit,
                locale,
                restrict_ids,
                name,
            )
        else:
            rows = await self._pool.fetch(
                f"{select} WHERE e.workspace_id = $1 "
                "AND (e.created_at, e.id) < ($2, $3) "
                "AND ($5::text IS NULL OR e.locale = $5) "
                "AND ($6::uuid[] IS NULL OR e.id = ANY($6)) "
                "AND ($7::text IS NULL OR e.name = $7) "
                "ORDER BY e.created_at DESC, e.id DESC LIMIT $4",
                workspace_id,
                after[0],
                after[1],
                limit,
                locale,
                restrict_ids,
                name,
            )
        return [PersonaRead.model_validate(dict(row)) for row in rows]

    async def list_distinct_tags(self, workspace_id: UUID) -> list[str]:
        """DISTINCT alle Persona-Tags des Workspaces, lexikografisch sortiert.

        Persona-Tags liegen — anders als bei Playbooks — nicht denormalisiert
        auf der Identitaets-Zeile, sondern im JSON der aktuellen Version
        (`persona_version.content->'tags'`). Wir lesen daher per Lateral-Join
        ueber die Current-Version (= globale Max-Version, Legacy-Tie-Break auf
        die Entity-Sprache) jeder Persona im Workspace. Historische
        Versions-Snapshots tragen nicht bei.
        """
        rows = await self._pool.fetch(
            "SELECT DISTINCT tag "
            "FROM persona e "
            "JOIN LATERAL ( "
            "    SELECT v.content FROM persona_version v "
            "    WHERE v.persona_id = e.id "
            "    ORDER BY v.version DESC, (v.locale = e.locale) DESC "
            "    LIMIT 1 "
            ") ev ON TRUE "
            "CROSS JOIN LATERAL jsonb_array_elements_text(ev.content->'tags') AS tag "
            "WHERE e.workspace_id = $1 "
            "ORDER BY tag ASC",
            workspace_id,
        )
        return [row["tag"] for row in rows]

    async def list_counts(
        self, workspace_id: UUID, persona_ids: list[UUID]
    ) -> dict[UUID, PersonaListCounts]:
        """Batch-Aggregat fuer die List-Card-Pills (ein Roundtrip, kein N+1).

        Set-basierter Join ueber `= ANY($2)`: Playbook-Anzahl (`persona_playbook`)
        und Agent-Anzahl (`agent.persona_id`) fuer alle uebergebenen Personae auf
        einmal. Leere ID-Liste => {}.
        """
        if not persona_ids:
            return {}
        rows = await self._pool.fetch(
            "SELECT p.id AS persona_id, "
            "       COALESCE(pp.cnt, 0)::int AS playbook_count, "
            "       COALESCE(ac.cnt, 0)::int AS agent_count "
            "FROM persona p "
            "LEFT JOIN ( "
            "    SELECT persona_id, COUNT(*) AS cnt "
            "    FROM persona_playbook GROUP BY persona_id "
            ") pp ON pp.persona_id = p.id "
            "LEFT JOIN ( "
            "    SELECT persona_id, COUNT(*) AS cnt "
            "    FROM agent GROUP BY persona_id "
            ") ac ON ac.persona_id = p.id "
            "WHERE p.workspace_id = $1 AND p.id = ANY($2)",
            workspace_id,
            persona_ids,
        )
        return {
            row["persona_id"]: PersonaListCounts(
                playbook_count=row["playbook_count"],
                agent_count=row["agent_count"],
            )
            for row in rows
        }
