"""Discovery-/Search-Models (ADR-0037, Passage-Ebene ADR-0046).

Zwei Vertraege fuer zwei verschiedene Fragen:

- `SearchHit` beantwortet „WELCHES Element passt zum Thema?" (Entity-Ranking,
  ADR-0037) — die Frage des Builders beim Kuratieren.
- `ContentChunkHit` beantwortet „WELCHE STELLE beantwortet meine Frage?"
  (Passage-Retrieval, ADR-0046) — die Frage des Agenten zur Laufzeit. Ein
  Entity-Treffer spart dort keinen Kontext, weil der Agent danach den
  Volltext nachladen muesste.

Stufe B (pgvector) legt sich hinter beide Formen; der Agent merkt von der
Umstellung nichts.
"""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from who2be_models.locale import DEFAULT_LOCALE, ContentLocale

SearchType = Literal["persona", "playbook", "resource", "external_tool"]

# Die Passage-Suche deckt zusaetzlich System-Prompt-Templates ab: sie tragen
# denselben BlockNote-Body und sind fuer den Builder genauso durchsuchbar.
ChunkType = Literal["persona", "playbook", "resource", "external_tool", "system_prompt_template"]


class SearchHit(BaseModel):
    """Ein rangsortierter Treffer der inhaltlichen Suche.

    `locale` (WP5, „Ein Element, eine Sprache"): die Sprache des getroffenen
    Elements (Identitaets-Zeile). Default `DEFAULT_LOCALE` deckt Alt-Clients/
    Fixtures ohne das Feld ab.
    """

    model_config = ConfigDict(from_attributes=True)

    type: SearchType
    id: UUID
    name: str
    snippet: str = ""
    score: float = Field(ge=0.0)
    locale: ContentLocale = DEFAULT_LOCALE


class ContentChunkHit(BaseModel):
    """Eine gefundene Passage aus der aktiven Version eines Elements.

    `block_id` ist der Heading-Anker aus ADR-0021 — zusammen mit `entity_id`
    ergibt er die bestehende Referenzform `"<entity_id>#<block_id>"`, es gibt
    also keine zweite Ankersprache. `None` bei Passagen ohne Anker
    (Beschreibung, Text vor dem ersten Heading, blocklose Aggregate).

    `heading_path` ist die Ueberschriften-Kette der Vorfahren (ohne die eigene
    Ueberschrift — die steht als erste Zeile in `text`) und sagt dem Modell,
    wo im Dokument die Passage steht.
    """

    model_config = ConfigDict(from_attributes=True)

    type: ChunkType
    entity_id: UUID
    name: str
    block_id: str | None = None
    heading_path: str = ""
    text: str
    score: float = Field(ge=0.0)
    locale: ContentLocale = DEFAULT_LOCALE
