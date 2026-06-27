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
    FeedbackEvents,
    FeedbackItem,
    FeedbackOverviewItem,
    FeedbackSummary,
    FeedbackUnusedItem,
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

    async def list_events(
        self, workspace_id: UUID, entity_type: str, entity_id: UUID, limit: int
    ) -> FeedbackEvents: ...

    async def overview(self, workspace_id: UUID) -> list[FeedbackOverviewItem]: ...

    async def unused(self, workspace_id: UUID) -> list[FeedbackUnusedItem]: ...

    async def list_items(self, workspace_id: UUID, limit: int) -> list[FeedbackItem]: ...

    async def feedback_belongs_to(self, workspace_id: UUID, feedback_id: UUID) -> bool: ...

    async def insert_resolution(
        self,
        workspace_id: UUID,
        feedback_id: UUID,
        actor_id: UUID,
        resolution: str,
        note: str | None,
    ) -> AgentFeedbackRead: ...


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

    async def list_events(
        self, workspace_id: UUID, entity_type: str, entity_id: UUID, limit: int
    ) -> FeedbackEvents:
        # Jedes Feedback traegt seinen aktuellen Triage-Status (juengstes
        # Resolution-Event, via korrelierter Subquery) — oder NULL.
        feedback_rows = await self._pool.fetch(
            "SELECT f.id, f.entity_type, f.entity_id, f.version, f.signal, f.note, "
            "f.agent_id, f.created_at, "
            "(SELECT r.resolution FROM feedback_resolution r "
            "   WHERE r.feedback_id = f.id ORDER BY r.created_at DESC LIMIT 1) AS resolution "
            "FROM agent_feedback f "
            "WHERE f.workspace_id = $1 AND f.entity_type = $2 AND f.entity_id = $3 "
            "ORDER BY f.created_at DESC LIMIT $4",
            workspace_id,
            entity_type,
            entity_id,
            limit,
        )
        usage_rows = await self._pool.fetch(
            "SELECT id, entity_type, entity_id, version, outcome, agent_id, created_at "
            "FROM usage_event "
            "WHERE workspace_id = $1 AND entity_type = $2 AND entity_id = $3 "
            "ORDER BY created_at DESC LIMIT $4",
            workspace_id,
            entity_type,
            entity_id,
            limit,
        )
        return FeedbackEvents(
            entity_type=entity_type,  # type: ignore[arg-type]
            entity_id=entity_id,
            feedback=[AgentFeedbackRead.model_validate(dict(r)) for r in feedback_rows],
            usage=[UsageEventRead.model_validate(dict(r)) for r in usage_rows],
        )

    async def overview(self, workspace_id: UUID) -> list[FeedbackOverviewItem]:
        # Workspace-weite Aggregation pro Element ueber beide Telemetrie-Tabellen.
        # FULL OUTER JOIN, damit auch Elemente mit nur Usage ODER nur Feedback
        # erscheinen. Der Namens-JOIN auf die drei Ziel-Tabellen filtert
        # implizit geloeschte Elemente (name NULL) heraus.
        rows = await self._pool.fetch(
            "WITH usage_agg AS ("
            "  SELECT entity_type, entity_id, COUNT(*)::int AS usage_count, "
            "         MAX(created_at) AS last_usage "
            "  FROM usage_event WHERE workspace_id = $1 "
            "  GROUP BY entity_type, entity_id"
            "), fb_agg AS ("
            "  SELECT entity_type, entity_id, COUNT(*)::int AS feedback_count, "
            "    COUNT(*) FILTER (WHERE signal IN ('outdated','incorrect','unclear'))::int "
            "      AS negative_count, "
            "    COUNT(*) FILTER (WHERE signal = 'helpful')::int AS helpful_count, "
            "    MAX(created_at) AS last_feedback "
            "  FROM agent_feedback WHERE workspace_id = $1 "
            "  GROUP BY entity_type, entity_id"
            "), combined AS ("
            "  SELECT COALESCE(u.entity_type, f.entity_type) AS entity_type, "
            "         COALESCE(u.entity_id, f.entity_id) AS entity_id, "
            "         COALESCE(u.usage_count, 0) AS usage_count, "
            "         COALESCE(f.feedback_count, 0) AS feedback_count, "
            "         COALESCE(f.negative_count, 0) AS negative_count, "
            "         COALESCE(f.helpful_count, 0) AS helpful_count, "
            "         GREATEST(u.last_usage, f.last_feedback) AS last_activity_at "
            "  FROM usage_agg u "
            "  FULL OUTER JOIN fb_agg f "
            "    ON u.entity_type = f.entity_type AND u.entity_id = f.entity_id"
            ") "
            "SELECT c.entity_type, c.entity_id, c.usage_count, c.feedback_count, "
            "       c.negative_count, c.helpful_count, c.last_activity_at, "
            "       COALESCE(p.name, pb.name, r.name) AS name "
            "FROM combined c "
            "LEFT JOIN persona p   ON c.entity_type = 'persona'  "
            "  AND p.id = c.entity_id  AND p.workspace_id = $1 "
            "LEFT JOIN playbook pb ON c.entity_type = 'playbook' "
            "  AND pb.id = c.entity_id AND pb.workspace_id = $1 "
            "LEFT JOIN resource r  ON c.entity_type = 'resource' "
            "  AND r.id = c.entity_id  AND r.workspace_id = $1 "
            "WHERE COALESCE(p.name, pb.name, r.name) IS NOT NULL "
            "ORDER BY c.last_activity_at DESC NULLS LAST",
            workspace_id,
        )
        return [FeedbackOverviewItem.model_validate(dict(r)) for r in rows]

    async def unused(self, workspace_id: UUID) -> list[FeedbackUnusedItem]:
        # „Ungenutzt" = hat eine aktive Version (Agenten KOENNTEN es nutzen), aber
        # kein einziges Usage-/Feedback-Ereignis. Pro Entitaetstyp dieselbe Logik,
        # via UNION ALL zusammengefuehrt. Der NOT-EXISTS-Doppelfilter haelt die
        # Stale-Definition streng (weder genutzt noch bewertet).
        rows = await self._pool.fetch(
            "SELECT entity_type, entity_id, name FROM ("
            "  SELECT 'persona' AS entity_type, p.id AS entity_id, p.name AS name "
            "  FROM persona p WHERE p.workspace_id = $1 "
            "    AND EXISTS (SELECT 1 FROM persona_version v "
            "      WHERE v.persona_id = p.id AND v.status = 'active') "
            "  UNION ALL "
            "  SELECT 'playbook', pb.id, pb.name "
            "  FROM playbook pb WHERE pb.workspace_id = $1 "
            "    AND EXISTS (SELECT 1 FROM playbook_version v "
            "      WHERE v.playbook_id = pb.id AND v.status = 'active') "
            "  UNION ALL "
            "  SELECT 'resource', r.id, r.name "
            "  FROM resource r WHERE r.workspace_id = $1 "
            "    AND EXISTS (SELECT 1 FROM resource_version v "
            "      WHERE v.resource_id = r.id AND v.status = 'active') "
            ") AS active_elements "
            "WHERE NOT EXISTS (SELECT 1 FROM usage_event u "
            "    WHERE u.workspace_id = $1 AND u.entity_type = active_elements.entity_type "
            "      AND u.entity_id = active_elements.entity_id) "
            "  AND NOT EXISTS (SELECT 1 FROM agent_feedback f "
            "    WHERE f.workspace_id = $1 AND f.entity_type = active_elements.entity_type "
            "      AND f.entity_id = active_elements.entity_id) "
            "ORDER BY entity_type, name",
            workspace_id,
        )
        return [FeedbackUnusedItem.model_validate(dict(r)) for r in rows]

    async def list_items(self, workspace_id: UUID, limit: int) -> list[FeedbackItem]:
        # Alle qualitativen Feedbacks des Workspaces + Element-Name (Namens-JOIN
        # filtert geloeschte Elemente raus) + aktueller Triage-Status. Speist den
        # zentralen Posteingang; serverseitig gekappt.
        rows = await self._pool.fetch(
            "SELECT f.id, f.entity_type, f.entity_id, f.version, f.signal, f.note, "
            "f.agent_id, f.created_at, "
            "(SELECT r.resolution FROM feedback_resolution r "
            "   WHERE r.feedback_id = f.id ORDER BY r.created_at DESC LIMIT 1) AS resolution, "
            "COALESCE(p.name, pb.name, rs.name) AS name "
            "FROM agent_feedback f "
            "LEFT JOIN persona p   ON f.entity_type = 'persona'  "
            "  AND p.id = f.entity_id  AND p.workspace_id = $1 "
            "LEFT JOIN playbook pb  ON f.entity_type = 'playbook' "
            "  AND pb.id = f.entity_id AND pb.workspace_id = $1 "
            "LEFT JOIN resource rs  ON f.entity_type = 'resource' "
            "  AND rs.id = f.entity_id AND rs.workspace_id = $1 "
            "WHERE f.workspace_id = $1 "
            "  AND COALESCE(p.name, pb.name, rs.name) IS NOT NULL "
            "ORDER BY f.created_at DESC LIMIT $2",
            workspace_id,
            limit,
        )
        return [FeedbackItem.model_validate(dict(r)) for r in rows]

    async def feedback_belongs_to(self, workspace_id: UUID, feedback_id: UUID) -> bool:
        owned = await self._pool.fetchval(
            "SELECT 1 FROM agent_feedback WHERE id = $1 AND workspace_id = $2",
            feedback_id,
            workspace_id,
        )
        return owned is not None

    async def insert_resolution(
        self,
        workspace_id: UUID,
        feedback_id: UUID,
        actor_id: UUID,
        resolution: str,
        note: str | None,
    ) -> AgentFeedbackRead:
        # Append-only Triage-Event schreiben, dann den Feedback-Eintrag mit dem
        # nun aktuellen Status (= dieses Event) zurueckgeben.
        await self._pool.execute(
            "INSERT INTO feedback_resolution "
            "(workspace_id, feedback_id, actor_id, resolution, note) "
            "VALUES ($1, $2, $3, $4, $5)",
            workspace_id,
            feedback_id,
            actor_id,
            resolution,
            note,
        )
        row = await self._pool.fetchrow(
            "SELECT f.id, f.entity_type, f.entity_id, f.version, f.signal, f.note, "
            "f.agent_id, f.created_at, "
            "(SELECT r.resolution FROM feedback_resolution r "
            "   WHERE r.feedback_id = f.id ORDER BY r.created_at DESC LIMIT 1) AS resolution "
            "FROM agent_feedback f WHERE f.id = $1 AND f.workspace_id = $2",
            feedback_id,
            workspace_id,
        )
        assert row is not None
        return AgentFeedbackRead.model_validate(dict(row))
