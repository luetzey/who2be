"""Persistenz fuer die Playbook-Composition-Relation (`playbook_composition`).

Self-m:n-Relation: ein Composite-Playbook referenziert geordnete Kinder.
`set_composition` fuehrt Workspace-Pruefung, Zyklus-Guard und Set-Replace in
einer Transaktion aus (`FOR UPDATE` auf der Parent-Zeile), damit zwischen
Pruefung und Schreiben kein Fenster bleibt (ADR-0024, Plan Gap 2.1).
"""

from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

import asyncpg

from who2be_models import PlaybookRead, PlaybookRef

# Spalten-Auswahl fuer Current-Version (non-active_only).
_SELECT_CURRENT = """
    SELECT p.id, p.workspace_id, p.owner_id, p.name, p.current_version,
           p.type, p.tags, p.triggers, p.created_at, p.updated_at, pv.content,
           pv.status AS current_status,
           EXISTS (
               SELECT 1 FROM playbook_version dv
               WHERE dv.playbook_id = p.id AND dv.status = 'draft'
           ) AS has_pending_draft,
           EXISTS (
               SELECT 1 FROM playbook_composition c WHERE c.parent_id = p.id
           ) AS is_composite
    FROM playbook p
    JOIN playbook_version pv
      ON pv.playbook_id = p.id AND pv.version = p.current_version
"""

# Spalten-Auswahl fuer Active-Version (active_only-Pfad, MCP).
_SELECT_ACTIVE = """
    SELECT p.id, p.workspace_id, p.owner_id, p.name,
           pv.version AS current_version,
           p.type, p.tags, p.triggers, p.created_at, p.updated_at, pv.content,
           pv.status AS current_status,
           EXISTS (
               SELECT 1 FROM playbook_version dv
               WHERE dv.playbook_id = p.id AND dv.status = 'draft'
           ) AS has_pending_draft,
           EXISTS (
               SELECT 1 FROM playbook_composition c WHERE c.parent_id = p.id
           ) AS is_composite
    FROM playbook p
    JOIN playbook_version pv
      ON pv.playbook_id = p.id AND pv.status = 'active'
"""

# WITH RECURSIVE-Zyklus-Guard: prueft ob parent_id Nachfahre eines der neuen
# Kinder ist. Trifft zu → Zyklus. Kommentar im Service erklaert die Logik.
_CYCLE_GUARD_SQL = """
WITH RECURSIVE descendants(id) AS (
    SELECT child_id FROM playbook_composition
      WHERE parent_id = ANY($1::uuid[])
    UNION
    SELECT pc.child_id FROM playbook_composition pc
      JOIN descendants d ON pc.parent_id = d.id
)
SELECT 1 FROM descendants WHERE id = $2
"""


@dataclass(frozen=True)
class SetCompositionResult:
    """Ergebnis einer atomaren `set_composition`-Operation.

    Erfolg, wenn `parent_found`, `missing_child_ids` leer und `cycle=False`.
    """

    parent_found: bool
    missing_child_ids: list[UUID] = field(default_factory=list)
    cycle: bool = False


class PlaybookCompositionRepository(Protocol):
    """Service-seitige Abstraktion fuer die Composition-Relation."""

    async def parent_belongs_to(self, workspace_id: UUID, parent_id: UUID) -> bool: ...

    async def list_children(
        self, parent_id: UUID, active_only: bool = False
    ) -> list[PlaybookRead]: ...

    async def list_parents(self, child_id: UUID) -> list[PlaybookRef]: ...

    async def set_composition(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        parent_id: UUID,
        child_ids: list[UUID],
    ) -> SetCompositionResult: ...


class PgPlaybookCompositionRepository:
    """asyncpg-Implementierung von `PlaybookCompositionRepository`."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def parent_belongs_to(self, workspace_id: UUID, parent_id: UUID) -> bool:
        owned = await self._pool.fetchval(
            "SELECT 1 FROM playbook WHERE id = $1 AND workspace_id = $2",
            parent_id,
            workspace_id,
        )
        return owned is not None

    async def list_children(self, parent_id: UUID, active_only: bool = False) -> list[PlaybookRead]:
        """Liefert geordnete Kinder des Composite-Playbooks.

        `active_only=True` filtert auf Active-Versionen (MCP-Pfad); ohne DB-Join
        auf aktive Versionen fallen Kinder ohne aktive Version heraus.
        """
        if active_only:
            select_clause = _SELECT_ACTIVE
        else:
            select_clause = _SELECT_CURRENT
        rows = await self._pool.fetch(
            f"{select_clause}"
            "JOIN playbook_composition pc ON pc.child_id = p.id "
            "WHERE pc.parent_id = $1 "
            "ORDER BY pc.position ASC",
            parent_id,
        )
        return [PlaybookRead.model_validate(dict(row)) for row in rows]

    async def list_parents(self, child_id: UUID) -> list[PlaybookRef]:
        """Liefert alle Parent-Playbooks (Reverse Composed-By) als schlanke Refs."""
        rows = await self._pool.fetch(
            "SELECT p.id, p.name "
            "FROM playbook_composition pc "
            "JOIN playbook p ON p.id = pc.parent_id "
            "WHERE pc.child_id = $1 "
            "ORDER BY p.name ASC",
            child_id,
        )
        return [PlaybookRef.model_validate(dict(row)) for row in rows]

    async def set_composition(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        parent_id: UUID,
        child_ids: list[UUID],
    ) -> SetCompositionResult:
        """Ersetzt die Kinder-Liste des Composite atomisch.

        Ablauf in einer Transaktion:
        1. SELECT ... FOR UPDATE auf Parent (Lock + Not-Found-Guard).
        2. Kinder im selben Workspace pruefen.
        3. WITH RECURSIVE Zyklus-Guard (nur wenn child_ids nicht leer).
        4. DELETE + INSERT via unnest WITH ORDINALITY (position = ordinality-1).
        """
        async with self._pool.acquire() as conn, conn.transaction():
            # Schritt 1: Parent-Lock
            parent = await conn.fetchval(
                "SELECT 1 FROM playbook WHERE id = $1 AND workspace_id = $2 FOR UPDATE",
                parent_id,
                workspace_id,
            )
            if parent is None:
                return SetCompositionResult(parent_found=False)

            # Schritt 2: Kinder-Workspace-Check
            if child_ids:
                owned_rows = await conn.fetch(
                    "SELECT id FROM playbook WHERE workspace_id = $1 AND id = ANY($2::uuid[])",
                    workspace_id,
                    child_ids,
                )
                owned = {row["id"] for row in owned_rows}
                missing = [cid for cid in child_ids if cid not in owned]
                if missing:
                    return SetCompositionResult(parent_found=True, missing_child_ids=missing)

                # Schritt 3: Zyklus-Guard via WITH RECURSIVE
                # Prueft ob parent_id in den Nachfahren eines der neuen Kinder auftaucht.
                # Wenn ja → zirkulaere Abhaengigkeit → 409.
                cycle_hit = await conn.fetchval(_CYCLE_GUARD_SQL, child_ids, parent_id)
                if cycle_hit is not None:
                    return SetCompositionResult(parent_found=True, cycle=True)

            # Schritt 4: Set-Replace
            await conn.execute(
                "DELETE FROM playbook_composition WHERE parent_id = $1",
                parent_id,
            )
            if child_ids:
                await conn.execute(
                    "INSERT INTO playbook_composition "
                    "    (parent_id, child_id, workspace_id, owner_id, position) "
                    "SELECT $1, c.id, $3, $4, c.ord - 1 "
                    "  FROM unnest($2::uuid[]) WITH ORDINALITY AS c(id, ord)",
                    parent_id,
                    child_ids,
                    workspace_id,
                    owner_id,
                )

        return SetCompositionResult(parent_found=True)
