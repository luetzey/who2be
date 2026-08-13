"""Schneidet doc-Artifacts in retrievebare WorkArea-Passagen (ADR-0047).

Vorbild ist `services/content_chunks.py` (ADR-0046): jeder Heading-Block
beginnt eine neue Passage, `heading_path` traegt die Ueberschriften-Kette der
VORFAHREN (ohne die eigene Ueberschrift — die steht als erste Zeile im
Passagentext) in den Index, nicht in die ausgelieferte Passage. Anker der
Passage ist die `block_id` des Heading-Blocks; Text VOR dem ersten Heading
ankert auf seinem ERSTEN Block (jeder doc-Block traegt eine ID — anders als
BlockNote gibt es keinen ankerlosen Praeambel-Fall).

Eine zu lange Passage wird an Block-/Absatzgrenzen auf mehrere Zeilen mit
gleichem `block_id` und fortlaufendem `ord` verteilt (4000-Zeichen-Cap wie
`content_chunks._MAX_CHUNK_CHARS`) — es geht KEIN Text verloren.

`sync_artifact_chunks` laeuft in der uebergebenen Transaktion (delete+insert)
und wird von WP5 (Ingest) und WP6 (Suche) wiederverwendet — die API dieses
Moduls bewusst schmal halten.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg

from who2be_api.repositories.wa_chunk_repository import (
    WaChunkDraft,
    delete_for_artifact,
    insert_chunks,
)
from who2be_models import DocBlock, DocBlockKind

# Obergrenze pro Passage — identisch zu `content_chunks._MAX_CHUNK_CHARS`.
_MAX_CHUNK_CHARS = 4_000
_PATH_SEPARATOR = " > "


def _heading_text(block: DocBlock) -> str:
    """Klartext einer Heading-Zeile (ohne ``#``-Marker) fuer den Pfad."""
    return block.md.lstrip("#").strip()


def _split_long(text: str) -> list[str]:
    """Teilt einen zu langen Passagentext an Absatzgrenzen, ohne Verlust."""
    if len(text) <= _MAX_CHUNK_CHARS:
        return [text]
    parts: list[str] = []
    current = ""
    for paragraph in text.split("\n\n"):
        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if current and len(candidate) > _MAX_CHUNK_CHARS:
            parts.append(current)
            current = paragraph
        else:
            current = candidate
        # Ein einzelner Absatz kann fuer sich schon zu lang sein — hart schneiden.
        while len(current) > _MAX_CHUNK_CHARS:
            parts.append(current[:_MAX_CHUNK_CHARS])
            current = current[_MAX_CHUNK_CHARS:]
    if current:
        parts.append(current)
    return parts


def build_chunks(blocks: list[DocBlock]) -> list[WaChunkDraft]:
    """Zerlegt die Block-Liste eines doc-Artifacts in Passagen (pure Funktion).

    Reihenfolge = Dokumentreihenfolge; `ord` fortlaufend ueber alle Passagen.
    Leere Sektionen (Heading ohne Text waere nie leer — der Heading-Text
    selbst zaehlt) bzw. leere Bloecke entfallen.
    """
    # (anchor_block_id, heading_path, [Texte]) — in Dokumentreihenfolge.
    sections: list[tuple[str, str, list[str]]] = []
    # Stack der offenen Ueberschriften: (level, text). Bildet `heading_path`.
    open_headings: list[tuple[int, str]] = []
    current: tuple[str, str, list[str]] | None = None

    for block in blocks:
        if block.kind == DocBlockKind.heading:
            if current is not None:
                sections.append(current)
            level = block.level or 1
            while open_headings and open_headings[-1][0] >= level:
                open_headings.pop()
            path = _PATH_SEPARATOR.join(h for _, h in open_headings)
            text = _heading_text(block)
            open_headings.append((level, text))
            current = (block.block_id, path, [text] if text else [])
            continue
        text = block.md.strip()
        if not text:
            continue
        if current is None:
            # Text vor dem ersten Heading — ankert auf dem ersten Block.
            current = (block.block_id, "", [])
        current[2].append(text)
    if current is not None:
        sections.append(current)

    drafts: list[WaChunkDraft] = []
    for block_id, path, parts in sections:
        joined = "\n\n".join(p for p in parts if p).strip()
        if not joined:
            continue
        for piece in _split_long(joined):
            drafts.append(
                WaChunkDraft(
                    ord=len(drafts),
                    block_id=block_id,
                    heading_path=path,
                    text=piece,
                )
            )
    return drafts


async def sync_artifact_chunks(
    conn: asyncpg.Connection,
    *,
    workspace_id: UUID,
    artifact_id: UUID,
    area_id: UUID,
    blocks: list[DocBlock],
    locale: str,
) -> int:
    """Baut die Passagen eines Artifacts neu — in der UEBERGEBENEN Transaktion.

    Delete+Insert statt Diff: Chunks sind abgeleitete Daten, der komplette
    Rebuild ist einfach korrekt (Muster `content_chunk`). Der Aufrufer haelt
    Content-Write und Chunk-Sync in EINER Transaktion zusammen. Rueckgabe:
    Anzahl geschriebener Passagen.
    """
    drafts = build_chunks(blocks)
    await delete_for_artifact(conn, workspace_id, artifact_id)
    await insert_chunks(conn, workspace_id, artifact_id, area_id, locale, drafts)
    return len(drafts)
