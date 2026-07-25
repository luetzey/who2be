"""Lokaler Embedding-Adapter (ADR-0046) — rechnet im eigenen Prozess.

Nutzt `fastembed` (ONNX-Runtime, keine Torch-Abhaengigkeit) mit einem kleinen
MULTILINGUALEN Satz-Encoder. Multilingual ist hier kein Luxus: der
Haupt-Gewinn gegenueber Volltext ist, dass eine deutsche Anfrage englischen
Inhalt findet — ein rein englisches Modell wuerde genau das nicht liefern.

Der Import von `fastembed` liegt bewusst IM Konstruktor, nicht auf Modulebene:
das Paket steckt in der optionalen Dependency-Gruppe `embeddings`. Ohne sie
soll der Kern importierbar bleiben und `build_embedding_port` still `None`
liefern, statt beim Start zu knallen.

Das Modell wird beim ersten Gebrauch geladen und im Prozess gehalten (der
Download passiert einmalig in den fastembed-Cache). `embed` laeuft in einem
Thread, weil die ONNX-Inferenz blockierend ist und sonst den Event-Loop
anhalten wuerde — bei `save_memory` (Laufzeit-Call eines Agenten) waere das
unmittelbar spuerbar.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from typing import Any

logger = logging.getLogger(__name__)

# 384 Dimensionen, Apache-2.0, ~0,22 GB. Bewusst das kleinste brauchbare
# MULTILINGUALE Modell in fastembed — die groesseren bringen fuer kurze
# Playbook-Passagen und 300-Zeichen-Memories kaum Trennschaerfe, kosten aber
# Image-Groesse und Ladezeit.
DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class LocalEmbeddingAdapter:
    """Erzeugt Vektoren lokal via fastembed/ONNX."""

    def __init__(self, model_name: str = DEFAULT_MODEL, dimensions: int = 384) -> None:
        try:
            from fastembed import TextEmbedding
        except ImportError as exc:  # pragma: no cover - haengt an der Dep-Gruppe
            raise RuntimeError(
                "Lokale Embeddings brauchen die optionale Dependency-Gruppe "
                "`embeddings` (`uv sync --group embeddings`)."
            ) from exc
        self._model: Any = TextEmbedding(model_name)
        self._model_name = model_name
        self._dimensions = dimensions

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @property
    def model_name(self) -> str:
        return self._model_name

    def _embed_sync(self, texts: Sequence[str]) -> list[list[float]]:
        return [[float(x) for x in vector] for vector in self._model.embed(list(texts))]

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        # Blockierende ONNX-Inferenz aus dem Event-Loop heraushalten.
        return await asyncio.to_thread(self._embed_sync, texts)
