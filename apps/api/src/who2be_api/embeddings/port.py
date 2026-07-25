"""`EmbeddingPort` — die Grenze zwischen Kern und Vektor-Erzeugung (ADR-0046).

Hexagonal (Ports & Adapters), analog `licensing/port.py`: der Kern kennt nur
`embed(texts) -> list[vector]` plus die Dimension. Welcher Adapter dahinter
steckt, ist austauschbar und fuer die Such-Pfade unsichtbar.

Der Port existiert aus zwei Gruenden, nicht aus Symmetrie:

1. **Build-Isolation.** Der Kern darf keine ML-Abhaengigkeit statisch
   importieren — das On-Prem-Artefakt soll sie physisch nicht brauchen
   (Muster ADR-0029/Billing). Der lokale Adapter haengt an der optionalen
   Dependency-Gruppe `embeddings`; fehlt sie, gibt es schlicht keinen Port.
2. **Datenschutz-Grenze.** `.env.example` verspricht On-Prem ausdruecklich
   „KEIN Phone-Home". Ein Adapter, der Text nach draussen gibt, waere eine
   bewusste Entscheidung an genau dieser Stelle — nicht ein beilaeufiger
   `import`.

`None` als Port ist der NORMALFALL, kein Fehler: dann bleibt `content_vector`
NULL und beide Suchen laufen im Volltext-Modus weiter.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

# Dimension der Vektor-Spalte (Migration 0071). Im Schema fixiert: ein
# Modellwechsel auf eine andere Dimension braucht eine neue Migration UND einen
# vollstaendigen Re-Embed. `build_embedding_port` prueft den Adapter dagegen,
# damit die Fehlkonfiguration beim Start auffaellt und nicht erst als
# `expected 384 dimensions, not 768` im INSERT.
EMBEDDING_DIMENSIONS = 384


class EmbeddingPort(Protocol):
    """Erzeugt Vektoren zu Texten — Herkunft ist Adapter-Sache."""

    @property
    def dimensions(self) -> int:
        """Laenge der erzeugten Vektoren; muss `EMBEDDING_DIMENSIONS` sein."""
        ...

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Vektoren in der Reihenfolge der Eingabe.

        Muss genau so viele Vektoren liefern wie Texte hineingingen. Fehler
        duerfen geworfen werden — die Aufrufer behandeln sie best-effort und
        lassen die Spalte im Zweifel NULL.
        """
        ...
