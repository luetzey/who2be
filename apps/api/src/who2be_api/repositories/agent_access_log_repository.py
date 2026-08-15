"""Persistenz fuer das Auto-Zugriffslog `agent_access_log` (ADR-0047, WP14 — Spec F).

Append-only Schreiber (Migration 0079): ein Eintrag pro
(Agent, Element, Operation, Kalendertag), dedupliziert ueber den
UNIQUE-Index `agent_access_log_dedupe_uniq` + ``ON CONFLICT DO NOTHING`` —
der zweite Zugriff desselben Tages ist ein No-op, `first_at` behaelt den
ersten Zugriff. `access_date` setzt die DB (``CURRENT_DATE``), damit der
Dedupe-Tag und der Timestamp aus derselben Uhr stammen.

`sensitivity_at_access` ist der SERVER-Snapshot zum Zugriffszeitpunkt
(Wert des gelesenen/geschriebenen Objekts, nie vom Client) — eine spaetere
Umstufung des Objekts faelscht das Log nicht. `ref_id` ist polymorph
(uuid fuer artifact/node/table, sha256 fuer blob), daher ``text`` und ohne FK.

Der Insert akzeptiert einen Executor (Pool ODER Connection, Muster
`audit_log_repository`) — Aufrufer loggen NACH der erfolgreichen Operation,
typischerweise best-effort ueber den Pool (`services/access_log.log_access`).
"""

from __future__ import annotations

from typing import Literal, Protocol, TypeAlias
from uuid import UUID

import asyncpg

# Connection ODER Pool — beide unterstuetzen ``.execute(query, *args)``.
Executor: TypeAlias = asyncpg.Connection | asyncpg.Pool

# Art des referenzierten Elements bzw. der Operation — gespiegelte
# CHECK-Constraints aus Migration 0079 (geschlossenes Vokabular).
AccessRefKind = Literal["artifact", "node", "table", "blob"]
AccessOperation = Literal["read", "write"]


class AgentAccessLogRepository(Protocol):
    """Service-seitige Abstraktion fuer den Zugriffslog-Insert."""

    async def record(
        self,
        executor: Executor,
        workspace_id: UUID,
        agent_id: UUID,
        *,
        ref_kind: AccessRefKind,
        ref_id: str,
        operation: AccessOperation,
        sensitivity: str,
    ) -> None: ...


class PgAgentAccessLogRepository:
    """asyncpg-Implementierung von `AgentAccessLogRepository`.

    Stateless — der Executor kommt pro Aufruf, damit dieselbe Instanz
    Pool-Inserts (best-effort nach Commit) und Connection-Inserts (in einer
    laufenden Transaktion) bedienen kann.
    """

    async def record(
        self,
        executor: Executor,
        workspace_id: UUID,
        agent_id: UUID,
        *,
        ref_kind: AccessRefKind,
        ref_id: str,
        operation: AccessOperation,
        sensitivity: str,
    ) -> None:
        await executor.execute(
            "INSERT INTO agent_access_log "
            "(workspace_id, agent_id, ref_kind, ref_id, operation, "
            " sensitivity_at_access, access_date) "
            "VALUES ($1, $2, $3, $4, $5, $6, CURRENT_DATE) "
            "ON CONFLICT (agent_id, ref_kind, ref_id, operation, access_date) DO NOTHING",
            workspace_id,
            agent_id,
            ref_kind,
            ref_id,
            operation,
            sensitivity,
        )
