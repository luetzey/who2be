"""Geschaeftslogik der WorkArea-Suche (ADR-0047, WP6 — Spec C).

Die Suche ist der EINSTIEG in die WorkArea: sie beantwortet „WELCHE STELLE
traegt das Material?" mit Anker + Snippet — nie mit ganzen Dokumenten. Die
Artifact-Liste ist bewusst NICHT der Einstieg (Metadaten zum Kuratieren, kein
Retrieval-Pfad).

Das Area-Scoping kommt aus `core/workarea_scope.readable_area_ids` — derselben
Quelle wie alle WorkArea-Reads (WP4) — und wandert als Filterliste IN die
WHERE-Klausel der Suchabfrage (Scope vor Ranking, ADR-0037 §47). Es gibt kein
Nachfiltern im Post-Processing (Spec-Akzeptanz E); eine leere Scope-Liste
kurzschliesst OHNE Query.

Ein `area_id`-Filter ausserhalb des Lese-Scopes liefert schlicht `[]` — ein
leeres Suchergebnis ist von „Area existiert nicht" nicht unterscheidbar (kein
Existenz-Orakel, Muster `workarea_scope`).

ARC-3: kein SQL, keine HTTPException — nur Scope-Helper und das Repository.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg

from who2be_api.core.security import WorkspaceContext
from who2be_api.core.workarea_scope import readable_area_ids
from who2be_api.repositories.wa_search_repository import WaSearchRepository
from who2be_models import WorkAreaSearchHit


class WaSearchService:
    """Sucht WorkArea-Passagen, gefiltert auf die lesbaren Areas des Aufrufers."""

    def __init__(self, pool: asyncpg.Pool, repo: WaSearchRepository) -> None:
        self._pool = pool
        self._repo = repo

    async def search(
        self,
        ctx: WorkspaceContext,
        query: str,
        area_id: UUID | None,
        limit: int,
    ) -> list[WorkAreaSearchHit]:
        """Rangsortierte Treffer (Anker + Snippet) im Lese-Scope des Aufrufers."""
        query = query.strip()
        if not query:
            return []
        restrict = await readable_area_ids(self._pool, ctx)
        if restrict is not None:
            if not restrict:
                # Keine lesbare Area (z. B. Agent ohne Grants): nichts sichtbar,
                # keine Query noetig.
                return []
            if area_id is not None and area_id not in restrict:
                # Filter auf eine nicht lesbare/unbekannte Area: leeres
                # Ergebnis statt Existenz-Leak.
                return []
        return await self._repo.search(
            ctx.workspace_id,
            query,
            limit,
            restrict_area_ids=restrict,
            area_id=area_id,
        )
