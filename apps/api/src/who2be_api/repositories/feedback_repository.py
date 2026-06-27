"""Append-only Persistenz fuer das Usage-/Feedback-Flywheel (ADR-0038).

`PgFeedbackRepository` schreibt Nutzungs-Ereignisse + Feedback (nur INSERT) und
liefert das Kurations-Aggregat (`FeedbackSummary`). Alle Queries scopen explizit
auf `workspace_id` (Defense-in-Depth zusaetzlich zur RLS).
"""

from typing import Protocol
from uuid import UUID

import asyncpg

from who2be_models import (
    AgentFeedbackRead,
    FeedbackSummary,
    UsageEventRead,
)


class FeedbackRepository(Protocol):
    """Service-seitige Abstraktion fuer das Flywheel."""

    async def entity_belongs_to(
        self, workspace_id: UUID, entity_type: str, entity_id: UUID
    ) -> bool: ...

    async def insert_usage(
        self,
        workspace_id: UUID,
        agent_id: UUID | None,
        actor_id: UUID,
        entity_type: str,
        entity_id: UUID,
        version: int | None,
        outcome: str | None,
    ) -> UsageEventRead: ...

    async def insert_feedback(
        self,
        workspace_id: UUID,
        agent_id: UUID | None,
        actor_id: UUID,
        entity_type: str,
        entity_id: UUID,
        version: int | None,
        signal: str,
        note: str | None,
    ) -> AgentFeedbackRead: ...

    async def summarize(
        self, workspace_id: UUID, entity_type: str, entity_id: UUID
    ) -> FeedbackSummary: ...


# Polymorphes entity_type → physische Tabelle fuer den Workspace-Belongs-Check.
_ENTITY_TABLE: dict[str, str] = {
    "persona": "persona",
    "playbook": "playbook",
    "resource": "resource",
}


class PgFeedbackRepository:
    """asyncpg-Implementierung von `FeedbackRepository`."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def entity_belongs_to(
        self, workspace_id: UUID, entity_type: str, entity_id: UUID
    ) -> bool:
        table = _ENTITY_TABLE.get(entity_type)
        if table is None:
            return False
        owned = await self._pool.fetchval(
            f"SELECT 1 FROM {table} WHERE id = $1 AND workspace_id = $2",
            entity_id,
            workspace_id,
        )
        return owned is not None

    async def insert_usage(
        self,
        workspace_id: UUID,
        agent_id: UUID | None,
        actor_id: UUID,
        entity_type: str,
        entity_id: UUID,
        version: int | None,
        outcome: str | None,
    ) -> UsageEventRead:
        row = await self._pool.fetchrow(
            "INSERT INTO usage_event "
            "(workspace_id, agent_id, actor_id, entity_type, entity_id, version, outcome) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7) "
            "RETURNING id, entity_type, entity_id, version, outcome, agent_id, created_at",
            workspace_id,
            agent_id,
            actor_id,
            entity_type,
            entity_id,
            version,
            outcome,
        )
        assert row is not None
        return UsageEventRead.model_validate(dict(row))

    async def insert_feedback(
        self,
        workspace_id: UUID,
        agent_id: UUID | None,
        actor_id: UUID,
        entity_type: str,
        entity_id: UUID,
        version: int | None,
        signal: str,
        note: str | None,
    ) -> AgentFeedbackRead:
        row = await self._pool.fetchrow(
            "INSERT INTO agent_feedback "
            "(workspace_id, agent_id, actor_id, entity_type, entity_id, version, signal, note) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8) "
            "RETURNING id, entity_type, entity_id, version, signal, note, agent_id, created_at",
            workspace_id,
            agent_id,
            actor_id,
            entity_type,
            entity_id,
            version,
            signal,
            note,
        )
        assert row is not None
        return AgentFeedbackRead.model_validate(dict(row))

    async def summarize(
        self, workspace_id: UUID, entity_type: str, entity_id: UUID
    ) -> FeedbackSummary:
        usage_count = await self._pool.fetchval(
            "SELECT COUNT(*)::int FROM usage_event "
            "WHERE workspace_id = $1 AND entity_type = $2 AND entity_id = $3",
            workspace_id,
            entity_type,
            entity_id,
        )
        outcome_rows = await self._pool.fetch(
            "SELECT outcome, COUNT(*)::int AS n FROM usage_event "
            "WHERE workspace_id = $1 AND entity_type = $2 AND entity_id = $3 "
            "AND outcome IS NOT NULL GROUP BY outcome",
            workspace_id,
            entity_type,
            entity_id,
        )
        signal_rows = await self._pool.fetch(
            "SELECT signal, COUNT(*)::int AS n FROM agent_feedback "
            "WHERE workspace_id = $1 AND entity_type = $2 AND entity_id = $3 GROUP BY signal",
            workspace_id,
            entity_type,
            entity_id,
        )
        note_rows = await self._pool.fetch(
            "SELECT note FROM agent_feedback "
            "WHERE workspace_id = $1 AND entity_type = $2 AND entity_id = $3 "
            "AND note IS NOT NULL AND note <> '' ORDER BY created_at DESC LIMIT 10",
            workspace_id,
            entity_type,
            entity_id,
        )
        return FeedbackSummary(
            entity_type=entity_type,  # type: ignore[arg-type]
            entity_id=entity_id,
            usage_count=usage_count or 0,
            by_outcome={row["outcome"]: row["n"] for row in outcome_rows},
            by_signal={row["signal"]: row["n"] for row in signal_rows},
            recent_notes=[row["note"] for row in note_rows],
        )
