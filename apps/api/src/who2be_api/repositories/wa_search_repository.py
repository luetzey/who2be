"""Such-Query der WorkArea-Passagen (`wa_chunk`, ADR-0047 — WP6, Spec C).

Nur der Volltext-Zweig des `content_chunk_repository`-Musters (ADR-0046):
WorkArea-Material hat (noch) keine Vektor-Spalte, RRF entfaellt — ein einzelner
`ts_rank`-Zweig sortiert direkt.

Der Scope sitzt als CTE VOR dem Ranking (ADR-0037 §47): `scoped` filtert
`wa_chunk` auf `workspace_id` und — fuer Agenten bzw. viewer — auf die
lesbaren Areas (`area_id = ANY(...)`) IN der WHERE-Klausel. Nicht lesbares
Material erreicht weder Ranking noch Snippet; es gibt kein Post-Processing,
das etwas verlieren oder leaken koennte (Spec-Akzeptanz E).

FTS-Config identisch zur Generated Column in Migration 0076 — sonst matcht
die Query ihren eigenen Index nicht (eine `german`-Spalte gegen eine
`simple`-Query findet nichts). Der JOIN auf `wa_artifact` liefert den Titel
des Treffers; verwaiste Chunks (Artifact geloescht) raeumt der FK CASCADE ab.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

import asyncpg

from who2be_api.repositories.fts_config import fts_config_expr
from who2be_api.repositories.snippet import snippet
from who2be_models import WorkAreaSearchHit

# FTS-Config exakt wie die Generated Column in Migration 0076: Sprach-Praefix
# entscheidet, unbekannte Sprachen fallen auf 'simple' zurueck. Gemeinsame
# Quelle mit 0070/0082 — s. `fts_config`.
_FTS_CONFIG = fts_config_expr("c.locale")


def _search_sql(*, restrict_pos: int | None, area_pos: int | None) -> str:
    """Volltext-Suche ueber `wa_chunk`, Scope-CTE vor Ranking.

    Feste Positionen: $1 Workspace, $2 Query, $3 Limit. Die optionalen
    Parameter (Area-Scope-Liste, expliziter Area-Filter) reicht der Aufrufer
    als Positionen herein (Muster `content_chunk_repository._search_sql`) —
    ein gebundener, aber ungenutzter Platzhalter waere fuer Postgres typlos.
    """
    filters = ""
    if restrict_pos is not None:
        filters += f" AND c.area_id = ANY(${restrict_pos}::uuid[])"
    if area_pos is not None:
        filters += f" AND c.area_id = ${area_pos}"
    return (
        "WITH scoped AS ("
        "  SELECT c.artifact_id, c.area_id, c.block_id, c.text, c.ord, c.search,"
        f"         a.title, {_FTS_CONFIG} AS cfg"
        "  FROM wa_chunk c"
        "  JOIN wa_artifact a ON a.id = c.artifact_id AND a.workspace_id = c.workspace_id"
        f"  WHERE c.workspace_id = $1{filters}"
        ") "
        "SELECT artifact_id, area_id, block_id, text, title, "
        "       ts_rank(search, plainto_tsquery(cfg, $2)) AS score "
        "FROM scoped "
        "WHERE search @@ plainto_tsquery(cfg, $2) "
        "ORDER BY score DESC, artifact_id ASC, ord ASC "
        "LIMIT $3"
    )


class WaSearchRepository(Protocol):
    """Vertrag der WorkArea-Passagen-Suche (der Service testet gegen Fakes)."""

    async def search(
        self,
        workspace_id: UUID,
        query: str,
        limit: int,
        *,
        restrict_area_ids: list[UUID] | None,
        area_id: UUID | None,
    ) -> list[WorkAreaSearchHit]: ...


class PgWaSearchRepository:
    """asyncpg-Implementierung der WorkArea-Passagen-Suche."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def search(
        self,
        workspace_id: UUID,
        query: str,
        limit: int,
        *,
        restrict_area_ids: list[UUID] | None,
        area_id: UUID | None,
    ) -> list[WorkAreaSearchHit]:
        """Rangsortierte Treffer (Anker + Snippet) im Lese-Scope.

        `restrict_area_ids`: `None` = kein Area-Filter (Mensch editor+),
        Liste = nur diese Areas, leere Liste = nichts sichtbar (kommt hier
        defensiv als `[]` zurueck, der Service kurzschliesst frueher).
        `area_id` schraenkt zusaetzlich auf EINE Area ein.
        """
        if restrict_area_ids is not None and not restrict_area_ids:
            return []
        args: list[object] = [workspace_id, query, limit]
        restrict_pos: int | None = None
        area_pos: int | None = None
        if restrict_area_ids is not None:
            args.append(restrict_area_ids)
            restrict_pos = len(args)
        if area_id is not None:
            args.append(area_id)
            area_pos = len(args)
        rows = await self._pool.fetch(
            _search_sql(restrict_pos=restrict_pos, area_pos=area_pos), *args
        )
        return [
            WorkAreaSearchHit(
                anchor=f"{row['artifact_id']}#{row['block_id']}",
                artifact_id=row["artifact_id"],
                block_id=row["block_id"],
                title=row["title"],
                snippet=snippet(row["text"]),
                score=float(row["score"]),
                area_id=row["area_id"],
            )
            for row in rows
        ]
