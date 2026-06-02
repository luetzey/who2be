"""Persistenz fuer die Sub-Resource-Relation (`resource_composition`).

Self-m:n-Relation Resource->Resource (Track E, §3.3). `set_links` fuehrt
Workspace-Pruefung, azyklischen Zyklus-Guard und Set-Replace in einer
Transaktion aus (`FOR UPDATE` auf der Parent-Zeile), damit zwischen Pruefung
und Schreiben kein Fenster bleibt — exakt das Muster aus
`playbook_composition_repository` (0028), erweitert um `link_scope`/`block_id`
analog `playbook_resource_link` (0016/0021).
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

import asyncpg

from who2be_models import ResourceRef, SubResourceLinkItem, SubResourceRead

# WITH RECURSIVE-Zyklus-Guard (wie 0028): prueft ob parent_id Nachfahre eines
# der neuen Kinder ist. Trifft zu -> transitiver Zyklus.
_CYCLE_GUARD_SQL = """
WITH RECURSIVE descendants(id) AS (
    SELECT child_id FROM resource_composition
      WHERE parent_id = ANY($1::uuid[])
    UNION
    SELECT rc.child_id FROM resource_composition rc
      JOIN descendants d ON rc.parent_id = d.id
)
SELECT 1 FROM descendants WHERE id = $2
"""


@dataclass(frozen=True)
class SetSubResourcesResult:
    """Ergebnis einer atomaren `set_links`-Operation.

    Erfolg, wenn `parent_found`, `missing_child_ids` leer und `cycle=False`.
    """

    parent_found: bool
    missing_child_ids: list[UUID] = field(default_factory=list)
    cycle: bool = False


class ResourceCompositionRepository(Protocol):
    """Service-seitige Abstraktion fuer die Sub-Resource-Relation."""

    async def parent_belongs_to(self, workspace_id: UUID, resource_id: UUID) -> bool: ...

    async def list_children(
        self, workspace_id: UUID, parent_id: UUID, active_only: bool = False
    ) -> list[SubResourceRead]: ...

    async def list_parents(self, workspace_id: UUID, child_id: UUID) -> list[ResourceRef]: ...

    async def set_links(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        parent_id: UUID,
        links: Sequence[SubResourceLinkItem],
    ) -> SetSubResourcesResult: ...


class PgResourceCompositionRepository:
    """asyncpg-Implementierung von `ResourceCompositionRepository`."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def parent_belongs_to(self, workspace_id: UUID, resource_id: UUID) -> bool:
        owned = await self._pool.fetchval(
            "SELECT 1 FROM resource WHERE id = $1 AND workspace_id = $2",
            resource_id,
            workspace_id,
        )
        return owned is not None

    async def list_children(
        self, workspace_id: UUID, parent_id: UUID, active_only: bool = False
    ) -> list[SubResourceRead]:
        """Liefert die geordneten direkten Sub-Resources eines Parents.

        `active_only=True` (MCP-/API-Token-Pfad) blendet Kinder ohne aktive
        Version aus — konsistent zur Invariante "MCP sieht nur active"
        (Phase 2.1b, wie `get_playbook_composes`): ein toter Pointer auf eine
        nur als Draft existierende Sub-Resource gelangt damit nicht an Agenten.
        Der Operator-/Web-Pfad (`active_only=False`) zeigt alle Links — der
        Picker braucht sie unabhaengig vom Status der Kind-Version.
        """
        rows = await self._pool.fetch(
            "SELECT rc.child_id AS id, child.name AS name, rc.link_scope, "
            "       rc.block_id, rc.position "
            "FROM resource_composition rc "
            "JOIN resource child ON child.id = rc.child_id "
            "WHERE rc.parent_id = $1 AND rc.workspace_id = $2 "
            "  AND ($3 IS FALSE OR EXISTS ("
            "      SELECT 1 FROM resource_version rv "
            "      WHERE rv.resource_id = child.id AND rv.status = 'active')) "
            "ORDER BY rc.position, child.name, COALESCE(rc.block_id, '')",
            parent_id,
            workspace_id,
            active_only,
        )
        return [SubResourceRead.model_validate(dict(row)) for row in rows]

    async def list_parents(self, workspace_id: UUID, child_id: UUID) -> list[ResourceRef]:
        """Liefert alle Parent-Resources (Reverse Used-By) als schlanke Refs.

        DISTINCT, weil ein Parent dasselbe Kind ueber mehrere Block-Anker
        referenzieren kann.
        """
        rows = await self._pool.fetch(
            "SELECT DISTINCT parent.id, parent.name "
            "FROM resource_composition rc "
            "JOIN resource parent ON parent.id = rc.parent_id "
            "WHERE rc.child_id = $1 AND rc.workspace_id = $2 "
            "ORDER BY parent.name ASC",
            child_id,
            workspace_id,
        )
        return [ResourceRef.model_validate(dict(row)) for row in rows]

    async def set_links(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        parent_id: UUID,
        links: Sequence[SubResourceLinkItem],
    ) -> SetSubResourcesResult:
        """Ersetzt die Sub-Resource-Liste des Parents atomisch.

        Ablauf in einer Transaktion (wie 0028):
        1. SELECT ... FOR UPDATE auf Parent (Lock + Not-Found-Guard).
        2. Kinder im selben Workspace pruefen.
        3. WITH RECURSIVE Zyklus-Guard (nur wenn child_ids nicht leer).
        4. DELETE + INSERT der neuen Links (executemany, Reihenfolge = position).
        """
        items = list(links)
        child_ids = list({item.child_id for item in items})
        async with self._pool.acquire() as conn, conn.transaction():
            parent = await conn.fetchval(
                "SELECT 1 FROM resource WHERE id = $1 AND workspace_id = $2 FOR UPDATE",
                parent_id,
                workspace_id,
            )
            if parent is None:
                return SetSubResourcesResult(parent_found=False)

            if child_ids:
                owned_rows = await conn.fetch(
                    "SELECT id FROM resource WHERE workspace_id = $1 AND id = ANY($2::uuid[])",
                    workspace_id,
                    child_ids,
                )
                owned = {row["id"] for row in owned_rows}
                missing = [cid for cid in child_ids if cid not in owned]
                if missing:
                    return SetSubResourcesResult(parent_found=True, missing_child_ids=missing)

                cycle_hit = await conn.fetchval(_CYCLE_GUARD_SQL, child_ids, parent_id)
                if cycle_hit is not None:
                    return SetSubResourcesResult(parent_found=True, cycle=True)

            await conn.execute(
                "DELETE FROM resource_composition WHERE parent_id = $1",
                parent_id,
            )
            if items:
                await conn.executemany(
                    "INSERT INTO resource_composition "
                    "(parent_id, child_id, block_id, workspace_id, "
                    " owner_id, position, link_scope) "
                    "VALUES ($1, $2, $3, $4, $5, $6, $7)",
                    [
                        (
                            parent_id,
                            item.child_id,
                            item.block_id,
                            workspace_id,
                            owner_id,
                            item.position,
                            item.link_scope,
                        )
                        for item in items
                    ],
                )

        return SetSubResourcesResult(parent_found=True)
