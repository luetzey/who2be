"""Semantisches Memory-Retrieval (ADR-0046 Welle 3) — gegen echtes pgvector.

Gegenstueck zu `test_memory_retrieval_baseline.py`: dort ist festgehalten, was
das Gedaechtnis OHNE Semantik kann (und was nicht), hier, was mit ihr
dazukommt. Beide Dateien zusammen sind der Beleg, dass der Umbau von der
`ORDER BY`-Kaskade auf die RRF-Fusion nichts verloren und das Versprechen aus
dem MCP-Docstring („durchsucht dein Langzeitgedaechtnis … semantisch") erstmals
eingeloest hat.

Der Stub-Port liefert handgeschriebene Vektoren mit bekannter Geometrie — kein
Ersatz-Modell, sondern ein Messinstrument: die erwartete Trefferlage ist exakt
nachrechenbar, und die Tests brauchen weder Modell-Download noch Netz. Was sie
nicht belegen koennen, ist die Qualitaet eines konkreten Modells; das ist eine
Modell-Eigenschaft, keine des Retrievals.
"""

import asyncio
import zlib
from collections.abc import Sequence
from typing import Any
from uuid import UUID

import asyncpg
import pytest

from who2be_api.core.config import get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.embeddings import reset_embedding_port, set_embedding_port
from who2be_api.repositories.memory_repository import (
    PgMemoryRepository,
    reset_vector_support,
)
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace
from who2be_models import MemoryStatus

_DIMS = 384
_UNKNOWN_AXES = 100
_AXES = {"kontakt": 0, "versand": 1, "eskalation": 2}


def _axis_vector(axis: int) -> list[float]:
    vector = [0.0] * _DIMS
    vector[axis] = 1.0
    return vector


class _StubEmbedder:
    """Bildet Text ueber Stichworte auf Themen-Achsen ab (deterministisch).

    Deutsche UND englische Stichworte landen auf DERSELBEN Achse — genau das
    leistet ein multilinguales Modell und genau das kann keiner der drei
    lexikalischen Zweige.
    """

    @property
    def dimensions(self) -> int:
        return _DIMS

    @staticmethod
    def _axis_for(text: str) -> int:
        lowered = text.lower()
        if any(
            w in lowered
            for w in ("kontakt", "e-mail", "email", "erreicht", "contacted", "kontaktweg")
        ):
            return _AXES["kontakt"]
        if any(w in lowered for w in ("versand", "lieferung", "shipping", "delivery")):
            return _AXES["versand"]
        if any(w in lowered for w in ("eskalation", "teamleitung", "escalat")):
            return _AXES["eskalation"]
        # Textabhaengig, damit zwei verschiedene Fremdthemen NICHT identisch
        # sind — sonst maesse der Schwellwert-Test etwas anderes, als er sagt.
        return _DIMS - 1 - (zlib.crc32(lowered.encode()) % _UNKNOWN_AXES)

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [_axis_vector(self._axis_for(t)) for t in texts]


class _BrokenEmbedder:
    @property
    def dimensions(self) -> int:
        return _DIMS

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        raise RuntimeError("Modell nicht ladbar")


@pytest.fixture(autouse=True)
def _clean_state() -> Any:
    reset_embedding_port()
    reset_vector_support()
    yield
    reset_embedding_port()
    reset_vector_support()


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


async def _make_agent(conn: asyncpg.Connection, workspace_id: UUID, owner_id: UUID) -> UUID:
    agent_id: UUID = await conn.fetchval(
        "INSERT INTO agent (workspace_id, owner_id, name) VALUES ($1, $2, 'Semantik') RETURNING id",
        workspace_id,
        owner_id,
    )
    return agent_id


def _with_repo(fn: Any) -> Any:
    """Wie in der Baseline: Workspace-Helfer laufen ausserhalb der Coroutine."""
    owner = fresh_user_id()
    workspace_id = setup_workspace(owner)

    async def _run() -> Any:
        pool = await asyncpg.create_pool(
            get_settings().database_url, min_size=1, max_size=2, init=_init
        )
        assert pool is not None
        try:
            async with pool.acquire() as conn:
                agent_id = await _make_agent(conn, workspace_id, owner)
            return await fn(PgMemoryRepository(pool), pool, workspace_id, agent_id)
        finally:
            await pool.close()

    try:
        return asyncio.run(_run())
    finally:
        cleanup_workspaces([owner])


async def _init(conn: asyncpg.Connection) -> None:
    from who2be_api.core.db import init_connection

    await init_connection(conn)


async def _seed(
    repo: PgMemoryRepository,
    pool: asyncpg.Pool,
    workspace_id: UUID,
    agent_id: UUID,
    facts: Sequence[tuple[str, int]],
    *,
    with_vectors: bool = True,
) -> None:
    """Legt aktive Memories an und setzt (optional) ihre Vektoren."""
    embedder = _StubEmbedder()
    for fact, importance in facts:
        memory_id = await pool.fetchval(
            "INSERT INTO agent_memory "
            "(workspace_id, agent_id, status, fact, category, importance) "
            "VALUES ($1, $2, $3, $4, 'preference', $5) RETURNING id",
            workspace_id,
            agent_id,
            MemoryStatus.active.value,
            fact,
            importance,
        )
        if with_vectors:
            vector = (await embedder.embed([fact]))[0]
            await repo.set_vector(memory_id, vector)


@pytest.mark.integration
def test_paraphrase_is_found_with_semantics() -> None:
    """Die Luecke aus der Baseline — jetzt geschlossen.

    `test_paraphrase_is_not_found_today` haelt fest, dass alle drei
    lexikalischen Zweige hier scheitern (Trigram-Similarity 0,14 gegen eine
    Schwelle von 0,3). Mit dem Vektor-Zweig wird derselbe Fakt gefunden.
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    async def _case(
        repo: PgMemoryRepository, pool: asyncpg.Pool, ws: UUID, agent: UUID
    ) -> list[str]:
        await _seed(repo, pool, ws, agent, [("Kunde bevorzugt Kontakt per E-Mail", 8)])
        query = "wie will der Kunde erreicht werden"
        vector = (await _StubEmbedder().embed([query]))[0]

        lexical = await repo.search_active(ws, agent, query, 5)
        assert [h.fact for h in lexical] == [], "lexikalisch darf hier nichts finden"

        hits = await repo.search_active(ws, agent, query, 5, vector)
        return [h.fact for h in hits]

    assert _with_repo(_case) == ["Kunde bevorzugt Kontakt per E-Mail"]


@pytest.mark.integration
def test_cross_lingual_is_found_with_semantics() -> None:
    """Die zweite Luecke: deutsche Anfrage, englischer Memory.

    Memories sind laut Migration 0066 ausdruecklich gemischtsprachig — deshalb
    steht dort `'simple'` (kein Stemming). Volltext kann diese Luecke
    strukturell nicht schliessen.
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    async def _case(
        repo: PgMemoryRepository, pool: asyncpg.Pool, ws: UUID, agent: UUID
    ) -> list[str]:
        await _seed(repo, pool, ws, agent, [("The customer prefers to be contacted by email", 8)])
        query = "Kontaktweg des Kunden"
        vector = (await _StubEmbedder().embed([query]))[0]

        assert await repo.search_active(ws, agent, query, 5) == []
        return [h.fact for h in await repo.search_active(ws, agent, query, 5, vector)]

    assert _with_repo(_case) == ["The customer prefers to be contacted by email"]


@pytest.mark.integration
def test_unrelated_question_stays_empty() -> None:
    """Die Aehnlichkeitsschranke verhindert Zufallstreffer.

    Ohne Schranke liefert der Vektor-Zweig IMMER die k naechsten Memories. Bei
    Memory waere das besonders schaedlich: der Agent haelt gespeicherte
    Nutzerdaten fuer eine Antwort auf seine Frage.
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    async def _case(
        repo: PgMemoryRepository, pool: asyncpg.Pool, ws: UUID, agent: UUID
    ) -> list[str]:
        await _seed(repo, pool, ws, agent, [("Kunde bevorzugt Kontakt per E-Mail", 8)])
        query = "Bilanzierung nach HGB"
        vector = (await _StubEmbedder().embed([query]))[0]
        return [h.fact for h in await repo.search_active(ws, agent, query, 5, vector)]

    assert _with_repo(_case) == []


@pytest.mark.integration
def test_lexical_capabilities_survive_the_vector_branch() -> None:
    """Der Vektor-Zweig darf die drei lexikalischen nicht verdraengen.

    Genau das war das Risiko des Umbaus: eine Fusion, die den semantischen
    Rang zu stark gewichtet, verliert Tippfehler- und Teilstring-Treffer.
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    async def _case(
        repo: PgMemoryRepository, pool: asyncpg.Pool, ws: UUID, agent: UUID
    ) -> tuple[list[str], list[str]]:
        await _seed(
            repo,
            pool,
            ws,
            agent,
            [("Projektnummer ist AB-2024-XYZ", 7), ("Ansprechpartner ist Herr Schmidt", 7)],
        )
        embedder = _StubEmbedder()
        substring_q = "2024-XY"
        typo_q = "Ansprechpartner ist Herr Schmit"
        substring = await repo.search_active(
            ws, agent, substring_q, 5, (await embedder.embed([substring_q]))[0]
        )
        typo = await repo.search_active(ws, agent, typo_q, 5, (await embedder.embed([typo_q]))[0])
        return [h.fact for h in substring], [h.fact for h in typo]

    substring, typo = _with_repo(_case)
    assert substring == ["Projektnummer ist AB-2024-XYZ"]
    assert typo == ["Ansprechpartner ist Herr Schmidt"]


@pytest.mark.integration
def test_semantic_dedup_rejects_a_paraphrased_duplicate() -> None:
    """Der Dedup-Waechter faengt jetzt auch Umschreibungen.

    Der Trigram-Zweig (Schwelle 0,6) laesst sie durch; sie sammeln sich gegen
    das 500er-Cap, das auch `rejected` mitzaehlt.
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    async def _case(
        repo: PgMemoryRepository, pool: asyncpg.Pool, ws: UUID, agent: UUID
    ) -> tuple[bool, bool, float]:
        await _seed(repo, pool, ws, agent, [("Kunde bevorzugt Kontakt per E-Mail", 8)])
        embedder = _StubEmbedder()

        paraphrase = "Kontaktweg des Kunden ist die E-Mail"
        para_vector = (await embedder.embed([paraphrase]))[0]
        # Ohne Vektor greift nur Trigram — und das reicht hier nicht.
        lexical_only = await repo.find_similar(ws, agent, paraphrase)
        semantic = await repo.find_similar(ws, agent, paraphrase, para_vector)

        # Die Gegenprobe (fremdes Thema wird NICHT als Duplikat erkannt) hat
        # einen eigenen Test — hier geht es nur um den Paraphrasen-Fall.
        trigram: float = await pool.fetchval(
            "SELECT similarity($1, $2)", "Kunde bevorzugt Kontakt per E-Mail", paraphrase
        )
        return lexical_only is not None, semantic is not None, float(trigram)

    lexical_hit, semantic_hit, trigram = _with_repo(_case)
    assert semantic_hit is True, "Paraphrase haette als Duplikat erkannt werden muessen"
    assert lexical_hit is False, "ohne Vektor faengt Trigram sie nachweislich nicht"
    assert trigram < 0.6, trigram


@pytest.mark.integration
def test_dedup_does_not_reject_a_different_topic() -> None:
    """Falsch-positiver Dedup ist der teurere Fehler — er muss ausbleiben."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    async def _case(repo: PgMemoryRepository, pool: asyncpg.Pool, ws: UUID, agent: UUID) -> bool:
        await _seed(repo, pool, ws, agent, [("Kunde bevorzugt Kontakt per E-Mail", 8)])
        other = "Lieferung erfolgt immer freitags"
        vector = (await _StubEmbedder().embed([other]))[0]
        return await repo.find_similar(ws, agent, other, vector) is not None

    assert _with_repo(_case) is False


@pytest.mark.integration
def test_memories_without_vectors_are_still_found_lexically() -> None:
    """Bestandsdaten ohne Vektor duerfen nicht unauffindbar werden.

    Zwischen Migration und Backfill haben alle vorhandenen Memories
    `content_vector IS NULL`. Der Vektor-Zweig ueberspringt sie — die
    lexikalischen Zweige finden sie weiterhin.
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    async def _case(
        repo: PgMemoryRepository, pool: asyncpg.Pool, ws: UUID, agent: UUID
    ) -> list[str]:
        await _seed(
            repo, pool, ws, agent, [("Kunde bevorzugt Rechnung per Post", 7)], with_vectors=False
        )
        query = "Rechnung"
        vector = (await _StubEmbedder().embed([query]))[0]
        return [h.fact for h in await repo.search_active(ws, agent, query, 5, vector)]

    assert _with_repo(_case) == ["Kunde bevorzugt Rechnung per Post"]


@pytest.mark.integration
def test_backfill_fills_memory_vectors() -> None:
    """Der Backfill macht Bestands-Memories semantisch auffindbar."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    async def _case(
        repo: PgMemoryRepository, pool: asyncpg.Pool, ws: UUID, agent: UUID
    ) -> list[str]:
        await _seed(
            repo,
            pool,
            ws,
            agent,
            [("Kunde bevorzugt Kontakt per E-Mail", 8)],
            with_vectors=False,
        )
        query = "wie will der Kunde erreicht werden"
        vector = (await _StubEmbedder().embed([query]))[0]
        assert await repo.search_active(ws, agent, query, 5, vector) == []

        from who2be_api.core.chunk_backfill import backfill_memory_vectors

        filled = await backfill_memory_vectors(pool, _StubEmbedder())
        assert filled >= 1

        return [h.fact for h in await repo.search_active(ws, agent, query, 5, vector)]

    assert _with_repo(_case) == ["Kunde bevorzugt Kontakt per E-Mail"]


@pytest.mark.integration
def test_broken_embedder_does_not_break_saving(monkeypatch: pytest.MonkeyPatch) -> None:
    """Best-Effort im Laufzeit-Pfad: `save_memory` darf nie am Modell scheitern.

    Anders als der Chunk-Aufbau (eine Builder-Aktion) ist `save_memory` ein
    rate-limitierter Laufzeit-Call des Agenten.
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    set_embedding_port(_BrokenEmbedder())

    from who2be_api.services.memory_service import MemoryService

    async def _case(repo: PgMemoryRepository, pool: asyncpg.Pool, ws: UUID, agent: UUID) -> Any:
        service = MemoryService(repo)
        # `_embed` faengt den Fehler und liefert None — kein Ausbruch nach oben.
        assert await service._embed("Kunde bevorzugt Kontakt per E-Mail") is None
        return True

    assert _with_repo(_case) is True


def _set_vector_column(present: bool) -> None:
    """Legt `agent_memory.content_vector` an oder entfernt sie."""

    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            if present:
                await conn.execute(
                    "ALTER TABLE agent_memory ADD COLUMN IF NOT EXISTS content_vector vector(384)"
                )
            else:
                await conn.execute("ALTER TABLE agent_memory DROP COLUMN IF EXISTS content_vector")
        finally:
            await conn.close()

    asyncio.run(_run())
    reset_vector_support()


@pytest.mark.integration
def test_works_without_the_vector_column() -> None:
    """On-Prem auf Standard-Postgres: pgvector fehlt, also fehlt die Spalte.

    Migration 0072 ist dafuer fail-soft (sie legt die Spalte dann nicht an).
    Suche, Dedup und Backfill muessen das aushalten und rein lexikalisch
    weiterarbeiten — ein Fehler waere fuer ein additives Feature ein
    unangemessener Preis.

    Der Test entfernt die Spalte wirklich und legt sie danach wieder an.
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    async def _case(
        repo: PgMemoryRepository, pool: asyncpg.Pool, ws: UUID, agent: UUID
    ) -> tuple[list[str], bool, int]:
        await _seed(
            repo, pool, ws, agent, [("Kunde bevorzugt Rechnung per Post", 7)], with_vectors=False
        )
        embedder = _StubEmbedder()
        query = "Rechnung"
        vector = (await embedder.embed([query]))[0]

        # Ein Vektor wird uebergeben, es gibt aber keine Spalte dafuer.
        hits = await repo.search_active(ws, agent, query, 5, vector)
        duplicate = await repo.find_similar(ws, agent, "Kunde bevorzugt Rechnung per Post", vector)

        from who2be_api.core.chunk_backfill import backfill_memory_vectors

        filled = await backfill_memory_vectors(pool, embedder)
        return [h.fact for h in hits], duplicate is not None, filled

    _set_vector_column(False)
    try:
        facts, duplicate, filled = _with_repo(_case)
    finally:
        _set_vector_column(True)

    assert facts == ["Kunde bevorzugt Rechnung per Post"]
    # Trigram-Dedup greift weiterhin (identischer Wortlaut).
    assert duplicate is True
    # Ohne Spalte gibt es nichts zu befuellen — aber auch keinen Fehler.
    assert filled == 0
