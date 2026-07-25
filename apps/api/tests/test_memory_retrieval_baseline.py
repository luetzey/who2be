"""Baseline des Memory-Retrievals vor der Semantik-Umstellung (ADR-0046).

`memory_repository.search_active` hatte bis hierher KEINEN eigenen Test — die
Ranking-Kaskade, die Trigram-Schwelle und der Dedup-Waechter waren nur
indirekt ueber `test_memory.py` abgedeckt. Welle 3 baut die Kaskade
(`ts_rank` → `similarity` → `importance`) auf eine Score-Fusion um; ohne
Baseline liesse sich hinterher nicht belegen, dass dabei keine Treffer
verloren gehen.

Zwei Sorten Test hier:

1. **Faehigkeiten, die erhalten bleiben muessen** — Wortstamm-Treffer,
   Teilstring, Fuzzy-Match auf Tippfehler, Status-Isolation, Agent-Isolation.
2. **Die dokumentierte Luecke** — `test_paraphrase_is_not_found_today` haelt
   fest, dass Paraphrasen heute NICHT gefunden werden. Der Test ist bewusst so
   formuliert, dass Welle 3 ihn umdrehen muss: er ist die ausfuehrbare Form
   des Versprechens aus dem MCP-Docstring („durchsucht … semantisch"), das die
   Implementierung bis heute nicht einloest.
"""

import asyncio
from typing import Any
from uuid import UUID

import asyncpg
import pytest

from who2be_api.core.config import get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.repositories.memory_repository import PgMemoryRepository
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace
from who2be_models import MemoryStatus


def _db_reachable() -> bool:
    async def _check() -> bool:
        try:
            conn = await asyncpg.connect(get_settings().database_url)
        except (asyncpg.PostgresError, OSError):
            return False
        await conn.close()
        return True

    return asyncio.run(_check())


def _prepare_db() -> None:
    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await apply_migrations(conn, MIGRATIONS_DIR)
        finally:
            await conn.close()

    asyncio.run(_run())


async def _make_agent(
    conn: asyncpg.Connection, workspace_id: UUID, owner_id: UUID, name: str
) -> UUID:
    """Legt eine minimale Agent-Huelle an (Memory haengt per FK am Agenten)."""
    agent_id: UUID = await conn.fetchval(
        "INSERT INTO agent (workspace_id, owner_id, name) VALUES ($1, $2, $3) RETURNING id",
        workspace_id,
        owner_id,
        name,
    )
    return agent_id


def _with_repo(fn: Any) -> Any:
    """Fuehrt `fn(repo, pool, workspace_id, agent_id)` gegen eine frische DB aus.

    `setup_workspace`/`cleanup_workspaces` sind synchrone Helfer, die intern
    selbst `asyncio.run` aufrufen — sie muessen deshalb AUSSERHALB der
    Coroutine laufen, sonst gibt es „cannot be called from a running loop".
    """
    owner = fresh_user_id()
    workspace_id = setup_workspace(owner)

    async def _run() -> Any:
        pool = await asyncpg.create_pool(get_settings().database_url, min_size=1, max_size=2)
        assert pool is not None
        try:
            async with pool.acquire() as conn:
                agent_id = await _make_agent(conn, workspace_id, owner, "Baseline")
            return await fn(PgMemoryRepository(pool), pool, workspace_id, agent_id)
        finally:
            await pool.close()

    try:
        return asyncio.run(_run())
    finally:
        cleanup_workspaces([owner])


async def _seed(
    pool: asyncpg.Pool,
    workspace_id: UUID,
    agent_id: UUID,
    facts: list[tuple[str, int]],
    status: MemoryStatus = MemoryStatus.active,
) -> None:
    for fact, importance in facts:
        await pool.execute(
            "INSERT INTO agent_memory "
            "(workspace_id, agent_id, status, fact, category, importance) "
            "VALUES ($1, $2, $3, $4, 'preference', $5)",
            workspace_id,
            agent_id,
            status.value,
            fact,
            importance,
        )


@pytest.mark.integration
def test_word_match_and_importance_tiebreak() -> None:
    """FTS-Treffer, `importance` bricht den Gleichstand — heutige Kaskade."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    async def _case(
        repo: PgMemoryRepository, pool: asyncpg.Pool, ws: UUID, agent: UUID
    ) -> list[str]:
        await _seed(
            pool,
            ws,
            agent,
            [
                ("Kunde Meier bevorzugt Rechnung per Post", 6),
                ("Kunde Meier bevorzugt Rechnung per Fax", 9),
            ],
        )
        hits = await repo.search_active(ws, agent, "Rechnung", 5)
        return [h.fact for h in hits]

    facts = _with_repo(_case)
    assert len(facts) == 2
    # Gleicher FTS-Rang ⇒ hoehere Importance zuerst.
    assert "Fax" in facts[0]


@pytest.mark.integration
def test_substring_match_via_ilike() -> None:
    """Der ILIKE-Zweig faengt Teilstrings, die FTS-Tokenisierung verfehlt."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    async def _case(
        repo: PgMemoryRepository, pool: asyncpg.Pool, ws: UUID, agent: UUID
    ) -> list[str]:
        await _seed(pool, ws, agent, [("Projektnummer ist AB-2024-XYZ", 7)])
        hits = await repo.search_active(ws, agent, "2024-XY", 5)
        return [h.fact for h in hits]

    assert _with_repo(_case) == ["Projektnummer ist AB-2024-XYZ"]


@pytest.mark.integration
def test_fuzzy_match_survives_a_typo() -> None:
    """Der Trigram-Zweig faengt Tippfehler — das kann FTS nicht."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    async def _case(
        repo: PgMemoryRepository, pool: asyncpg.Pool, ws: UUID, agent: UUID
    ) -> list[str]:
        await _seed(pool, ws, agent, [("Ansprechpartner ist Herr Schmidt", 7)])
        hits = await repo.search_active(ws, agent, "Ansprechpartner ist Herr Schmit", 5)
        return [h.fact for h in hits]

    assert _with_repo(_case) == ["Ansprechpartner ist Herr Schmidt"]


@pytest.mark.integration
def test_only_active_memories_are_retrievable() -> None:
    """Kurations-Schleuse: pending/rejected tauchen nie im Retrieval auf."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    async def _case(
        repo: PgMemoryRepository, pool: asyncpg.Pool, ws: UUID, agent: UUID
    ) -> list[str]:
        await _seed(pool, ws, agent, [("Freigegebener Fakt zur Rechnung", 7)])
        await _seed(
            pool, ws, agent, [("Wartender Fakt zur Rechnung", 9)], status=MemoryStatus.pending
        )
        await _seed(
            pool, ws, agent, [("Abgelehnter Fakt zur Rechnung", 9)], status=MemoryStatus.rejected
        )
        hits = await repo.search_active(ws, agent, "Rechnung", 10)
        return [h.fact for h in hits]

    assert _with_repo(_case) == ["Freigegebener Fakt zur Rechnung"]


@pytest.mark.integration
def test_search_is_isolated_per_agent() -> None:
    """Der kritischste Test: kein Agent sieht die Memories eines anderen."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    async def _case(
        repo: PgMemoryRepository, pool: asyncpg.Pool, ws: UUID, agent: UUID
    ) -> list[str]:
        async with pool.acquire() as conn:
            owner_id = await conn.fetchval("SELECT owner_id FROM agent WHERE id = $1", agent)
            other = await _make_agent(conn, ws, owner_id, "Fremd")
        await _seed(pool, ws, other, [("Fremdes Geheimnis zur Rechnung", 9)])
        await _seed(pool, ws, agent, [("Eigener Fakt zur Rechnung", 5)])
        hits = await repo.search_active(ws, agent, "Rechnung", 10)
        return [h.fact for h in hits]

    assert _with_repo(_case) == ["Eigener Fakt zur Rechnung"]


@pytest.mark.integration
def test_dedup_guard_catches_near_identical_wording() -> None:
    """Trigram-Dedup greift bei fast gleichem Wortlaut (Schwelle 0.6)."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    async def _case(
        repo: PgMemoryRepository, pool: asyncpg.Pool, ws: UUID, agent: UUID
    ) -> tuple[bool, bool]:
        await _seed(pool, ws, agent, [("Kunde bevorzugt Kontakt per E-Mail", 7)])
        near = await repo.find_similar(ws, agent, "Kunde bevorzugt Kontakt per E-Mails")
        unrelated = await repo.find_similar(ws, agent, "Lieferung erfolgt immer freitags")
        return near is not None, unrelated is not None

    near_hit, unrelated_hit = _with_repo(_case)
    assert near_hit is True
    assert unrelated_hit is False


@pytest.mark.integration
def test_paraphrase_is_not_found_today() -> None:
    """DIE LUECKE, die ADR-0046 Welle 3 schliessen soll.

    Der MCP-Docstring von `search_memory` verspricht dem Modell heute schon,
    das Gedaechtnis werde „semantisch" durchsucht. Tatsaechlich scheitern bei
    einer Paraphrase alle drei Zweige: FTS teilt keine Wortstaemme, ILIKE
    findet keinen Teilstring, und die Trigram-Similarity liegt weit unter der
    Schwelle von 0.3.

    Dieser Test haelt den Ist-Zustand fest. **Welle 3 muss ihn umdrehen** —
    dann ist er der Beleg, dass die Semantik wirklich greift.
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    async def _case(
        repo: PgMemoryRepository, pool: asyncpg.Pool, ws: UUID, agent: UUID
    ) -> tuple[list[str], float]:
        await _seed(pool, ws, agent, [("Kunde bevorzugt Kontakt per E-Mail", 8)])
        hits = await repo.search_active(ws, agent, "wie will der Kunde erreicht werden", 5)
        similarity = await pool.fetchval(
            "SELECT similarity($1, $2)",
            "Kunde bevorzugt Kontakt per E-Mail",
            "wie will der Kunde erreicht werden",
        )
        return [h.fact for h in hits], float(similarity)

    facts, similarity = _with_repo(_case)
    assert facts == [], f"Unerwarteter Treffer — ist die Semantik schon aktiv? {facts}"
    # Die Zahl macht sichtbar, WARUM Trigram hier nichts ausrichtet.
    assert similarity < 0.3, similarity


@pytest.mark.integration
def test_cross_lingual_is_not_found_today() -> None:
    """Zweite Luecke: eine deutsche Query findet keinen englischen Memory.

    Memories sind laut Migration 0066 ausdruecklich gemischtsprachig — genau
    deshalb steht dort `'simple'` (kein Stemming). Volltext kann diese Luecke
    strukturell nicht schliessen, ein multilinguales Embedding schon.
    Auch dieser Test wird in Welle 3 umgedreht.
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    async def _case(
        repo: PgMemoryRepository, pool: asyncpg.Pool, ws: UUID, agent: UUID
    ) -> list[str]:
        await _seed(pool, ws, agent, [("The customer prefers to be contacted by email", 8)])
        hits = await repo.search_active(ws, agent, "Kontaktweg des Kunden", 5)
        return [h.fact for h in hits]

    assert _with_repo(_case) == []


@pytest.mark.integration
def test_retrieval_log_is_bumped_for_delivered_hits() -> None:
    """Ausgelieferte Treffer erhoehen das Nutzungs-Log (Transparenz, ADR-0044)."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    async def _case(repo: PgMemoryRepository, pool: asyncpg.Pool, ws: UUID, agent: UUID) -> int:
        await _seed(pool, ws, agent, [("Fakt zur Rechnung", 7)])
        await repo.search_active(ws, agent, "Rechnung", 5)
        count: int = await pool.fetchval(
            "SELECT retrieval_count FROM agent_memory WHERE agent_id = $1", agent
        )
        return count

    assert _with_repo(_case) == 1


@pytest.mark.integration
def test_blank_and_unmatched_queries_return_nothing() -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    async def _case(
        repo: PgMemoryRepository, pool: asyncpg.Pool, ws: UUID, agent: UUID
    ) -> list[str]:
        await _seed(pool, ws, agent, [("Fakt zur Rechnung", 7)])
        hits = await repo.search_active(ws, agent, "voellig anderes Thema Segelboot", 5)
        return [h.fact for h in hits]

    assert _with_repo(_case) == []


@pytest.mark.integration
def test_limit_is_respected() -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    async def _case(repo: PgMemoryRepository, pool: asyncpg.Pool, ws: UUID, agent: UUID) -> int:
        await _seed(pool, ws, agent, [(f"Fakt {i} zur Rechnung", 5 + i % 3) for i in range(8)])
        hits = await repo.search_active(ws, agent, "Rechnung", 3)
        return len(hits)

    assert _with_repo(_case) == 3
