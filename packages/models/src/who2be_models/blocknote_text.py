"""Klartext-Serialisierung von BlockNote-Dokumenten (Single Source, ADR-0056).

Reine Funktionen ohne Datenbank- und Netzwerkzugriff: ein BlockNote-Block,
eine Block-Liste oder ein stringifizierter BlockNote-Body wird zu lesbarem
Text. Die Funktionen lagen frueher in der API (`placeholders._core`,
`services/content_text`). Sie liegen hier, weil auch der MCP-Prozess sie
braucht und `who2be_api` nicht importieren darf (kein DB-Zugriff, ADR-0005).
Die API re-exportiert sie unter den alten Namen; es gibt also genau eine
Implementierung.

Zwei Inline-Renderer stehen bereit:

- `text_inline_only` (Default): `type='text'`-Inlines und Links, alles andere
  verschwindet. So rendern die Placeholder-Resolver.
- `placeholder_token_inline`: Placeholder-Pills werden zum stabilen Token
  `{{kind:target_id}}`. So rendern die Versions-Diff-Serialisierung und die
  Text-Antworten des MCP, die den Inhalt ohne Aufloesung zeigen.

Zwei Formen gelten in allen Klartext-Pfaden (Renderer, Passagen, MCP) gleich
und sind deshalb nur hier definiert:

- Ein Inline-Link wird zu `Text (URL)` (`format_link`).
- Ein Tabellenblock (`content` ist ein `tableContent`-Objekt statt einer
  Inline-Liste) wird zu einer GFM-Tabelle: erste Zeile als Kopfzeile, darunter
  der Trenner, Zellen als einzeiliger Klartext mit maskiertem `|`
  (`table_cells`, `format_table`). Der ADR-0058-Konverter uebernimmt diese Form.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

# Signatur eines Inline-Renderers: ein Inline-Element-Dict -> Textbeitrag.
InlineTextFn = Callable[[dict[str, object]], str]

_TABLE_CONTENT_TYPE = "tableContent"


def format_link(text: str, href: str) -> str:
    """Link als `Text (URL)`; fehlt eins von beiden oder sind sie gleich, nur eins."""
    text = text.strip()
    href = href.strip()
    if not href or text == href:
        return text
    if not text:
        return href
    return f"{text} ({href})"


def _link_text(inline: dict[str, object]) -> str:
    """Klartext eines Link-Inlines (`content` ist eine StyledText-Liste)."""
    raw = inline.get("content")
    if isinstance(raw, str):
        inner = raw
    elif isinstance(raw, list):
        inner = "".join(
            str(item.get("text", ""))
            for item in raw
            if isinstance(item, dict) and item.get("type") == "text"
        )
    else:
        inner = ""
    return format_link(inner, str(inline.get("href", "") or ""))


def text_inline_only(inline: dict[str, object]) -> str:
    """Default-Inline-Renderer: Text und Links (`Text (URL)`), alles andere leer."""
    inline_type = inline.get("type")
    if inline_type == "text":
        return str(inline.get("text", ""))
    if inline_type == "link":
        return _link_text(inline)
    return ""


def placeholder_token_inline(inline: dict[str, object]) -> str:
    """Inline-Renderer, der Placeholder-Pills als `{{kind:target_id}}` zeigt.

    `type='text'` liefert den Roh-Text, Links werden zu `Text (URL)`;
    Placeholder-Pills werden nicht aufgeloest (kein DB-Zugriff), sondern als
    stabiles Token gerendert. Damit ergibt derselbe Inhalt immer denselben
    Text. Unbekannte Inline-Typen verschwinden wie im Default.
    """
    inline_type = inline.get("type")
    if inline_type == "text":
        return str(inline.get("text", ""))
    if inline_type == "link":
        return _link_text(inline)
    if inline_type == "placeholder":
        raw_props = inline.get("props")
        props: dict[str, object] = raw_props if isinstance(raw_props, dict) else {}
        kind = str(props.get("kind", ""))
        target_id = str(props.get("target_id", ""))
        return f"{{{{{kind}:{target_id}}}}}"
    return ""


def table_cells(content: object) -> list[list[list[dict[str, object]]]] | None:
    """Zerlegt ein `tableContent`-Objekt in Zeilen → Zellen → Inline-Listen.

    BlockNote kennt zwei Zellformen: die Inline-Liste direkt oder ein
    `{"type": "tableCell", "content": [...]}`-Objekt. Beide werden zur
    Inline-Liste. Kein `tableContent` → `None`; kaputte Teile werden leer.
    """
    if not isinstance(content, dict) or content.get("type") != _TABLE_CONTENT_TYPE:
        return None
    rows = content.get("rows")
    result: list[list[list[dict[str, object]]]] = []
    for row in rows if isinstance(rows, list) else []:
        cells = row.get("cells") if isinstance(row, dict) else None
        row_cells: list[list[dict[str, object]]] = []
        for cell in cells if isinstance(cells, list) else []:
            inlines = cell.get("content") if isinstance(cell, dict) else cell
            row_cells.append(
                [i for i in inlines if isinstance(i, dict)] if isinstance(inlines, list) else []
            )
        result.append(row_cells)
    return result


def _table_cell_text(text: str) -> str:
    """Zellinhalt einzeilig und mit maskiertem `|`, damit die Tabelle haelt."""
    return " ".join(text.replace("|", "\\|").split())


def format_table(rows: list[list[str]]) -> str:
    """Rendert Zelltexte als GFM-Tabelle (Kopfzeile + Trenner); leer → ``""``.

    Die erste Zeile ist immer die Kopfzeile (GFM verlangt eine); kuerzere
    Zeilen werden mit leeren Zellen aufgefuellt.
    """
    width = max((len(row) for row in rows), default=0)
    if width == 0:
        return ""
    lines: list[str] = []
    for index, row in enumerate(rows):
        cells = [_table_cell_text(cell) for cell in row] + [""] * (width - len(row))
        lines.append("| " + " | ".join(cells) + " |")
        if index == 0:
            lines.append("| " + " | ".join(["---"] * width) + " |")
    return "\n".join(lines)


def _block_inline_text(block: dict[str, object], inline_text: InlineTextFn) -> str:
    """Eigener Text eines Blocks: Inline-Liste oder Tabelle, sonst leer."""
    content = block.get("content")
    if isinstance(content, list):
        return "".join(inline_text(i) for i in content if isinstance(i, dict))
    rows = table_cells(content)
    if rows is None:
        return ""
    return format_table([["".join(inline_text(i) for i in cell) for cell in row] for row in rows])


def block_plain_text(block: dict[str, object], inline_text: InlineTextFn = text_inline_only) -> str:
    """Extrahiert Plain-Text aus einem einzelnen BlockNote-Block-Dict.

    Deckt paragraph/heading/bulletListItem/numberedListItem/checkListItem und
    Tabellen (GFM) ab. Nested children werden rekursiv prozessiert.
    Inline-Content wird ueber `inline_text` gerendert (Default: Text und
    Links) und konkateniert. Unbekannte `content`-Formen ergeben keinen Text
    statt eines Fehlers.
    """
    text = _block_inline_text(block, inline_text).strip()

    children = block.get("children")
    child_texts: list[str] = []
    for child in children if isinstance(children, list) else []:
        if not isinstance(child, dict):
            continue
        child_text = block_plain_text(child, inline_text)
        if child_text:
            child_texts.append(child_text)

    all_parts: list[str] = []
    if text:
        all_parts.append(text)
    all_parts.extend(child_texts)
    return "\n".join(all_parts)


def blocks_plain_text(raw: object, inline_text: InlineTextFn = text_inline_only) -> str:
    """Rendert eine BlockNote-Block-Liste als Plain-Text.

    Pro Block wird `block_plain_text` angewandt, leere Blocks werden
    uebersprungen, Ergebnisse mit Doppel-Newline verbunden. Nicht-Listen
    (z. B. None oder ein Alt-String, der die Koerzion nicht durchlief) liefern
    einen leeren String — so erzeugt der haeufigste Leerfall keine Zeilen.
    """
    if not isinstance(raw, list):
        return ""
    block_parts: list[str] = []
    for block in raw:
        if not isinstance(block, dict):
            continue
        text = block_plain_text(block, inline_text)
        if text:
            block_parts.append(text)
    return "\n\n".join(block_parts).strip()


def parse_blocknote_blocks(body: str) -> tuple[list[dict[str, Any]] | None, str]:
    """Zerlegt einen stringifizierten BlockNote-Body in seine Block-Liste.

    Akzeptiert die beiden BlockNote-JSON-Shapes (Top-Level-Array bzw.
    `{"content": [...]}`-Wrapper).

    Liefert `(blocks, raw)`: `blocks` ist `None`, wenn der Body kein
    verwertbares BlockNote-Dokument ist (leer, kaputtes JSON aus Alt-Bestand,
    Plain-Text oder Skalar-JSON) — dann traegt `raw` den getrimmten Rohwert,
    den die Aufrufer als Klartext behandeln.
    """
    stripped = body.strip()
    if not stripped:
        return None, ""
    try:
        parsed: Any = json.loads(stripped)
    except json.JSONDecodeError:
        return None, stripped
    if isinstance(parsed, list):
        return [b for b in parsed if isinstance(b, dict)], stripped
    if isinstance(parsed, dict):
        nested = parsed.get("content", [])
        blocks = nested if isinstance(nested, list) else []
        return [b for b in blocks if isinstance(b, dict)], stripped
    # Skalar-JSON (Zahl/String) — als Rohtext behandeln.
    return None, stripped


def blocknote_body_text(body: str, inline_text: InlineTextFn = placeholder_token_inline) -> str:
    """Serialisiert einen stringifizierten BlockNote-Body zu Klartext.

    Default-Inline-Renderer ist `placeholder_token_inline`: Pills erscheinen
    als `{{kind:target_id}}`. Kein gueltiges BlockNote-Dokument
    (Alt-Bestand/Plain-Text) → Rohwert getrimmt zurueck.
    """
    blocks, raw = parse_blocknote_blocks(body)
    if blocks is None:
        return raw
    return blocks_plain_text(blocks, inline_text)


__all__ = [
    "InlineTextFn",
    "block_plain_text",
    "blocknote_body_text",
    "blocks_plain_text",
    "format_link",
    "format_table",
    "parse_blocknote_blocks",
    "placeholder_token_inline",
    "table_cells",
    "text_inline_only",
]
