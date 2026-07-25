"""Schneidet Versions-Content in retrievebare Passagen (ADR-0046).

Entity-Ranking allein loest das Laufzeit-Retrieval nicht: ein Treffer
„Playbook X" spart keinen Kontext, wenn danach `fetch_playbook` ueber den
Volltext folgt. Dieser Modul zerlegt den Content einer Version in Passagen,
die einzeln gefunden und einzeln ausgeliefert werden koennen.

Schnitt entlang der Heading-Bloecke: jeder Heading-Block beginnt eine neue
Passage, `block_id` ist damit exakt der bestehende Block-Anker aus ADR-0021 —
ein Treffer ist unmittelbar als `"<uuid>#<block_id>"` referenzierbar. Es
entsteht KEINE zweite Ankersprache.

`heading_path` traegt die Ueberschriften-Kette der VORFAHREN (ohne die eigene
Ueberschrift — die steht bereits als erste Zeile im Passagentext). Sie geht in
den FTS-Index, aber nicht in die ausgelieferte Passage: Kontext ohne Duplikat.

Die Klartext-Extraktion nutzt `placeholders._core.block_plain_text` — dieselbe
Single-Source wie die Diff-Serialisierung (`content_text`), nicht die rohe
jsonb-Serialisierung. Placeholder-Pills fallen dabei bewusst weg: ihr
`{{kind:uuid}}`-Token traegt keinen suchbaren Text, nur Rauschen.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from who2be_api.services.content_text import parse_blocknote_blocks
from who2be_api.services.placeholders._core import block_plain_text

# Obergrenze pro Passage. Eine sehr lange Section wird an Block-Grenzen auf
# mehrere Passagen verteilt (gleicher `block_id`, fortlaufender `ord`) — es
# geht KEIN Text verloren, anders als bei stiller Truncation.
_MAX_CHUNK_CHARS = 4_000

_HEADING_TYPE = "heading"
_DEFAULT_HEADING_LEVEL = 1
_PATH_SEPARATOR = " > "


@dataclass(frozen=True)
class ChunkDraft:
    """Eine noch nicht persistierte Passage."""

    ord: int
    block_id: str | None
    heading_path: str
    text: str


def _is_heading(block: dict[str, Any]) -> bool:
    return block.get("type") == _HEADING_TYPE


def _heading_level(block: dict[str, Any]) -> int:
    props = block.get("props")
    if isinstance(props, dict):
        level = props.get("level")
        if isinstance(level, int):
            return level
    return _DEFAULT_HEADING_LEVEL


def _blocks_of(entity_type: str, content: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    """Liefert `(Praeambel, Bloecke)` fuer einen Versions-Content.

    Die Praeambel ist der blocklose Kopftext (Beschreibung und, beim
    ExternalTool, die beschreibenden Kopffelder). Die Bloecke liegen je nach
    Typ direkt als Liste vor oder als stringifiziertes BlockNote-JSON.
    """
    description = str(content.get("description", "") or "").strip()

    if entity_type == "resource":
        raw = content.get("blocks", [])
        return description, [b for b in raw if isinstance(b, dict)] if isinstance(raw, list) else []

    if entity_type == "persona":
        profile = content.get("content")
        if isinstance(profile, dict):
            raw = profile.get("blocks", [])
            blocks = [b for b in raw if isinstance(b, dict)] if isinstance(raw, list) else []
        else:
            blocks = []
        # `traits` ist als Persona-Strukturfeld deprecated, traegt aber bei
        # Bestandsdaten weiter Inhalt — als Teil der Praeambel indexieren.
        traits = content.get("traits")
        if isinstance(traits, list):
            trait_text = ", ".join(str(t) for t in traits if str(t).strip())
            if trait_text:
                description = "\n\n".join(p for p in (description, trait_text) if p)
        return description, blocks

    if entity_type in ("playbook", "system_prompt_template"):
        parsed, raw_body = parse_blocknote_blocks(str(content.get("body", "") or ""))
        if parsed is None:
            # Alt-Bestand/Plain-Text: kein Block-Dokument, alles in die Praeambel.
            return "\n\n".join(p for p in (description, raw_body) if p), []
        return description, parsed

    if entity_type == "external_tool":
        head = [
            str(content.get("display_name", "") or "").strip(),
            description,
            str(content.get("fallback_note") or "").strip(),
        ]
        parsed, raw_body = parse_blocknote_blocks(str(content.get("usage_notes", "") or ""))
        if parsed is None:
            head.append(raw_body)
            return "\n\n".join(p for p in head if p), []
        return "\n\n".join(p for p in head if p), parsed

    return description, []


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


def chunk_content(entity_type: str, content: dict[str, Any]) -> list[ChunkDraft]:
    """Zerlegt einen Versions-Content in Passagen.

    Reihenfolge: erst die blocklose Praeambel (`block_id=None`), dann eine
    Passage je Heading-Block. Text vor dem ersten Heading bildet ebenfalls eine
    ankerlose Passage. Leere Passagen entfallen.
    """
    preamble, blocks = _blocks_of(entity_type, content)

    # (block_id, heading_path, [Texte]) — in Dokumentreihenfolge.
    sections: list[tuple[str | None, str, list[str]]] = []
    if preamble:
        sections.append((None, "", [preamble]))

    # Stack der offenen Ueberschriften: (level, text). Bildet `heading_path`.
    open_headings: list[tuple[int, str]] = []
    current: tuple[str | None, str, list[str]] | None = None

    for block in blocks:
        text = block_plain_text(block).strip()
        if _is_heading(block):
            if current is not None:
                sections.append(current)
            level = _heading_level(block)
            while open_headings and open_headings[-1][0] >= level:
                open_headings.pop()
            path = _PATH_SEPARATOR.join(h for _, h in open_headings)
            open_headings.append((level, text))
            block_id = block.get("id")
            current = (
                block_id if isinstance(block_id, str) else None,
                path,
                [text] if text else [],
            )
            continue
        if not text:
            continue
        if current is None:
            # Text vor dem ersten Heading — ankerlose Passage.
            current = (None, "", [])
        current[2].append(text)
    if current is not None:
        sections.append(current)

    drafts: list[ChunkDraft] = []
    for block_id, path, parts in sections:
        joined = "\n\n".join(p for p in parts if p).strip()
        if not joined:
            continue
        for piece in _split_long(joined):
            drafts.append(
                ChunkDraft(
                    ord=len(drafts),
                    block_id=block_id,
                    heading_path=path,
                    text=piece,
                )
            )
    return drafts


def chunk_version_content(entity_type: str, content: Any) -> list[ChunkDraft]:
    """Wie `chunk_content`, akzeptiert aber auch einen jsonb-String.

    asyncpg liefert `content` dank registriertem Codec als `dict`; Alt-Pfade
    und Tests reichen gelegentlich den rohen JSON-String durch.
    """
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except json.JSONDecodeError:
            return []
    if not isinstance(content, dict):
        return []
    return chunk_content(entity_type, content)


__all__ = ["ChunkDraft", "chunk_content", "chunk_version_content"]
