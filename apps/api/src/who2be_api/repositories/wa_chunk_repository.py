"""Persistenz der WorkArea-Passagen (`wa_chunk`, Migration 0076).

Chunks sind ABGELEITET und jederzeit aus `wa_artifact.content` regenerierbar
(Muster `content_chunk_repository`): der Sync loescht den Bestand eines
Artifacts und schreibt ihn neu — in DERSELBEN Transaktion wie der
Content-Write, damit Artifact und Passagen nie auseinanderlaufen. Deshalb
nehmen alle Funktionen eine `Connection` (keinen Pool).

Die Such-Query (Scope-CTE vor Ranking) folgt in WP6 — dieses Modul traegt in
WP4 nur den Schreibpfad, den WP5 (Ingest) und WP6 wiederverwenden.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import asyncpg

_DELETE_SQL = "DELETE FROM wa_chunk WHERE workspace_id = $1 AND artifact_id = $2"

_INSERT_SQL = (
    "INSERT INTO wa_chunk "
    "(workspace_id, artifact_id, area_id, block_id, heading_path, ord, text, locale) "
    "VALUES ($1, $2, $3, $4, $5, $6, $7, $8)"
)


@dataclass(frozen=True)
class WaChunkDraft:
    """Eine noch nicht persistierte WorkArea-Passage.

    `block_id` ist der Anker-Block der Passage (ADR-0021-Sprache) — anders als
    bei `content_chunk` immer gesetzt, weil JEDER doc-Block eine serverseitig
    vergebene ID traegt (kein ankerloser Praeambel-Fall).
    """

    ord: int
    block_id: str
    heading_path: str
    text: str


async def delete_for_artifact(
    conn: asyncpg.Connection, workspace_id: UUID, artifact_id: UUID
) -> None:
    """Loescht alle Passagen eines Artifacts (Teil des Rebuilds)."""
    await conn.execute(_DELETE_SQL, workspace_id, artifact_id)


async def insert_chunks(
    conn: asyncpg.Connection,
    workspace_id: UUID,
    artifact_id: UUID,
    area_id: UUID,
    locale: str,
    drafts: list[WaChunkDraft],
) -> None:
    """Schreibt die Passagen eines Artifacts (nach `delete_for_artifact`)."""
    if not drafts:
        return
    await conn.executemany(
        _INSERT_SQL,
        [
            (
                workspace_id,
                artifact_id,
                area_id,
                draft.block_id,
                draft.heading_path,
                draft.ord,
                draft.text,
                locale,
            )
            for draft in drafts
        ],
    )
