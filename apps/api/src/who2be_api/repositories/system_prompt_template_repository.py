"""Persistenz fuer das SystemPromptTemplate-Aggregat.

Versionierung ueber eine History-Tabelle (ADR-0004); Aufbau und Verhalten
spiegeln `PersonaRepository`. Mandantenschluessel ist `workspace_id`
(siehe Migration 0022); `owner_id` bleibt Audit-Spalte.

Phase 3 Runde 3: Template-Reads filtern KEIN active_only mehr nach
`is_api_token` — Templates werden nur ueber den Render-Endpoint vom
API-Token-Pfad konsumiert und der Render-Service waehlt selbst die Active-
Version. Die Default-Such- und List-Reads liefern daher immer die aktuelle
Version (analog zur Persona-/Playbook-`active_only`-Logik wuerde sonst der
Render-Endpoint nichts mehr finden, solange das Template noch im Draft ist).

„Ein Element, eine Sprache" (ADR-0045): Templates ziehen nach — `locale` liegt
auf der `system_prompt_template`-Identitaets-Zeile (Migration 0069), Reads
liefern sie Top-Level, `list_by_workspace` filtert optional darauf, Versions-
Writes uebernehmen die Entity-Sprache, ein gesetztes Update-`locale` wechselt
sie (Metadaten-Update).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Protocol
from uuid import UUID

import asyncpg

from who2be_api.repositories.versioned_repository import (
    check_base_rev,
    compute_base_rev,
    current_expected_base_rev,
)
from who2be_models import (
    SystemPromptTemplateContent,
    SystemPromptTemplateRead,
    SystemPromptTemplateVersionRead,
    VersionStatus,
)

# Identitaets-Zeile + Inhalt der aktuellen Version (analog Persona).
# Track B (Nur-BlockNote): `body_format` ist entfallen — der Body ist immer
# BlockNote-JSON. `locale` kommt von der Identitaets-Zeile (ADR-0045).
_SELECT_CURRENT = """
    SELECT t.id, t.workspace_id, t.owner_id, t.name, t.slug,
           t.is_managed, t.current_version, t.locale,
           t.created_at, t.updated_at, tv.content,
           tv.status AS current_status,
           EXISTS (
               SELECT 1 FROM system_prompt_template_version dv
               WHERE dv.template_id = t.id AND dv.status = 'draft'
           ) AS has_pending_draft
    FROM system_prompt_template t
    JOIN system_prompt_template_version tv
      ON tv.template_id = t.id AND tv.version = t.current_version
"""

_RETURNING = (
    "RETURNING id, workspace_id, owner_id, name, slug, locale, "
    "current_version, created_at, updated_at"
)

# Schreibziel fuer den Konflikt-Token `base_rev` (ADR-0058 §6.3 A): der offene
# Draft, sonst die Version hinter `current_version`. Gleiche Hash-Form wie im
# generischen Kern (`compute_base_rev`).
_BASE_REV_TARGET = """
    SELECT t.name, t.locale, tv.version, tv.content
    FROM system_prompt_template t
    JOIN LATERAL (
        SELECT v.version, v.content FROM system_prompt_template_version v
        WHERE v.template_id = t.id
          AND (v.status = 'draft' OR v.version = t.current_version)
        ORDER BY (v.status = 'draft') DESC, v.version DESC
        LIMIT 1
    ) tv ON TRUE
    WHERE t.id = $1 AND t.workspace_id = $2
"""


@dataclass(frozen=True)
class SystemPromptTemplateUpdateOutcome:
    """Ergebnis eines `update`-/`upsert_draft`-Aufrufs (analog `PersonaUpdateOutcome`).

    `draft_exists` markiert den PUT-Pfad bei offenem Draft, `review_pending`
    den Draft-Pfad gegen eine Review-Version.
    """

    template: SystemPromptTemplateRead | None
    conflict: Literal["draft_exists", "review_pending"] | None = None


class SystemPromptTemplateRepository(Protocol):
    """Service-seitige Abstraktion."""

    async def insert(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        name: str,
        slug: str,
        content: SystemPromptTemplateContent,
        locale: str,
    ) -> SystemPromptTemplateRead: ...

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        limit: int,
        after: tuple[datetime, UUID] | None,
        locale: str | None = None,
    ) -> list[SystemPromptTemplateRead]: ...

    async def fetch(
        self, workspace_id: UUID, template_id: UUID
    ) -> SystemPromptTemplateRead | None: ...

    async def list_agent_counts(
        self, workspace_id: UUID, template_ids: list[UUID]
    ) -> dict[UUID, int]: ...

    async def fetch_active_content(
        self, workspace_id: UUID, template_id: UUID
    ) -> SystemPromptTemplateContent | None: ...

    async def fetch_locale(self, workspace_id: UUID, template_id: UUID) -> str | None: ...

    async def update(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        template_id: UUID,
        name: str | None,
        content: SystemPromptTemplateContent,
        new_locale: str | None = None,
    ) -> SystemPromptTemplateUpdateOutcome: ...

    async def upsert_draft(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        template_id: UUID,
        name: str | None,
        content: SystemPromptTemplateContent,
        new_locale: str | None = None,
    ) -> SystemPromptTemplateUpdateOutcome: ...

    async def fetch_base_rev(
        self, workspace_id: UUID, template_id: UUID
    ) -> tuple[int, str] | None: ...

    async def restore_version(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        template_id: UUID,
        content: SystemPromptTemplateContent,
    ) -> SystemPromptTemplateUpdateOutcome: ...

    async def list_versions(
        self, workspace_id: UUID, template_id: UUID
    ) -> list[SystemPromptTemplateVersionRead] | None: ...

    async def fetch_version(
        self, workspace_id: UUID, template_id: UUID, version: int
    ) -> SystemPromptTemplateVersionRead | None: ...

    async def is_managed(self, workspace_id: UUID, template_id: UUID) -> bool: ...


def _row_to_read(row: dict[str, Any]) -> SystemPromptTemplateRead:
    """Wandelt eine SELECT-Row in ein Read-Modell — `content` als jsonb-dict."""
    return SystemPromptTemplateRead.model_validate(row)


async def _check_base_rev_locked(
    conn: asyncpg.Connection, workspace_id: UUID, template_id: UUID
) -> None:
    """Prueft einen erwarteten `base_rev` in der laufenden Transaktion.

    Nur nach dem `FOR UPDATE`-Read aufrufen; ohne erwarteten Wert No-Op ohne
    zusaetzliche Abfrage (Logik und Fehler aus dem generischen Kern).
    """
    if current_expected_base_rev() is None:
        return
    row = await conn.fetchrow(_BASE_REV_TARGET, template_id, workspace_id)
    assert row is not None  # die Zeile ist gesperrt, also vorhanden
    check_base_rev(row["version"], row["content"], row["name"], row["locale"])


class PgSystemPromptTemplateRepository:
    """asyncpg-Implementierung."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def is_managed(self, workspace_id: UUID, template_id: UUID) -> bool:
        val = await self._pool.fetchval(
            "SELECT is_managed FROM system_prompt_template WHERE id = $1 AND workspace_id = $2",
            template_id,
            workspace_id,
        )
        return bool(val)

    async def insert(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        name: str,
        slug: str,
        content: SystemPromptTemplateContent,
        locale: str,
    ) -> SystemPromptTemplateRead:
        content_json = content.model_dump(mode="json")
        async with self._pool.acquire() as conn, conn.transaction():
            template = await conn.fetchrow(
                "INSERT INTO system_prompt_template "
                "(workspace_id, owner_id, name, slug, locale) "
                "VALUES ($1, $2, $3, $4, $5) "
                f"{_RETURNING}",
                workspace_id,
                owner_id,
                name,
                slug,
                locale,
            )
            await conn.execute(
                "INSERT INTO system_prompt_template_version "
                "(template_id, version, content, status, created_by, locale) "
                "VALUES ($1, $2, $3, $4, $5, $6)",
                template["id"],
                template["current_version"],
                content_json,
                VersionStatus.draft.value,
                owner_id,
                locale,
            )
        return SystemPromptTemplateRead.model_validate(
            {
                **dict(template),
                "content": content_json,
                "current_status": VersionStatus.draft,
                "has_pending_draft": True,
            }
        )

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        limit: int,
        after: tuple[datetime, UUID] | None,
        locale: str | None = None,
    ) -> list[SystemPromptTemplateRead]:
        # `locale` ist der optionale Sprachfilter auf die Entity-Sprache
        # (NULL ⇒ alle Sprachen).
        if after is None:
            rows = await self._pool.fetch(
                f"{_SELECT_CURRENT} WHERE t.workspace_id = $1 "
                "AND ($3::text IS NULL OR t.locale = $3) "
                "ORDER BY t.created_at DESC, t.id DESC LIMIT $2",
                workspace_id,
                limit,
                locale,
            )
        else:
            rows = await self._pool.fetch(
                f"{_SELECT_CURRENT} WHERE t.workspace_id = $1 "
                "AND (t.created_at, t.id) < ($2, $3) "
                "AND ($5::text IS NULL OR t.locale = $5) "
                "ORDER BY t.created_at DESC, t.id DESC LIMIT $4",
                workspace_id,
                after[0],
                after[1],
                limit,
                locale,
            )
        return [_row_to_read(dict(row)) for row in rows]

    async def fetch(self, workspace_id: UUID, template_id: UUID) -> SystemPromptTemplateRead | None:
        row = await self._pool.fetchrow(
            f"{_SELECT_CURRENT} WHERE t.id = $1 AND t.workspace_id = $2",
            template_id,
            workspace_id,
        )
        return _row_to_read(dict(row)) if row is not None else None

    async def list_agent_counts(
        self, workspace_id: UUID, template_ids: list[UUID]
    ) -> dict[UUID, int]:
        """Batch-Aggregat fuer die List-Card-Pill (ein Roundtrip, kein N+1).

        Set-basierter Join ueber `= ANY($2)`: Anzahl der Agenten mit
        `agent.system_prompt_template_id = id` fuer alle uebergebenen Templates
        auf einmal. Leere ID-Liste => {}.
        """
        if not template_ids:
            return {}
        rows = await self._pool.fetch(
            "SELECT t.id AS template_id, COALESCE(ac.cnt, 0)::int AS agent_count "
            "FROM system_prompt_template t "
            "LEFT JOIN ( "
            "    SELECT system_prompt_template_id, COUNT(*) AS cnt "
            "    FROM agent GROUP BY system_prompt_template_id "
            ") ac ON ac.system_prompt_template_id = t.id "
            "WHERE t.workspace_id = $1 AND t.id = ANY($2)",
            workspace_id,
            template_ids,
        )
        return {row["template_id"]: row["agent_count"] for row in rows}

    async def fetch_active_content(
        self, workspace_id: UUID, template_id: UUID
    ) -> SystemPromptTemplateContent | None:
        """Liefert den Inhalt der Active-Version (oder None, falls keine).

        Wird vom Render-Service genutzt: rendere nur, wenn das Template eine
        publizierte Version hat — ungeprueftes Draft-Material soll nicht aus
        Versehen in einen externen LLM-Chat kopiert werden.
        """
        row = await self._pool.fetchrow(
            "SELECT tv.content FROM system_prompt_template_version tv "
            "JOIN system_prompt_template t ON t.id = tv.template_id "
            "WHERE t.id = $1 AND t.workspace_id = $2 AND tv.status = 'active'",
            template_id,
            workspace_id,
        )
        if row is None:
            return None
        return SystemPromptTemplateContent.model_validate(row["content"])

    async def fetch_locale(self, workspace_id: UUID, template_id: UUID) -> str | None:
        """Liefert die Entity-Sprache der Identitaets-Zeile (WP5, ADR-0045).

        Schlankes Single-Column-Read fuer den Agent-Render-Pfad
        (`AgentRenderService`/`AgentFetchRenderedService`): die Sprachanweisung
        und `RenderContext.locale` (Datumsformat) leiten sich daraus ab, ohne
        die (potenziell grosse) `content`-Spalte der Version mitzuladen.
        """
        value: str | None = await self._pool.fetchval(
            "SELECT locale FROM system_prompt_template WHERE id = $1 AND workspace_id = $2",
            template_id,
            workspace_id,
        )
        return value

    async def update(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        template_id: UUID,
        name: str | None,
        content: SystemPromptTemplateContent,
        new_locale: str | None = None,
    ) -> SystemPromptTemplateUpdateOutcome:
        content_json = content.model_dump(mode="json")
        async with self._pool.acquire() as conn, conn.transaction():
            current = await conn.fetchrow(
                "SELECT t.current_version, tv.status "
                "FROM system_prompt_template t "
                "JOIN system_prompt_template_version tv "
                "  ON tv.template_id = t.id AND tv.version = t.current_version "
                "WHERE t.id = $1 AND t.workspace_id = $2 FOR UPDATE OF t",
                template_id,
                workspace_id,
            )
            if current is None:
                return SystemPromptTemplateUpdateOutcome(template=None)
            await _check_base_rev_locked(conn, workspace_id, template_id)
            existing_draft = await conn.fetchval(
                "SELECT 1 FROM system_prompt_template_version "
                "WHERE template_id = $1 AND status = 'draft'",
                template_id,
            )
            if existing_draft is not None:
                return SystemPromptTemplateUpdateOutcome(template=None, conflict="draft_exists")
            next_version = current["current_version"] + 1
            new_status: VersionStatus
            if current["status"] == VersionStatus.active.value:
                new_status = VersionStatus.draft
            else:
                new_status = VersionStatus.inactive
            # Ein gesetztes `new_locale` wechselt die Entity-Sprache
            # (Metadaten-Update, ADR-0045); die neue Versions-Row uebernimmt
            # die (ggf. neue) Entity-Sprache.
            template = await conn.fetchrow(
                "UPDATE system_prompt_template "
                "SET current_version = $1, name = COALESCE($2, name), "
                "    locale = COALESCE($4, locale), updated_at = now() "
                "WHERE id = $3 "
                f"{_RETURNING}",
                next_version,
                name,
                template_id,
                new_locale,
            )
            await conn.execute(
                "INSERT INTO system_prompt_template_version "
                "(template_id, version, content, status, created_by, locale) "
                "VALUES ($1, $2, $3, $4, $5, $6)",
                template_id,
                next_version,
                content_json,
                new_status.value,
                owner_id,
                template["locale"],
            )
        return SystemPromptTemplateUpdateOutcome(
            template=SystemPromptTemplateRead.model_validate(
                {
                    **dict(template),
                    "content": content_json,
                    "current_status": new_status,
                    "has_pending_draft": new_status == VersionStatus.draft,
                }
            )
        )

    async def fetch_base_rev(self, workspace_id: UUID, template_id: UUID) -> tuple[int, str] | None:
        """`(version, base_rev)` des Schreibziels, None wenn nicht im Workspace."""
        row = await self._pool.fetchrow(_BASE_REV_TARGET, template_id, workspace_id)
        if row is None:
            return None
        return row["version"], compute_base_rev(row["content"], row["name"], row["locale"])

    async def upsert_draft(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        template_id: UUID,
        name: str | None,
        content: SystemPromptTemplateContent,
        new_locale: str | None = None,
    ) -> SystemPromptTemplateUpdateOutcome:
        """Draft-in-place-Pfad (ADR-0058 §6.2), Semantik wie
        `VersionedAggregateRepository._upsert_draft`.

        - Ist ein Draft offen, wird er in place ueberschrieben, ohne neue
          Version. Active bleibt unangetastet.
        - Ist keiner offen, entsteht ein Draft v(n+1), und `current_version`
          zeigt auf ihn.
        - Steht die aktuelle Version in Review: `review_pending`.
        `new_locale` wechselt die Entity-Sprache (Metadaten-Update). Ein
        erwarteter `base_rev` wird unter der Sperre geprueft.
        """
        content_json = content.model_dump(mode="json")
        async with self._pool.acquire() as conn, conn.transaction():
            current = await conn.fetchrow(
                "SELECT t.current_version, tv.status "
                "FROM system_prompt_template t "
                "JOIN system_prompt_template_version tv "
                "  ON tv.template_id = t.id AND tv.version = t.current_version "
                "WHERE t.id = $1 AND t.workspace_id = $2 FOR UPDATE OF t",
                template_id,
                workspace_id,
            )
            if current is None:
                return SystemPromptTemplateUpdateOutcome(template=None)
            await _check_base_rev_locked(conn, workspace_id, template_id)
            draft_version = await conn.fetchval(
                "SELECT version FROM system_prompt_template_version "
                "WHERE template_id = $1 AND status = 'draft'",
                template_id,
            )
            if draft_version is not None:
                template = await conn.fetchrow(
                    "UPDATE system_prompt_template "
                    "SET name = COALESCE($1, name), locale = COALESCE($3, locale), "
                    "    updated_at = now() "
                    "WHERE id = $2 "
                    f"{_RETURNING}",
                    name,
                    template_id,
                    new_locale,
                )
                await conn.execute(
                    "UPDATE system_prompt_template_version "
                    "SET content = $1, created_by = $2 "
                    "WHERE template_id = $3 AND version = $4 AND status = 'draft'",
                    content_json,
                    owner_id,
                    template_id,
                    draft_version,
                )
                return SystemPromptTemplateUpdateOutcome(
                    template=SystemPromptTemplateRead.model_validate(
                        {
                            **dict(template),
                            "current_version": draft_version,
                            "content": content_json,
                            "current_status": VersionStatus.draft,
                            "has_pending_draft": True,
                        }
                    )
                )
            if current["status"] == VersionStatus.review.value:
                return SystemPromptTemplateUpdateOutcome(template=None, conflict="review_pending")
            next_version = current["current_version"] + 1
            template = await conn.fetchrow(
                "UPDATE system_prompt_template "
                "SET current_version = $1, name = COALESCE($2, name), "
                "    locale = COALESCE($4, locale), updated_at = now() "
                "WHERE id = $3 "
                f"{_RETURNING}",
                next_version,
                name,
                template_id,
                new_locale,
            )
            await conn.execute(
                "INSERT INTO system_prompt_template_version "
                "(template_id, version, content, status, created_by, locale) "
                "VALUES ($1, $2, $3, $4, $5, $6)",
                template_id,
                next_version,
                content_json,
                VersionStatus.draft.value,
                owner_id,
                template["locale"],
            )
        return SystemPromptTemplateUpdateOutcome(
            template=SystemPromptTemplateRead.model_validate(
                {
                    **dict(template),
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
        template_id: UUID,
        content: SystemPromptTemplateContent,
    ) -> SystemPromptTemplateUpdateOutcome:
        """Schreibt `content` (Snapshot) als neue Draft-Version (Track A §3.1).

        Non-destruktiv: frische Draft v(n+1), kein Pointer-Reset. 409
        (`draft_exists`) bei bereits offenem Draft. Name, Slug und Sprache
        bleiben unveraendert; die neue Row traegt die Entity-Sprache.
        """
        content_json = content.model_dump(mode="json")
        async with self._pool.acquire() as conn, conn.transaction():
            current = await conn.fetchrow(
                "SELECT current_version FROM system_prompt_template "
                "WHERE id = $1 AND workspace_id = $2 FOR UPDATE",
                template_id,
                workspace_id,
            )
            if current is None:
                return SystemPromptTemplateUpdateOutcome(template=None)
            existing_draft = await conn.fetchval(
                "SELECT 1 FROM system_prompt_template_version "
                "WHERE template_id = $1 AND status = 'draft'",
                template_id,
            )
            if existing_draft is not None:
                return SystemPromptTemplateUpdateOutcome(template=None, conflict="draft_exists")
            next_version = current["current_version"] + 1
            template = await conn.fetchrow(
                "UPDATE system_prompt_template "
                "SET current_version = $1, updated_at = now() "
                "WHERE id = $2 "
                f"{_RETURNING}",
                next_version,
                template_id,
            )
            await conn.execute(
                "INSERT INTO system_prompt_template_version "
                "(template_id, version, content, status, created_by, locale) "
                "VALUES ($1, $2, $3, $4, $5, $6)",
                template_id,
                next_version,
                content_json,
                VersionStatus.draft.value,
                owner_id,
                template["locale"],
            )
        return SystemPromptTemplateUpdateOutcome(
            template=SystemPromptTemplateRead.model_validate(
                {
                    **dict(template),
                    "content": content_json,
                    "current_status": VersionStatus.draft,
                    "has_pending_draft": True,
                }
            )
        )

    async def list_versions(
        self, workspace_id: UUID, template_id: UUID
    ) -> list[SystemPromptTemplateVersionRead] | None:
        owned = await self._pool.fetchval(
            "SELECT 1 FROM system_prompt_template WHERE id = $1 AND workspace_id = $2",
            template_id,
            workspace_id,
        )
        if owned is None:
            return None
        rows = await self._pool.fetch(
            "SELECT id, version, status, locale, content, created_by, created_at "
            "FROM system_prompt_template_version WHERE template_id = $1 "
            "ORDER BY version DESC",
            template_id,
        )
        return [SystemPromptTemplateVersionRead.model_validate(dict(row)) for row in rows]

    async def fetch_version(
        self, workspace_id: UUID, template_id: UUID, version: int
    ) -> SystemPromptTemplateVersionRead | None:
        row = await self._pool.fetchrow(
            "SELECT tv.id, tv.version, tv.status, tv.locale, tv.content, tv.created_by, "
            "tv.created_at "
            "FROM system_prompt_template_version tv "
            "JOIN system_prompt_template t ON t.id = tv.template_id "
            "WHERE t.id = $1 AND t.workspace_id = $2 AND tv.version = $3",
            template_id,
            workspace_id,
            version,
        )
        return (
            SystemPromptTemplateVersionRead.model_validate(dict(row)) if row is not None else None
        )
