"""Geschaeftslogik der Passage-Suche (ADR-0046).

Beantwortet „WELCHE STELLE beantwortet meine Frage?" — die Frage des Agenten
zur Laufzeit. Der Unterschied zur Entity-Suche (`SearchService`) ist nicht
kosmetisch: ein Treffer „Playbook X" zwingt den Agenten danach zum
`fetch_playbook` ueber den Volltext und spart damit keinen Kontext. Eine
Passage ist die Antwort selbst.

Das Read-Scoping teilt sich die Quelle mit der Entity-Suche
(`agent_scope.readable_content_scope`) — beide Pfade duerfen nie
unterschiedlich viel sichtbar machen.

`mode` (ADR-0037 §35-38, hier eingeloest): `auto` nutzt Semantik, wenn ein
Embedding-Port da ist, und faellt sonst lautlos auf Volltext zurueck. Damit
aendert sich der Tool-Vertrag nicht, wenn eine Installation ohne die optionale
Dependency-Gruppe laeuft.
"""

import logging

import asyncpg

from who2be_api.core.agent_scope import readable_content_scope
from who2be_api.core.security import WorkspaceContext
from who2be_api.embeddings import EmbeddingPort
from who2be_api.repositories.content_chunk_repository import PgContentChunkRepository
from who2be_models import ChunkType, ContentChunkHit, SearchMode

logger = logging.getLogger(__name__)

# System-Prompt-Templates sind bewusst NICHT im Default: sie haengen an der
# Capability `system_prompt_write` (ADR-0040) und werden nur durchsucht, wenn
# der Aufrufer sie explizit anfragt und pflegen darf.
_DEFAULT_TYPES: tuple[ChunkType, ...] = ("persona", "playbook", "resource", "external_tool")


class ContentChunkService:
    """Sucht Passagen der aktiven Versionen, gefiltert auf den Read-Scope."""

    def __init__(
        self,
        repo: PgContentChunkRepository,
        pool: asyncpg.Pool | None = None,
        embedder: EmbeddingPort | None = None,
    ) -> None:
        self._repo = repo
        self._pool = pool
        self._embedder = embedder

    async def _query_vector(self, query: str, mode: SearchMode) -> list[float] | None:
        """Vektor der Anfrage — oder `None`, wenn nicht moeglich/gewuenscht.

        Ein Fehler beim Einbetten der ANFRAGE degradiert bewusst auf Volltext,
        statt die Suche scheitern zu lassen: eine schlechtere Antwort ist
        besser als keine.
        """
        if mode == SearchMode.text or self._embedder is None:
            return None
        try:
            vectors = await self._embedder.embed([query])
        except Exception:  # noqa: BLE001 - Degradation ist Absicht
            logger.warning("Query-Embedding fehlgeschlagen — Suche faellt auf Volltext zurueck.")
            return None
        return vectors[0] if vectors else None

    async def search(
        self,
        ctx: WorkspaceContext,
        query: str,
        types: list[ChunkType] | None,
        limit: int,
        mode: SearchMode = SearchMode.auto,
    ) -> list[ContentChunkHit]:
        query = query.strip()
        if not query:
            return []
        requested: list[str] = list(types) if types else list(_DEFAULT_TYPES)
        scope = await readable_content_scope(self._pool, ctx, requested)
        if not scope.types:
            return []

        query_vector = await self._query_vector(query, mode)
        if mode == SearchMode.semantic and query_vector is None:
            # Explizit semantisch angefragt, aber kein Port: lieber Volltext als
            # ein leeres Ergebnis, das wie „nichts gefunden" aussieht.
            logger.info("mode=semantic ohne Embedding-Port — es wird Volltext gesucht.")
        use_text = mode != SearchMode.semantic or query_vector is None

        hits = await self._repo.search(
            ctx.workspace_id,
            query,
            scope.types,
            limit,
            scope.restrict or None,
            query_vector,
            use_text=use_text,
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
