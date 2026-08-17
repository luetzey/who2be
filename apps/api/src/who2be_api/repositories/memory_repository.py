"""Datenzugriff fuer das Agent-Memory (ADR-0044).

Jede Query filtert auf `workspace_id` UND `agent_id` — per Signatur erzwungen
(Defense-in-Depth zusaetzlich zur RLS): es gibt keinen Weg, ueber dieses
Repository fremde Memories zu lesen oder zu schreiben (Leak-Test-Kritikalitaet,
Kap. 11.7 des Memory-Konzepts).

Retrieval (nur `status='active'`): drei Zweige — FTS ('simple'-tsvector,
ADR-0037-Muster), ILIKE und pg_trgm-Similarity — plus optional ein
Vektor-Zweig (ADR-0046 Welle 3). Die drei lexikalischen Zweige faengt auch
Namen/IDs/Abkuerzungen, die reine FTS verfehlt; der Vektor-Zweig faengt
Umschreibungen und sprachuebergreifende Treffer, die keiner von ihnen findet.

Die Raenge werden per Reciprocal Rank Fusion verschmolzen, NICHT mehr als
lexikografische `ORDER BY`-Kaskade sortiert. Der Grund ist nicht Eleganz: eine
Kaskade laesst den ersten Term dominieren, sodass ein perfekter Vektor-Treffer
hinter jedem beliebigen FTS-Treffer landet. RRF fusioniert Raenge und ist damit
skalenunabhaengig — `ts_rank`, Trigram-Similarity und Cosinus-Distanz sind
nicht vergleichbar normierbar.

Ausgelieferte Treffer erhoehen das Nutzungs-Log
(`retrieval_count`/`last_retrieved_at`) — in einem SEPARATEN Statement, nicht
in derselben Transaktion (der frueher hier stehende Satz war falsch).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

import asyncpg

from who2be_models import MemoryGuardConfig, MemoryHit, MemoryRead, MemoryStatus

# Trigram-Schwelle fuer den Dedup-Waechter (similarity(fact, kandidat)).
MEMORY_DEDUP_SIMILARITY = 0.6
# Trigram-Schwelle, ab der ein Fakt als Fuzzy-Suchtreffer gilt.
_SEARCH_SIMILARITY = 0.3

# Reciprocal Rank Fusion, identisch zur Passage-Suche (content_chunk_repository).
_RRF_K = 60

# Ab welcher Cosinus-AEHNLICHKEIT ein Vektor-Treffer zaehlt. Ohne Schranke
# liefert die Vektor-Suche IMMER die k naechsten Memories — auch zu einer voellig
# fremden Frage. Bei Memory waere das besonders schaedlich: der Agent haelt
# gespeicherte Nutzerdaten fuer eine Antwort auf seine Frage.
# Bewusst konservativ, gegen das reale Modell noch nicht kalibriert (ADR-0046).
_MIN_VECTOR_SIMILARITY = 0.45

# Ab welcher Cosinus-AEHNLICHKEIT der Dedup-Waechter zuschlaegt. DEUTLICH
# strenger als die Suchschwelle: ein falsch positiver Dedup verwirft einen
# gueltigen Fakt dauerhaft (409), ein falsch negativer kostet nur einen
# Listenplatz von 500. Die Asymmetrie der Kosten bestimmt die Schwelle.
_DEDUP_VECTOR_SIMILARITY = 0.92

# Existiert die Vektor-Spalte? Migration 0072 legt sie NICHT an, wenn pgvector
# auf dem Server fehlt (fail-soft) — der Normalfall einer On-Prem-Instanz auf
# Standard-Postgres, der keinen Fehler ausloesen darf.
_HAS_VECTOR_SQL = """
SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'agent_memory' AND column_name = 'content_vector'
)
"""

_vector_supported: bool | None = None

_READ_COLUMNS = (
    "id, agent_id, status, fact, context, category, importance, source, "
    "triage_note, retrieval_count, last_retrieved_at, created_at, updated_at"
)


def reset_vector_support() -> None:
    """Verwirft den Prozess-Cache der Spalten-Erkennung (Tests)."""
    global _vector_supported
    _vector_supported = None


class MemoryRepository(Protocol):
    """Vertrag des Memory-Datenzugriffs (Service-Sicht)."""

    async def agent_belongs_to(self, workspace_id: UUID, agent_id: UUID) -> bool: ...

    async def get_guard_config(self, workspace_id: UUID) -> MemoryGuardConfig: ...

    async def set_guard_config(
        self, workspace_id: UUID, config: MemoryGuardConfig
    ) -> MemoryGuardConfig: ...

    async def count_for_agent(self, workspace_id: UUID, agent_id: UUID) -> int: ...

    async def find_similar(
        self,
        workspace_id: UUID,
        agent_id: UUID,
        fact: str,
        fact_vector: Sequence[float] | None = None,
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
        self,
        workspace_id: UUID,
        agent_id: UUID,
        query: str,
        k: int,
        query_vector: Sequence[float] | None = None,
    ) -> list[MemoryHit]: ...

    async def set_vector(self, memory_id: UUID, vector: Sequence[float]) -> None: ...

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
        # dict, NICHT vor-serialisiert: der `::jsonb`-Cast aktiviert den
        # jsonb-Codec des App-Pools (`core/db.init_connection`), ein String
        # wuerde ein zweites Mal encodiert und landete als JSON-*String* in
        # der Spalte. `get_guard_config` faengt das zwar tolerant ab — die
        # gleiche Doppel-Encodierung hat den describe-Pfad aber ueber einen
        # strengeren Leser mit 500 beendet (Befund 2026-08-16).
        await self._pool.execute(
            "UPDATE workspace SET memory_guard = $2::jsonb WHERE id = $1",
            workspace_id,
            config.model_dump(mode="json"),
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
        self,
        workspace_id: UUID,
        agent_id: UUID,
        fact: str,
        fact_vector: Sequence[float] | None = None,
    ) -> tuple[UUID, str] | None:
        """Findet ein hinreichend aehnliches Memory (Dedup-Waechter).

        Prueft gegen ALLE Status, auch `rejected` — sonst schlaegt der Agent
        Abgelehntes in der naechsten Session erneut vor.

        Der Trigram-Zweig (≥ `MEMORY_DEDUP_SIMILARITY`) bleibt massgeblich und
        unveraendert. Der Vektor-Zweig kommt additiv dazu und faengt
        Paraphrasen, die zeichenbasiert nicht aehnlich sind („Kunde bevorzugt
        E-Mail" vs. „Kontaktpraeferenz des Kunden ist E-Mail"). Seine Schwelle
        ist deutlich strenger als die der Suche: ein falsch positiver Dedup
        verwirft einen gueltigen Fakt dauerhaft, ein falsch negativer kostet
        nur einen von 500 Listenplaetzen.
        """
        use_vector = fact_vector is not None and await self.vector_supported()
        if not use_vector:
            row = await self._pool.fetchrow(
                "SELECT id, fact FROM agent_memory "
                "WHERE workspace_id = $1 AND agent_id = $2 AND similarity(fact, $3) >= $4 "
                "ORDER BY similarity(fact, $3) DESC LIMIT 1",
                workspace_id,
                agent_id,
                fact,
                MEMORY_DEDUP_SIMILARITY,
            )
        else:
            row = await self._pool.fetchrow(
                "SELECT id, fact FROM agent_memory "
                "WHERE workspace_id = $1 AND agent_id = $2 "
                "  AND (similarity(fact, $3) >= $4 "
                "       OR (content_vector IS NOT NULL "
                f"           AND 1 - (content_vector <=> $5::vector) >= "
                f"{_DEDUP_VECTOR_SIMILARITY})) "
                "ORDER BY similarity(fact, $3) DESC LIMIT 1",
                workspace_id,
                agent_id,
                fact,
                MEMORY_DEDUP_SIMILARITY,
                list(fact_vector or []),
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

    async def vector_supported(self) -> bool:
        """True, wenn `agent_memory.content_vector` existiert (gecacht)."""
        global _vector_supported
        if _vector_supported is None:
            _vector_supported = bool(await self._pool.fetchval(_HAS_VECTOR_SQL))
        return _vector_supported

    async def search_active(
        self,
        workspace_id: UUID,
        agent_id: UUID,
        query: str,
        k: int,
        query_vector: Sequence[float] | None = None,
    ) -> list[MemoryHit]:
        """Rangsortierte aktive Memories (ADR-0044, Fusion nach ADR-0046).

        Vier Zweige, jeder liefert einen eigenen Rang, verschmolzen per RRF:

        - **FTS** — Wortstamm-Treffer.
        - **ILIKE** — Teilstrings, die die Tokenisierung zerlegt (Projekt-IDs).
        - **Trigram** — Tippfehler und Abkuerzungen.
        - **Vektor** (optional) — Umschreibungen und sprachuebergreifend.

        Frueher entschied eine lexikografische Kaskade
        (`ts_rank` → `similarity` → `importance`). Die liess den ersten Term
        dominieren: ein perfekter Vektor-Treffer waere hinter jedem beliebigen
        FTS-Treffer gelandet. `importance` bleibt als Tiebreak — ein
        Transparenz-Signal des Kurators, kein Relevanzmass.

        `query_vector=None` (kein Embedding-Port oder keine Spalte) heisst
        einfach: drei Zweige statt vier.
        """
        use_vector = query_vector is not None and await self.vector_supported()

        # Feste Positionen: $1 workspace, $2 agent, $3 query, $4 limit,
        # $5 Trigram-Schwelle. Der Vektor kommt nur dazu, wenn er gebraucht
        # wird — ein gebundener, aber unreferenzierter Parameter waere fuer
        # Postgres typlos.
        args: list[object] = [workspace_id, agent_id, query, k, _SEARCH_SIMILARITY]
        # „ilike" waere als CTE-Name ein reserviertes Keyword.
        branches = ["fts", "substr", "trgm"]
        vector_cte = ""
        if use_vector:
            args.append(list(query_vector or []))
            branches.append("vec")
            vector_cte = (
                ", vec AS ("
                "  SELECT id, row_number() OVER ("
                "    ORDER BY content_vector <=> $6::vector, importance DESC"
                "  ) AS rnk"
                "  FROM scoped"
                "  WHERE content_vector IS NOT NULL"
                f"    AND 1 - (content_vector <=> $6::vector) >= {_MIN_VECTOR_SIMILARITY}"
                ")"
            )

        score = " + ".join(f"coalesce(1.0 / ({_RRF_K} + {b}.rnk), 0)" for b in branches)
        joins = " ".join(f"LEFT JOIN {b} ON {b}.id = s.id" for b in branches)
        matched = " OR ".join(f"{b}.id IS NOT NULL" for b in branches)

        sql = (
            "WITH scoped AS ("
            "  SELECT id, fact, category, importance, search"
            f"{', content_vector' if use_vector else ''}"
            "  FROM agent_memory"
            "  WHERE workspace_id = $1 AND agent_id = $2 AND status = 'active'"
            "), "
            "fts AS ("
            "  SELECT id, row_number() OVER ("
            "    ORDER BY ts_rank(search, plainto_tsquery('simple', $3)) DESC, importance DESC"
            "  ) AS rnk"
            "  FROM scoped WHERE search @@ plainto_tsquery('simple', $3)"
            "), "
            "substr AS ("
            "  SELECT id, row_number() OVER (ORDER BY importance DESC) AS rnk"
            "  FROM scoped WHERE fact ILIKE '%' || $3 || '%'"
            "), "
            "trgm AS ("
            "  SELECT id, row_number() OVER ("
            "    ORDER BY similarity(fact, $3) DESC, importance DESC"
            "  ) AS rnk"
            "  FROM scoped WHERE similarity(fact, $3) >= $5"
            ")"
            f"{vector_cte} "
            "SELECT s.id, s.fact, s.category "
            f"FROM scoped s {joins} "
            f"WHERE {matched} "
            f"ORDER BY ({score}) DESC, s.importance DESC "
            "LIMIT $4"
        )

        rows = await self._pool.fetch(sql, *args)
        hits = [MemoryHit.model_validate(dict(row)) for row in rows]
        await self._bump_retrieval(workspace_id, agent_id, [hit.id for hit in hits])
        return hits

    async def set_vector(self, memory_id: UUID, vector: Sequence[float]) -> None:
        """Setzt den Vektor eines Memories (Schreibpfad + Backfill)."""
        if not await self.vector_supported():
            return
        await self._pool.execute(
            "UPDATE agent_memory SET content_vector = $2 WHERE id = $1",
            memory_id,
            list(vector),
        )

    async def fetch_missing_vectors(self, limit: int) -> list[tuple[UUID, str]]:
        """Memories ohne Vektor — Arbeitsvorrat des Backfills."""
        if not await self.vector_supported():
            return []
        rows = await self._pool.fetch(
            "SELECT id, fact FROM agent_memory "
            "WHERE content_vector IS NULL ORDER BY created_at LIMIT $1",
            limit,
        )
        return [(row["id"], row["fact"]) for row in rows]

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
