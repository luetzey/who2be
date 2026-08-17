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

Die Passagen-GRENZEN (`split_sections`) sind zugleich die Grenze des
Lesepfads: `wa_artifacts.read` loest einen Suchtreffer-Anker ueber
`passage_for_anchor` in dieselbe Passage auf, die der Index gefunden hat.
Vorher lieferte der Read nur den Heading-Block — der Agent bekam auf einen
Treffer hin die Ueberschrift ohne Inhalt (Befund 2026-08-16).
"""

from __future__ import annotations

from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class Section:
    """Eine Passage als BLOECKE — die gemeinsame Quelle fuer Index und Read.

    `anchor` ist die `block_id`, unter der die Passage im Index steht und die
    ein Suchtreffer ausliefert; `heading_path` die Ueberschriften-Kette der
    Vorfahren. `blocks` sind die Original-Bloecke der Passage — daraus baut
    `build_chunks` den Indextext und `passage_for_anchor` das Markdown des
    Lesepfads.
    """

    anchor: str
    heading_path: str
    blocks: list[DocBlock]


def split_sections(blocks: list[DocBlock]) -> list[Section]:
    """Schneidet die Block-Liste in Passagen (pure Funktion, Dokumentreihenfolge).

    Regel: JEDER Heading-Block beginnt eine neue Passage und gehoert selbst
    dazu; sie reicht bis zum naechsten Heading (gleich welcher Ebene). Text
    VOR dem ersten Heading bildet eine eigene Passage und ankert auf seinem
    ersten Block.

    Bewusst EINE Funktion fuer Index UND Lesepfad: die Passage, die der Index
    findet, muss dieselbe sein, die `read_artifact(anchor)` ausliefert. Zwei
    Implementierungen derselben Grenze driften auseinander — und die
    Abweichung faellt niemandem auf, weil beide fuer sich plausibel aussehen.
    """
    sections: list[Section] = []
    # Stack der offenen Ueberschriften: (level, text). Bildet `heading_path`.
    open_headings: list[tuple[int, str]] = []
    current: Section | None = None

    for block in blocks:
        if block.kind == DocBlockKind.heading:
            if current is not None:
                sections.append(current)
            level = block.level or 1
            while open_headings and open_headings[-1][0] >= level:
                open_headings.pop()
            path = _PATH_SEPARATOR.join(h for _, h in open_headings)
            open_headings.append((level, _heading_text(block)))
            current = Section(anchor=block.block_id, heading_path=path, blocks=[block])
            continue
        if current is None:
            # Text vor dem ersten Heading — ankert auf dem ersten Block.
            current = Section(anchor=block.block_id, heading_path="", blocks=[])
        current.blocks.append(block)
    if current is not None:
        sections.append(current)
    return sections


def passage_for_anchor(blocks: list[DocBlock], anchor: str) -> list[DocBlock] | None:
    """Die Bloecke der Passage, die `anchor` EROEFFNET; `None` = keine Passage.

    `None` heisst „der Anker zeigt mitten in eine Passage" — dann bleibt es
    beim einzelnen Block (der Lesepfad entscheidet das, s.
    `wa_artifacts.read`). Nur Passagen-Anker liefern eine Passage, und genau
    die vergibt der Suchindex.
    """
    for section in split_sections(blocks):
        if section.anchor == anchor:
            return section.blocks
    return None


def _section_text(section: Section) -> str:
    """Indextext einer Passage: Heading ohne ``#``, leere Bloecke entfallen."""
    parts: list[str] = []
    for block in section.blocks:
        text = _heading_text(block) if block.kind == DocBlockKind.heading else block.md.strip()
        if text:
            parts.append(text)
    return "\n\n".join(parts).strip()


def build_chunks(blocks: list[DocBlock]) -> list[WaChunkDraft]:
    """Zerlegt die Block-Liste eines doc-Artifacts in Passagen (pure Funktion).

    Reihenfolge = Dokumentreihenfolge; `ord` fortlaufend ueber alle Passagen.
    Leere Sektionen (Heading ohne Text waere nie leer — der Heading-Text
    selbst zaehlt) bzw. leere Bloecke entfallen.
    """
    drafts: list[WaChunkDraft] = []
    for section in split_sections(blocks):
        joined = _section_text(section)
        if not joined:
            continue
        for piece in _split_long(joined):
            drafts.append(
                WaChunkDraft(
                    ord=len(drafts),
                    block_id=section.anchor,
                    heading_path=section.heading_path,
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
