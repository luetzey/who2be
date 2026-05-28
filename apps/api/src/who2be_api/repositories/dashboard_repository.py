"""Read-only Aggregat-Queries fuers Workspace-Dashboard (Phase 2.1b-B).

Zwei Stoerquellen, drei Queries: pro Entity-Typ eine Distribution-Query
(`GROUP BY status` ueber `*_version`, joined ans Entitaets-Aggregat fuer den
`workspace_id`-Filter) und eine Activity-Query gegen `status_history` mit
`entity_id`-Subquery zur Workspace-Isolation. Verantwortung wie ueberall:
SQL + Row-Mapping, keine Geschaeftsregeln.

`status_history` traegt selbst keinen `workspace_id`; die Isolation laeuft
daher ueber `entity_id IN (SELECT id FROM <entity> WHERE workspace_id = $1)`.
Sobald Resource-Status in 2.2 dazu kommt, muss die Activity-Query um einen
dritten `OR`-Zweig (`entity_type = 'resource'`) ergaenzt werden.
"""

from typing import Protocol
from uuid import UUID

import asyncpg

from who2be_models import StatusHistoryEntry, VersionStatus

_ACTIVITY_LIMIT = 50

_PERSONA_DISTRIBUTION = """
    SELECT pv.status, COUNT(*)::int AS n
    FROM persona_version pv
    JOIN persona p ON p.id = pv.persona_id
    WHERE p.workspace_id = $1
    GROUP BY pv.status
"""

_PLAYBOOK_DISTRIBUTION = """
    SELECT pv.status, COUNT(*)::int AS n
    FROM playbook_version pv
    JOIN playbook p ON p.id = pv.playbook_id
    WHERE p.workspace_id = $1
    GROUP BY pv.status
"""

# `entity_type` listet bewusst nur persona/playbook — Resource-Status kommt
# in Phase 2.2. Subquery-Filter ersetzt einen fehlenden `workspace_id` in
# `status_history` und haelt die Tabelle entity-agnostisch.
_ACTIVITY = """
    SELECT id, entity_type, entity_id, from_status, to_status,
           changed_by, changed_at, note
    FROM status_history
    WHERE (entity_type = 'persona'  AND entity_id IN
              (SELECT id FROM persona  WHERE workspace_id = $1))
       OR (entity_type = 'playbook' AND entity_id IN
              (SELECT id FROM playbook WHERE workspace_id = $1))
    ORDER BY changed_at DESC
    LIMIT $2
"""


class DashboardRepository(Protocol):
    """Service-seitige Abstraktion fuer den Dashboard-Zugriff."""

    async def status_distribution(
        self, workspace_id: UUID
    ) -> tuple[dict[VersionStatus, int], dict[VersionStatus, int]]: ...

    async def recent_activity(self, workspace_id: UUID) -> list[StatusHistoryEntry]: ...


class PgDashboardRepository:
    """asyncpg-Implementierung von `DashboardRepository`."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def status_distribution(
        self, workspace_id: UUID
    ) -> tuple[dict[VersionStatus, int], dict[VersionStatus, int]]:
        persona_rows = await self._pool.fetch(_PERSONA_DISTRIBUTION, workspace_id)
        playbook_rows = await self._pool.fetch(_PLAYBOOK_DISTRIBUTION, workspace_id)
        return (
            {VersionStatus(row["status"]): row["n"] for row in persona_rows},
            {VersionStatus(row["status"]): row["n"] for row in playbook_rows},
        )

    async def recent_activity(self, workspace_id: UUID) -> list[StatusHistoryEntry]:
        rows = await self._pool.fetch(_ACTIVITY, workspace_id, _ACTIVITY_LIMIT)
        return [StatusHistoryEntry.model_validate(dict(row)) for row in rows]
