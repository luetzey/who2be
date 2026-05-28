"""Service-Adapter um `status_history` schreiben zu lassen.

Selbst keine Geschaeftslogik — reicht die `asyncpg.Connection` durch, damit
der Aufrufer (Transition-Service) Audit-Eintrag und Status-Wechsel in einer
Transaktion buendelt. Existiert primaer als Andockpunkt fuer die Dashboard-
Activity-Reads (Phase 2.1b-B) und als testbarer Wrapper.
"""

from uuid import UUID

import asyncpg

from who2be_api.repositories.status_history_repository import StatusHistoryRepository
from who2be_models import EntityType, VersionStatus


class StatusHistoryService:
    """Append-only Schreiber fuer Status-Audit-Eintraege."""

    def __init__(self, repo: StatusHistoryRepository) -> None:
        self._repo = repo

    async def record(
        self,
        conn: asyncpg.Connection,
        entity_type: EntityType,
        entity_id: UUID,
        from_status: VersionStatus | None,
        to_status: VersionStatus,
        changed_by: UUID,
        note: str | None,
    ) -> None:
        await self._repo.insert(
            conn,
            entity_type,
            entity_id,
            from_status,
            to_status,
            changed_by,
            note,
        )
