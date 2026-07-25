"""Backfill der Retrieval-Ebenen (`content_chunk` + `agent_memory`, ADR-0046).

Chunks entstehen im Normalbetrieb beim Statuswechsel auf `active`
(`version_status._transition`). Bestands-Workspaces haben ihre Inhalte aber
laengst aktiviert — deren aktive Versionen haetten ohne diesen Lauf **keine**
Passagen, und `search_content` faende dort nichts.

Der Lauf ist idempotent und jederzeit wiederholbar: Chunks sind abgeleitete
Daten, `replace` loescht den Entity-Bestand und schreibt ihn neu. Damit ist das
hier auch das Reparatur-Werkzeug, wenn sich der Chunk-Schnitt aendert — kein
Datenverlust moeglich.

Zusaetzlich raeumt der Lauf verwaiste Chunks weg: `entity_id` ist polymorph
ueber fuenf Tabellen und kann deshalb keinen FK tragen. Verwaiste Zeilen sind
zwar unauffindbar (die Suche joint auf die Entity), aber sie kosten Platz.

Bewusst KEIN Teil einer SQL-Migration: der Schnitt lebt in Python
(`services/content_chunks.py`), nicht in SQL. Eine Migration koennte ihn nicht
nachbauen, ohne die Logik zu duplizieren. Dasselbe gilt fuer die Vektoren: sie
entstehen ueber den `EmbeddingPort`, den SQL nicht aufrufen kann.

Deckt beide Vektor-Korpora ab — Passagen (Welle 2) und Agent-Memories
(Welle 3). Bestehende Memories haben naturgemaess keinen Vektor: sie wurden
geschrieben, bevor es die Spalte gab.
"""

from __future__ import annotations

import asyncio
import logging

import asyncpg

from who2be_api.core.config import get_settings
from who2be_api.core.db import init_connection
from who2be_api.embeddings import EmbeddingPort, build_embedding_port
from who2be_api.repositories.content_chunk_repository import (
    CHUNK_TYPE_TABLES,
    PgContentChunkRepository,
)
from who2be_api.repositories.memory_repository import PgMemoryRepository
from who2be_api.services.content_chunks import chunk_version_content

logger = logging.getLogger(__name__)

# Aktive Versionen eines Typs, inklusive Workspace der Identitaets-Zeile.
_ACTIVE_VERSIONS_SQL = """
SELECT e.workspace_id, e.id AS entity_id, ev.version, ev.locale, ev.content
FROM {entity} e
JOIN {version} ev ON ev.{fk} = e.id AND ev.status = 'active'
ORDER BY e.workspace_id, e.id
"""

# Chunks, deren Entity es nicht mehr gibt.
_ORPHANS_SQL = """
DELETE FROM content_chunk c
WHERE c.entity_type = $1
  AND NOT EXISTS (SELECT 1 FROM {entity} e WHERE e.id = c.entity_id)
"""


async def backfill_chunks(conn: asyncpg.Connection) -> tuple[int, int, int]:
    """Baut die Passagen aller aktiven Versionen neu auf.

    Liefert `(Entities, Passagen, entfernte Waisen)`. Jede Entity wird in einer
    eigenen Transaktion geschrieben — ein kaputter Content-Snapshot im Bestand
    soll nicht den ganzen Lauf zuruecknehmen.
    """
    repo = PgContentChunkRepository()
    entities = 0
    chunks = 0
    orphans = 0

    for entity_type, (entity_tbl, version_tbl, fk) in CHUNK_TYPE_TABLES.items():
        removed = await conn.execute(_ORPHANS_SQL.format(entity=entity_tbl), entity_type)
        # asyncpg liefert "DELETE <n>".
        orphans += int(removed.rsplit(" ", 1)[-1]) if removed.startswith("DELETE") else 0

        rows = await conn.fetch(
            _ACTIVE_VERSIONS_SQL.format(entity=entity_tbl, version=version_tbl, fk=fk)
        )
        for row in rows:
            drafts = chunk_version_content(entity_type, row["content"])
            async with conn.transaction():
                await repo.replace(
                    conn,
                    row["workspace_id"],
                    entity_type,
                    row["entity_id"],
                    row["version"],
                    row["locale"],
                    drafts,
                )
            entities += 1
            chunks += len(drafts)
    return entities, chunks, orphans


async def backfill_vectors(
    conn: asyncpg.Connection, embedder: EmbeddingPort | None, batch_size: int = 64
) -> int:
    """Holt fehlende Vektoren nach (ADR-0046 Welle 2).

    Zaehlt, wie viele Passagen einen Vektor bekommen haben. Ohne Port ist das
    ein No-Op — das ist der Normalfall einer Installation ohne die optionale
    Dependency-Gruppe, kein Fehler.

    Arbeitet in Baetzen und bricht ab, sobald ein Batch fehlschlaegt: der
    naechste Lauf setzt dort fort, weil die Auswahl an `content_vector IS NULL`
    haengt und damit von selbst nur die Nachzuegler sieht.
    """
    if embedder is None:
        return 0
    repo = PgContentChunkRepository()
    embedded = 0
    while True:
        pending = await repo.fetch_missing_vectors(conn, batch_size)
        if not pending:
            break
        try:
            vectors = await embedder.embed([text for _, text in pending])
        except Exception:  # noqa: BLE001 - Teil-Erfolg ist besser als Abbruch
            logger.warning("Embedding-Batch fehlgeschlagen — Backfill bricht ab.", exc_info=True)
            break
        if len(vectors) != len(pending):
            logger.warning("Embedding lieferte eine falsche Anzahl Vektoren — Backfill bricht ab.")
            break
        async with conn.transaction():
            for (chunk_id, _text), vector in zip(pending, vectors, strict=True):
                await repo.set_vector(conn, chunk_id, vector)
        embedded += len(pending)
    return embedded


async def backfill_memory_vectors(
    pool: asyncpg.Pool, embedder: EmbeddingPort | None, batch_size: int = 64
) -> int:
    """Holt fehlende Memory-Vektoren nach (ADR-0046 Welle 3).

    Bestehende Memories haben keinen Vektor — sie entstanden vor der Spalte.
    Ohne diesen Lauf faende `search_memory` sie nur lexikalisch, und die
    Semantik griffe erst fuer kuenftige Eintraege.

    Nimmt einen Pool statt einer Connection, weil `PgMemoryRepository` (anders
    als das Chunk-Repository) am Pool haengt.
    """
    if embedder is None:
        return 0
    repo = PgMemoryRepository(pool)
    embedded = 0
    while True:
        pending = await repo.fetch_missing_vectors(batch_size)
        if not pending:
            break
        try:
            vectors = await embedder.embed([fact for _, fact in pending])
        except Exception:  # noqa: BLE001 - Teil-Erfolg ist besser als Abbruch
            logger.warning("Memory-Embedding-Batch fehlgeschlagen — Backfill bricht ab.")
            break
        if len(vectors) != len(pending):
            logger.warning("Embedding lieferte eine falsche Anzahl Vektoren — Backfill bricht ab.")
            break
        for (memory_id, _fact), vector in zip(pending, vectors, strict=True):
            await repo.set_vector(memory_id, vector)
        embedded += len(pending)
    return embedded


async def _run() -> None:
    settings = get_settings()
    embedder = build_embedding_port()
    try:
        conn = await asyncpg.connect(settings.database_url)
    except (asyncpg.PostgresError, OSError) as exc:
        raise SystemExit(f"Datenbank nicht erreichbar: {exc}") from exc
    try:
        await init_connection(conn)
        entities, chunks, orphans = await backfill_chunks(conn)
        embedded = await backfill_vectors(conn, embedder)
    finally:
        await conn.close()

    pool = await asyncpg.create_pool(settings.database_url, init=init_connection, min_size=1)
    assert pool is not None
    try:
        memories = await backfill_memory_vectors(pool, embedder)
    finally:
        await pool.close()

    print(
        f"Passagen neu gebaut: {chunks} aus {entities} aktiven Versionen "
        f"({orphans} verwaiste Chunks entfernt)."
    )
    if embedded or memories:
        print(f"Vektoren nachgeholt: {embedded} Passagen, {memories} Memories.")
    else:
        print("Keine Vektoren erzeugt (Semantik nicht aktiv oder nichts offen).")


def cli() -> None:
    """Console-Entrypoint fuer `who2be-retrieval-backfill`."""
    asyncio.run(_run())


if __name__ == "__main__":
    cli()
