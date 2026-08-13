"""In-Memory-Adapter — Referenz-Implementierung des Port-Contracts (ADR-0048).

Fuer Tests (DB- und netzlos) und als lesbare Definition dessen, was jeder
Adapter leisten muss: idempotentes `put`/`delete`, `BlobNotFoundError` bei
`get` auf fehlende Keys, Praefix-Listing lexikographisch aufsteigend. Der
MinIO-Adapter muss sich exakt so verhalten — Abweichungen sind Bugs dort,
nicht hier.
"""

from __future__ import annotations

from who2be_api.blobstore.port import BlobNotFoundError


class MemoryBlobStore:
    """Dict-basierter Store — Semantik wie S3, Lebensdauer wie der Prozess."""

    def __init__(self) -> None:
        self._objects: dict[str, tuple[bytes, str]] = {}

    async def put(self, key: str, data: bytes, media_type: str) -> None:
        self._objects[key] = (data, media_type)

    async def get(self, key: str) -> bytes:
        try:
            return self._objects[key][0]
        except KeyError as exc:
            raise BlobNotFoundError(key) from exc

    async def exists(self, key: str) -> bool:
        return key in self._objects

    async def delete(self, key: str) -> None:
        self._objects.pop(key, None)

    async def list_keys(self, prefix: str) -> list[str]:
        return sorted(key for key in self._objects if key.startswith(prefix))

    def media_type(self, key: str) -> str:
        """Testhilfe: der beim `put` mitgegebene Media-Type."""
        try:
            return self._objects[key][1]
        except KeyError as exc:
            raise BlobNotFoundError(key) from exc
