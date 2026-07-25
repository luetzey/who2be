"""Vektor-Erzeugung hinter einem Port (ADR-0046).

Der Kern importiert NIE einen konkreten Adapter — nur `build_embedding_port`.
"""

from who2be_api.embeddings.port import EMBEDDING_DIMENSIONS, EmbeddingPort
from who2be_api.embeddings.service import (
    build_embedding_port,
    reset_embedding_port,
    set_embedding_port,
)

__all__ = [
    "EMBEDDING_DIMENSIONS",
    "EmbeddingPort",
    "build_embedding_port",
    "reset_embedding_port",
    "set_embedding_port",
]
