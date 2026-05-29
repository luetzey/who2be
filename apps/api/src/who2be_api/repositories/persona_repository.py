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
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

import asyncpg

from who2be_models import (
    PersonaRead,
    PersonaVersionContent,
    PersonaVersionRead,
    VersionStatus,
)

# Persona-Zeile verbunden mit dem Inhalt ihrer aktuellen Version, plus
# Status-Felder (Phase 2.1b). `has_pending_draft` ist ein EXISTS-Subquery,
# damit die Standard-Liste in einem Roundtrip bleibt.
_SELECT_CURRENT = """
    SELECT p.id, p.workspace_id, p.owner_id, p.name, p.current_version,
           p.created_at, p.updated_at, pv.content,
           pv.status AS current_status,
           EXISTS (
               SELECT 1 FROM persona_version dv
               WHERE dv.persona_id = p.id AND dv.status = 'draft'
           ) AS has_pending_draft
    FROM persona p
    JOIN persona_version pv
      ON pv.persona_id = p.id AND pv.version = p.current_version
"""

# Active-Variante: gibt die Active-Version aus (falls vorhanden) statt der
# Current-Version. `current_version` wird dabei auf die Version-Nummer der
# Active-Version umgeschrieben, damit Konsument (MCP) ein konsistentes Bild
# bekommt — current_version und content matchen.
_SELECT_ACTIVE = """
    SELECT p.id, p.workspace_id, p.owner_id, p.name,
           pv.version AS current_version,
           p.created_at, p.updated_at, pv.content,
           pv.status AS current_status,
           EXISTS (
               SELECT 1 FROM persona_version dv
               WHERE dv.persona_id = p.id AND dv.status = 'draft'
           ) AS has_pending_draft
    FROM persona p
    JOIN persona_version pv
      ON pv.persona_id = p.id AND pv.status = 'active'
"""


@dataclass(frozen=True)
class PersonaUpdateOutcome:
    """Ergebnis eines `update`-Aufrufs.

    Bei `conflict='draft_exists'` ist `persona=None`; der Service mappt das auf
    409. `conflict=None` und `persona=None` heisst "nicht gefunden" (→ 404).
    """

    persona: PersonaRead | None
    conflict: Literal["draft_exists"] | None = None


class PersonaRepository(Protocol):
    """Service-seitige Abstraktion fuer den Persona-Zugriff."""

    async def insert(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        name: str,
        content: PersonaVersionContent,
    ) -> PersonaRead: ...

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        limit: int,
        after: tuple[datetime, UUID] | None,
        active_only: bool = False,
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
    ) -> PersonaUpdateOutcome: ...

    async def list_versions(
        self, workspace_id: UUID, persona_id: UUID
    ) -> list[PersonaVersionRead] | None: ...

    async def fetch_version(
        self, workspace_id: UUID, persona_id: UUID, version: int
    ) -> PersonaVersionRead | None: ...


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
    ) -> PersonaRead:
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
            await conn.execute(
                "INSERT INTO persona_version "
                "(persona_id, version, content, created_by) "
                "VALUES ($1, $2, $3, $4)",
                persona["id"],
                persona["current_version"],
                content_json,
                owner_id,
            )
        # Neue v1 startet mit DB-Default `status='inactive'`, kein Draft existiert.
        return PersonaRead.model_validate(
            {
                **dict(persona),
                "content": content_json,
                "current_status": VersionStatus.inactive,
                "has_pending_draft": False,
            }
        )

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        limit: int,
        after: tuple[datetime, UUID] | None,
        active_only: bool = False,
    ) -> list[PersonaRead]:
        select = _SELECT_ACTIVE if active_only else _SELECT_CURRENT
        # Tie-Breaker auf `id` haelt die Sortierung stabil, wenn zwei Rows
        # auf die Microsekunde gleichzeitig angelegt wurden.
        if after is None:
            rows = await self._pool.fetch(
                f"{select} WHERE p.workspace_id = $1 "
                "ORDER BY p.created_at DESC, p.id DESC LIMIT $2",
                workspace_id,
                limit,
            )
        else:
            rows = await self._pool.fetch(
                f"{select} WHERE p.workspace_id = $1 "
                "AND (p.created_at, p.id) < ($2, $3) "
                "ORDER BY p.created_at DESC, p.id DESC LIMIT $4",
                workspace_id,
                after[0],
                after[1],
                limit,
            )
        return [PersonaRead.model_validate(dict(row)) for row in rows]

    async def fetch(
        self,
        workspace_id: UUID,
        persona_id: UUID,
        active_only: bool = False,
    ) -> PersonaRead | None:
        select = _SELECT_ACTIVE if active_only else _SELECT_CURRENT
        row = await self._pool.fetchrow(
            f"{select} WHERE p.id = $1 AND p.workspace_id = $2",
            persona_id,
            workspace_id,
        )
        return PersonaRead.model_validate(dict(row)) if row is not None else None

    async def update(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        persona_id: UUID,
        name: str | None,
        content: PersonaVersionContent,
    ) -> PersonaUpdateOutcome:
        content_json = content.model_dump(mode="json")
        async with self._pool.acquire() as conn, conn.transaction():
            current = await conn.fetchrow(
                "SELECT p.current_version, pv.status "
                "FROM persona p "
                "JOIN persona_version pv "
                "  ON pv.persona_id = p.id AND pv.version = p.current_version "
                "WHERE p.id = $1 AND p.workspace_id = $2 FOR UPDATE OF p",
                persona_id,
                workspace_id,
            )
            if current is None:
                return PersonaUpdateOutcome(persona=None)
            # Solange irgendein Draft existiert, blockiert PUT: der Caller
            # soll erst Promote/Discard durchspielen. Damit fasst der Konflikt-
            # zweig zwei Faelle zusammen — frischer Edit auf einem aktiven Stand,
            # bei dem schon ein Draft pending ist, und wiederholter Edit auf
            # bereits angelegtem Draft.
            existing_draft = await conn.fetchval(
                "SELECT 1 FROM persona_version WHERE persona_id = $1 AND status = 'draft'",
                persona_id,
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
                "SET current_version = $1, name = COALESCE($2, name), "
                "updated_at = now() "
                "WHERE id = $3 "
                "RETURNING id, workspace_id, owner_id, name, current_version, "
                "created_at, updated_at",
                next_version,
                name,
                persona_id,
            )
            await conn.execute(
                "INSERT INTO persona_version "
                "(persona_id, version, content, status, created_by) "
                "VALUES ($1, $2, $3, $4, $5)",
                persona_id,
                next_version,
                content_json,
                new_status.value,
                owner_id,
            )
        # `has_pending_draft` ist genau dann True, wenn wir hier soeben einen
        # Draft erzeugt haben — vorhandene Drafts haetten 409 ausgeloest.
        return PersonaUpdateOutcome(
            persona=PersonaRead.model_validate(
                {
                    **dict(persona),
                    "content": content_json,
                    "current_status": new_status,
                    "has_pending_draft": new_status == VersionStatus.draft,
                }
            )
        )

    async def list_versions(
        self, workspace_id: UUID, persona_id: UUID
    ) -> list[PersonaVersionRead] | None:
        owned = await self._pool.fetchval(
            "SELECT 1 FROM persona WHERE id = $1 AND workspace_id = $2",
            persona_id,
            workspace_id,
        )
        if owned is None:
            return None
        rows = await self._pool.fetch(
            "SELECT version, status, content, created_by, created_at "
            "FROM persona_version WHERE persona_id = $1 ORDER BY version DESC",
            persona_id,
        )
        return [PersonaVersionRead.model_validate(dict(row)) for row in rows]

    async def fetch_version(
        self, workspace_id: UUID, persona_id: UUID, version: int
    ) -> PersonaVersionRead | None:
        row = await self._pool.fetchrow(
            "SELECT pv.version, pv.status, pv.content, pv.created_by, pv.created_at "
            "FROM persona_version pv "
            "JOIN persona p ON p.id = pv.persona_id "
            "WHERE p.id = $1 AND p.workspace_id = $2 AND pv.version = $3",
            persona_id,
            workspace_id,
            version,
        )
        return PersonaVersionRead.model_validate(dict(row)) if row is not None else None
