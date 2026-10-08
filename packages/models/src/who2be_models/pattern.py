"""Muster (ADR-0053 3.7, Lernschleife Phase D, Paket D5a).

Muster sind eine **berechnete Sicht** ohne eigenes Aggregat und ohne Zustand.
Sie entstehen deterministisch (Weiche M9) aus zwei Quellen:

- **Lernvorschlaege:** `kind='lesson'`, `status='pending'`; aehnliche
  Eintraege desselben Agenten bilden ein Cluster, Muster ab Zaehler `>= n`.
  Aehnlich heisst: derselbe Trigram-/Vektor-Weg wie die Dublettenpruefung
  (`memory_repository.MEMORY_DEDUP_SIMILARITY`).
- **Faelle:** gleicher Agent, gleiche Element-Zuordnung, mindestens n offene
  Faelle im Zeitfenster.

Ein Muster aktiviert nichts und legt nichts an. Daraus wird erst ein Fall
(`reporter_kind='pattern'`), wenn ein Mensch oder der Builder ihn formuliert.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from who2be_models.case import CaseStatus, CaseTarget

# Musterschwelle n und Zeitfenster der Fall-Muster: gesetzte Annahmen aus
# ADR-0053 Anhang B.
PATTERN_MIN_COUNT = 3
PATTERN_CASE_WINDOW_DAYS = 30

# „offene Faelle“ (3.7): noch nicht abgeschlossen. `addressed`, `verified` und
# `dismissed` sind die Stellen, an denen ein Mensch abschliessend gehandelt hat
# (3.3); `triaged` und `reopened` bleiben offen, weil die Zuordnung, nach der
# 3.7 gruppiert, gerade beim Triagieren entsteht.
PATTERN_OPEN_CASE_STATUSES: frozenset[CaseStatus] = frozenset(
    {CaseStatus.open, CaseStatus.triaged, CaseStatus.in_progress, CaseStatus.reopened}
)


class PatternSource(StrEnum):
    """Quelle eines Musters (3.7)."""

    lesson = "lesson"
    case = "case"


class PatternElement(BaseModel):
    """Element-Zuordnung eines Fall-Musters; `entity_id` leer bei `tool_policy`/`model_limit`."""

    model_config = ConfigDict(frozen=True)

    target: CaseTarget
    entity_id: UUID | None = None


class Pattern(BaseModel):
    """Ein berechnetes Muster.

    - `element`: nur bei `source='case'` — die gemeinsame Zuordnung.
    - `evidence_ids`: die Belege — Fall-IDs bzw. die IDs der Lernvorschlaege
      im Cluster, aufsteigend sortiert.
    - `count`: bei Faellen die Zahl der Faelle, bei Lernvorschlaegen die Summe
      von `occurrence_count` im Cluster.
    - `first_seen`/`last_seen`: Zeitraum der Belege (Lernvorschlag: Anlage
      bis juengste Wiederholung).
    """

    model_config = ConfigDict(frozen=True)

    source: PatternSource
    agent_id: UUID
    element: PatternElement | None = None
    count: int = Field(ge=1)
    evidence_ids: list[UUID]
    first_seen: datetime
    last_seen: datetime
