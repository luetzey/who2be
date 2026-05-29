"""Read-only Aggregat-Queries fuers Workspace-Dashboard (Phase 2.1b-B).

Drei Distribution-Queries (eine pro Entity-Typ, `GROUP BY status` ueber
`*_version`, joined ans Entitaets-Aggregat fuer den `workspace_id`-Filter)
und **eine** Activity-Query — eine UNION-ALL ueber persona/playbook/resource,
die sowohl den Entity-Namen mitliefert als auch (LEFT JOIN auf `auth.users`)
Email und `raw_user_meta_data` fuer den Anzeigenamen heranholt. Kein
Per-Row-Lookup, kein N+1.

`status_history` traegt selbst keinen `workspace_id`; die Isolation laeuft
weiterhin per `entity_id IN (SELECT id FROM <entity> WHERE workspace_id = $1)`
in jedem UNION-Zweig. Aktivitaeten zu zwischenzeitlich geloeschten Entities
fallen damit aus dem Feed — der Audit-Trail in `status_history` ist
schemaseitig ohne workspace_id-Snapshot nicht kreuz-isolier-fest und der
Aufruf in `dashboard_service` faellt fuer fehlende Namen auf den
`entity_id`-Tail zurueck (Tombstone-Schutz fuer Race-Faelle).

`auth.users` lebt im GoTrue-Schema; LEFT JOIN, damit Test-User ohne
GoTrue-Row trotzdem mit reinem User-ID-Fallback durchkommen.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

import asyncpg

from who2be_models import EntityType, VersionStatus

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

_RESOURCE_DISTRIBUTION = """
    SELECT rv.status, COUNT(*)::int AS n
    FROM resource_version rv
    JOIN resource r ON r.id = rv.resource_id
    WHERE r.workspace_id = $1
    GROUP BY rv.status
"""

# Single UNION-ALL — persona/playbook/resource in einer Query, plus
# Anzeige-Felder (`entity_name`, `user_email`, `user_meta`). LIMIT greift
# nach dem ORDER BY ueber das Gesamtergebnis.
_ACTIVITY = """
    WITH activity AS (
        SELECT 'persona'::text AS entity_type, sh.entity_id,
               sh.changed_at, sh.changed_by,
               sh.from_status, sh.to_status,
               p.name AS entity_name
        FROM status_history sh
        LEFT JOIN persona p ON p.id = sh.entity_id AND p.workspace_id = $1
        WHERE sh.entity_type = 'persona'
          AND sh.entity_id IN (SELECT id FROM persona WHERE workspace_id = $1)
        UNION ALL
        SELECT 'playbook'::text, sh.entity_id,
               sh.changed_at, sh.changed_by,
               sh.from_status, sh.to_status,
               pb.name AS entity_name
        FROM status_history sh
        LEFT JOIN playbook pb ON pb.id = sh.entity_id AND pb.workspace_id = $1
        WHERE sh.entity_type = 'playbook'
          AND sh.entity_id IN (SELECT id FROM playbook WHERE workspace_id = $1)
        UNION ALL
        SELECT 'resource'::text, sh.entity_id,
               sh.changed_at, sh.changed_by,
               sh.from_status, sh.to_status,
               r.name AS entity_name
        FROM status_history sh
        LEFT JOIN resource r ON r.id = sh.entity_id AND r.workspace_id = $1
        WHERE sh.entity_type = 'resource'
          AND sh.entity_id IN (SELECT id FROM resource WHERE workspace_id = $1)
    )
    SELECT a.entity_type, a.entity_id, a.changed_at, a.changed_by,
           a.from_status, a.to_status, a.entity_name,
           u.email AS user_email,
           u.raw_user_meta_data AS user_meta
    FROM activity a
    LEFT JOIN auth.users u ON u.id = a.changed_by
    ORDER BY a.changed_at DESC
    LIMIT $2
"""


@dataclass(frozen=True)
class DashboardActivityRow:
    """Raw-Row aus `_ACTIVITY` — wird im Service zum DTO gemappt."""

    entity_type: EntityType
    entity_id: UUID
    changed_at: datetime
    changed_by: UUID
    from_status: VersionStatus | None
    to_status: VersionStatus
    entity_name: str | None
    user_email: str | None
    user_meta: dict[str, Any] | None


class DashboardRepository(Protocol):
    """Service-seitige Abstraktion fuer den Dashboard-Zugriff."""

    async def status_distribution(
        self, workspace_id: UUID
    ) -> tuple[dict[VersionStatus, int], dict[VersionStatus, int], dict[VersionStatus, int]]: ...

    async def recent_activity(self, workspace_id: UUID) -> list[DashboardActivityRow]: ...


class PgDashboardRepository:
    """asyncpg-Implementierung von `DashboardRepository`."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def status_distribution(
        self, workspace_id: UUID
    ) -> tuple[dict[VersionStatus, int], dict[VersionStatus, int], dict[VersionStatus, int]]:
        persona_rows = await self._pool.fetch(_PERSONA_DISTRIBUTION, workspace_id)
        playbook_rows = await self._pool.fetch(_PLAYBOOK_DISTRIBUTION, workspace_id)
        resource_rows = await self._pool.fetch(_RESOURCE_DISTRIBUTION, workspace_id)
        return (
            {VersionStatus(row["status"]): row["n"] for row in persona_rows},
            {VersionStatus(row["status"]): row["n"] for row in playbook_rows},
            {VersionStatus(row["status"]): row["n"] for row in resource_rows},
        )

    async def recent_activity(self, workspace_id: UUID) -> list[DashboardActivityRow]:
        rows = await self._pool.fetch(_ACTIVITY, workspace_id, _ACTIVITY_LIMIT)
        return [_row_to_activity(row) for row in rows]


def _row_to_activity(row: asyncpg.Record) -> DashboardActivityRow:
    raw_meta = row["user_meta"]
    # GoTrue speichert `raw_user_meta_data` als jsonb; asyncpg liefert es
    # je nach Codec als dict oder als JSON-String — beides absichern.
    meta: dict[str, Any] | None
    if isinstance(raw_meta, dict):
        meta = raw_meta
    elif isinstance(raw_meta, str) and raw_meta:
        import json

        try:
            parsed = json.loads(raw_meta)
        except json.JSONDecodeError:
            parsed = None
        meta = parsed if isinstance(parsed, dict) else None
    else:
        meta = None

    from_status_raw = row["from_status"]
    return DashboardActivityRow(
        entity_type=row["entity_type"],
        entity_id=row["entity_id"],
        changed_at=row["changed_at"],
        changed_by=row["changed_by"],
        from_status=VersionStatus(from_status_raw) if from_status_raw is not None else None,
        to_status=VersionStatus(row["to_status"]),
        entity_name=row["entity_name"],
        user_email=row["user_email"],
        user_meta=meta,
    )
