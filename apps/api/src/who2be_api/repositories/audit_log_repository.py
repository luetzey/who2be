"""Persistenz fuer `audit_log` (Compliance-Remediation WP-B, Migration 0044).

Append-only Schreiber fuer Admin-/Security-Events. Der Insert akzeptiert
einen Executor — entweder einen Pool (separater Tx-Pfad) oder eine bereits
gehaltene `asyncpg.Connection` (Insert in einer laufenden Transaktion,
analog `status_history_repository.py`). Damit kann der Audit-Eintrag in
demselben atomaren Schritt wie die ausloesende Mutation landen.

Die App-Rolle `who2be_app` darf nur SELECT/INSERT (Migration 0044);
UPDATE/DELETE schlaegt zur Laufzeit mit `InsufficientPrivilege` fehl — der
Audit-Trail ist DB-seitig append-only.
"""

from __future__ import annotations

import json
from typing import Any, Protocol, TypeAlias
from uuid import UUID

import asyncpg

# Connection ODER Pool — beide unterstuetzen ``.execute(query, *args)``.
Executor: TypeAlias = asyncpg.Connection | asyncpg.Pool


class AuditLogRepository(Protocol):
    """Service-seitige Abstraktion fuer den Audit-Insert."""

    async def insert(
        self,
        executor: Executor,
        *,
        action: str,
        org_id: UUID | None = None,
        workspace_id: UUID | None = None,
        actor_id: UUID | None = None,
        target: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None: ...


class PgAuditLogRepository:
    """asyncpg-Implementierung von `AuditLogRepository`.

    Stateless — der Executor wird pro Aufruf uebergeben, damit derselbe
    Repo-Instance sowohl Pool-Inserts (best-effort) als auch
    Connection-Inserts (in laufender Transaktion) bedienen kann.
    """

    async def insert(
        self,
        executor: Executor,
        *,
        action: str,
        org_id: UUID | None = None,
        workspace_id: UUID | None = None,
        actor_id: UUID | None = None,
        target: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        # ``detail`` als jsonb-String serialisieren — der App-Pool registriert
        # einen jsonb-Codec (siehe core/db.init_connection), Owner-/Test-
        # Connections nicht zwingend. Ein String funktioniert unter beiden.
        detail_json = json.dumps(detail) if detail is not None else "{}"
        await executor.execute(
            "INSERT INTO audit_log "
            "(org_id, workspace_id, actor_id, action, target, detail) "
            "VALUES ($1, $2, $3, $4, $5, $6::jsonb)",
            org_id,
            workspace_id,
            actor_id,
            action,
            target,
            detail_json,
        )
