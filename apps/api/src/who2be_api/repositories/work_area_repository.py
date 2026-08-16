"""Datenzugriff fuer WorkArea-Areas + Grants (`work_area`/`work_area_grant`).

Jede Query filtert auf `workspace_id` (Defense-in-Depth zusaetzlich zur RLS,
Muster `memory_repository`). Grants sind MATERIALISIERT — auch der Owner-Grant
der privaten Area (Plan-Entscheidung 5), damit die Scope-Filter-SQL in
`core/workarea_scope.py` uniform bleibt.

`get_or_create_private_area` ist der Auto-Anlage-Pfad beim ersten Zugriff
eines agent-gebundenen Tokens: Area + Owner-Grant entstehen in EINER
Transaktion; `ON CONFLICT DO NOTHING` macht den Pfad race-frei idempotent
(der partielle UNIQUE-Index aus Migration 0073 ist der Backstop — bei einem
parallelen Insert wartet Postgres auf die konkurrierende Transaktion und der
anschliessende SELECT liest den Gewinner).
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

import asyncpg

from who2be_models import (
    WorkAreaAssignment,
    WorkAreaGrantLevel,
    WorkAreaGrantRead,
    WorkAreaRead,
)

_AREA_COLUMNS = (
    "id, workspace_id, scope, owner_agent_id, name, retention_days, created_at, updated_at"
)

# Partieller Unique-Index aus 0073 als Conflict-Target: Namens-Kollision einer
# shared Area liefert KEINE Zeile zurueck (Service → 409).
_INSERT_SHARED_SQL = (
    "INSERT INTO work_area (workspace_id, scope, name, retention_days) "
    "VALUES ($1, 'shared', $2, $3) "
    "ON CONFLICT (workspace_id, name) WHERE scope = 'shared' DO NOTHING "
    f"RETURNING {_AREA_COLUMNS}"
)

_INSERT_PRIVATE_SQL = (
    "INSERT INTO work_area (workspace_id, scope, owner_agent_id, name) "
    "VALUES ($1, 'private', $2, $3) "
    "ON CONFLICT (workspace_id, owner_agent_id) WHERE scope = 'private' DO NOTHING "
    f"RETURNING {_AREA_COLUMNS}"
)

_SELECT_PRIVATE_SQL = (
    f"SELECT {_AREA_COLUMNS} FROM work_area "
    "WHERE workspace_id = $1 AND owner_agent_id = $2 AND scope = 'private'"
)

_UPSERT_GRANT_SQL = (
    "INSERT INTO work_area_grant (workspace_id, area_id, agent_id, level) "
    "VALUES ($1, $2, $3, $4) "
    "ON CONFLICT (area_id, agent_id) DO UPDATE SET level = excluded.level "
    "RETURNING area_id, agent_id, level, created_at"
)

_OWNER_GRANT_SQL = (
    "INSERT INTO work_area_grant (workspace_id, area_id, agent_id, level) "
    "VALUES ($1, $2, $3, 'write') "
    "ON CONFLICT (area_id, agent_id) DO NOTHING"
)

# Stabile Reihenfolge nach `agent_id`: der Grant-Editor der Web-UI soll bei
# unveraendertem Bestand immer dieselbe Liste sehen.
_LIST_GRANTS_SQL = (
    "SELECT area_id, agent_id, level, created_at FROM work_area_grant "
    "WHERE workspace_id = $1 AND area_id = $2 ORDER BY agent_id"
)

_AGENT_NAME_SQL = "SELECT name FROM agent WHERE id = $1 AND workspace_id = $2"


class WorkAreaRepository(Protocol):
    """Vertrag des Area-Datenzugriffs (Service-Sicht)."""

    async def create_shared(
        self, workspace_id: UUID, name: str, retention_days: int | None
    ) -> WorkAreaRead | None: ...

    async def get(self, workspace_id: UUID, area_id: UUID) -> WorkAreaRead | None: ...

    async def list_areas(
        self, workspace_id: UUID, restrict_ids: list[UUID] | None
    ) -> list[WorkAreaRead]: ...

    async def get_or_create_private_area(
        self, workspace_id: UUID, agent_id: UUID
    ) -> WorkAreaRead | None: ...

    async def agent_exists(self, workspace_id: UUID, agent_id: UUID) -> bool: ...

    async def set_grant(
        self, workspace_id: UUID, area_id: UUID, agent_id: UUID, level: WorkAreaGrantLevel
    ) -> WorkAreaGrantRead: ...

    async def list_grants(self, workspace_id: UUID, area_id: UUID) -> list[WorkAreaGrantRead]: ...

    async def delete_grant(self, workspace_id: UUID, area_id: UUID, agent_id: UUID) -> bool: ...

    async def list_assignments_for_agent(
        self, workspace_id: UUID, agent_id: UUID
    ) -> list[WorkAreaAssignment]: ...


class PgWorkAreaRepository:
    """asyncpg-Implementierung von `WorkAreaRepository`."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create_shared(
        self, workspace_id: UUID, name: str, retention_days: int | None
    ) -> WorkAreaRead | None:
        """Legt eine shared Area an; `None` = Name bereits vergeben (→ 409)."""
        row = await self._pool.fetchrow(_INSERT_SHARED_SQL, workspace_id, name, retention_days)
        return WorkAreaRead.model_validate(dict(row)) if row is not None else None

    async def get(self, workspace_id: UUID, area_id: UUID) -> WorkAreaRead | None:
        row = await self._pool.fetchrow(
            f"SELECT {_AREA_COLUMNS} FROM work_area WHERE workspace_id = $1 AND id = $2",
            workspace_id,
            area_id,
        )
        return WorkAreaRead.model_validate(dict(row)) if row is not None else None

    async def list_areas(
        self, workspace_id: UUID, restrict_ids: list[UUID] | None
    ) -> list[WorkAreaRead]:
        """Sichtbare Areas gemaess Scope-Filter.

        `restrict_ids=None` heisst „keine Einschraenkung" (Mensch editor+);
        sonst die vom Scope-Helper (`readable_area_ids`) berechnete ID-Menge
        (viewer: shared Areas; Agent: Grant-Areas) — ein Filterpfad fuer alle
        Aufrufer-Klassen.
        """
        rows = await self._pool.fetch(
            f"SELECT {_AREA_COLUMNS} FROM work_area "
            "WHERE workspace_id = $1 "
            "AND ($2::uuid[] IS NULL OR id = ANY($2::uuid[])) "
            "ORDER BY scope DESC, name, id",
            workspace_id,
            restrict_ids,
        )
        return [WorkAreaRead.model_validate(dict(row)) for row in rows]

    async def get_or_create_private_area(
        self, workspace_id: UUID, agent_id: UUID
    ) -> WorkAreaRead | None:
        """Get-or-create der privaten Area inkl. Owner-Grant (EINE Transaktion).

        `None` nur, wenn der Agent nicht (mehr) existiert — der Aufrufer
        behandelt das defensiv (404 bzw. leere whoami-Liste). Der Name ist der
        Agent-Name (Fallback 'Privat' fuer leere Namen).
        """
        async with self._pool.acquire() as conn, conn.transaction():
            agent_name = await conn.fetchval(_AGENT_NAME_SQL, agent_id, workspace_id)
            if agent_name is None:
                return None
            name = str(agent_name).strip() or "Privat"
            row = await conn.fetchrow(_INSERT_PRIVATE_SQL, workspace_id, agent_id, name)
            if row is None:
                row = await conn.fetchrow(_SELECT_PRIVATE_SQL, workspace_id, agent_id)
            assert row is not None  # UNIQUE-Index + Conflict-Wait garantieren die Zeile
            # Owner-Grant materialisieren (write impliziert read) — idempotent.
            await conn.execute(_OWNER_GRANT_SQL, workspace_id, row["id"], agent_id)
            return WorkAreaRead.model_validate(dict(row))

    async def agent_exists(self, workspace_id: UUID, agent_id: UUID) -> bool:
        found = await self._pool.fetchval(
            "SELECT 1 FROM agent WHERE id = $1 AND workspace_id = $2", agent_id, workspace_id
        )
        return found is not None

    async def set_grant(
        self, workspace_id: UUID, area_id: UUID, agent_id: UUID, level: WorkAreaGrantLevel
    ) -> WorkAreaGrantRead:
        row = await self._pool.fetchrow(
            _UPSERT_GRANT_SQL, workspace_id, area_id, agent_id, level.value
        )
        assert row is not None
        return WorkAreaGrantRead.model_validate(dict(row))

    async def list_grants(self, workspace_id: UUID, area_id: UUID) -> list[WorkAreaGrantRead]:
        """Alle Grants einer Area (Ist-Stand fuer den Grant-Editor).

        Kein Existenz-Check: der Service hat die Area vorher aufgeloest — eine
        leere Liste heisst hier schlicht „keine Grants vergeben".
        """
        rows = await self._pool.fetch(_LIST_GRANTS_SQL, workspace_id, area_id)
        return [WorkAreaGrantRead.model_validate(dict(row)) for row in rows]

    async def delete_grant(self, workspace_id: UUID, area_id: UUID, agent_id: UUID) -> bool:
        result = await self._pool.execute(
            "DELETE FROM work_area_grant "
            "WHERE workspace_id = $1 AND area_id = $2 AND agent_id = $3",
            workspace_id,
            area_id,
            agent_id,
        )
        return bool(str(result).endswith("1"))

    async def list_assignments_for_agent(
        self, workspace_id: UUID, agent_id: UUID
    ) -> list[WorkAreaAssignment]:
        """Area-Zuordnungen eines Agenten fuer `whoami.work_areas` (ADR-0047)."""
        rows = await self._pool.fetch(
            "SELECT wa.id, wa.name, wa.scope, g.level "
            "FROM work_area_grant g "
            "JOIN work_area wa ON wa.id = g.area_id AND wa.workspace_id = g.workspace_id "
            "WHERE g.workspace_id = $1 AND g.agent_id = $2 "
            "ORDER BY wa.scope DESC, wa.name, wa.id",
            workspace_id,
            agent_id,
        )
        return [WorkAreaAssignment.model_validate(dict(row)) for row in rows]
