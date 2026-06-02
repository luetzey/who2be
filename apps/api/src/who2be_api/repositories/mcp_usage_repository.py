"""Persistenz des MCP-Monatskontingents (`mcp_usage`, Migration 0031).

`increment_if_allowed` ist ein **harter**, atomarer Check-and-Increment: der
Zaehler wird nur erhoeht, solange er unter dem Quota liegt. So bleibt das Limit
auch bei parallelen Requests strikt eingehalten und abgewiesene Reads treiben
den persistierten Stand nicht ueber das Quota hinaus (Defense gegen
Quota-Overrun durch Nebenlaeufigkeit/wiederholte Reads).
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

import asyncpg


class McpUsageRepository(Protocol):
    """Service-seitige Abstraktion fuer das MCP-Kontingent."""

    async def increment_if_allowed(self, org_id: UUID, period: str, quota: int) -> int | None: ...

    async def current(self, org_id: UUID, period: str) -> int: ...


class PgMcpUsageRepository:
    """asyncpg-Implementierung von `McpUsageRepository`."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def increment_if_allowed(self, org_id: UUID, period: str, quota: int) -> int | None:
        """Erhoeht atomar nur, wenn unter `quota`; liefert den neuen Stand oder `None`.

        `None` bedeutet: Kontingent erschoepft — der Zaehler wurde **nicht**
        erhoeht. Die `WHERE`-Klausel am `ON CONFLICT`-Pfad macht den Check und
        das Increment in einer einzigen atomaren Anweisung (kein Read-modify-write).
        """
        count = await self._pool.fetchval(
            "INSERT INTO mcp_usage (org_id, period, count) VALUES ($1, $2, 1) "
            "ON CONFLICT (org_id, period) DO UPDATE "
            "  SET count = mcp_usage.count + 1, updated_at = now() "
            "  WHERE mcp_usage.count < $3 "
            "RETURNING count",
            org_id,
            period,
            quota,
        )
        return int(count) if count is not None else None

    async def current(self, org_id: UUID, period: str) -> int:
        """Liest den aktuellen Stand (0, wenn fuer die Periode noch nichts zaehlt)."""
        count = await self._pool.fetchval(
            "SELECT count FROM mcp_usage WHERE org_id = $1 AND period = $2",
            org_id,
            period,
        )
        return int(count) if count is not None else 0
