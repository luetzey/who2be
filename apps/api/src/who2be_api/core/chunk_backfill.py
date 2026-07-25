"""Backfill der Passage-Ebene (`content_chunk`, ADR-0046).

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
nachbauen, ohne die Logik zu duplizieren.
"""

from __future__ import annotations

import asyncio

import asyncpg

from who2be_api.core.config import get_settings
from who2be_api.repositories.content_chunk_repository import (
    CHUNK_TYPE_TABLES,
    PgContentChunkRepository,
)
from who2be_api.services.content_chunks import chunk_version_content

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


async def _run() -> None:
    try:
        conn = await asyncpg.connect(get_settings().database_url)
    except (asyncpg.PostgresError, OSError) as exc:
        raise SystemExit(f"Datenbank nicht erreichbar: {exc}") from exc
    try:
        entities, chunks, orphans = await backfill_chunks(conn)
    finally:
        await conn.close()
    print(
        f"Passagen neu gebaut: {chunks} aus {entities} aktiven Versionen "
        f"({orphans} verwaiste Chunks entfernt)."
    )


def cli() -> None:
    """Console-Entrypoint fuer `who2be-chunk-backfill`."""
    asyncio.run(_run())


if __name__ == "__main__":
    cli()
