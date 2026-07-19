"""Datenzugriff fuer das Agent-Memory (ADR-0044).

Jede Query filtert auf `workspace_id` UND `agent_id` — per Signatur erzwungen
(Defense-in-Depth zusaetzlich zur RLS): es gibt keinen Weg, ueber dieses
Repository fremde Memories zu lesen oder zu schreiben (Leak-Test-Kritikalitaet,
Kap. 11.7 des Memory-Konzepts).

Retrieval (nur `status='active'`): hybrider Match aus FTS ('simple'-tsvector,
ADR-0037-Muster), ILIKE und pg_trgm-Similarity — faengt auch Namen/IDs/
Abkuerzungen, die reine FTS verfehlt. Ausgelieferte Treffer erhoehen das
Nutzungs-Log (`retrieval_count`/`last_retrieved_at`) in derselben Transaktion.
"""

from __future__ import annotations

import json
from typing import Protocol
from uuid import UUID

import asyncpg

from who2be_models import MemoryGuardConfig, MemoryHit, MemoryRead, MemoryStatus

# Trigram-Schwelle fuer den Dedup-Waechter (similarity(fact, kandidat)).
MEMORY_DEDUP_SIMILARITY = 0.6
# Trigram-Schwelle, ab der ein Fakt als Fuzzy-Suchtreffer gilt.
_SEARCH_SIMILARITY = 0.3

_READ_COLUMNS = (
    "id, agent_id, status, fact, context, category, importance, source, "
    "triage_note, retrieval_count, last_retrieved_at, created_at, updated_at"
)


class MemoryRepository(Protocol):
    """Vertrag des Memory-Datenzugriffs (Service-Sicht)."""

    async def agent_belongs_to(self, workspace_id: UUID, agent_id: UUID) -> bool: ...

    async def get_guard_config(self, workspace_id: UUID) -> MemoryGuardConfig: ...

    async def set_guard_config(
        self, workspace_id: UUID, config: MemoryGuardConfig
    ) -> MemoryGuardConfig: ...

    async def count_for_agent(self, workspace_id: UUID, agent_id: UUID) -> int: ...

    async def find_similar(
        self, workspace_id: UUID, agent_id: UUID, fact: str
    ) -> tuple[UUID, str] | None: ...

    async def insert(
        self,
        workspace_id: UUID,
        agent_id: UUID,
        status: MemoryStatus,
        fact: str,
        context: str | None,
        category: str,
        importance: int,
    ) -> MemoryRead: ...

    async def search_active(
        self, workspace_id: UUID, agent_id: UUID, query: str, k: int
    ) -> list[MemoryHit]: ...

    async def list_active(
        self, workspace_id: UUID, agent_id: UUID, limit: int
    ) -> list[MemoryHit]: ...

    async def list_for_agent(
        self, workspace_id: UUID, agent_id: UUID, status: MemoryStatus | None
    ) -> list[MemoryRead]: ...

    async def get(
        self, workspace_id: UUID, agent_id: UUID, memory_id: UUID
    ) -> MemoryRead | None: ...

    async def triage(
        self,
        workspace_id: UUID,
        agent_id: UUID,
        memory_id: UUID,
        new_status: MemoryStatus,
        fact: str | None,
        note: str | None,
    ) -> MemoryRead | None: ...

    async def update(
        self,
        workspace_id: UUID,
        agent_id: UUID,
        memory_id: UUID,
        fact: str | None,
        category: str | None,
        importance: int | None,
    ) -> MemoryRead | None: ...

    async def delete(self, workspace_id: UUID, agent_id: UUID, memory_id: UUID) -> bool: ...

    async def delete_all(self, workspace_id: UUID, agent_id: UUID) -> int: ...


class PgMemoryRepository:
    """asyncpg-Implementierung von `MemoryRepository`."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def agent_belongs_to(self, workspace_id: UUID, agent_id: UUID) -> bool:
        owned = await self._pool.fetchval(
            "SELECT 1 FROM agent WHERE id = $1 AND workspace_id = $2",
            agent_id,
            workspace_id,
        )
        return owned is not None

    async def get_guard_config(self, workspace_id: UUID) -> MemoryGuardConfig:
        # `{}` (Spalten-Default) deserialisiert zur Standard-Konfiguration.
        raw = await self._pool.fetchval(
            "SELECT memory_guard FROM workspace WHERE id = $1", workspace_id
        )
        if raw is None:
            return MemoryGuardConfig()
        return MemoryGuardConfig.model_validate(json.loads(raw) if isinstance(raw, str) else raw)

    async def set_guard_config(
        self, workspace_id: UUID, config: MemoryGuardConfig
    ) -> MemoryGuardConfig:
        await self._pool.execute(
            "UPDATE workspace SET memory_guard = $2::jsonb WHERE id = $1",
            workspace_id,
            json.dumps(config.model_dump(mode="json")),
        )
        return config

    async def count_for_agent(self, workspace_id: UUID, agent_id: UUID) -> int:
        count = await self._pool.fetchval(
            "SELECT COUNT(*)::int FROM agent_memory WHERE workspace_id = $1 AND agent_id = $2",
            workspace_id,
            agent_id,
        )
        return int(count or 0)

    async def find_similar(
        self, workspace_id: UUID, agent_id: UUID, fact: str
    ) -> tuple[UUID, str] | None:
        # Dedup-Waechter: prueft gegen ALLE Status (auch rejected — sonst
        # schlaegt der Agent Abgelehntes naechste Session erneut vor).
        row = await self._pool.fetchrow(
            "SELECT id, fact FROM agent_memory "
            "WHERE workspace_id = $1 AND agent_id = $2 AND similarity(fact, $3) >= $4 "
            "ORDER BY similarity(fact, $3) DESC LIMIT 1",
            workspace_id,
            agent_id,
            fact,
            MEMORY_DEDUP_SIMILARITY,
        )
        if row is None:
            return None
        return (row["id"], row["fact"])

    async def insert(
        self,
        workspace_id: UUID,
        agent_id: UUID,
        status: MemoryStatus,
        fact: str,
        context: str | None,
        category: str,
        importance: int,
    ) -> MemoryRead:
        row = await self._pool.fetchrow(
            "INSERT INTO agent_memory "
            "(workspace_id, agent_id, status, fact, context, category, importance) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7) "
            f"RETURNING {_READ_COLUMNS}",
            workspace_id,
            agent_id,
            status.value,
            fact,
            context,
            category,
            importance,
        )
        assert row is not None
        return MemoryRead.model_validate(dict(row))

    async def search_active(
        self, workspace_id: UUID, agent_id: UUID, query: str, k: int
    ) -> list[MemoryHit]:
        # Hybrid-Retrieval ueber aktive Memories: FTS ODER ILIKE ODER Trigram.
        # Ranking: FTS-Rank dominiert, Similarity und Importance justieren.
        rows = await self._pool.fetch(
            "SELECT id, fact, category FROM agent_memory "
            "WHERE workspace_id = $1 AND agent_id = $2 AND status = 'active' "
            "AND (search @@ plainto_tsquery('simple', $3) "
            "     OR fact ILIKE '%' || $3 || '%' "
            "     OR similarity(fact, $3) >= $5) "
            "ORDER BY ts_rank(search, plainto_tsquery('simple', $3)) DESC, "
            "         similarity(fact, $3) DESC, importance DESC "
            "LIMIT $4",
            workspace_id,
            agent_id,
            query,
            k,
            _SEARCH_SIMILARITY,
        )
        hits = [MemoryHit.model_validate(dict(row)) for row in rows]
        await self._bump_retrieval(workspace_id, agent_id, [hit.id for hit in hits])
        return hits

    async def list_active(self, workspace_id: UUID, agent_id: UUID, limit: int) -> list[MemoryHit]:
        rows = await self._pool.fetch(
            "SELECT id, fact, category FROM agent_memory "
            "WHERE workspace_id = $1 AND agent_id = $2 AND status = 'active' "
            "ORDER BY importance DESC, created_at DESC LIMIT $3",
            workspace_id,
            agent_id,
            limit,
        )
        hits = [MemoryHit.model_validate(dict(row)) for row in rows]
        await self._bump_retrieval(workspace_id, agent_id, [hit.id for hit in hits])
        return hits

    async def _bump_retrieval(
        self, workspace_id: UUID, agent_id: UUID, memory_ids: list[UUID]
    ) -> None:
        # Nutzungs-Log (Transparenz, ADR-0044). Selbstlimitierend: pro Memory
        # hoechstens ein Write/Minute (Security-Review N-1 — Reads sind sonst
        # ein ungedrosselter Write-Verstaerker am write_rate_limit vorbei).
        # Der Zaehler ist ein Transparenz-Signal, kein exakter Abruf-Counter.
        if not memory_ids:
            return
        await self._pool.execute(
            "UPDATE agent_memory "
            "SET retrieval_count = retrieval_count + 1, last_retrieved_at = now() "
            "WHERE workspace_id = $1 AND agent_id = $2 AND id = ANY($3::uuid[]) "
            "AND (last_retrieved_at IS NULL OR last_retrieved_at < now() - interval '60 seconds')",
            workspace_id,
            agent_id,
            memory_ids,
        )

    async def list_for_agent(
        self, workspace_id: UUID, agent_id: UUID, status: MemoryStatus | None
    ) -> list[MemoryRead]:
        if status is None:
            rows = await self._pool.fetch(
                f"SELECT {_READ_COLUMNS} FROM agent_memory "
                "WHERE workspace_id = $1 AND agent_id = $2 "
                "ORDER BY created_at DESC",
                workspace_id,
                agent_id,
            )
        else:
            rows = await self._pool.fetch(
                f"SELECT {_READ_COLUMNS} FROM agent_memory "
                "WHERE workspace_id = $1 AND agent_id = $2 AND status = $3 "
                "ORDER BY created_at DESC",
                workspace_id,
                agent_id,
                status.value,
            )
        return [MemoryRead.model_validate(dict(row)) for row in rows]

    async def get(self, workspace_id: UUID, agent_id: UUID, memory_id: UUID) -> MemoryRead | None:
        row = await self._pool.fetchrow(
            f"SELECT {_READ_COLUMNS} FROM agent_memory "
            "WHERE workspace_id = $1 AND agent_id = $2 AND id = $3",
            workspace_id,
            agent_id,
            memory_id,
        )
        return MemoryRead.model_validate(dict(row)) if row is not None else None

    async def triage(
        self,
        workspace_id: UUID,
        agent_id: UUID,
        memory_id: UUID,
        new_status: MemoryStatus,
        fact: str | None,
        note: str | None,
    ) -> MemoryRead | None:
        # Triage wirkt NUR auf pending (Schleusen-Invariante): active/rejected
        # Zeilen bleiben unberuehrt — dann kommt None zurueck (Service → 409).
        row = await self._pool.fetchrow(
            "UPDATE agent_memory "
            "SET status = $4, fact = COALESCE($5, fact), triage_note = $6, updated_at = now() "
            "WHERE workspace_id = $1 AND agent_id = $2 AND id = $3 AND status = 'pending' "
            f"RETURNING {_READ_COLUMNS}",
            workspace_id,
            agent_id,
            memory_id,
            new_status.value,
            fact,
            note,
        )
        return MemoryRead.model_validate(dict(row)) if row is not None else None

    async def update(
        self,
        workspace_id: UUID,
        agent_id: UUID,
        memory_id: UUID,
        fact: str | None,
        category: str | None,
        importance: int | None,
    ) -> MemoryRead | None:
        row = await self._pool.fetchrow(
            "UPDATE agent_memory "
            "SET fact = COALESCE($4, fact), category = COALESCE($5, category), "
            "    importance = COALESCE($6, importance), updated_at = now() "
            "WHERE workspace_id = $1 AND agent_id = $2 AND id = $3 "
            f"RETURNING {_READ_COLUMNS}",
            workspace_id,
            agent_id,
            memory_id,
            fact,
            category,
            importance,
        )
        return MemoryRead.model_validate(dict(row)) if row is not None else None

    async def delete(self, workspace_id: UUID, agent_id: UUID, memory_id: UUID) -> bool:
        result = await self._pool.execute(
            "DELETE FROM agent_memory WHERE workspace_id = $1 AND agent_id = $2 AND id = $3",
            workspace_id,
            agent_id,
            memory_id,
        )
        return bool(str(result).endswith("1"))

    async def delete_all(self, workspace_id: UUID, agent_id: UUID) -> int:
        result = await self._pool.execute(
            "DELETE FROM agent_memory WHERE workspace_id = $1 AND agent_id = $2",
            workspace_id,
            agent_id,
        )
        try:
            return int(result.rsplit(" ", 1)[-1])
        except ValueError:
            return 0
