"""Persistenz fuer die Persona-Playbook-Verknuepfung (`persona_playbook`).

Eine reine Aktuell-Stand-m:n-Relation (ADR-0004). `set_links` fuehrt
Workspace-Pruefung und Schreiben in einer Transaktion aus (`FOR UPDATE` auf
der Persona-Zeile), damit zwischen Pruefung und Schreiben kein Fenster
bleibt.

Phase 2.1a-2: Verknuepfungen sind ueber `workspace_id` isoliert; die
Composite-FKs aus 0014 erzwingen, dass nur Entities desselben Workspaces
verknuepft werden koennen.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

import asyncpg

from who2be_models import PlaybookRead


@dataclass(frozen=True)
class SetLinksResult:
    """Ergebnis einer atomaren `set_links`-Operation.

    Erfolg, wenn `persona_found` und `missing_playbook_ids` leer ist.
    """

    persona_found: bool
    missing_playbook_ids: list[UUID] = field(default_factory=list)


class PersonaPlaybookRepository(Protocol):
    """Service-seitige Abstraktion fuer die Verknuepfung."""

    async def persona_belongs_to(self, workspace_id: UUID, persona_id: UUID) -> bool: ...

    async def list_linked(
        self, persona_id: UUID, active_only: bool = False
    ) -> list[PlaybookRead]: ...

    async def set_links(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        persona_id: UUID,
        playbook_ids: Sequence[UUID],
    ) -> SetLinksResult: ...


class PgPersonaPlaybookRepository:
    """asyncpg-Implementierung von `PersonaPlaybookRepository`."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def persona_belongs_to(self, workspace_id: UUID, persona_id: UUID) -> bool:
        owned = await self._pool.fetchval(
            "SELECT 1 FROM persona WHERE id = $1 AND workspace_id = $2",
            persona_id,
            workspace_id,
        )
        return owned is not None

    async def list_linked(self, persona_id: UUID, active_only: bool = False) -> list[PlaybookRead]:
        # `active_only` schwenkt den Join: statt der Current-Version wird die
        # Active-Version geliefert, eintraege ohne Active-Version fallen raus
        # (MCP-Pfad, Plan §2.1.D).
        join_clause = (
            "JOIN playbook_version pv   ON pv.playbook_id = p.id AND pv.status = 'active' "
            if active_only
            else "JOIN playbook_version pv "
            "  ON pv.playbook_id = p.id AND pv.version = p.current_version "
        )
        version_col = "pv.version AS current_version" if active_only else "p.current_version"
        rows = await self._pool.fetch(
            f"SELECT p.id, p.workspace_id, p.owner_id, p.name, {version_col}, "
            "p.type, p.tags, p.triggers, p.created_at, p.updated_at, pv.content, "
            "pv.status AS current_status, "
            "EXISTS ("
            "  SELECT 1 FROM playbook_version dv "
            "  WHERE dv.playbook_id = p.id AND dv.status = 'draft'"
            ") AS has_pending_draft "
            "FROM persona_playbook pp "
            "JOIN playbook p ON p.id = pp.playbook_id "
            f"{join_clause}"
            "WHERE pp.persona_id = $1 "
            "ORDER BY p.created_at DESC",
            persona_id,
        )
        return [PlaybookRead.model_validate(dict(row)) for row in rows]

    async def set_links(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        persona_id: UUID,
        playbook_ids: Sequence[UUID],
    ) -> SetLinksResult:
        ids = list(playbook_ids)
        async with self._pool.acquire() as conn, conn.transaction():
            persona = await conn.fetchval(
                "SELECT 1 FROM persona WHERE id = $1 AND workspace_id = $2 FOR UPDATE",
                persona_id,
                workspace_id,
            )
            if persona is None:
                return SetLinksResult(persona_found=False)
            if ids:
                owned_rows = await conn.fetch(
                    "SELECT id FROM playbook WHERE workspace_id = $1 AND id = ANY($2::uuid[])",
                    workspace_id,
                    ids,
                )
                owned = {row["id"] for row in owned_rows}
                missing = [pid for pid in ids if pid not in owned]
                if missing:
                    return SetLinksResult(persona_found=True, missing_playbook_ids=missing)
            await conn.execute("DELETE FROM persona_playbook WHERE persona_id = $1", persona_id)
            await conn.execute(
                "INSERT INTO persona_playbook (persona_id, playbook_id, workspace_id, owner_id) "
                "SELECT $1, unnest($2::uuid[]), $3, $4",
                persona_id,
                ids,
                workspace_id,
                owner_id,
            )
        return SetLinksResult(persona_found=True)
