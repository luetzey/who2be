"""Volltext-Suche ueber die aktive Version der Kern-Inhaltselemente (ADR-0037).

Stufe A: Postgres-Volltext (`to_tsvector`/`plainto_tsquery`/`ts_rank`) ueber
Name + Content-Text der `status='active'`-Version (Locale `de`). Laufzeit-FTS
ohne materialisierten Index — funktional korrekt; ein GIN-Index pro Tabelle ist
der Folge-Perf-Schritt. Workspace-Scope explizit (Defense + RLS).

`content::text` ist die jsonb-Repraesentation inkl. Schluessel — eine bewusst
grobe, aber robuste Textquelle fuer Stufe A; Stufe B (semantisch) ersetzt das.
"""

from typing import Protocol
from uuid import UUID

import asyncpg

from who2be_models import SearchHit

# Pro Typ: (Entity-Tabelle, Version-Tabelle, FK-Spalte). Locale-agnostisch
# (ADR-0045, „Ein Element, eine Sprache"): die aktive Version ist per Entity
# eindeutig — kein Locale-Pin mehr noetig.
_TYPE_TABLES: dict[str, tuple[str, str, str]] = {
    "persona": ("persona", "persona_version", "persona_id"),
    "playbook": ("playbook", "playbook_version", "playbook_id"),
    "resource": ("resource", "resource_version", "resource_id"),
    # WP-3: ExternalTool-Aggregat — Name + Content (u. a. `display_name`,
    # `usage_notes`) der aktiven Version.
    "external_tool": ("external_tool", "external_tool_version", "external_tool_id"),
}


def _query_for(entity: str, version: str, fk: str) -> str:
    # `simple`-Config: keine Stemming-/Stopword-Sprache (robust fuer DE/EN-Mix).
    vector = "to_tsvector('simple', coalesce(e.name, '') || ' ' || coalesce(ev.content::text, ''))"
    return (
        f"SELECT e.id, e.name, "
        f"       ts_rank({vector}, plainto_tsquery('simple', $2)) AS score, "
        f"       coalesce(ev.content->>'description', '') AS snippet "
        f"FROM {entity} e "
        f"JOIN {version} ev ON ev.{fk} = e.id AND ev.status = 'active' "
        f"WHERE e.workspace_id = $1 "
        f"  AND {vector} @@ plainto_tsquery('simple', $2) "
        f"ORDER BY score DESC, e.name ASC "
        f"LIMIT $3"
    )


class SearchRepository(Protocol):
    async def search(
        self, workspace_id: UUID, query: str, types: list[str], limit: int
    ) -> list[SearchHit]: ...


class PgSearchRepository:
    """asyncpg-Implementierung der Volltext-Suche."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def search(
        self, workspace_id: UUID, query: str, types: list[str], limit: int
    ) -> list[SearchHit]:
        hits: list[SearchHit] = []
        for entity_type in types:
            tables = _TYPE_TABLES.get(entity_type)
            if tables is None:
                continue
            rows = await self._pool.fetch(_query_for(*tables), workspace_id, query, limit)
            for row in rows:
                hits.append(
                    SearchHit(
                        type=entity_type,  # type: ignore[arg-type]
                        id=row["id"],
                        name=row["name"],
                        snippet=(row["snippet"] or "")[:200],
                        score=float(row["score"]),
                    )
                )
        # Ueber alle Typen nach Score sortieren, dann global kappen.
        hits.sort(key=lambda h: (-h.score, h.name))
        return hits[:limit]
