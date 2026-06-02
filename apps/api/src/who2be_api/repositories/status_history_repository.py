"""Persistenz fuer den Status-Audit-Trail (`status_history`).

Append-only Schreiber (Migration 0012). Der Insert laeuft mit einer extern
gehaltenen `asyncpg.Connection`, damit der Aufrufer (Transition-Service) den
Eintrag in derselben Transaktion wie den Status-Wechsel ablegen kann.
"""

from typing import Protocol
from uuid import UUID

import asyncpg

from who2be_models import EntityType, VersionStatus


class StatusHistoryRepository(Protocol):
    """Service-seitige Abstraktion fuer Status-Audit-Eintraege."""

    async def insert(
        self,
        conn: asyncpg.Connection,
        entity_type: EntityType,
        entity_id: UUID,
        from_status: VersionStatus | None,
        to_status: VersionStatus,
        changed_by: UUID,
        note: str | None,
        version: int | None = None,
    ) -> None: ...


class PgStatusHistoryRepository:
    """asyncpg-Implementierung von `StatusHistoryRepository`."""

    async def insert(
        self,
        conn: asyncpg.Connection,
        entity_type: EntityType,
        entity_id: UUID,
        from_status: VersionStatus | None,
        to_status: VersionStatus,
        changed_by: UUID,
        note: str | None,
        version: int | None = None,
    ) -> None:
        await conn.execute(
            "INSERT INTO status_history "
            "(entity_type, entity_id, version, from_status, to_status, changed_by, note) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7)",
            entity_type,
            entity_id,
            version,
            from_status.value if from_status is not None else None,
            to_status.value,
            changed_by,
            note,
        )
