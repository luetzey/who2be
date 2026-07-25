"""Persistenz der Passage-Ebene (`content_chunk`, ADR-0046).

Chunks sind ABGELEITET: sie spiegeln immer genau die aktive Version einer
Entity und werden bei jedem Statuswechsel neu gebaut. Deshalb ersetzt
`replace` den kompletten Bestand einer Entity (nicht nur den der Version) —
so bleibt hoechstens ein Versionsstand materialisiert.

Alle Methoden nehmen eine `Connection` statt des Pools: der Rebuild laeuft in
derselben Transaktion wie der Statuswechsel (`version_status._transition`), so
dass Status und Passagen nie auseinanderlaufen.

Die Suche joint auf die Entity-Tabelle — sie braucht `name` und `locale` fuer
den Treffer. Dadurch sind verwaiste Chunks (Entity geloescht) nicht
auffindbar; der polymorphe `entity_id` erlaubt keinen FK ueber fuenf Tabellen.
"""

from collections.abc import Mapping, Sequence
from typing import Protocol
from uuid import UUID

import asyncpg

from who2be_api.services.content_chunks import ChunkDraft
from who2be_models import ContentChunkHit

# Pro Typ: (Entity-Tabelle, Version-Tabelle, FK-Spalte) — wie in
# `search_repository`, damit beide Suchpfade dieselbe Typ-Landkarte nutzen.
# Oeffentlich, weil der Backfill (`core/chunk_backfill.py`) ueber dieselben
# Typen laeuft; eine zweite Kopie wuerde beim naechsten Typ auseinanderlaufen.
CHUNK_TYPE_TABLES: dict[str, tuple[str, str, str]] = {
    "persona": ("persona", "persona_version", "persona_id"),
    "playbook": ("playbook", "playbook_version", "playbook_id"),
    "resource": ("resource", "resource_version", "resource_id"),
    "external_tool": ("external_tool", "external_tool_version", "external_tool_id"),
    "system_prompt_template": (
        "system_prompt_template",
        "system_prompt_template_version",
        "template_id",
    ),
}

_DELETE_SQL = (
    "DELETE FROM content_chunk WHERE workspace_id = $1 AND entity_type = $2 AND entity_id = $3"
)

_INSERT_SQL = (
    "INSERT INTO content_chunk "
    "(workspace_id, entity_type, entity_id, version, locale, block_id, heading_path, ord, text) "
    "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)"
)


def _search_sql(entity_tbl: str, version_tbl: str, fk: str, *, restricted: bool) -> str:
    """Passage-Suche fuer EINEN Entity-Typ.

    Der JOIN auf die aktive Version stellt sicher, dass nur Passagen des
    veroeffentlichten Stands gefunden werden — auch wenn ein Rebuild einmal
    ausgefallen sein sollte, und er macht verwaiste Chunks unauffindbar.

    Die FTS-Config folgt der Chunk-Sprache und ist identisch zur Generated
    Column in Migration 0070 — sonst matcht die Query ihren eigenen Index
    nicht (eine `german`-Spalte gegen eine `simple`-Query findet nichts).

    Nur die Tabellennamen werden interpoliert (feste Werte aus
    `CHUNK_TYPE_TABLES`);
    Workspace, Query, Typ und ID-Menge sind gebundene Parameter.
    """
    config = (
        "CASE split_part(c.locale, '-', 1) "
        "WHEN 'de' THEN 'german'::regconfig "
        "WHEN 'en' THEN 'english'::regconfig "
        "ELSE 'simple'::regconfig END"
    )
    restrict_clause = "  AND c.entity_id = ANY($5::uuid[]) " if restricted else ""
    return (
        f"SELECT c.entity_id, c.block_id, c.heading_path, c.text, c.locale, e.name, "
        f"       ts_rank(c.search, plainto_tsquery({config}, $2)) AS score "
        f"FROM content_chunk c "
        f"JOIN {entity_tbl} e ON e.id = c.entity_id AND e.workspace_id = c.workspace_id "
        f"JOIN {version_tbl} ev ON ev.{fk} = e.id AND ev.status = 'active' "
        f"WHERE c.workspace_id = $1 "
        f"  AND c.entity_type = $4 "
        f"  AND c.search @@ plainto_tsquery({config}, $2) "
        f"{restrict_clause}"
        f"ORDER BY score DESC, c.ord ASC "
        f"LIMIT $3"
    )


class ContentChunkRepository(Protocol):
    async def replace(
        self,
        conn: asyncpg.Connection,
        workspace_id: UUID,
        entity_type: str,
        entity_id: UUID,
        version: int,
        locale: str,
        chunks: Sequence[ChunkDraft],
    ) -> None: ...

    async def clear(
        self,
        conn: asyncpg.Connection,
        workspace_id: UUID,
        entity_type: str,
        entity_id: UUID,
    ) -> None: ...


class PgContentChunkRepository:
    """asyncpg-Implementierung der Passage-Persistenz."""

    def __init__(self, pool: asyncpg.Pool | None = None) -> None:
        self._pool = pool

    async def replace(
        self,
        conn: asyncpg.Connection,
        workspace_id: UUID,
        entity_type: str,
        entity_id: UUID,
        version: int,
        locale: str,
        chunks: Sequence[ChunkDraft],
    ) -> None:
        await conn.execute(_DELETE_SQL, workspace_id, entity_type, entity_id)
        if not chunks:
            return
        await conn.executemany(
            _INSERT_SQL,
            [
                (
                    workspace_id,
                    entity_type,
                    entity_id,
                    version,
                    locale,
                    chunk.block_id,
                    chunk.heading_path,
                    chunk.ord,
                    chunk.text,
                )
                for chunk in chunks
            ],
        )

    async def clear(
        self,
        conn: asyncpg.Connection,
        workspace_id: UUID,
        entity_type: str,
        entity_id: UUID,
    ) -> None:
        await conn.execute(_DELETE_SQL, workspace_id, entity_type, entity_id)

    async def search(
        self,
        workspace_id: UUID,
        query: str,
        types: Sequence[str],
        limit: int,
        restrict: Mapping[str, Sequence[UUID]] | None = None,
    ) -> list[ContentChunkHit]:
        """Rangsortierte Passagen ueber die angefragten Typen.

        `restrict` wie in `SearchRepository`: fehlender Schluessel = keine
        Einschraenkung, leere Sequenz = nichts sichtbar.
        """
        if self._pool is None:  # pragma: no cover - nur Fehlkonfiguration
            raise RuntimeError("ContentChunkRepository ohne Pool angelegt.")
        hits: list[ContentChunkHit] = []
        for entity_type in types:
            tables = CHUNK_TYPE_TABLES.get(entity_type)
            if tables is None:
                continue
            entity_tbl, version_tbl, fk = tables
            allowed = None if restrict is None else restrict.get(entity_type)
            if allowed is None:
                rows = await self._pool.fetch(
                    _search_sql(entity_tbl, version_tbl, fk, restricted=False),
                    workspace_id,
                    query,
                    limit,
                    entity_type,
                )
            else:
                if not allowed:
                    continue
                rows = await self._pool.fetch(
                    _search_sql(entity_tbl, version_tbl, fk, restricted=True),
                    workspace_id,
                    query,
                    limit,
                    entity_type,
                    list(allowed),
                )
            for row in rows:
                hits.append(
                    ContentChunkHit(
                        type=entity_type,  # type: ignore[arg-type]
                        entity_id=row["entity_id"],
                        name=row["name"],
                        block_id=row["block_id"],
                        heading_path=row["heading_path"] or "",
                        text=row["text"],
                        score=float(row["score"]),
                        locale=row["locale"],
                    )
                )
        hits.sort(key=lambda h: (-h.score, h.name, h.text))
        return hits[:limit]
