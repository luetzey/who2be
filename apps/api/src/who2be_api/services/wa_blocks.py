"""Deterministischer Markdown↔Block-Konverter fuer doc-Artifacts (ADR-0047).

Die API nimmt Markdown an; der Server splittet deterministisch in eine
Block-Liste (`DocBlock`) und vergibt stabile 8-stellige `block_id`s — die
Anker-Sprache folgt ADR-0021 (``<artifact_id>#<block_id>``). Der Split ist
bewusst simpel und verlustfrei statt CommonMark-vollstaendig:

- **Heading**: Zeile ``#{1,6} ␣ Text`` wird ein eigener ``heading``-Block
  (`level` = Anzahl ``#``).
- **Code-Fence**: ````` ``` ````` bis zur schliessenden Fence ist EIN
  ``code``-Block — inklusive der Fences, damit ``render → split`` verlustfrei
  roundtrippt (unschliessende Fence laeuft bis zum Textende).
- **Absatz**: Leerzeilen trennen Bloecke; beginnt die erste Zeile mit einem
  Listen-Marker (``-``/``*``/``+``/``1.``), ist der Block ein ``list``-Block.

`render_markdown(with_anchors=True)` annotiert jeden Block mit `` [#<id>]`` am
Block-Ende (Headings: am Ende der Heading-Zeile; Code-Bloecke: eigene Zeile
NACH der schliessenden Fence, sonst laege der Anker im Code). So kann ein
Agent Suchtreffer und Patch-Anker direkt im Text verorten.

`apply_patch` ist die reine Patch-Op-Logik (replace/insert_after/delete) —
DB-los testbar; der Service mappt „Anker unbekannt" auf 422
`anchor_unresolvable`.
"""

from __future__ import annotations

import re
import secrets

from who2be_models import ArtifactPatchOp, DocBlock, DocBlockKind
from who2be_models.workarea import DOC_BLOCK_MD_MAX_LENGTH

# Alphabet der Block-IDs: 8 Zeichen a-z0-9 → 36^8 ≈ 2,8e12 Kombinationen;
# der Kollisions-Check gegen die bestehenden IDs macht die Vergabe exakt.
_BLOCK_ID_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"
BLOCK_ID_LENGTH = 8

_HEADING_RE = re.compile(r"^(#{1,6})\s+\S")
_LIST_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")


def new_block_id(existing: set[str]) -> str:
    """Vergibt eine neue, gegen `existing` kollisionsfreie Block-ID.

    `secrets` statt `random`: Block-IDs sind zwar keine Credentials, aber sie
    duerfen nicht erratbar-sequenziell sein (Anker werden extern referenziert).
    """
    while True:
        candidate = "".join(secrets.choice(_BLOCK_ID_ALPHABET) for _ in range(BLOCK_ID_LENGTH))
        if candidate not in existing:
            return candidate


def _split_oversize(md: str) -> list[str]:
    """Haelt die Modell-Obergrenze pro Block ein — harter Schnitt, kein Verlust."""
    if len(md) <= DOC_BLOCK_MD_MAX_LENGTH:
        return [md]
    return [md[i : i + DOC_BLOCK_MD_MAX_LENGTH] for i in range(0, len(md), DOC_BLOCK_MD_MAX_LENGTH)]


def _segments(md: str) -> list[tuple[DocBlockKind, int | None, str]]:
    """Zerlegt Markdown in `(kind, level, text)`-Segmente (ohne IDs)."""
    segments: list[tuple[DocBlockKind, int | None, str]] = []
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        if not paragraph:
            return
        text = "\n".join(paragraph).strip()
        paragraph.clear()
        if not text:
            return
        kind = DocBlockKind.list if _LIST_RE.match(text) else DocBlockKind.paragraph
        segments.append((kind, None, text))

    lines = md.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        fence = _FENCE_RE.match(line)
        if fence is not None:
            flush_paragraph()
            marker = fence.group(1)
            code_lines = [line]
            i += 1
            while i < len(lines):
                code_lines.append(lines[i])
                if lines[i].strip().startswith(marker):
                    i += 1
                    break
                i += 1
            segments.append((DocBlockKind.code, None, "\n".join(code_lines)))
            continue
        heading = _HEADING_RE.match(line)
        if heading is not None:
            flush_paragraph()
            segments.append((DocBlockKind.heading, len(heading.group(1)), line.strip()))
            i += 1
            continue
        if not line.strip():
            flush_paragraph()
            i += 1
            continue
        paragraph.append(line)
        i += 1
    flush_paragraph()
    return segments


def split_markdown(md: str, existing_ids: set[str] | None = None) -> list[DocBlock]:
    """Splittet Markdown deterministisch in `DocBlock`s mit frischen IDs.

    `existing_ids` sind die bereits vergebenen Block-IDs des Artifacts
    (append/patch) — neue IDs kollidieren weder untereinander noch mit ihnen.
    Leerer/whitespace-only Input ergibt eine leere Liste.
    """
    ids = set(existing_ids or ())
    blocks: list[DocBlock] = []
    for kind, level, text in _segments(md):
        for piece in _split_oversize(text):
            block_id = new_block_id(ids)
            ids.add(block_id)
            blocks.append(DocBlock(block_id=block_id, kind=kind, level=level, md=piece))
    return blocks


def render_markdown(blocks: list[DocBlock], with_anchors: bool) -> str:
    """Rendert die Block-Liste zurueck zu Markdown (Bloecke per Leerzeile).

    `with_anchors=True` haengt `` [#<block_id>]`` an: Headings am Ende der
    Heading-Zeile, Code-Bloecke auf eigener Zeile nach der schliessenden Fence
    (im Code selbst waere der Anker Teil des Inhalts), sonst am Block-Ende.
    """
    parts: list[str] = []
    for block in blocks:
        if not with_anchors:
            parts.append(block.md)
        elif block.kind == DocBlockKind.code:
            parts.append(f"{block.md}\n[#{block.block_id}]")
        else:
            parts.append(f"{block.md} [#{block.block_id}]")
    return "\n\n".join(parts)


def apply_patch(
    blocks: list[DocBlock],
    anchor: str,
    op: ArtifactPatchOp,
    replacement: list[DocBlock],
) -> list[DocBlock] | None:
    """Wendet eine Patch-Op auf die Block-Liste an (pure Funktion).

    `None` = Anker nicht aufloesbar (Service → 422 `anchor_unresolvable`).
    `replacement` sind die bereits gesplitteten neuen Bloecke (bei `delete`
    leer). Bei `replace` erbt der ERSTE neue Block die Anker-ID — bestehende
    Verweise auf den Anker bleiben damit ueber das Edit hinweg gueltig
    (Anker-Stabilitaet, Entscheidung 3.3).
    """
    index = next((i for i, b in enumerate(blocks) if b.block_id == anchor), None)
    if index is None:
        return None
    if op == "delete":
        return blocks[:index] + blocks[index + 1 :]
    if op == "insert_after":
        return blocks[: index + 1] + replacement + blocks[index + 1 :]
    # replace: Anker-ID auf den ersten Ersatz-Block uebertragen.
    if replacement:
        replacement = [replacement[0].model_copy(update={"block_id": anchor})] + replacement[1:]
    return blocks[:index] + replacement + blocks[index + 1 :]
