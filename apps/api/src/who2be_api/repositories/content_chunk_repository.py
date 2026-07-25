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

_INSERT_COLUMNS = (
    "workspace_id, entity_type, entity_id, version, locale, block_id, heading_path, ord, text"
)
_INSERT_SQL = (
    f"INSERT INTO content_chunk ({_INSERT_COLUMNS}) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)"
)
_INSERT_SQL_WITH_VECTOR = (
    f"INSERT INTO content_chunk ({_INSERT_COLUMNS}, content_vector) "
    "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)"
)

# Existiert die Vektor-Spalte? Migration 0071 legt sie NICHT an, wenn pgvector
# auf dem Server fehlt (fail-soft, siehe dort) — dieser Zustand ist der
# Normalfall einer On-Prem-Instanz auf Standard-Postgres und darf keinen Fehler
# ausloesen, sondern nur die Semantik abschalten.
_HAS_VECTOR_SQL = """
SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'content_chunk' AND column_name = 'content_vector'
)
"""

# Prozessweit einmal aufgeloest: das Schema aendert sich im Betrieb nicht.
_vector_supported: bool | None = None


async def vector_supported(conn: asyncpg.Connection) -> bool:
    """True, wenn `content_chunk.content_vector` existiert (gecacht)."""
    global _vector_supported
    if _vector_supported is None:
        _vector_supported = bool(await conn.fetchval(_HAS_VECTOR_SQL))
    return _vector_supported


def reset_vector_support() -> None:
    """Verwirft den Cache (Tests, Schema-Wechsel zur Laufzeit)."""
    global _vector_supported
    _vector_supported = None


_MISSING_VECTORS_SQL = (
    "SELECT id, text, heading_path FROM content_chunk "
    "WHERE content_vector IS NULL ORDER BY created_at LIMIT $1"
)

_SET_VECTOR_SQL = "UPDATE content_chunk SET content_vector = $2 WHERE id = $1"

# Reciprocal Rank Fusion: score = Σ 1/(K + rang). K daempft den Einfluss der
# vordersten Raenge; 60 ist der in der Literatur uebliche Wert und robust genug,
# dass wir ihn nicht kalibrieren muessen. RRF fusioniert RAENGE statt Scores —
# genau richtig hier, weil `ts_rank` und Cosinus-Distanz voellig
# unterschiedliche Skalen haben und nicht vergleichbar normierbar sind.
_RRF_K = 60

# Ab welcher Cosinus-AEHNLICHKEIT ein Vektor-Treffer ueberhaupt zaehlt.
# Ohne diese Schranke liefert die Vektor-Suche IMMER die k naechsten Passagen —
# auch bei voellig unpassender Frage. Das widerspraeche der Tool-Anweisung
# „findest du nichts, sag das offen" und wuerde den Agenten mit
# Beinahe-Zufallstreffern fuettern.
# Der Wert ist bewusst konservativ; er ist gegen das reale Modell noch nicht
# kalibriert (ADR-0046, offener Punkt).
_MIN_VECTOR_SIMILARITY = 0.40

# FTS-Config identisch zur Generated Column in Migration 0070 — sonst matcht die
# Query ihren eigenen Index nicht (eine `german`-Spalte gegen eine
# `simple`-Query findet nichts).
_FTS_CONFIG = (
    "CASE split_part(c.locale, '-', 1) "
    "WHEN 'de' THEN 'german'::regconfig "
    "WHEN 'en' THEN 'english'::regconfig "
    "ELSE 'simple'::regconfig END"
)


def _search_sql(
    entity_tbl: str,
    version_tbl: str,
    fk: str,
    *,
    restrict_pos: int | None,
    query_pos: int | None,
    vector_pos: int | None,
) -> str:
    """Passage-Suche fuer EINEN Entity-Typ, wahlweise Volltext, Vektor oder beides.

    Der JOIN auf die aktive Version stellt sicher, dass nur Passagen des
    veroeffentlichten Stands gefunden werden — auch wenn ein Rebuild einmal
    ausgefallen sein sollte, und er macht verwaiste Chunks unauffindbar.

    Beide Zweige ranken innerhalb DERSELBEN vorgefilterten Menge (`scoped`), die
    den Read-Scope bereits anwendet — das Scoping wirkt also vor dem Ranking
    (ADR-0037 §47), auch im semantischen Zweig.

    Nur die Tabellennamen werden interpoliert (feste Werte aus
    `CHUNK_TYPE_TABLES`); Workspace, Query, Typ, ID-Menge und Query-Vektor sind
    gebundene Parameter.

    Die Positionen der optionalen Parameter reicht der Aufrufer herein, statt
    sie hier zu erraten: ein nur manchmal referenzierter Platzhalter waere
    sonst im ungenutzten Fall typlos („could not determine data type of
    parameter"). $1 ist immer der Workspace, $2 das Limit, $3 der Entity-Typ.
    """
    use_text = query_pos is not None
    use_vector = vector_pos is not None
    vector_column = "c.content_vector," if use_vector else ""
    restrict_clause = (
        f"  AND c.entity_id = ANY(${restrict_pos}::uuid[]) " if restrict_pos is not None else ""
    )
    vector_param = f"${vector_pos}"

    parts = [
        "WITH scoped AS (",
        "  SELECT c.id, c.entity_id, c.block_id, c.heading_path, c.text, c.locale, c.ord,",
        f"         c.search, {vector_column} e.name,",
        f"         {_FTS_CONFIG} AS cfg",
        "  FROM content_chunk c",
        f"  JOIN {entity_tbl} e ON e.id = c.entity_id AND e.workspace_id = c.workspace_id",
        f"  JOIN {version_tbl} ev ON ev.{fk} = e.id AND ev.status = 'active'",
        "  WHERE c.workspace_id = $1",
        "    AND c.entity_type = $3",
        restrict_clause,
        ")",
    ]
    branches: list[str] = []
    if use_text:
        parts.append(
            ", fts AS ("
            "  SELECT id, row_number() OVER ("
            f"    ORDER BY ts_rank(search, plainto_tsquery(cfg, ${query_pos})) DESC, ord ASC"
            "  ) AS rnk"
            "  FROM scoped"
            f"  WHERE search @@ plainto_tsquery(cfg, ${query_pos})"
            ")"
        )
        branches.append("fts")
    if use_vector:
        parts.append(
            ", vec AS ("
            "  SELECT id, row_number() OVER ("
            f"    ORDER BY content_vector <=> {vector_param}::vector, ord ASC"
            "  ) AS rnk"
            "  FROM scoped"
            "  WHERE content_vector IS NOT NULL"
            f"    AND 1 - (content_vector <=> {vector_param}::vector) >= "
            f"{_MIN_VECTOR_SIMILARITY}"
            ")"
        )
        branches.append("vec")

    score_terms = " + ".join(f"coalesce(1.0 / ({_RRF_K} + {b}.rnk), 0)" for b in branches)
    joins = " ".join(f"LEFT JOIN {b} ON {b}.id = s.id" for b in branches)
    matched = " OR ".join(f"{b}.id IS NOT NULL" for b in branches)

    parts.append(
        f"SELECT s.entity_id, s.block_id, s.heading_path, s.text, s.locale, s.name, "
        f"       ({score_terms}) AS score "
        f"FROM scoped s {joins} "
        f"WHERE {matched} "
        f"ORDER BY score DESC, s.ord ASC "
        f"LIMIT $2"
    )
    return " ".join(parts)


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
        vectors: Sequence[Sequence[float] | None] | None = None,
    ) -> None:
        """Ersetzt die Passagen einer Entity.

        `vectors` ist optional und positionsgleich zu `chunks`; `None`-Eintraege
        (und ein fehlendes Argument) landen als NULL in `content_vector`. Damit
        ist der Vektor durchgaengig best-effort: ein fehlgeschlagenes Embedding
        darf das Speichern nie verhindern.
        """
        await conn.execute(_DELETE_SQL, workspace_id, entity_type, entity_id)
        if not chunks:
            return
        base = [
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
        ]
        if vectors is None or not await vector_supported(conn):
            await conn.executemany(_INSERT_SQL, base)
            return
        await conn.executemany(
            _INSERT_SQL_WITH_VECTOR,
            [
                (
                    *row,
                    None
                    if index >= len(vectors) or vectors[index] is None
                    else list(vectors[index] or []),
                )
                for index, row in enumerate(base)
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

    async def fetch_missing_vectors(
        self, conn: asyncpg.Connection, limit: int
    ) -> list[tuple[UUID, str]]:
        """Passagen ohne Vektor — Arbeitsvorrat des Backfills.

        Liefert `(id, indexierter Text)`; der Text ist derselbe, den auch der
        FTS-Index sieht (`heading_path` + Passagentext), damit Volltext und
        Vektor auf demselben Material arbeiten.
        """
        if not await vector_supported(conn):
            return []
        rows = await conn.fetch(_MISSING_VECTORS_SQL, limit)
        return [
            (row["id"], f"{row['heading_path']} {row['text']}".strip() or row["text"])
            for row in rows
        ]

    async def set_vector(
        self, conn: asyncpg.Connection, chunk_id: UUID, vector: Sequence[float]
    ) -> None:
        await conn.execute(_SET_VECTOR_SQL, chunk_id, list(vector))

    async def search(
        self,
        workspace_id: UUID,
        query: str,
        types: Sequence[str],
        limit: int,
        restrict: Mapping[str, Sequence[UUID]] | None = None,
        query_vector: Sequence[float] | None = None,
        *,
        use_text: bool = True,
    ) -> list[ContentChunkHit]:
        """Rangsortierte Passagen ueber die angefragten Typen.

        `restrict` wie in `SearchRepository`: fehlender Schluessel = keine
        Einschraenkung, leere Sequenz = nichts sichtbar.

        `query_vector` schaltet den semantischen Zweig zu, `use_text` den
        lexikalischen. Beide zusammen ergeben Hybrid (RRF), keiner von beiden
        ist ein Programmierfehler und liefert nichts.
        """
        if self._pool is None:  # pragma: no cover - nur Fehlkonfiguration
            raise RuntimeError("ContentChunkRepository ohne Pool angelegt.")
        use_vector = query_vector is not None
        if use_vector:
            # Fehlt pgvector auf dem Server, gibt es die Spalte nicht (0071 ist
            # fail-soft) — dann bleibt nur der lexikalische Zweig.
            async with self._pool.acquire() as probe:
                if not await vector_supported(probe):
                    use_vector = False
                    use_text = True
        if not use_text and not use_vector:
            return []
        hits: list[ContentChunkHit] = []
        for entity_type in types:
            tables = CHUNK_TYPE_TABLES.get(entity_type)
            if tables is None:
                continue
            entity_tbl, version_tbl, fk = tables
            allowed = None if restrict is None else restrict.get(entity_type)
            if allowed is not None and not allowed:
                continue

            # Feste Positionen ($1 workspace, $2 limit, $3 typ), danach nur die
            # Parameter, die die Query tatsaechlich referenziert — ein
            # gebundener, aber ungenutzter Platzhalter waere fuer Postgres
            # typlos.
            args: list[object] = [workspace_id, limit, entity_type]
            restrict_pos: int | None = None
            query_pos: int | None = None
            vector_pos: int | None = None
            if allowed is not None:
                args.append(list(allowed))
                restrict_pos = len(args)
            if use_text:
                args.append(query)
                query_pos = len(args)
            if use_vector:
                args.append(list(query_vector or []))
                vector_pos = len(args)

            sql = _search_sql(
                entity_tbl,
                version_tbl,
                fk,
                restrict_pos=restrict_pos,
                query_pos=query_pos,
                vector_pos=vector_pos,
            )
            rows = await self._pool.fetch(sql, *args)
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
