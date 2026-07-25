"""Geschaeftslogik der inhaltlichen Suche (ADR-0037, Scoping praezisiert in ADR-0046).

Wendet das Pro-Agent-Read-Scoping auf die Treffer an: ein `assigned`-Agent findet
nur in seinem zugewiesenen Set, `none` blendet den Typ aus, `persona_read=False`
verbirgt Personae. Nur `status='active'` (das Repo joint bereits darauf).

Das Scoping geht als `restrict`-Praedikat **in** die Repo-Query (ADR-0037 §47:
„vor dem Ranking"). Frueher wurde hinter dem `LIMIT` nachgefiltert — dabei
liefert die Suche `[]`, sobald die globalen Top-k ausserhalb des zugewiesenen
Sets liegen, obwohl passende zugewiesene Treffer dahinter stehen. Der
Nachfilter bleibt zusaetzlich als Defense-in-Depth erhalten.

Die Scope-Mengen werden nur fuer **angefragte** Typen berechnet: `*_read_restrict`
wirft bei Scope `none` ein 403, und ein Typ, der ohnehin schon aus der Anfrage
gefallen ist, darf die uebrige Suche nicht mit 403 abbrechen (ein Agent mit
`playbook_read=none` muss weiterhin nach Personae suchen koennen).

`external_tool` (WP-3) hat keine `assigned`-Teilmenge (flacher Workspace-
Katalog ohne Persona-/Playbook-Zuordnung) — dort genuegt der `none`-Ausschluss,
kein zusaetzlicher ID-Set-Filter noetig.
"""

from collections.abc import Sequence
from uuid import UUID

import asyncpg

from who2be_api.core.agent_scope import visible_playbook_ids, visible_resource_ids
from who2be_api.core.security import WorkspaceContext
from who2be_api.repositories.search_repository import SearchRepository
from who2be_models import ReadScope, SearchHit, SearchType

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
        policy = ctx.tool_policy

        # Typen ausblenden, die der Agent gar nicht lesen darf (none / persona off).
        if policy is not None:
            allowed: list[str] = []
            for t in requested:
                if t == "persona" and not policy.persona_read:
                    continue
                if t == "playbook" and policy.playbook_read == ReadScope.none:
                    continue
                if t == "resource" and policy.resource_read == ReadScope.none:
                    continue
                if t == "external_tool" and policy.external_tool_read == ReadScope.none:
                    continue
                allowed.append(t)
            requested = allowed
        if not requested:
            return []

        # `assigned`-Scope VOR dem Ranking — nur fuer noch angefragte Typen.
        restrict: dict[str, Sequence[UUID]] = {}
        pb_scope: set[UUID] | None = None
        res_scope: set[UUID] | None = None
        if "playbook" in requested:
            pb_scope = await visible_playbook_ids(self._pool, ctx)
            if pb_scope is not None:
                restrict["playbook"] = sorted(pb_scope)
        if "resource" in requested:
            res_scope = await visible_resource_ids(self._pool, ctx)
            if res_scope is not None:
                restrict["resource"] = sorted(res_scope)

        hits = await self._repo.search(ctx.workspace_id, query, requested, limit, restrict or None)

        # Defense-in-Depth: das Praedikat oben ist massgeblich, dieser Filter
        # faengt nur ein Repo, das `restrict` ignoriert (z. B. ein Test-Fake).
        filtered: list[SearchHit] = []
        for hit in hits:
            if hit.type == "playbook" and pb_scope is not None and hit.id not in pb_scope:
                continue
            if hit.type == "resource" and res_scope is not None and hit.id not in res_scope:
                continue
            filtered.append(hit)
        return filtered
