"""Datenzugriff fuer WorkArea-Artifacts (`wa_artifact`, Migration 0074).

Nebenlaeufigkeits-Kern der WorkArea (Entscheidung 3.3):

- `append_blocks` ist EIN atomares ``UPDATE … SET content = content || $blocks,
  rev = rev + 1`` — lockfrei, Appends kollidieren nie (die Row-Level-
  Serialisierung von Postgres reiht parallele Appends einfach hintereinander).
- `patch_blocks` schreibt optimistisch ``WHERE rev = $expected_rev``; trifft
  das 0 Zeilen, liest es die aktuelle rev nach und liefert ``(None, rev)`` —
  der Service macht daraus ein 409 `rev_conflict` mit der aktuellen rev im
  detail (bzw. 404, wenn das Artifact ganz verschwunden ist).

Die Schreibmethoden nehmen eine `Connection`: der Service haelt Content-Write
und Chunk-Sync (`wa_chunks.sync_artifact_chunks`) in EINER Transaktion
zusammen (Muster `status_history_repository`). Reads laufen ueber Pool ODER
Connection (`_Fetcher`). Jede Query filtert auf `workspace_id`; Reads tragen
zusaetzlich den Area-Scope-Filter (`restrict_area_ids`) IN der SQL — kein
Existenz-Leak durch Nachfiltern.
"""

from __future__ import annotations

import json
from typing import Any, Protocol, TypeAlias
from uuid import UUID

import asyncpg

from who2be_models import ArtifactRead, DocBlock
from who2be_models.workarea import INGEST_MAX_BLOCKS

_Fetcher: TypeAlias = asyncpg.Pool | asyncpg.Connection

_META_COLUMNS = (
    "id, workspace_id, area_id, type, title, rev, occurred_at, occurred_precision, "
    "sensitivity, source_system, source_url, fetched_at, blob_sha256, content_ref, "
    "created_at, updated_at, updated_by"
)
_FULL_COLUMNS = f"{_META_COLUMNS}, content"


def _to_read(row: asyncpg.Record, *, include_blocks: bool) -> ArtifactRead:
    """Baut das `ArtifactRead` aus einer Row; `content` → `blocks` (nur doc).

    `updated_by` ist in der DB eine nackte Akteur-UUID (agent- oder user-id);
    das Modell fuehrt sie als String.
    """
    data: dict[str, Any] = dict(row)
    raw = data.pop("content", None)
    updated_by = data.get("updated_by")
    data["updated_by"] = str(updated_by) if updated_by is not None else None
    blocks: list[DocBlock] | None = None
    if include_blocks:
        if isinstance(raw, str):
            raw = json.loads(raw)
        if isinstance(raw, list):
            blocks = [DocBlock.model_validate(item) for item in raw]
    return ArtifactRead.model_validate({**data, "blocks": blocks})


def _blocks_payload(blocks: list[DocBlock]) -> list[dict[str, Any]]:
    """Block-Liste als jsonb-Parameter.

    WICHTIG: die PYTHON-Liste uebergeben, nicht selbst serialisieren — der
    Pool-Codec (`init_connection`, encoder=json.dumps) encodiert jsonb-Params
    bereits; ein vor-serialisierter String wuerde doppelt encodiert und als
    JSON-STRING-Skalar statt als Array persistiert (Append haengt dann Strings
    statt Objekte an).
    """
    return [block.model_dump(mode="json", exclude_none=True) for block in blocks]


class WaArtifactRepository(Protocol):
    """Vertrag des Artifact-Datenzugriffs (Service-Sicht)."""

    async def insert_doc(
        self,
        conn: asyncpg.Connection,
        workspace_id: UUID,
        area_id: UUID,
        *,
        title: str,
        occurred_at: Any,
        occurred_precision: str,
        sensitivity: str,
        source_system: str | None,
        source_url: str | None,
        fetched_at: Any,
        blocks: list[DocBlock],
        updated_by: UUID,
    ) -> ArtifactRead: ...

    async def get(
        self,
        fetcher: _Fetcher,
        workspace_id: UUID,
        artifact_id: UUID,
        *,
        restrict_area_ids: list[UUID] | None,
        include_blocks: bool,
    ) -> ArtifactRead | None: ...

    async def list_for_area(
        self, fetcher: _Fetcher, workspace_id: UUID, area_id: UUID
    ) -> list[ArtifactRead]: ...

    async def append_blocks(
        self,
        conn: asyncpg.Connection,
        workspace_id: UUID,
        artifact_id: UUID,
        new_blocks: list[DocBlock],
        updated_by: UUID,
    ) -> ArtifactRead | None: ...

    async def patch_blocks(
        self,
        conn: asyncpg.Connection,
        workspace_id: UUID,
        artifact_id: UUID,
        expected_rev: int,
        new_content: list[DocBlock],
        updated_by: UUID,
    ) -> tuple[ArtifactRead | None, int | None]: ...

    async def delete(
        self, conn: asyncpg.Connection, workspace_id: UUID, artifact_id: UUID
    ) -> bool: ...


class PgWaArtifactRepository:
    """asyncpg-Implementierung von `WaArtifactRepository`.

    Bewusst ohne Pool im Konstruktor: die Schreibpfade laufen auf der
    Transaktions-Connection des Services (s. Modul-Kopf).
    """

    async def insert_doc(
        self,
        conn: asyncpg.Connection,
        workspace_id: UUID,
        area_id: UUID,
        *,
        title: str,
        occurred_at: Any,
        occurred_precision: str,
        sensitivity: str,
        source_system: str | None,
        source_url: str | None,
        fetched_at: Any,
        blocks: list[DocBlock],
        updated_by: UUID,
    ) -> ArtifactRead:
        row = await conn.fetchrow(
            "INSERT INTO wa_artifact "
            "(workspace_id, area_id, type, title, occurred_at, occurred_precision, "
            " sensitivity, source_system, source_url, fetched_at, content, updated_by) "
            "VALUES ($1, $2, 'doc', $3, $4, $5, $6, $7, $8, $9, $10::jsonb, $11) "
            f"RETURNING {_FULL_COLUMNS}",
            workspace_id,
            area_id,
            title,
            occurred_at,
            occurred_precision,
            sensitivity,
            source_system,
            source_url,
            fetched_at,
            _blocks_payload(blocks),
            updated_by,
        )
        assert row is not None
        return _to_read(row, include_blocks=True)

    async def get(
        self,
        fetcher: _Fetcher,
        workspace_id: UUID,
        artifact_id: UUID,
        *,
        restrict_area_ids: list[UUID] | None,
        include_blocks: bool,
    ) -> ArtifactRead | None:
        """Einzel-Read mit Area-Scope-Filter IN der SQL (`None` = unbeschraenkt)."""
        columns = _FULL_COLUMNS if include_blocks else _META_COLUMNS
        row = await fetcher.fetchrow(
            f"SELECT {columns} FROM wa_artifact "
            "WHERE workspace_id = $1 AND id = $2 "
            "AND ($3::uuid[] IS NULL OR area_id = ANY($3::uuid[]))",
            workspace_id,
            artifact_id,
            restrict_area_ids,
        )
        return _to_read(row, include_blocks=include_blocks) if row is not None else None

    async def list_for_area(
        self, fetcher: _Fetcher, workspace_id: UUID, area_id: UUID
    ) -> list[ArtifactRead]:
        """Artifacts einer Area (Metadaten ohne Blocks — Payload-Budget).

        Der Aufrufer hat den Lese-Zugriff auf die Area bereits erzwungen
        (`ensure_area_access`) — deshalb reicht hier der Area-Filter.
        """
        rows = await fetcher.fetch(
            f"SELECT {_META_COLUMNS} FROM wa_artifact "
            "WHERE workspace_id = $1 AND area_id = $2 "
            "ORDER BY occurred_at DESC, id",
            workspace_id,
            area_id,
        )
        return [_to_read(row, include_blocks=False) for row in rows]

    async def append_blocks(
        self,
        conn: asyncpg.Connection,
        workspace_id: UUID,
        artifact_id: UUID,
        new_blocks: list[DocBlock],
        updated_by: UUID,
    ) -> ArtifactRead | None:
        """Lockfreies Anhaengen: EIN atomares UPDATE, rev + 1 (s. Modul-Kopf).

        Das Praedikat deckelt die KUMULATIVE Blockzahl atomar auf
        `INGEST_MAX_BLOCKS` (Security-Review 2026-08-13 M7, geteilte
        H3b-Konstante): 0 Rows heisst „verschwunden ODER Cap erreicht" — die
        Unterscheidung (404 vs. 413) trifft der Service per Exists-Nachlese.
        """
        row = await conn.fetchrow(
            "UPDATE wa_artifact "
            "SET content = coalesce(content, '[]'::jsonb) || $3::jsonb, "
            "    rev = rev + 1, updated_at = now(), updated_by = $4 "
            "WHERE workspace_id = $1 AND id = $2 AND type = 'doc' "
            "  AND jsonb_array_length(coalesce(content, '[]'::jsonb)) + $5 <= $6 "
            f"RETURNING {_FULL_COLUMNS}",
            workspace_id,
            artifact_id,
            _blocks_payload(new_blocks),
            updated_by,
            len(new_blocks),
            INGEST_MAX_BLOCKS,
        )
        return _to_read(row, include_blocks=True) if row is not None else None

    async def patch_blocks(
        self,
        conn: asyncpg.Connection,
        workspace_id: UUID,
        artifact_id: UUID,
        expected_rev: int,
        new_content: list[DocBlock],
        updated_by: UUID,
    ) -> tuple[ArtifactRead | None, int | None]:
        """Optimistisches Voll-Update `WHERE rev = expected_rev`.

        Rueckgabe: ``(artifact, None)`` bei Erfolg; ``(None, aktuelle_rev)``
        bei veralteter Revision (Service → 409 `rev_conflict`);
        ``(None, None)``, wenn das Artifact nicht (mehr) existiert (→ 404).
        """
        row = await conn.fetchrow(
            "UPDATE wa_artifact "
            "SET content = $4::jsonb, rev = rev + 1, updated_at = now(), updated_by = $5 "
            "WHERE workspace_id = $1 AND id = $2 AND type = 'doc' AND rev = $3 "
            f"RETURNING {_FULL_COLUMNS}",
            workspace_id,
            artifact_id,
            expected_rev,
            _blocks_payload(new_content),
            updated_by,
        )
        if row is not None:
            return _to_read(row, include_blocks=True), None
        current_rev = await conn.fetchval(
            "SELECT rev FROM wa_artifact WHERE workspace_id = $1 AND id = $2 AND type = 'doc'",
            workspace_id,
            artifact_id,
        )
        return None, int(current_rev) if current_rev is not None else None

    async def delete(self, conn: asyncpg.Connection, workspace_id: UUID, artifact_id: UUID) -> bool:
        """Loescht das Artifact; `wa_chunk` raeumt der FK ON DELETE CASCADE ab
        (Migration 0076 — verifiziert, kein manueller Chunk-Delete noetig)."""
        result = await conn.execute(
            "DELETE FROM wa_artifact WHERE workspace_id = $1 AND id = $2",
            workspace_id,
            artifact_id,
        )
        return bool(str(result).endswith("1"))
