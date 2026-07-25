"""Discovery-/Search-Models (ADR-0037).

Ein stabiler Tool-Vertrag fuer die inhaltliche Suche ueber die Kern-
Inhaltselemente PLUS das ExternalTool-Aggregat (WP-3). Stufe A (dieser Stand):
Postgres-Volltext ueber die aktive Version. Stufe B (Folge-Plan): semantische
Suche (pgvector) hinter derselben `SearchHit`-Form — der Agent merkt von der
Umstellung nichts.
"""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from who2be_models.locale import DEFAULT_LOCALE, ContentLocale

SearchType = Literal["persona", "playbook", "resource", "external_tool"]


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
