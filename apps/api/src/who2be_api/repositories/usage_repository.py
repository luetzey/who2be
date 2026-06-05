"""Reverse-Lookups fuer Persona->Playbook und Playbook->Resource (Phase 3-A).

`PgUsageRepository` liefert die Backlinks fuer zwei UI-Bloecke
(`PlaybookDetailPage`, `ResourceDetailPage`):

- `list_playbook_usages` — welche Personas verlinken dieses Playbook?
  Quelle: `persona_playbook`-Tabelle.
- `list_resource_usages` — welche Playbooks referenzieren Bloecke dieser
  Resource? Quelle: `playbook_resource_link` GROUP BY playbook.

Beide Queries scopen explizit auf `workspace_id` (Defense; FKs garantieren
das ohnehin, aber die explizite Bindung haelt den Pfad robust gegen
Schema-Drift).
"""

from typing import Protocol
from uuid import UUID

import asyncpg

from who2be_models import PersonaUsage, PlaybookRef, PlaybookUsage, ResourceRef, ResourceUsage


class UsageRepository(Protocol):
    """Service-seitige Abstraktion fuer die Reverse-Lookups."""

    async def playbook_belongs_to(self, workspace_id: UUID, playbook_id: UUID) -> bool: ...

    async def resource_belongs_to(self, workspace_id: UUID, resource_id: UUID) -> bool: ...

    async def list_persona_usages(
        self, workspace_id: UUID, persona_id: UUID
    ) -> list[PersonaUsage]: ...

    async def list_playbook_usages(
        self, workspace_id: UUID, playbook_id: UUID
    ) -> list[PlaybookUsage]: ...

    async def list_playbook_parent_composites(
        self, workspace_id: UUID, playbook_id: UUID
    ) -> list[PlaybookRef]: ...

    async def list_resource_usages(
        self, workspace_id: UUID, resource_id: UUID
    ) -> list[ResourceUsage]: ...

    async def list_resource_parent_composites(
        self, workspace_id: UUID, resource_id: UUID
    ) -> list[ResourceRef]: ...


class PgUsageRepository:
    """asyncpg-Implementierung von `UsageRepository`."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def playbook_belongs_to(self, workspace_id: UUID, playbook_id: UUID) -> bool:
        owned = await self._pool.fetchval(
            "SELECT 1 FROM playbook WHERE id = $1 AND workspace_id = $2",
            playbook_id,
            workspace_id,
        )
        return owned is not None

    async def resource_belongs_to(self, workspace_id: UUID, resource_id: UUID) -> bool:
        owned = await self._pool.fetchval(
            "SELECT 1 FROM resource WHERE id = $1 AND workspace_id = $2",
            resource_id,
            workspace_id,
        )
        return owned is not None

    async def list_persona_usages(self, workspace_id: UUID, persona_id: UUID) -> list[PersonaUsage]:
        """Welche Agenten nutzen diese Persona? (Quelle `agent.persona_id`).

        Blockiert das Persona-Delete (409): der `agent.persona_id`-FK steht auf
        ON DELETE RESTRICT.
        """
        rows = await self._pool.fetch(
            "SELECT a.id AS agent_id, a.name AS agent_name "
            "FROM agent a "
            "WHERE a.persona_id = $1 AND a.workspace_id = $2 "
            "ORDER BY a.name ASC, a.id ASC",
            persona_id,
            workspace_id,
        )
        return [PersonaUsage.model_validate(dict(row)) for row in rows]

    async def list_playbook_usages(
        self, workspace_id: UUID, playbook_id: UUID
    ) -> list[PlaybookUsage]:
        rows = await self._pool.fetch(
            "SELECT pp.persona_id, p.name AS persona_name "
            "FROM persona_playbook pp "
            "JOIN persona p ON p.id = pp.persona_id "
            "WHERE pp.playbook_id = $1 AND pp.workspace_id = $2 "
            "ORDER BY p.name ASC, pp.persona_id ASC",
            playbook_id,
            workspace_id,
        )
        return [PlaybookUsage.model_validate(dict(row)) for row in rows]

    async def list_playbook_parent_composites(
        self, workspace_id: UUID, playbook_id: UUID
    ) -> list[PlaybookRef]:
        """Eltern-Composites, die dieses Playbook als Kind einbetten.

        Quelle: `playbook_composition` WHERE `child_id = $1` (parent-Playbooks).
        Blockiert das Playbook-Delete (409) zusaetzlich zu verlinkenden Personas.
        """
        rows = await self._pool.fetch(
            "SELECT parent.id, parent.name "
            "FROM playbook_composition pc "
            "JOIN playbook parent ON parent.id = pc.parent_id "
            "WHERE pc.child_id = $1 AND pc.workspace_id = $2 "
            "ORDER BY parent.name ASC, parent.id ASC",
            playbook_id,
            workspace_id,
        )
        return [PlaybookRef.model_validate(dict(row)) for row in rows]

    async def list_resource_usages(
        self, workspace_id: UUID, resource_id: UUID
    ) -> list[ResourceUsage]:
        rows = await self._pool.fetch(
            "SELECT prl.playbook_id, p.name AS playbook_name, "
            "       COUNT(*)::int AS block_count "
            "FROM playbook_resource_link prl "
            "JOIN playbook p ON p.id = prl.playbook_id "
            "WHERE prl.resource_id = $1 AND prl.workspace_id = $2 "
            "GROUP BY prl.playbook_id, p.name "
            "ORDER BY p.name ASC, prl.playbook_id ASC",
            resource_id,
            workspace_id,
        )
        return [ResourceUsage.model_validate(dict(row)) for row in rows]

    async def list_resource_parent_composites(
        self, workspace_id: UUID, resource_id: UUID
    ) -> list[ResourceRef]:
        """Eltern-Composites, die diese Resource als Sub-Resource einbetten.

        Quelle: `resource_composition` WHERE `child_id = $1` (parent-Resources).
        DISTINCT, weil ein Parent dieselbe Resource ueber mehrere Block-Anker
        referenzieren kann. Blockiert das Resource-Delete (409) zusaetzlich zu
        referenzierenden Playbooks.
        """
        rows = await self._pool.fetch(
            "SELECT DISTINCT parent.id, parent.name "
            "FROM resource_composition rc "
            "JOIN resource parent ON parent.id = rc.parent_id "
            "WHERE rc.child_id = $1 AND rc.workspace_id = $2 "
            "ORDER BY parent.name ASC, parent.id ASC",
            resource_id,
            workspace_id,
        )
        return [ResourceRef.model_validate(dict(row)) for row in rows]
