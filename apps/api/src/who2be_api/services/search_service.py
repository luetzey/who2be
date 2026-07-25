"""Geschaeftslogik der inhaltlichen Suche (ADR-0037, Scoping praezisiert in ADR-0046).

Beantwortet „WELCHES Element passt zum Thema?" (Entity-Ranking). Die Frage
„WELCHE STELLE beantwortet meine Frage?" beantwortet der
`ContentChunkService` (Passage-Retrieval).

Das Read-Scoping liegt in `agent_scope.readable_content_scope` — dieselbe
Quelle wie fuer die Passage-Suche, damit beide Pfade nicht auseinanderlaufen.
Es geht als `restrict`-Praedikat IN die Repo-Query (ADR-0037 §47: „vor dem
Ranking"); der Nachfilter unten bleibt als Defense-in-Depth.

`external_tool` (WP-3) hat keine `assigned`-Teilmenge (flacher Workspace-
Katalog ohne Persona-/Playbook-Zuordnung) — dort genuegt der `none`-Ausschluss,
kein zusaetzlicher ID-Set-Filter noetig.
"""

import asyncpg

from who2be_api.core.agent_scope import readable_content_scope
from who2be_api.core.security import WorkspaceContext
from who2be_api.repositories.search_repository import SearchRepository
from who2be_models import SearchHit, SearchType

_ALL_TYPES: tuple[SearchType, ...] = ("persona", "playbook", "resource", "external_tool")


class SearchService:
    """Sucht ueber die Kern-Inhaltselemente, gefiltert auf den Read-Scope."""

    def __init__(self, repo: SearchRepository, pool: asyncpg.Pool | None = None) -> None:
        self._repo = repo
        self._pool = pool

    async def search(
        self,
        ctx: WorkspaceContext,
        query: str,
        types: list[SearchType] | None,
        limit: int,
    ) -> list[SearchHit]:
        query = query.strip()
        if not query:
            return []
        requested: list[str] = list(types) if types else list(_ALL_TYPES)
        scope = await readable_content_scope(self._pool, ctx, requested)
        if not scope.types:
            return []

        hits = await self._repo.search(
            ctx.workspace_id, query, scope.types, limit, scope.restrict or None
        )

        # Defense-in-Depth: das Praedikat im Repo ist massgeblich, dieser Filter
        # faengt nur ein Repo, das `restrict` ignoriert (z. B. ein Test-Fake).
        filtered: list[SearchHit] = []
        for hit in hits:
            if hit.type == "playbook" and scope.playbooks is not None:
                if hit.id not in scope.playbooks:
                    continue
            if hit.type == "resource" and scope.resources is not None:
                if hit.id not in scope.resources:
                    continue
            filtered.append(hit)
        return filtered
