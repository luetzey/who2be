"""Geschaeftslogik der Passage-Suche (ADR-0046).

Beantwortet „WELCHE STELLE beantwortet meine Frage?" — die Frage des Agenten
zur Laufzeit. Der Unterschied zur Entity-Suche (`SearchService`) ist nicht
kosmetisch: ein Treffer „Playbook X" zwingt den Agenten danach zum
`fetch_playbook` ueber den Volltext und spart damit keinen Kontext. Eine
Passage ist die Antwort selbst.

Das Read-Scoping teilt sich die Quelle mit der Entity-Suche
(`agent_scope.readable_content_scope`) — beide Pfade duerfen nie
unterschiedlich viel sichtbar machen.
"""

import asyncpg

from who2be_api.core.agent_scope import readable_content_scope
from who2be_api.core.security import WorkspaceContext
from who2be_api.repositories.content_chunk_repository import PgContentChunkRepository
from who2be_models import ChunkType, ContentChunkHit

# System-Prompt-Templates sind bewusst NICHT im Default: sie haengen an der
# Capability `system_prompt_write` (ADR-0040) und werden nur durchsucht, wenn
# der Aufrufer sie explizit anfragt und pflegen darf.
_DEFAULT_TYPES: tuple[ChunkType, ...] = ("persona", "playbook", "resource", "external_tool")


class ContentChunkService:
    """Sucht Passagen der aktiven Versionen, gefiltert auf den Read-Scope."""

    def __init__(self, repo: PgContentChunkRepository, pool: asyncpg.Pool | None = None) -> None:
        self._repo = repo
        self._pool = pool

    async def search(
        self,
        ctx: WorkspaceContext,
        query: str,
        types: list[ChunkType] | None,
        limit: int,
    ) -> list[ContentChunkHit]:
        query = query.strip()
        if not query:
            return []
        requested: list[str] = list(types) if types else list(_DEFAULT_TYPES)
        scope = await readable_content_scope(self._pool, ctx, requested)
        if not scope.types:
            return []

        hits = await self._repo.search(
            ctx.workspace_id, query, scope.types, limit, scope.restrict or None
        )

        # Defense-in-Depth wie in der Entity-Suche.
        filtered: list[ContentChunkHit] = []
        for hit in hits:
            if hit.type == "playbook" and scope.playbooks is not None:
                if hit.entity_id not in scope.playbooks:
                    continue
            if hit.type == "resource" and scope.resources is not None:
                if hit.entity_id not in scope.resources:
                    continue
            filtered.append(hit)
        return filtered
