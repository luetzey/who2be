"""Datenzugriff fuer den WorkArea-Ingest (`wa_blob` + Ingest-Artifacts, ADR-0048).

Buendelt die drei Schreib-Statements der Ingest-Transaktion (Pipeline B) plus
den Dedup-Lookup:

- `upsert_blob`: Katalog-Zeile in `wa_blob` (0075), `ON CONFLICT DO NOTHING` —
  content-addressed heisst: dieselbe (workspace, sha256)-Zeile ist idempotent.
- `insert_blob_artifact`: das Roh-Artifact (`type='blob'`, `content_ref` =
  sha256, 0074) — die unveraenderte Quelle bleibt adressierbar.
- `insert_doc_artifact`: der abgeleitete Text (`type='doc'`, Block-Liste in
  `content`, `blob_sha256` als Provenance-Rueckverweis).
- `find_dedup`: existieren `wa_blob`-Zeile UND doc-Artifact mit
  `blob_sha256 = hash` (plus zugehoeriges blob-Artifact) in der Ziel-Area,
  liefert er beide IDs — der Service antwortet dann idempotent ohne Write.

Die Schreibmethoden nehmen eine `Connection`: der Service haelt Blob-Upsert,
beide Artifact-Inserts und den Chunk-Sync in EINER Transaktion zusammen
(Muster `wa_artifact_repository`). Jede Query filtert auf `workspace_id`
(Defense-in-Depth zusaetzlich zur RLS).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, TypeAlias
from uuid import UUID

import asyncpg

from who2be_models import DocBlock

_Fetcher: TypeAlias = asyncpg.Pool | asyncpg.Connection

# Dedup-Kriterium (Pipeline B, Schritt 5): wa_blob-Zeile UND ein doc-Artifact
# mit blob_sha256 = hash in der ZIEL-Area; das blob-Artifact derselben Area
# liefert die zweite ID der idempotenten Antwort. Aelteste Ingest-Runde
# gewinnt (ORDER BY d.created_at) — deterministisch bei Alt-Duplikaten.
_FIND_DEDUP_SQL = """
SELECT b.id AS blob_artifact_id,
       d.id AS doc_artifact_id,
       coalesce(jsonb_array_length(d.content), 0) AS block_count
FROM wa_blob wb
JOIN wa_artifact d
  ON d.workspace_id = wb.workspace_id
 AND d.type = 'doc'
 AND d.blob_sha256 = wb.sha256
JOIN wa_artifact b
  ON b.workspace_id = wb.workspace_id
 AND b.area_id = d.area_id
 AND b.type = 'blob'
 AND b.content_ref = wb.sha256
WHERE wb.workspace_id = $1 AND wb.sha256 = $2 AND d.area_id = $3
ORDER BY d.created_at, d.id
LIMIT 1
"""

_UPSERT_BLOB_SQL = (
    "INSERT INTO wa_blob "
    "(workspace_id, sha256, size_bytes, media_type, storage_key, source_url, fetched_at) "
    "VALUES ($1, $2, $3, $4, $5, $6, $7) "
    "ON CONFLICT (workspace_id, sha256) DO NOTHING"
)

_INSERT_BLOB_ARTIFACT_SQL = (
    "INSERT INTO wa_artifact "
    "(workspace_id, area_id, type, title, occurred_at, occurred_precision, "
    " sensitivity, content_ref, source_url, fetched_at, updated_by) "
    "VALUES ($1, $2, 'blob', $3, $4, $5, $6, $7, $8, $9, $10) "
    "RETURNING id"
)

_INSERT_DOC_ARTIFACT_SQL = (
    "INSERT INTO wa_artifact "
    "(workspace_id, area_id, type, title, occurred_at, occurred_precision, "
    " sensitivity, blob_sha256, source_url, fetched_at, content, updated_by) "
    "VALUES ($1, $2, 'doc', $3, $4, $5, $6, $7, $8, $9, $10::jsonb, $11) "
    "RETURNING id"
)


def _blocks_payload(blocks: list[DocBlock]) -> list[dict[str, Any]]:
    """Block-Liste als jsonb-Parameter — die PYTHON-Liste uebergeben, nicht
    selbst serialisieren (Pool-Codec encodiert jsonb-Params bereits; Details
    im gleichnamigen Helper von `wa_artifact_repository`)."""
    return [block.model_dump(mode="json", exclude_none=True) for block in blocks]


@dataclass(frozen=True)
class IngestDedupHit:
    """Bestehende Artifact-IDs eines bereits ingestierten Blobs (Dedup-Fall)."""

    blob_artifact_id: UUID
    doc_artifact_id: UUID
    block_count: int


class WaBlobRepository(Protocol):
    """Vertrag des Ingest-Datenzugriffs (Service-Sicht)."""

    async def find_dedup(
        self, fetcher: _Fetcher, workspace_id: UUID, sha256: str, area_id: UUID
    ) -> IngestDedupHit | None: ...

    async def upsert_blob(
        self,
        conn: asyncpg.Connection,
        workspace_id: UUID,
        *,
        sha256: str,
        size_bytes: int,
        media_type: str,
        storage_key: str,
        source_url: str | None,
        fetched_at: datetime | None,
    ) -> None: ...

    async def insert_blob_artifact(
        self,
        conn: asyncpg.Connection,
        workspace_id: UUID,
        area_id: UUID,
        *,
        title: str,
        occurred_at: datetime,
        occurred_precision: str,
        sensitivity: str,
        sha256: str,
        source_url: str | None,
        fetched_at: datetime | None,
        updated_by: UUID,
    ) -> UUID: ...

    async def insert_doc_artifact(
        self,
        conn: asyncpg.Connection,
        workspace_id: UUID,
        area_id: UUID,
        *,
        title: str,
        occurred_at: datetime,
        occurred_precision: str,
        sensitivity: str,
        blob_sha256: str,
        source_url: str | None,
        fetched_at: datetime | None,
        blocks: list[DocBlock],
        updated_by: UUID,
    ) -> UUID: ...


class PgWaBlobRepository:
    """asyncpg-Implementierung von `WaBlobRepository`.

    Bewusst ohne Pool im Konstruktor: die Schreibpfade laufen auf der
    Transaktions-Connection des Services (Muster `wa_artifact_repository`).
    """

    async def find_dedup(
        self, fetcher: _Fetcher, workspace_id: UUID, sha256: str, area_id: UUID
    ) -> IngestDedupHit | None:
        row = await fetcher.fetchrow(_FIND_DEDUP_SQL, workspace_id, sha256, area_id)
        if row is None:
            return None
        return IngestDedupHit(
            blob_artifact_id=row["blob_artifact_id"],
            doc_artifact_id=row["doc_artifact_id"],
            block_count=int(row["block_count"]),
        )

    async def upsert_blob(
        self,
        conn: asyncpg.Connection,
        workspace_id: UUID,
        *,
        sha256: str,
        size_bytes: int,
        media_type: str,
        storage_key: str,
        source_url: str | None,
        fetched_at: datetime | None,
    ) -> None:
        await conn.execute(
            _UPSERT_BLOB_SQL,
            workspace_id,
            sha256,
            size_bytes,
            media_type,
            storage_key,
            source_url,
            fetched_at,
        )

    async def insert_blob_artifact(
        self,
        conn: asyncpg.Connection,
        workspace_id: UUID,
        area_id: UUID,
        *,
        title: str,
        occurred_at: datetime,
        occurred_precision: str,
        sensitivity: str,
        sha256: str,
        source_url: str | None,
        fetched_at: datetime | None,
        updated_by: UUID,
    ) -> UUID:
        artifact_id = await conn.fetchval(
            _INSERT_BLOB_ARTIFACT_SQL,
            workspace_id,
            area_id,
            title,
            occurred_at,
            occurred_precision,
            sensitivity,
            sha256,
            source_url,
            fetched_at,
            updated_by,
        )
        assert artifact_id is not None
        return UUID(str(artifact_id))

    async def insert_doc_artifact(
        self,
        conn: asyncpg.Connection,
        workspace_id: UUID,
        area_id: UUID,
        *,
        title: str,
        occurred_at: datetime,
        occurred_precision: str,
        sensitivity: str,
        blob_sha256: str,
        source_url: str | None,
        fetched_at: datetime | None,
        blocks: list[DocBlock],
        updated_by: UUID,
    ) -> UUID:
        artifact_id = await conn.fetchval(
            _INSERT_DOC_ARTIFACT_SQL,
            workspace_id,
            area_id,
            title,
            occurred_at,
            occurred_precision,
            sensitivity,
            blob_sha256,
            source_url,
            fetched_at,
            _blocks_payload(blocks),
            updated_by,
        )
        assert artifact_id is not None
        return UUID(str(artifact_id))
