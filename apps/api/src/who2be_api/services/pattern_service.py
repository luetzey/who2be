"""Muster: berechnete Sicht aus Lernvorschlaegen und Faellen (ADR-0053 3.7).

Lernschleife Phase D, Paket D5a. Nur die Service-Schicht — der Router
(`GET /patterns?agent_id`, 6.5) folgt mit D5b.

Deterministisch (Weiche M9 = LW4): Zaehler, Aehnlichkeits-Cluster, Schwelle
n. Kein LLM, kein eigenes Aggregat, kein Zustand. Ein Muster aktiviert nichts
und legt keinen Fall an; das tut erst ein Mensch oder der Builder.

- **Lernvorschlaege:** offene Lernvorschlaege (`pending`) desselben Agenten,
  die einander nach der Pruefung der Dublettenerkennung aehneln, bilden ein
  Cluster (Zusammenhangskomponente der aehnlichen Paare; ein Eintrag ohne
  Partner ist ein Cluster aus einem). Zaehler ist die Summe von
  `occurrence_count`; Muster ab `PATTERN_MIN_COUNT`.
- **Faelle:** gleicher Agent, gleiche Zuordnung, mindestens
  `PATTERN_MIN_COUNT` offene Faelle (`PATTERN_OPEN_CASE_STATUSES`) in
  `PATTERN_CASE_WINDOW_DAYS` Tagen (Abfrage im Repository).

Sichtbarkeit (6.5): Mensch ab `editor`, Agent-Token mit `case_triage` —
dieselbe Pruefung wie beim Triagieren (`case_service.require_triage_right`).
Das Nutzergedaechtnis fliesst nie ein: Kandidaten sind nur `scope='agent'`.
"""

from __future__ import annotations

from typing import ClassVar
from uuid import UUID

from who2be_api.core.security import WorkspaceContext
from who2be_api.repositories.case_repository import CaseRepository
from who2be_api.repositories.memory_repository import (
    LessonCandidate,
    LessonPatternSignals,
    MemoryRepository,
)
from who2be_api.services.case_service import require_triage_right
from who2be_models.pattern import (
    PATTERN_CASE_WINDOW_DAYS,
    PATTERN_MIN_COUNT,
    PATTERN_OPEN_CASE_STATUSES,
    Pattern,
    PatternSource,
)


def lesson_clusters(signals: LessonPatternSignals) -> list[list[LessonCandidate]]:
    """Zusammenhangskomponenten der aehnlichen Paare (Single Linkage).

    Deterministisch: Mitglieder je Cluster nach ID, Cluster nach Agent und
    kleinster ID. Paare gibt das Repository nur innerhalb eines Agenten aus
    (`lesson_pattern_signals`), ein Cluster gehoert also genau einem Agenten.
    """
    by_id = {c.id: c for c in signals.candidates}
    parent: dict[UUID, UUID] = {cid: cid for cid in by_id}

    def find(x: UUID) -> UUID:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in signals.similar_pairs:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    groups: dict[UUID, list[LessonCandidate]] = {}
    for cid in sorted(by_id):
        groups.setdefault(find(cid), []).append(by_id[cid])
    return sorted(groups.values(), key=lambda g: (str(g[0].agent_id), str(g[0].id)))


def lesson_patterns(signals: LessonPatternSignals, min_count: int) -> list[Pattern]:
    """Cluster mit Zaehler `>= min_count` als Muster."""
    patterns: list[Pattern] = []
    for cluster in lesson_clusters(signals):
        count = sum(c.occurrence_count for c in cluster)
        if count < min_count:
            continue
        patterns.append(
            Pattern(
                source=PatternSource.lesson,
                agent_id=cluster[0].agent_id,
                count=count,
                evidence_ids=[c.id for c in cluster],
                first_seen=min(c.created_at for c in cluster),
                last_seen=max(c.last_seen for c in cluster),
            )
        )
    return patterns


class PatternService:
    """Berechnete Musterliste (ADR-0053 3.7, 6.5)."""

    __test__: ClassVar[bool] = False

    def __init__(self, cases: CaseRepository, memories: MemoryRepository) -> None:
        self._cases = cases
        self._memories = memories

    async def list_patterns(
        self, ctx: WorkspaceContext, *, agent_id: UUID | None = None
    ) -> list[Pattern]:
        """Alle Muster des Workspace, optional fuer einen Agenten.

        Reihenfolge: Fall-Muster vor Lernvorschlags-Mustern, darin nach Agent
        und Element bzw. kleinster Beleg-ID.
        """
        require_triage_right(ctx)
        case_patterns = await self._cases.case_patterns(
            ctx.workspace_id,
            agent_id=agent_id,
            statuses=PATTERN_OPEN_CASE_STATUSES,
            window_days=PATTERN_CASE_WINDOW_DAYS,
            min_count=PATTERN_MIN_COUNT,
        )
        signals = await self._memories.lesson_pattern_signals(ctx.workspace_id, agent_id)
        return [*case_patterns, *lesson_patterns(signals, PATTERN_MIN_COUNT)]
