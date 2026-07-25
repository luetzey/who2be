"""Adapter-Auswahl fuer Embeddings (ADR-0046), analog `licensing/service.py`.

`build_embedding_port` ist der einzige Ort, an dem entschieden wird, OB und
WOMIT Vektoren erzeugt werden. Alle Aufrufer sehen nur `EmbeddingPort | None`.

Fail-soft ist hier die richtige Haltung, nicht Bequemlichkeit: Semantik ist
additiv. Fehlt der Adapter (Dependency-Gruppe nicht installiert, Modell nicht
ladbar, Feature abgeschaltet), soll die Anwendung normal laufen und die Suche
im Volltext-Modus bleiben — nicht der Start scheitern. Ein Fehler wird EINMAL
geloggt, damit die Abwesenheit sichtbar ist und nicht stillschweigend
weiterlaeuft.

Der Port wird prozessweit einmal gebaut und gecacht: das Modell zu laden kostet
Sekunden, und jede Anfrage neu zu laden waere absurd.
"""

from __future__ import annotations

import logging

from who2be_api.core.config import Settings, get_settings
from who2be_api.embeddings.port import EMBEDDING_DIMENSIONS, EmbeddingPort

logger = logging.getLogger(__name__)

_cached_port: EmbeddingPort | None = None
_resolved = False


def build_embedding_port(settings: Settings | None = None) -> EmbeddingPort | None:
    """Liefert den Embedding-Port — oder `None`, wenn Semantik nicht verfuegbar ist.

    `None` ist der Normalfall einer Installation ohne die optionale
    Dependency-Gruppe und KEIN Fehlerzustand.
    """
    global _cached_port, _resolved
    if _resolved:
        return _cached_port

    resolved_settings = settings or get_settings()
    _resolved = True
    if not resolved_settings.embeddings_enabled:
        logger.info("Embeddings deaktiviert (WHO2BE_EMBEDDINGS_ENABLED) — Suche bleibt Volltext.")
        _cached_port = None
        return None

    try:
        from who2be_api.embeddings.adapters.local import LocalEmbeddingAdapter

        adapter = LocalEmbeddingAdapter(
            model_name=resolved_settings.embedding_model,
            dimensions=EMBEDDING_DIMENSIONS,
        )
    except Exception:  # noqa: BLE001 - fail-soft ist hier Absicht (siehe Modul-Docstring)
        logger.warning(
            "Embedding-Adapter nicht verfuegbar — semantische Suche bleibt aus, "
            "Volltext laeuft weiter. Fuer Semantik: `uv sync --group embeddings`.",
            exc_info=True,
        )
        _cached_port = None
        return None

    if adapter.dimensions != EMBEDDING_DIMENSIONS:
        # Waere sonst erst beim INSERT als „expected 384 dimensions" sichtbar —
        # und dann pro Chunk, nicht einmal beim Start.
        logger.error(
            "Embedding-Modell liefert %s Dimensionen, das Schema erwartet %s — "
            "semantische Suche bleibt aus. Modellwechsel braucht eine Migration.",
            adapter.dimensions,
            EMBEDDING_DIMENSIONS,
        )
        _cached_port = None
        return None

    _cached_port = adapter
    return _cached_port


def reset_embedding_port() -> None:
    """Verwirft den Prozess-Cache (Tests, Konfig-Wechsel)."""
    global _cached_port, _resolved
    _cached_port = None
    _resolved = False


def set_embedding_port(port: EmbeddingPort | None) -> None:
    """Setzt den Port direkt — fuer Tests und fuer die CLIs, die ihn selbst bauen."""
    global _cached_port, _resolved
    _cached_port = port
    _resolved = True
