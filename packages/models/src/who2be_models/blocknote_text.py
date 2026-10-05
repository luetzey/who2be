"""Klartext-Serialisierung von BlockNote-Dokumenten (Single Source, ADR-0056).

Reine Funktionen ohne Datenbank- und Netzwerkzugriff: ein BlockNote-Block,
eine Block-Liste oder ein stringifizierter BlockNote-Body wird zu lesbarem
Text. Die Funktionen lagen frueher in der API (`placeholders._core`,
`services/content_text`). Sie liegen hier, weil auch der MCP-Prozess sie
braucht und `who2be_api` nicht importieren darf (kein DB-Zugriff, ADR-0005).
Die API re-exportiert sie unter den alten Namen; es gibt also genau eine
Implementierung.

Zwei Inline-Renderer stehen bereit:

- `text_inline_only` (Default): nur `type='text'`-Inlines, alles andere
  verschwindet. So rendern die Placeholder-Resolver.
- `placeholder_token_inline`: Placeholder-Pills werden zum stabilen Token
  `{{kind:target_id}}`. So rendern die Versions-Diff-Serialisierung und die
  Text-Antworten des MCP, die den Inhalt ohne Aufloesung zeigen.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

# Signatur eines Inline-Renderers: ein Inline-Element-Dict -> Textbeitrag.
InlineTextFn = Callable[[dict[str, object]], str]


def text_inline_only(inline: dict[str, object]) -> str:
    """Default-Inline-Renderer: nur `type='text'`-Inlines, alles andere leer."""
    if inline.get("type") == "text":
        return str(inline.get("text", ""))
    return ""


def placeholder_token_inline(inline: dict[str, object]) -> str:
    """Inline-Renderer, der Placeholder-Pills als `{{kind:target_id}}` zeigt.

    `type='text'` liefert den Roh-Text; Placeholder-Pills werden nicht
    aufgeloest (kein DB-Zugriff), sondern als stabiles Token gerendert. Damit
    ergibt derselbe Inhalt immer denselben Text. Unbekannte Inline-Typen
    verschwinden wie im Default.
    """
    inline_type = inline.get("type")
    if inline_type == "text":
        return str(inline.get("text", ""))
    if inline_type == "placeholder":
        raw_props = inline.get("props")
        props: dict[str, object] = raw_props if isinstance(raw_props, dict) else {}
        kind = str(props.get("kind", ""))
        target_id = str(props.get("target_id", ""))
        return f"{{{{{kind}:{target_id}}}}}"
    return ""


def block_plain_text(block: dict[str, object], inline_text: InlineTextFn = text_inline_only) -> str:
    """Extrahiert Plain-Text aus einem einzelnen BlockNote-Block-Dict.

    Deckt paragraph/heading/bulletListItem/numberedListItem/checkListItem ab.
    Nested children werden rekursiv prozessiert. Inline-Content wird ueber
    `inline_text` gerendert (Default: nur type='text') und konkateniert.
    """
    parts: list[str] = []
    inline_content: list[dict[str, object]] = block.get("content", [])  # type: ignore[assignment]
    for inline in inline_content:
        parts.append(inline_text(inline))
    text = "".join(parts).strip()

    children: list[dict[str, object]] = block.get("children", [])  # type: ignore[assignment]
    child_texts: list[str] = []
    for child in children:
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
    "parse_blocknote_blocks",
    "placeholder_token_inline",
    "text_inline_only",
]
