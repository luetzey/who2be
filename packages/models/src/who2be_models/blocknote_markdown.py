"""BlockNote <-> Markdown, der Schreibstandard fuer Agenten (ADR-0058, Paket P1).

Reine Funktionen ohne Datenbank- und Netzwerkzugriff, damit API und MCP
dieselbe Quelle nutzen (wie `who2be_models.blocknote_text`, ADR-0056).
Dieses Modul aendert kein Verhalten: es wird erst mit P2 (API) und P3 (MCP)
aufgerufen.

Oeffentliche Funktionen:

- `to_markdown(blocks)` liefert die **Normalform** (ADR-0058 §5.2): Listenmarker
  `-`, Nummern `1.`, Einrueckung zwei Leerzeichen, genau eine Leerzeile
  zwischen Bloecken, Fett `**`, kursiv `*`, Fences mit drei Backticks,
  Ueberschriften mit Anker ` [#<id>]` am Zeilenende (§4.2).
- `from_markdown(md, base)` baut BlockNote-Bloecke zurueck. Ueberschriften
  behalten ihre ID ueber den Anker, die uebrigen Bloecke ordnet `base` je
  Abschnitt zu (§4.3): inhaltsgleich -> alter Block bitgleich, sonst gleicher
  Typ an gleicher Position -> alte ID, sonst neue ID.
- `normalize(md)` bringt Markdown ohne Basis in die Normalform (§5.2 G2).
- `block_representability(block)` ist die Darstellbarkeitspruefung (§3.3).

Garantien (§5.2): G1 `from_markdown(to_markdown(B), base=B) == B` bitgleich,
G2 `to_markdown(from_markdown(M)) == normalize(M)` bis auf die Anker, die
neue Ueberschriften dabei bekommen, und `normalize` ist idempotent. G3 kein
stiller Verlust: was nicht abbildbar ist, erscheint lesend als geschuetzter
Marker (samt Kindern) und endet schreibend in einem `MarkdownConversionError`
(P2 macht daraus 422).

Was Markdown nicht zeigt, aber kein Inhalt ist, normalisiert die Normalform:
Stil auf Leerraum an einer Stilgrenze (`**fett **` -> `**fett** `), die
Aufteilung gleich formatierter Text-Laeufe und fehlende Default-Props. Ein
unveraenderter Block bleibt trotzdem bitgleich, weil die Zuordnung ihn aus der
Basis uebernimmt (§4.3 Schritt 1).

Dialekt-Grenzen, die bewusst enger sind als CommonMark: Hervorhebung nur mit
`*`/`**`/`~~` (ein `_` ist immer Text, sonst zerfiele jeder `snake_case`-Name),
keine HTML-Durchreichung, keine Zitate, keine Trennlinien, keine Bilder,
keine Referenz-Links, keine Entities, Ueberschriften nur Ebene 1 bis 3.
"""

from __future__ import annotations

import copy
import re
import secrets
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any, Literal

from who2be_models.blocknote_text import block_plain_text, placeholder_token_inline

Block = dict[str, Any]

# --- Darstellbarer Umfang (ADR-0058 §3.2/§3.3) ---------------------------

#: Version von `@blocknote/core`, gegen die die Typlisten gezogen sind
#: (`apps/web/package-lock.json`). Ein BlockNote-Update laesst den
#: Versions-Test reissen, bis jemand die Listen neu geprueft hat.
BLOCKNOTE_VERSION = "0.56.0"

#: Blocktypen mit Markdown-Gegenstueck.
REPRESENTABLE_BLOCK_TYPES: frozenset[str] = frozenset(
    {
        "paragraph",
        "heading",
        "bulletListItem",
        "numberedListItem",
        "checkListItem",
        "codeBlock",
        "table",
    }
)

#: Blocktypen aus `defaultBlockSpecs` von @blocknote/core 0.56.0 ohne
#: Markdown-Gegenstueck. Sie erscheinen als Marker `<!-- w2b:block ... -->`.
NON_REPRESENTABLE_BLOCK_TYPES: frozenset[str] = frozenset(
    {"audio", "divider", "file", "image", "quote", "toggleListItem", "video"}
)

MAX_HEADING_LEVEL = 3

#: Inline-Stile mit Markdown-Gegenstueck (Reihenfolge wie BlockNote
#: `defaultStyleSpecs`). Unterstreichung und Farben haben keins.
SUPPORTED_STYLES: tuple[str, ...] = ("bold", "italic", "strike", "code")

ErrorReason = Literal[
    "markdown_unsupported",
    "block_not_representable",
    "anchor_unknown",
    "anchor_duplicate",
]
Representability = Literal["ok", "locked", "block"]

_DEFAULT_PROPS: dict[str, str] = {
    "textColor": "default",
    "backgroundColor": "default",
    "textAlignment": "left",
}
_CELL_DEFAULT_PROPS: dict[str, Any] = {
    "backgroundColor": "default",
    "textColor": "default",
    "textAlignment": "left",
    "colspan": 1,
    "rowspan": 1,
}
_TEXT_BLOCK_TYPES = frozenset(
    {"paragraph", "heading", "bulletListItem", "numberedListItem", "checkListItem"}
)
_BLOCK_KEYS = frozenset({"id", "type", "props", "content", "children"})

_ID_RE = re.compile(r"[A-Za-z0-9_.:-]+")
_TYPE_RE = re.compile(r"[A-Za-z0-9_-]+")
_KIND_RE = re.compile(r"[a-z][a-z0-9-]*")
_LANGUAGE_RE = re.compile(r"[^\s`~]+")
_ENTITY_RE = re.compile(r"&(?:#[0-9]{1,7}|#[xX][0-9a-fA-F]{1,6}|[A-Za-z][A-Za-z0-9]{1,31});")
_HTML_RE = re.compile(
    r"<(?:[A-Za-z][A-Za-z0-9-]*(?:\s[^<>]*)?/?>|/[A-Za-z][A-Za-z0-9-]*\s*>|!--|![A-Za-z]|\?"
    r"|[A-Za-z][A-Za-z0-9+.-]{1,31}:[^\s<>]*>|[^\s<>@]+@[^\s<>]+>)"
)
_MARKER_RE = re.compile(
    r"<!-- w2b:(block|locked) (" + _ID_RE.pattern + r")(?: (" + _TYPE_RE.pattern + r"))? -->"
)
_HEADING_START_RE = re.compile(r"(#{1,6})(?=[ \t]|$)")
_CLOSING_HASHES_RE = re.compile(r"(?:^|[ \t]+)#+[ \t]*$")
_TRAILING_HASH_TEXT_RE = re.compile(r"(?:^|(?<=[ \t]))#+$")
_ANCHOR_RE = re.compile(r"(?:^|[ \t])\[#(" + _ID_RE.pattern + r")\][ \t]*$")
_TRAILING_ANCHOR_RE = re.compile(r"[ \t]\[#" + _ID_RE.pattern + r"\][ \t]*$")
_CHECK_RE = re.compile(r"[-*+][ \t]+\[([ xX])\](?:[ \t]+(.*))?$")
_BULLET_RE = re.compile(r"[-*+](?:[ \t]+(.*))?$")
_NUMBERED_RE = re.compile(r"(\d{1,9})[.)](?:[ \t]+(.*))?$")
_FENCE_RE = re.compile(r"(`{3,}|~{3,})(.*)$")
_THEMATIC_RE = re.compile(r"(?:(?:\*[ \t]*){3,}|(?:-[ \t]*){3,}|(?:_[ \t]*){3,})$")
_SETEXT_RE = re.compile(r"(?:=+|-+)[ \t]*$")
_DELIMITER_CELL_RE = re.compile(r"[ \t]*:?-+:?[ \t]*")
_REFERENCE_DEF_RE = re.compile(r"\[[^\]]+\]:[ \t]")
_LINE_START_ESCAPE_RE = re.compile(r"[#\-+>|=_]")
_LINE_START_NUMBER_RE = re.compile(r"(\d+)([.)])")

_PREAMBLE = "\x00preamble"


class MarkdownConversionError(ValueError):
    """Markdown laesst sich nicht verlustfrei in BlockNote wandeln (ADR-0058 §3.3, §4.2).

    `reason` ist der stabile Fehlercode, den P2 als 422 ausliefert. `line` ist
    1-basiert und zeigt in das eingegebene Markdown, `block_id` nennt den
    betroffenen Block, `construct` das nicht unterstuetzte Konstrukt.
    """

    def __init__(
        self,
        reason: ErrorReason,
        message: str,
        *,
        line: int | None = None,
        block_id: str | None = None,
        construct: str | None = None,
    ) -> None:
        super().__init__(message if line is None else f"Zeile {line}: {message}")
        self.reason: ErrorReason = reason
        self.line = line
        self.block_id = block_id
        self.construct = construct


def _unsupported(construct: str, line: int | None, hint: str = "") -> MarkdownConversionError:
    message = f"Markdown-Konstrukt nicht unterstuetzt: {construct}"
    return MarkdownConversionError(
        "markdown_unsupported",
        f"{message}. {hint}" if hint else message,
        line=line,
        construct=construct,
    )


# --- Darstellbarkeitspruefung (§3.3, §3.4) --------------------------------


def _styles_ok(styles: object) -> bool:
    if styles is None:
        return True
    if not isinstance(styles, dict):
        return False
    for key, value in styles.items():
        if value is False:
            continue
        if key not in SUPPORTED_STYLES or value is not True:
            return False
    return True


def _style_set(styles: object) -> frozenset[str]:
    if not isinstance(styles, dict):
        return frozenset()
    return frozenset(k for k, v in styles.items() if v is True and k in SUPPORTED_STYLES)


def _text_run_ok(item: dict[str, Any]) -> bool:
    text = item.get("text")
    if set(item) - {"type", "text", "styles"}:
        return False
    if not isinstance(text, str) or "\r" in text or not _styles_ok(item.get("styles")):
        return False
    if "code" in _style_set(item.get("styles")):
        # Ein Code-Span ueber einen Umbruch gibt es nicht; ab zwei Backticks im
        # Code braucht der Span eine Dreier-Fence, die am Zeilenanfang als
        # Code-Block gelesen wuerde.
        return "\n" not in text and "``" not in text
    return True


def _link_ok(item: dict[str, Any]) -> bool:
    href = item.get("href")
    content = item.get("content")
    if set(item) - {"type", "content", "href"}:
        return False
    if not isinstance(href, str) or any(c.isspace() for c in href) or not isinstance(content, list):
        return False
    return all(
        isinstance(run, dict)
        and run.get("type") == "text"
        and _text_run_ok(run)
        and "\n" not in run["text"]
        for run in content
    )


def _placeholder_ok(item: dict[str, Any]) -> bool:
    props = item.get("props")
    if set(item) - {"type", "props"} or not isinstance(props, dict):
        return False
    if set(props) - {"kind", "target_id", "label"}:
        return False
    kind = props.get("kind")
    target = props.get("target_id")
    return (
        isinstance(kind, str)
        and _KIND_RE.fullmatch(kind) is not None
        and isinstance(target, str)
        and "}" not in target
        and "\n" not in target
    )


def _surface_text(inlines: list[Any]) -> str:
    """Nicht-Code-Text eines Blocks; Code-Spans, Links und Pills zaehlen als `x`."""
    parts: list[str] = []
    for item in inlines:
        if item.get("type") == "text" and "code" not in _style_set(item.get("styles")):
            parts.append(item["text"])
        else:
            parts.append("x")
    return "".join(parts)


def _whitespace_edges_ok(surface: str) -> bool:
    """Fuehrender/abschliessender Leerraum und Einrueckung nach Umbruch sind nicht abbildbar."""
    if not surface:
        return True
    if surface[0].isspace() or surface[-1].isspace():
        return False
    return re.search(r"\n\s", surface) is None


def _inline_list_ok(content: object, *, allow_placeholders: bool, allow_break: bool) -> bool:
    if not isinstance(content, list):
        return False
    for item in content:
        if not isinstance(item, dict):
            return False
        kind = item.get("type")
        if kind == "text":
            if not _text_run_ok(item) or (not allow_break and "\n" in item["text"]):
                return False
        elif kind == "link":
            if not _link_ok(item):
                return False
        elif kind == "placeholder":
            if not allow_placeholders or not _placeholder_ok(item):
                return False
        else:
            return False
    # Benachbarte Code-Laeufe verschmelzen beim Rendern; die Regel aus
    # `_text_run_ok` gilt deshalb auch fuer die verschmolzene Folge.
    code = ""
    for item in content:
        if item.get("type") == "text" and "code" in _style_set(item.get("styles")):
            code += item["text"]
            if "``" in code:
                return False
        else:
            code = ""
    return _whitespace_edges_ok(_surface_text(content))


def _props_ok(block_type: str, props: object) -> bool:
    if props is None:
        return True
    if not isinstance(props, dict):
        return False
    for key, value in props.items():
        if key in _DEFAULT_PROPS and block_type != "codeBlock":
            if value != _DEFAULT_PROPS[key] or (block_type == "table" and key != "textColor"):
                return False
        elif block_type == "heading" and key == "level":
            if type(value) is not int or not 1 <= value <= MAX_HEADING_LEVEL:
                return False
        elif block_type == "heading" and key == "isToggleable":
            if value is not False:
                return False
        elif block_type == "checkListItem" and key == "checked":
            if not isinstance(value, bool):
                return False
        elif block_type == "numberedListItem" and key == "start":
            if value is not None:
                return False
        elif block_type == "codeBlock" and key == "language":
            if not isinstance(value, str) or _LANGUAGE_RE.fullmatch(value) is None:
                return False
        else:
            return False
    return True


def _table_rows(content: object) -> list[list[list[Any]]] | None:
    """Zeilen -> Zellen -> Inline-Listen einer abbildbaren Tabelle, sonst `None`."""
    if not isinstance(content, dict) or content.get("type") != "tableContent":
        return None
    if set(content) - {"type", "columnWidths", "headerRows", "headerCols", "rows"}:
        return None
    rows = content.get("rows")
    if not isinstance(rows, list) or not rows:
        return None
    result: list[list[list[Any]]] = []
    for row in rows:
        if not isinstance(row, dict) or set(row) - {"cells"}:
            return None
        cells = row.get("cells")
        if not isinstance(cells, list):
            return None
        out_row: list[list[Any]] = []
        for cell in cells:
            if isinstance(cell, dict):
                if cell.get("type") != "tableCell" or set(cell) - {"type", "props", "content"}:
                    return None
                props = cell.get("props") or {}
                if not isinstance(props, dict):
                    return None
                for key, value in props.items():
                    if key not in _CELL_DEFAULT_PROPS or value != _CELL_DEFAULT_PROPS[key]:
                        return None
                inlines = cell.get("content", [])
            else:
                inlines = cell
            if not _inline_list_ok(inlines, allow_placeholders=False, allow_break=False):
                return None
            out_row.append(inlines)
        result.append(out_row)
    if max(len(row) for row in result) == 0:
        return None
    return result


def block_representability(block: Block) -> Representability:
    """Darstellbarkeit eines Blocks nach ADR-0058 §3.3.

    - ``"ok"``: der Block hat eine Markdown-Form.
    - ``"locked"``: der Typ ist abbildbar, aber Inline-Stile, Props oder Inhalt
      nicht (Unterstreichung, Farbe, Ausrichtung, Ebene 4+, leerer Absatz, ...).
      Lesend Marker `<!-- w2b:locked <id> -->`.
    - ``"block"``: der Typ hat kein Gegenstueck (Bild, Video, ...) oder es ist
      eine Tabelle ausserhalb der Form aus §3.4. Lesend Marker
      `<!-- w2b:block <id> <typ> -->`.

    Die Kinder entscheiden nicht mit; sie werden je fuer sich geprueft.
    """
    block_type = block.get("type")
    if not isinstance(block_type, str) or block_type not in REPRESENTABLE_BLOCK_TYPES:
        return "block"
    if set(block) - _BLOCK_KEYS:
        return "block" if block_type == "table" else "locked"
    if not _props_ok(block_type, block.get("props")):
        return "block" if block_type == "table" else "locked"
    children = block.get("children", [])
    if not isinstance(children, list) or not all(isinstance(c, dict) for c in children):
        return "block" if block_type == "table" else "locked"
    content = block.get("content")
    if block_type == "table":
        return "ok" if _table_rows(content) is not None else "block"
    if block_type == "codeBlock":
        if not isinstance(content, list) or not all(
            isinstance(run, dict)
            and run.get("type") == "text"
            and isinstance(run.get("text"), str)
            and "\r" not in run["text"]
            and not _style_set(run.get("styles"))
            and _styles_ok(run.get("styles"))
            for run in content
        ):
            return "locked"
        return "ok"
    if not _inline_list_ok(content, allow_placeholders=True, allow_break=block_type != "heading"):
        return "locked"
    if block_type == "paragraph" and not content:
        return "locked"
    if block_type == "heading" and _ID_RE.fullmatch(str(block.get("id", ""))) is None:
        return "locked"
    return "ok"


# --- Rendern: BlockNote -> Markdown ---------------------------------------

# Stile, die als Delimiter ausgegeben werden. Die Rot-Probe der Golden-Tests
# ersetzt dieses Tupel, um einen verlustbehafteten Konverter zu simulieren.
_RENDER_STYLES: tuple[str, ...] = ("bold", "italic", "strike")


def _underscore_may_open(text: str, index: int) -> bool:
    """Gehoert das `_` an `index` zu einer Folge, die nicht im Wort steht?

    Solche Folgen koennte CommonMark als Hervorhebung lesen; der Parser
    lehnt sie ab (§3.3), deshalb maskiert der Renderer sie.
    """
    start = index
    while start > 0 and text[start - 1] == "_":
        start -= 1
    return start == 0 or not text[start - 1].isalnum()


def _escape_text(text: str, *, line_start: bool, table_cell: bool) -> str:
    out: list[str] = []
    for index, char in enumerate(text):
        if char in "\\*`~[]{<":
            out.append("\\" + char)
        elif char == "_" and _underscore_may_open(text, index):
            out.append("\\_")
        elif char == "&" and _ENTITY_RE.match(text, index):
            out.append("\\&")
        else:
            out.append(char)
    escaped = "".join(out)
    if line_start and not table_cell:
        number = _LINE_START_NUMBER_RE.match(escaped)
        if number:
            escaped = number.group(1) + "\\" + escaped[number.end(1) :]
        elif _LINE_START_ESCAPE_RE.match(escaped):
            escaped = "\\" + escaped
    return escaped


def _code_span(text: str) -> str:
    longest = max((len(m) for m in re.findall(r"`+", text)), default=0)
    fence = "`" * (longest + 1)
    pad = (
        text.startswith("`")
        or text.endswith("`")
        or (len(text) >= 2 and text[0] == " " and text[-1] == " " and text.strip(" ") != "")
    )
    return f"{fence} {text} {fence}" if pad else f"{fence}{text}{fence}"


@dataclass
class _Atom:
    kind: Literal["text", "space", "code", "pill", "link"]
    value: str
    styles: frozenset[str]


def _merged_runs(runs: Iterable[dict[str, Any]]) -> list[tuple[str, frozenset[str]]]:
    merged: list[tuple[str, frozenset[str]]] = []
    for run in runs:
        text = run["text"]
        if not text:
            continue
        styles = _style_set(run.get("styles"))
        if merged and merged[-1][1] == styles:
            merged[-1] = (merged[-1][0] + text, styles)
        else:
            merged.append((text, styles))
    return merged


def _atoms(
    inlines: list[dict[str, Any]], render_link: Callable[[dict[str, Any]], str]
) -> list[_Atom]:
    atoms: list[_Atom] = []
    pending: list[dict[str, Any]] = []

    def flush() -> None:
        for text, styles in _merged_runs(pending):
            if "code" in styles:
                atoms.append(_Atom("code", text, styles - {"code"}))
                continue
            for part in re.findall(r"\s+|\S+", text):
                atoms.append(_Atom("space" if part.isspace() else "text", part, styles))
        pending.clear()

    for item in inlines:
        kind = item.get("type")
        if kind == "text":
            pending.append(item)
            continue
        flush()
        if kind == "placeholder":
            props = item["props"]
            atoms.append(
                _Atom("pill", f"{{{{{props['kind']}:{props['target_id']}}}}}", frozenset())
            )
        else:
            atoms.append(_Atom("link", render_link(item), frozenset()))
    flush()
    return atoms


#: Feste Schachtelung der Hervorhebungen: fett aussen, kursiv, durchgestrichen
#: innen. Ein Wechsel schliesst bis zum gemeinsamen Praefix und oeffnet neu.
_NESTING: tuple[str, ...] = ("bold", "italic", "strike")
_DELIMS: dict[str, str] = {"bold": "**", "italic": "*", "strike": "~~"}


def _canon(styles: frozenset[str]) -> list[str]:
    return [s for s in _NESTING if s in styles]


def _common_prefix(*lists: list[str]) -> list[str]:
    prefix: list[str] = []
    for items in zip(*lists, strict=False):
        if len(set(items)) != 1:
            break
        prefix.append(items[0])
    return prefix


def _effective_styles(
    atoms: list[_Atom], styles_shown: tuple[str, ...] | None = None
) -> list[list[str] | None]:
    """Geschachtelte Stilliste je Atom (`None` = Pill, aendert nichts).

    Leerraum bekommt nur das gemeinsame Praefix seiner Nachbarn. So schliesst
    ein Delimiter immer direkt nach Nicht-Leerraum und oeffnet direkt davor
    (die Flanking-Regel des Parsers). Links schliessen alle Stile; ihr Text
    traegt seine Stile selbst. `styles_shown` sind die ausgegebenen Stile
    (Default `_RENDER_STYLES`, zur Laufzeit gelesen wegen der Rot-Probe).
    """
    render = set(_RENDER_STYLES if styles_shown is None else styles_shown)
    raw: list[list[str] | None] = []
    for atom in atoms:
        if atom.kind == "pill":
            raw.append(None)
        elif atom.kind == "link":
            raw.append([])
        else:
            raw.append(_canon(frozenset(s for s in atom.styles if s in render)))

    def neighbour(index: int, step: int) -> list[str]:
        cursor = index + step
        while 0 <= cursor < len(atoms):
            value = raw[cursor]
            if atoms[cursor].kind != "space" and value is not None:
                return value
            cursor += step
        return []

    effective = list(raw)
    for index, atom in enumerate(atoms):
        if atom.kind == "space":
            own = raw[index] or []
            effective[index] = _common_prefix(own, neighbour(index, -1), neighbour(index, 1))
    return effective


def _transition(active: list[str], target: list[str]) -> str:
    keep = len(_common_prefix(active, target))
    closing = "".join(_DELIMS[s] for s in reversed(active[keep:]))
    opening = "".join(_DELIMS[s] for s in target[keep:])
    return closing + opening


def _render_inlines(
    inlines: list[dict[str, Any]],
    *,
    continuation: str = "",
    table_cell: bool = False,
    line_start_escape: bool = True,
) -> str:
    """Rendert eine Inline-Liste; `continuation` ist die Einrueckung nach Umbruch."""

    def render_link(item: dict[str, Any]) -> str:
        # `|` maskiert erst der aeussere Aufruf, sonst stuende es doppelt da.
        inner = _render_inlines(item["content"], line_start_escape=False)
        href = re.sub(r"([\\()<>])", r"\\\1", item["href"])
        return f"[{inner}]({href})"

    atoms = _atoms(inlines, render_link)
    effective = _effective_styles(atoms)
    out: list[str] = []
    active: list[str] = []
    line_start = line_start_escape
    for index, atom in enumerate(atoms):
        target = effective[index]
        if target is not None:
            out.append(_transition(active, target))
            active = target
        if atom.kind == "text":
            text = atom.value
            next_atom = atoms[index + 1] if index + 1 < len(atoms) else None
            escaped = _escape_text(text, line_start=line_start, table_cell=table_cell)
            if next_atom is not None and next_atom.kind == "link" and escaped.endswith("!"):
                escaped = escaped[:-1] + "\\!"
            out.append(escaped)
            line_start = False
        elif atom.kind == "space":
            if "\n" in atom.value:
                out.append(atom.value.replace("\n", "\\\n" + continuation))
                line_start = line_start_escape
            else:
                out.append(atom.value)
        elif atom.kind == "code":
            out.append(_code_span(atom.value))
            line_start = False
        else:
            out.append(atom.value)
            line_start = False
    out.append(_transition(active, []))
    rendered = "".join(out)
    return rendered.replace("|", "\\|") if table_cell else rendered


def _code_text(content: list[dict[str, Any]]) -> str:
    return "".join(run["text"] for run in content)


def _render_table(block: Block, indent: str) -> list[str]:
    rows = _table_rows(block.get("content"))
    assert rows is not None  # noqa: S101 - nur fuer abbildbare Tabellen aufgerufen
    width = max(len(row) for row in rows)
    lines: list[str] = []
    for index, row in enumerate(rows):
        cells = [_render_inlines(cell, table_cell=True, line_start_escape=False) for cell in row]
        cells += [""] * (width - len(cells))
        lines.append(indent + "| " + " | ".join(cells) + " |")
        if index == 0:
            lines.append(indent + "| " + " | ".join(["---"] * width) + " |")
    return lines


def _marker_lines(block: Block, kind: Representability, indent: str) -> list[str]:
    block_id = str(block.get("id", ""))
    if _ID_RE.fullmatch(block_id) is None:
        raise MarkdownConversionError(
            "block_not_representable",
            "Block ohne gueltige ID laesst sich nicht schuetzen",
            block_id=block_id or None,
        )
    if kind == "locked":
        head = f"<!-- w2b:locked {block_id} -->"
    else:
        raw_type = str(block.get("type", ""))
        shown = raw_type if _TYPE_RE.fullmatch(raw_type) else "unknown"
        head = f"<!-- w2b:block {block_id} {shown} -->"
    return [indent + head] + [indent + line for line in _quote_lines(block)]


def _quote_lines(block: Block) -> list[str]:
    text = block_plain_text(block, placeholder_token_inline)
    return [f"> {line}" if line else ">" for line in text.split("\n")] if text else []


def _content_lines(block: Block, indent: str) -> list[str]:
    """Markdown-Zeilen eines abbildbaren Blocks ohne Kinder."""
    block_type = block["type"]
    props = block.get("props") or {}
    content = block.get("content") or []
    if block_type == "codeBlock":
        text = _code_text(content)
        longest = max((len(m) for m in re.findall(r"`+", text)), default=0)
        fence = "`" * max(3, longest + 1)
        body = [indent + line if line else "" for line in text.split("\n")]
        return [indent + fence + str(props.get("language", "text")), *body, indent + fence]
    if block_type == "table":
        return _render_table(block, indent)
    if block_type == "heading":
        marker = "#" * int(props.get("level", 1)) + " "
    elif block_type == "bulletListItem":
        marker = "- "
    elif block_type == "numberedListItem":
        marker = "1. "
    elif block_type == "checkListItem":
        marker = "- [x] " if props.get("checked") else "- [ ] "
    else:
        marker = ""
    text = _render_inlines(content, continuation=indent)
    if block_type == "heading":
        # Eine #-Folge am Textende laese CommonMark ohne Anker als schliessende
        # Folge; maskiert bleibt sie Text.
        text = _TRAILING_HASH_TEXT_RE.sub(lambda m: "\\" + m.group(0), text)
    if block_type == "heading" and block.get("id") is not None:
        text += f" [#{block['id']}]"
    return (indent + marker + text).split("\n")


def _render_block(block: Block, depth: int) -> list[str]:
    indent = "  " * depth
    kind = block_representability(block)
    if kind != "ok":
        return _marker_lines(block, kind, indent)
    lines = _content_lines(block, indent)
    for child in block.get("children") or []:
        lines.append("")
        lines.extend(_render_block(child, depth + 1))
    return lines


def _render_list(blocks: Iterable[Block], depth: int = 0) -> str:
    return "\n\n".join(
        "\n".join(_render_block(block, depth)) for block in blocks if isinstance(block, dict)
    )


def to_markdown(blocks: Iterable[Block]) -> str:
    """Rendert BlockNote-Bloecke in die Markdown-Normalform (ADR-0058 §5.2).

    Nicht abbildbare Bloecke erscheinen als geschuetzte Marker mit ihrem
    Klartext als Zitat (§3.3); Pills als `{{kind:target_id}}`. Ohne
    abschliessenden Zeilenumbruch.
    """
    return _render_list(blocks)


def _visible_inlines(inlines: list[dict[str, Any]]) -> list[tuple[str, ...]]:
    """Inline-Liste als Folge sichtbarer Laeufe, wie Markdown sie zeigen kann.

    Leerraum an Stilgrenzen bekommt dieselben Stile wie beim Rendern (er ist
    in Markdown nicht unterscheidbar); gleich formatierte Laeufe verschmelzen.
    Massgeblich sind die echten Stile, nicht die gerenderten: ein Konverter,
    der einen Stil verwirft, aendert diesen Wert.
    """

    def link_key(item: dict[str, Any]) -> str:
        return repr((item["href"], _visible_inlines(item["content"])))

    atoms = _atoms(inlines, link_key)
    effective = _effective_styles(atoms, _NESTING)
    out: list[tuple[str, ...]] = []
    for atom, styles in zip(atoms, effective, strict=True):
        if atom.kind == "pill":
            out.append(("pill", atom.value))
        elif atom.kind == "link":
            out.append(("link", atom.value))
        elif atom.kind == "code":
            out.append(("code", atom.value, ",".join(styles or [])))
        else:
            key = ",".join(styles or [])
            if out and out[-1][0] == "text" and out[-1][2] == key:
                out[-1] = ("text", out[-1][1] + atom.value, key)
            else:
                out.append(("text", atom.value, key))
    return out


def visible_content(blocks: Iterable[Block]) -> list[Any]:
    """Was Markdown von einem Dokument zeigt, ohne IDs (ausser an Ueberschriften).

    Zwei Dokumente mit gleichem `visible_content` ergeben dasselbe Markdown,
    bis auf Leerraum an Stilgrenzen. Geschuetzte Bloecke zaehlen mit ID und
    Typ. Gedacht fuer P2 (Erkennen einer Schreibung ohne Inhaltsaenderung) und
    als Pruefmass der Tests: ein verlustbehafteter Konverter aendert es.
    """
    out: list[Any] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        kind = block_representability(block)
        if kind != "ok":
            out.append(("marker", kind, block.get("id"), block.get("type")))
            continue
        props = block.get("props") or {}
        visible_props = {k: props[k] for k in ("level", "checked", "language") if k in props}
        if block["type"] == "heading":
            visible_props["id"] = block.get("id")
        rows = _table_rows(block.get("content"))
        if rows is not None:
            content: Any = [[_visible_inlines(cell) for cell in row] for row in rows]
        elif block["type"] == "codeBlock":
            content = _code_text(block.get("content") or [])
        else:
            content = _visible_inlines(block.get("content") or [])
        out.append(
            (block["type"], visible_props, content, visible_content(block.get("children") or []))
        )
    return out


# --- Parsen: Markdown -> Knotenbaum ---------------------------------------


@dataclass
class _Node:
    line: int
    block: Block | None = None
    marker: tuple[str, str, str | None, list[str]] | None = None
    children: list[_Node] = field(default_factory=list)

    @property
    def explicit_id(self) -> str | None:
        if self.marker is not None:
            return self.marker[1]
        if self.block is not None and self.block["type"] == "heading":
            value = self.block.get("id")
            return value if isinstance(value, str) else None
        return None


def _new_text(text: str, styles: frozenset[str]) -> dict[str, Any]:
    return {
        "type": "text",
        "text": text,
        "styles": {s: True for s in SUPPORTED_STYLES if s in styles},
    }


@dataclass
class _Tok:
    kind: Literal["text", "delim", "code", "pill", "link"]
    value: str = ""
    count: int = 0
    can_open: bool = False
    can_close: bool = False
    target: str = ""
    inner: list[dict[str, Any]] = field(default_factory=list)


def _find_link(text: str, start: int, line: int) -> tuple[int, str, str] | None:
    """`[inner](href)` ab `start`; liefert (Ende, inner, href) oder `None`.

    `None` heisst: an dieser Stelle steht kein Link (CommonMark liest den Text
    ebenso als Text). Ein Link-Ziel, das CommonMark als Link liest, das der
    Dialekt aber nicht abbildet (Titel, `<…>`-Ziel), ist ein Fehler (§3.3).
    Ausgeglichene Klammern im Ziel gehoeren wie in CommonMark zum Ziel.
    """
    depth = 0
    index = start
    while index < len(text):
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if char == "`":
            run = re.match(r"`+", text[index:])
            assert run is not None  # noqa: S101
            close = text.find(run.group(0), index + len(run.group(0)))
            index = close + len(run.group(0)) if close != -1 else index + len(run.group(0))
            continue
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                break
        index += 1
    else:
        return None
    if not text.startswith("(", index + 1):
        return None
    href_chars: list[str] = []
    cursor = index + 2
    if text.startswith("<", cursor):
        raise _unsupported(
            "Link-Ziel in spitzen Klammern", line, "Das Ziel ohne <> schreiben: [Text](URL)."
        )
    parens = 0
    while cursor < len(text):
        char = text[cursor]
        if char == "\\" and cursor + 1 < len(text) and text[cursor + 1] in _ESCAPABLE:
            href_chars.append(text[cursor + 1])
            cursor += 2
            continue
        if char == ")" and parens == 0:
            return cursor + 1, text[start + 1 : index], "".join(href_chars)
        if char.isspace():
            raise _unsupported(
                "Link mit Titel oder Leerraum im Ziel",
                line,
                "Links nur als [Text](URL), ohne Titel und ohne Leerraum im Ziel.",
            )
        if char == "(":
            parens += 1
        elif char == ")":
            parens -= 1
        href_chars.append(char)
        cursor += 1
    raise _unsupported("nicht geschlossenes Link-Ziel", line, "Das Ziel mit ) schliessen.")


def _is_link_like(text: str, start: int, line: int) -> bool:
    """Steht ab `start` etwas, das CommonMark als Link liest (auch ein nicht abbildbarer)?"""
    try:
        return _find_link(text, start, line) is not None
    except MarkdownConversionError:
        return True


def _tokenize(text: str, line: int, *, allow_pills: bool, in_link: bool) -> list[_Tok]:
    tokens: list[_Tok] = []
    buf: list[str] = []

    def flush() -> None:
        if buf:
            tokens.append(_Tok("text", "".join(buf)))
            buf.clear()

    index = 0
    underscore_open = False
    while index < len(text):
        char = text[index]
        if char == "\\" and index + 1 < len(text) and text[index + 1] in _ESCAPABLE:
            buf.append(text[index + 1])
            index += 2
            continue
        if char == "_":
            # CommonMark liest `_x_`/`__x__` als Hervorhebung; der Dialekt kennt
            # nur `*`. Wortinterne `_` (snake_case) bleiben Text.
            run_end = index
            while run_end < len(text) and text[run_end] == "_":
                run_end += 1
            before = text[index - 1] if index > 0 else " "
            after = text[run_end] if run_end < len(text) else " "
            if underscore_open and not before.isspace() and not after.isalnum():
                raise _unsupported(
                    "Hervorhebung mit Unterstrich", line, "Hervorhebung mit * bzw. ** schreiben."
                )
            if not after.isspace() and not before.isalnum():
                underscore_open = True
            buf.append(text[index:run_end])
            index = run_end
            continue
        if char == "`":
            run = re.match(r"`+", text[index:])
            assert run is not None  # noqa: S101
            fence = run.group(0)
            close = index + len(fence)
            while True:
                close = text.find(fence, close)
                if close == -1 or not text.startswith("`", close + len(fence)):
                    break
                close = re.match(r"`+", text[close:]).end() + close  # type: ignore[union-attr]
            if close == -1:
                buf.append(fence)
                index += len(fence)
                continue
            body = text[index + len(fence) : close]
            if len(body) >= 2 and body[0] == " " and body[-1] == " " and body.strip(" "):
                body = body[1:-1]
            flush()
            tokens.append(_Tok("code", body))
            index = close + len(fence)
            continue
        if char in "*~":
            run_match = re.match(r"\*+" if char == "*" else r"~+", text[index:])
            assert run_match is not None  # noqa: S101
            run_len = len(run_match.group(0))
            before = text[index - 1] if index > 0 else " "
            after = text[index + run_len] if index + run_len < len(text) else " "
            flush()
            tokens.append(
                _Tok(
                    "delim",
                    char,
                    run_len,
                    can_open=not after.isspace(),
                    can_close=not before.isspace(),
                )
            )
            index += run_len
            continue
        if char == "!" and text.startswith("[", index + 1) and _is_link_like(text, index + 1, line):
            raise _unsupported("Bild", line, "Bilder fuegt der Web-Editor ein.")
        if char == "[":
            found = None if in_link else _find_link(text, index, line)
            if found is not None:
                end, inner, href = found
                flush()
                inner_inlines = _parse_inline(inner, line, allow_pills=False, in_link=True)
                tokens.append(_Tok("link", target=href, inner=inner_inlines))
                index = end
                continue
            if in_link and _is_link_like(text, index, line):
                raise _unsupported("verschachtelter Link", line)
        if char == "{" and text.startswith("{", index + 1):
            close = text.find("}}", index + 2)
            token = text[index + 2 : close] if close != -1 else ""
            kind, sep, target = token.partition(":")
            if close != -1 and sep and _KIND_RE.fullmatch(kind) and "\n" not in target:
                if not allow_pills:
                    where = "Link" if in_link else "Tabellenzelle"
                    raise _unsupported(f"Platzhalter in {where}", line)
                flush()
                tokens.append(_Tok("pill", kind, target=target))
                index = close + 2
                continue
        if char == "<" and _HTML_RE.match(text, index):
            raise _unsupported("HTML", line, "HTML hat kein BlockNote-Gegenstueck.")
        if char == "&" and _ENTITY_RE.match(text, index):
            raise _unsupported(
                "HTML-Entity", line, "Zeichen direkt schreiben oder das & als \\& maskieren."
            )
        buf.append(char)
        index += 1
    flush()
    return tokens


_ESCAPABLE = frozenset("!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~")


def _resolve(tokens: list[_Tok]) -> list[tuple[str, Any, frozenset[str]]]:
    """Delimiter -> Stil-Umschaltungen; unbeendete Oeffner werden zu Text."""
    literal: set[tuple[int, str]] = set()
    while True:
        out: list[tuple[str, Any, frozenset[str]]] = []
        active: set[str] = set()
        opened: dict[str, int] = {}
        for index, tok in enumerate(tokens):
            if tok.kind != "delim":
                out.append((tok.kind, tok, frozenset(active)))
                continue
            remaining = tok.count
            opens: list[str] = []
            if tok.value == "*":
                if tok.can_close and "bold" in active and remaining >= 2:
                    active.discard("bold")
                    remaining -= 2
                if tok.can_close and "italic" in active and remaining >= 1:
                    active.discard("italic")
                    remaining -= 1
                if (
                    tok.can_open
                    and "bold" not in active
                    and remaining >= 2
                    and (index, "bold") not in literal
                ):
                    opens.append("bold")
                    remaining -= 2
                if (
                    tok.can_open
                    and "italic" not in active
                    and remaining >= 1
                    and (index, "italic") not in literal
                ):
                    opens.append("italic")
                    remaining -= 1
            else:
                if remaining >= 2 and "strike" in active and tok.can_close:
                    active.discard("strike")
                    remaining -= 2
                elif remaining >= 2 and tok.can_open and (index, "strike") not in literal:
                    opens.append("strike")
                    remaining -= 2
            if remaining:
                out.append(("text", _Tok("text", tok.value * remaining), frozenset(active)))
            for style in opens:
                active.add(style)
                opened[style] = index
        if not active:
            return out
        literal.update((opened[style], style) for style in active)


def _parse_inline(
    text: str, line: int, *, allow_pills: bool = True, in_link: bool = False
) -> list[dict[str, Any]]:
    tokens = _tokenize(text, line, allow_pills=allow_pills, in_link=in_link)
    inlines: list[dict[str, Any]] = []
    for kind, tok, styles in _resolve(tokens):
        if kind == "text" or kind == "code":
            run_styles = styles | {"code"} if kind == "code" else styles
            if not tok.value:
                continue
            last = inlines[-1] if inlines else None
            if (
                last is not None
                and last["type"] == "text"
                and _style_set(last["styles"]) == run_styles
                and kind == "text"
                and "code" not in run_styles
            ):
                last["text"] += tok.value
            else:
                inlines.append(_new_text(tok.value, run_styles))
        elif kind == "pill":
            inlines.append(
                {"type": "placeholder", "props": {"kind": tok.value, "target_id": tok.target}}
            )
        else:
            # Eine Hervorhebung um den Link gilt fuer seinen Text (BlockNote
            # kennt Stile nur an Text-Laeufen, nicht am Link).
            inner = [
                _new_text(run["text"], _style_set(run["styles"]) | styles) for run in tok.inner
            ]
            inlines.append({"type": "link", "content": _merge_inlines(inner), "href": tok.target})
    return _merge_inlines(inlines)


def _merge_inlines(inlines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for item in inlines:
        last = merged[-1] if merged else None
        if (
            item["type"] == "text"
            and last is not None
            and last["type"] == "text"
            and last["styles"] == item["styles"]
        ):
            last["text"] += item["text"]
        else:
            merged.append(item)
    return merged


def _leading_spaces(raw: str, line: int) -> int:
    stripped = raw.lstrip(" ")
    if stripped.startswith("\t"):
        raise _unsupported("Tabulator-Einrueckung", line, "Bitte mit Leerzeichen einruecken.")
    return len(raw) - len(stripped)


def _split_row(content: str) -> list[str]:
    body = content.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|") and not body.endswith("\\|"):
        body = body[:-1]
    cells: list[str] = []
    current: list[str] = []
    for index, char in enumerate(body):
        if char == "|" and (index == 0 or body[index - 1] != "\\"):
            cells.append("".join(current))
            current = []
        else:
            current.append(char)
    cells.append("".join(current))
    return [cell.strip().replace("\\|", "|") for cell in cells]


def _is_delimiter_row(content: str) -> bool:
    if "|" not in content:
        return False
    cells = _split_row(content)
    return bool(cells) and all(_DELIMITER_CELL_RE.fullmatch(cell) for cell in cells)


def _has_cell_pipe(content: str) -> bool:
    """Enthaelt die Zeile ein unmaskiertes `|` (GFM: moegliche Tabellenzeile)?"""
    return re.search(r"(?<!\\)\|", content) is not None


def _is_table_start(lines: list[str], index: int) -> bool:
    """GFM-Tabellenbeginn: Kopfzeile mit `|`, darunter eine Trennzeile.

    Erkennt auch Tabellen ohne aeussere Pipes, damit `_parse_table` sie als
    nicht unterstuetzt melden kann, statt sie still zu Absatztext zu machen.
    """
    content = lines[index].strip()
    return (
        _has_cell_pipe(content)
        and index + 1 < len(lines)
        and _is_delimiter_row(lines[index + 1].strip())
    )


def _starts_block(lines: list[str], index: int) -> bool:
    content = lines[index].strip()
    return bool(
        _HEADING_START_RE.match(content)
        or _FENCE_RE.match(content)
        or _BULLET_RE.match(content)
        or _NUMBERED_RE.match(content)
        or content.startswith(("<!--", ">"))
        or _THEMATIC_RE.match(content)
        or _HTML_RE.match(content)
        or _is_table_start(lines, index)
    )


def _default_props(block_type: str) -> dict[str, Any]:
    if block_type == "codeBlock":
        return {}
    if block_type == "table":
        return {"textColor": "default"}
    return dict(_DEFAULT_PROPS)


def _text_block(block_type: str, inlines: list[dict[str, Any]], line: int, **props: Any) -> Block:
    block: Block = {
        "id": props.pop("block_id", None),
        "type": block_type,
        "props": {**_default_props(block_type), **props},
        "content": inlines,
        "children": [],
    }
    if block_representability({**block, "id": block["id"] or "x"}) != "ok":
        raise _unsupported(
            "nicht abbildbarer Inhalt",
            line,
            "Fuehrender oder abschliessender Leerraum, Einrueckung nach einem Umbruch, "
            "Code-Span ueber einen Umbruch oder ein leerer Absatz lassen sich nicht abbilden.",
        )
    return block


def _check_no_block_anchor(text: str, line: int) -> None:
    if _TRAILING_ANCHOR_RE.search(text):
        raise _unsupported(
            "Anker an einem Block, der keine Ueberschrift ist",
            line,
            "Anker [#id] stehen nur an Ueberschriften.",
        )


def _join_paragraph(lines: list[str], start: int, first: str) -> tuple[str, int]:
    """Absatztext ab Zeile `start` samt Fortsetzungszeilen; liefert (Text, naechste Zeile)."""
    parts = [first]
    index = start + 1
    while index < len(lines) and lines[index].strip():
        content = lines[index].strip()
        if _SETEXT_RE.fullmatch(content):
            raise _unsupported("Setext-Ueberschrift", index + 1, "Ueberschriften mit # schreiben.")
        if _starts_block(lines, index):
            break
        previous = parts[-1]
        backslashes = len(previous) - len(previous.rstrip("\\"))
        if lines[index - 1].endswith("  ") and "".join(parts):
            # CommonMark: zwei Leerzeichen am Zeilenende sind ein harter
            # Umbruch, dieselbe Bedeutung wie `\` (§3.2); die Normalform
            # schreibt ihn als `\`.
            parts.append("\n" + content)
        elif backslashes % 2 == 1:
            parts[-1] = previous[:-1]
            parts.append("\n" + content)
        elif not "".join(parts):
            parts.append(content)
        else:
            parts.append(" " + content)
        index += 1
    return "".join(parts), index


def _parse_heading(content: str, line: int) -> Block:
    hashes = _HEADING_START_RE.match(content)
    assert hashes is not None  # noqa: S101
    level = len(hashes.group(1))
    if level > MAX_HEADING_LEVEL:
        raise _unsupported(f"Ueberschrift Ebene {level}", line, "Erlaubt sind # bis ###.")
    rest = content[level:]
    anchor = _ANCHOR_RE.search(rest)
    block_id = anchor.group(1) if anchor else None
    if anchor:
        rest = rest[: anchor.start()]
    else:
        # CommonMark: eine schliessende #-Folge (nach Leerraum) gehoert nicht
        # zum Text. Mit Anker steht sie nicht am Zeilenende und bleibt Text.
        rest = _CLOSING_HASHES_RE.sub("", rest)
    return _text_block(
        "heading", _parse_inline(rest.strip(), line), line, level=level, block_id=block_id
    )


def _parse_fence(lines: list[str], index: int, indent: int, content: str) -> tuple[Block, int]:
    line = index + 1
    match = _FENCE_RE.match(content)
    assert match is not None  # noqa: S101
    fence, info = match.group(1), match.group(2).strip()
    if fence[0] == "`" and "`" in info:
        raise _unsupported("Backtick in der Code-Sprache", line)
    words = info.split()
    if len(words) > 1:
        raise _unsupported("Code-Fence mit mehr als einer Sprachangabe", line)
    language = words[0] if words else "text"
    body: list[str] = []
    cursor = index + 1
    closing = re.compile(re.escape(fence[0]) + "{" + str(len(fence)) + r",}[ \t]*")
    while cursor < len(lines):
        raw = lines[cursor]
        if closing.fullmatch(raw.strip()):
            break
        prefix = " " * indent
        if raw.startswith(prefix):
            body.append(raw[indent:])
        elif not raw.strip():
            body.append("")
        else:
            body.append(raw.lstrip(" "))
        cursor += 1
    else:
        raise _unsupported("nicht geschlossene Code-Fence", line)
    text = "\n".join(body)
    block: Block = {
        "id": None,
        "type": "codeBlock",
        "props": {"language": language},
        "content": [_new_text(text, frozenset())] if text else [],
        "children": [],
    }
    return block, cursor + 1


def _check_table_row(content: str, line: int) -> None:
    body = content.strip()
    if not body.startswith("|") or not body.endswith("|") or body.endswith("\\|"):
        raise _unsupported(
            "Tabellenzeile ohne aeussere Pipes",
            line,
            "Jede Tabellenzeile beginnt und endet mit |, nach der Tabelle folgt eine Leerzeile.",
        )


def _parse_table(lines: list[str], index: int) -> tuple[Block, int]:
    _check_table_row(lines[index], index + 1)
    _check_table_row(lines[index + 1], index + 2)
    rows: list[list[str]] = [_split_row(lines[index].strip())]
    delimiter = lines[index + 1].strip()
    if ":" in delimiter:
        raise _unsupported(
            "Tabellen-Ausrichtung", index + 2, "Die Trennzeile traegt keine Ausrichtung."
        )
    if len(_split_row(delimiter)) != len(rows[0]):
        raise _unsupported(
            "Tabellen-Trennzeile mit anderer Spaltenzahl als die Kopfzeile",
            index + 2,
            "Die Trennzeile hat so viele Zellen wie die Kopfzeile.",
        )
    cursor = index + 2
    while cursor < len(lines) and lines[cursor].strip():
        # GFM: Die Tabelle endet erst an einer Leerzeile oder einem neuen
        # Block; jede Zeile davor ist eine Tabellenzeile.
        if not lines[cursor].strip().startswith("|") and _starts_block(lines, cursor):
            break
        _check_table_row(lines[cursor], cursor + 1)
        rows.append(_split_row(lines[cursor].strip()))
        cursor += 1
    width = max(len(row) for row in rows)
    parsed_rows: list[dict[str, Any]] = []
    for offset, row in enumerate(rows):
        line = index + 1 + (offset if offset == 0 else offset + 1)
        cells = []
        for cell in row + [""] * (width - len(row)):
            inlines = _parse_inline(cell, line, allow_pills=False)
            cells.append(
                {"type": "tableCell", "props": dict(_CELL_DEFAULT_PROPS), "content": inlines}
            )
        parsed_rows.append({"cells": cells})
    block: Block = {
        "id": None,
        "type": "table",
        "props": {"textColor": "default"},
        "content": {"type": "tableContent", "columnWidths": [None] * width, "rows": parsed_rows},
        "children": [],
    }
    if block_representability({**block, "id": "x"}) != "ok":
        raise _unsupported("nicht abbildbare Tabellenzelle", index + 1)
    return block, cursor


def _parse_marker(lines: list[str], index: int, indent: int, content: str) -> tuple[_Node, int]:
    line = index + 1
    match = _MARKER_RE.fullmatch(content)
    if match is None:
        raise _unsupported("HTML-Kommentar", line, "Nur die Marker <!-- w2b:... --> sind erlaubt.")
    kind, block_id, block_type = match.group(1), match.group(2), match.group(3)
    if (kind == "block") != (block_type is not None):
        raise _unsupported("unvollstaendiger Marker", line)
    quote: list[str] = []
    cursor = index + 1
    while cursor < len(lines):
        raw = lines[cursor]
        if not raw.strip() or not raw[indent:].startswith(">") or not raw.startswith(" " * indent):
            break
        quote.append(raw[indent:].rstrip())
        cursor += 1
    return _Node(line=line, marker=(kind, block_id, block_type, quote)), cursor


def _parse_nodes(md: str) -> list[_Node]:
    lines = md.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    root: list[_Node] = []
    stack: list[tuple[int, _Node]] = []
    index = 0
    while index < len(lines):
        raw = lines[index]
        if not raw.strip():
            index += 1
            continue
        line = index + 1
        indent = _leading_spaces(raw, line)
        content = raw[indent:].rstrip()
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if indent - (stack[-1][0] if stack else 0) >= 4:
            raise _unsupported(
                "eingerueckter Code-Block",
                line,
                "Code als Fence (```) schreiben; Kinder um zwei Leerzeichen einruecken.",
            )
        if stack and stack[-1][1].marker is not None:
            raise _unsupported(
                "Inhalt unter einem geschuetzten Marker", line, "Marker haben keine Kinder."
            )
        siblings = stack[-1][1].children if stack else root
        node, index = _parse_one(lines, index, indent, content)
        siblings.append(node)
        stack.append((indent, node))
    return root


def _parse_one(lines: list[str], index: int, indent: int, content: str) -> tuple[_Node, int]:
    line = index + 1
    if content.startswith("<!--"):
        return _parse_marker(lines, index, indent, content)
    if content.startswith(">"):
        raise _unsupported("Zitat", line, "Zitate hat nur der Web-Editor.")
    if _THEMATIC_RE.fullmatch(content):
        raise _unsupported("Trennlinie", line, "Trennlinien hat nur der Web-Editor.")
    if _HTML_RE.match(content):
        raise _unsupported("HTML", line, "HTML hat kein BlockNote-Gegenstueck.")
    if _REFERENCE_DEF_RE.match(content):
        raise _unsupported("Referenz-Link-Definition", line, "Links inline als [Text](URL).")
    if _FENCE_RE.match(content):
        block, cursor = _parse_fence(lines, index, indent, content)
        return _Node(line=line, block=block), cursor
    if _HEADING_START_RE.match(content):
        return _Node(line=line, block=_parse_heading(content, line)), index + 1
    if _is_table_start(lines, index):
        block, cursor = _parse_table(lines, index)
        return _Node(line=line, block=block), cursor
    check = _CHECK_RE.match(content)
    bullet = _BULLET_RE.match(content)
    numbered = _NUMBERED_RE.match(content)
    if check:
        block_type, first, extra = (
            "checkListItem",
            check.group(2) or "",
            {"checked": check.group(1) != " "},
        )
    elif bullet:
        block_type, first, extra = "bulletListItem", bullet.group(1) or "", {}
    elif numbered:
        block_type, first, extra = "numberedListItem", numbered.group(2) or "", {}
        if re.match(r"\[[ xX]\](?:[ \t]|$)", first):
            raise _unsupported(
                "Checkbox in nummerierter Liste", line, "Aufgaben als - [ ] schreiben."
            )
    else:
        block_type, first, extra = "paragraph", content, {}
    text, cursor = _join_paragraph(lines, index, first)
    _check_no_block_anchor(text, line)
    block = _text_block(block_type, _parse_inline(text, line), line, **extra)
    return _Node(line=line, block=block), cursor


def _node_block(node: _Node) -> Block:
    """Block-Dict eines Knotens samt Kindern (Marker sind nur ueber `base` aufloesbar)."""
    assert node.block is not None  # noqa: S101
    block = dict(node.block)
    block["children"] = [_node_block(child) for child in node.children if child.block is not None]
    return block


def _render_nodes(nodes: list[_Node], depth: int) -> list[str]:
    parts: list[list[str]] = []
    for node in nodes:
        indent = "  " * depth
        if node.marker is not None:
            kind, block_id, block_type, quote = node.marker
            head = (
                f"<!-- w2b:locked {block_id} -->"
                if kind == "locked"
                else f"<!-- w2b:block {block_id} {block_type} -->"
            )
            parts.append([indent + head] + [indent + q for q in quote])
            continue
        assert node.block is not None  # noqa: S101
        lines = _content_lines(node.block, indent)
        if node.children:
            lines.append("")
            lines.extend(_render_nodes(node.children, depth + 1))
        parts.append(lines)
    out: list[str] = []
    for index, lines in enumerate(parts):
        if index:
            out.append("")
        out.extend(lines)
    return out


def normalize(md: str) -> str:
    """Bringt Markdown in die Normalform von `to_markdown` (ADR-0058 §5.2 G2).

    Rein syntaktisch, ohne Basis: Anker und Marker bleiben, wie sie stehen,
    Ueberschriften ohne Anker bekommen keinen. Nicht unterstuetzte Konstrukte
    werfen `MarkdownConversionError` wie `from_markdown`.
    """
    return "\n".join(_render_nodes(_parse_nodes(md), 0))


# --- Zuordnung gegen die Basis (§4.2/§4.3) --------------------------------


def _walk(blocks: Iterable[Any]) -> Iterable[Block]:
    for block in blocks:
        if isinstance(block, dict):
            yield block
            yield from _walk(block.get("children") or [])


def _subtree_ids(block: Block) -> set[str]:
    return {str(b.get("id")) for b in _walk([block])}


def _node_explicit_ids(node: _Node) -> set[str]:
    ids = {node.explicit_id} if node.explicit_id else set()
    for child in node.children:
        ids |= _node_explicit_ids(child)
    return ids


def default_new_block_id(existing: set[str]) -> str:
    """Neue, kollisionsfreie Block-ID (8 Zeichen a-z0-9, `secrets` wie die WorkArea)."""
    alphabet = "abcdefghijklmnopqrstuvwxyz0123456789"
    while True:
        candidate = "".join(secrets.choice(alphabet) for _ in range(8))
        if candidate not in existing:
            return candidate


@dataclass
class _Matcher:
    base: list[Block]
    allow_tables: bool
    resolve_label: Callable[[str, str], str | None] | None
    new_id: Callable[[set[str]], str]
    used: set[str] = field(default_factory=set)
    reserved: set[str] = field(default_factory=set)
    reserved_explicit: set[str] = field(default_factory=set)
    index: dict[str, Block] = field(default_factory=dict)
    labels: dict[tuple[str, str], str] = field(default_factory=dict)
    # Render-Cache fuer die Zuordnung (Schluessel `id()` der Basisbloecke und
    # Knoten; beide leben so lange wie der Matcher).
    rendered: dict[int, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for block in _walk(self.base):
            block_id = block.get("id")
            if isinstance(block_id, str):
                self.index.setdefault(block_id, block)
            content = block.get("content")
            for item in content if isinstance(content, list) else []:
                if isinstance(item, dict) and item.get("type") == "placeholder":
                    props = item.get("props") or {}
                    key = (str(props.get("kind", "")), str(props.get("target_id", "")))
                    if isinstance(props.get("label"), str):
                        self.labels.setdefault(key, props["label"])
        self.reserved = set(self.index)

    def fresh_id(self) -> str:
        new = self.new_id(self.reserved | self.used)
        self.used.add(new)
        return new

    def label(self, kind: str, target: str) -> str:
        if (kind, target) in self.labels:
            return self.labels[(kind, target)]
        if self.resolve_label is not None:
            resolved = self.resolve_label(kind, target)
            if resolved is not None:
                return resolved
        return f"{kind}:{target}"

    def finish(self, block: Block, line: int) -> Block:
        """Neuer oder geaenderter Block: Pill-Labels setzen, Tabellenregel pruefen."""
        if block["type"] == "table" and not self.allow_tables:
            raise _unsupported(
                "neue oder geaenderte Tabelle", line, "Tabellen gibt es nur in einer Resource."
            )
        content = block.get("content")
        for item in content if isinstance(content, list) else []:
            if item.get("type") == "placeholder":
                props = item["props"]
                props["label"] = self.label(props["kind"], props["target_id"])
        return block

    def claim(self, ids: set[str], node: _Node, block_id: str) -> None:
        """Belegt IDs; eine schon vergebene ID hiesse denselben Block zweimal."""
        if ids & self.used:
            raise MarkdownConversionError(
                "anchor_duplicate",
                f"Block {block_id} steht schon an anderer Stelle im Dokument",
                line=node.line,
                block_id=block_id,
            )
        self.used |= ids

    def take_marker(self, node: _Node) -> Block:
        assert node.marker is not None  # noqa: S101
        kind, block_id, block_type, quote = node.marker
        base = self.index.get(block_id)
        expected: Representability = "locked" if kind == "locked" else "block"
        if base is None or block_representability(base) != expected:
            raise MarkdownConversionError(
                "block_not_representable",
                f"Marker zeigt auf keinen geschuetzten Block der Basis: {block_id}",
                line=node.line,
                block_id=block_id,
            )
        if kind == "block":
            raw_type = str(base.get("type", ""))
            if (raw_type if _TYPE_RE.fullmatch(raw_type) else "unknown") != block_type:
                raise MarkdownConversionError(
                    "block_not_representable",
                    f"Marker-Typ passt nicht zum Block {block_id}",
                    line=node.line,
                    block_id=block_id,
                )
        if [q.rstrip() for q in quote] != [q.rstrip() for q in _quote_lines(base)]:
            raise MarkdownConversionError(
                "block_not_representable",
                f"Block {block_id} ist geschuetzt und laesst sich nur im Web-Editor aendern",
                line=node.line,
                block_id=block_id,
            )
        self.claim(_subtree_ids(base), node, block_id)
        return copy.deepcopy(base)

    def take_heading(self, node: _Node) -> Block:
        assert node.block is not None  # noqa: S101
        anchor = node.block.get("id")
        if anchor is None:
            block = _node_block(node)
            block["id"] = self.fresh_id()
            block["children"] = self.match_list(node.children, [])
            return self.finish(block, node.line)
        base = self.index.get(anchor)
        if base is None or base.get("type") != "heading":
            raise MarkdownConversionError(
                "anchor_unknown",
                f"Anker [#{anchor}] gibt es in der Basis nicht",
                line=node.line,
                block_id=anchor,
            )
        if block_representability(base) != "ok":
            raise MarkdownConversionError(
                "block_not_representable",
                f"Ueberschrift {anchor} ist geschuetzt und laesst sich nur im Web-Editor aendern",
                line=node.line,
                block_id=anchor,
            )
        if self._same(node, base) and not (_subtree_ids(base) - {anchor}) & self.reserved_explicit:
            self.claim(_subtree_ids(base), node, anchor)
            return copy.deepcopy(base)
        self.claim({anchor}, node, anchor)
        return self._changed(node, base)

    def _same(self, node: _Node, base: Block) -> bool:
        key = id(base)
        if key not in self.rendered:
            self.rendered[key] = "\n".join(_render_block(base, 0))
        if id(node) not in self.rendered:
            self.rendered[id(node)] = "\n".join(_render_nodes([node], 0))
        return self.rendered[id(node)] == self.rendered[key]

    def _changed(self, node: _Node, base: Block) -> Block:
        """Alte ID, neuer Inhalt; Basis-Props bleiben, sichtbare Props kommen aus Markdown.

        Ist nur ein Kind anders, bleibt der eigene Inhalt des Blocks bitgleich.
        """
        assert node.block is not None  # noqa: S101
        parsed = node.block
        block: Block = {"id": base["id"], "type": parsed["type"]}
        own_same = base.get("type") == parsed["type"] and _content_lines(
            {**parsed, "children": []}, ""
        ) == _content_lines({**base, "children": []}, "")
        if own_same:
            for key in ("props", "content"):
                if key in base:
                    block[key] = copy.deepcopy(base[key])
        else:
            if base.get("type") == parsed["type"] and isinstance(base.get("props"), dict):
                props = dict(base["props"])
                for key in ("level", "checked", "language"):
                    if key in parsed["props"]:
                        props[key] = parsed["props"][key]
            else:
                props = dict(parsed["props"])
            block["props"] = props
            block["content"] = self._table_content(parsed, base)
        base_children = base.get("children") if isinstance(base.get("children"), list) else []
        block["children"] = self.match_list(node.children, base_children or [])
        return block if own_same else self.finish(block, node.line)

    @staticmethod
    def _table_content(parsed: Block, base: Block) -> Any:
        """Neuer Inhalt; bei Tabellen gleicher Breite Spaltenbreiten und Kopf aus der Basis."""
        content = copy.deepcopy(parsed["content"])
        if parsed["type"] != "table":
            return content
        base_content = base.get("content")
        if not isinstance(base_content, dict):
            return content
        base_widths = base_content.get("columnWidths")
        if isinstance(base_widths, list) and len(base_widths) == len(content["columnWidths"]):
            content["columnWidths"] = copy.deepcopy(base_widths)
            for key in ("headerRows", "headerCols"):
                if key in base_content:
                    content[key] = base_content[key]
        return content

    def match_list(self, nodes: list[_Node], candidates: list[Block]) -> list[Block]:
        out: list[Block | None] = [None] * len(nodes)
        for i, node in enumerate(nodes):
            if node.marker is not None:
                out[i] = self.take_marker(node)
            elif node.block is not None and node.block["type"] == "heading":
                out[i] = self.take_heading(node)
        eligible = [
            (j, c)
            for j, c in enumerate(candidates)
            if isinstance(c, dict)
            and c.get("type") != "heading"
            and block_representability(c) == "ok"
        ]
        # Schritt 1: inhaltsgleich -> alter Block bitgleich.
        for i, node in enumerate(nodes):
            if out[i] is not None:
                continue
            own = _node_explicit_ids(node)
            for _, cand in eligible:
                ids = _subtree_ids(cand)
                if ids & self.used or (ids & self.reserved_explicit) - own:
                    continue
                if self._same(node, cand):
                    out[i] = copy.deepcopy(cand)
                    self.used |= ids
                    break
        # Schritt 2: gleicher Typ an gleicher Position -> alte ID, neuer Inhalt.
        for i, node in enumerate(nodes):
            if out[i] is not None or i >= len(candidates):
                continue
            cand = candidates[i]
            assert node.block is not None  # noqa: S101
            if (
                isinstance(cand, dict)
                and cand.get("type") == node.block["type"]
                and cand.get("type") != "heading"
                and block_representability(cand) == "ok"
                and str(cand.get("id")) not in self.used
            ):
                self.used.add(str(cand.get("id")))
                out[i] = self._changed(node, cand)
        # Schritt 3: neue ID.
        for i, node in enumerate(nodes):
            if out[i] is not None:
                continue
            block = _node_block(node)
            block["id"] = self.fresh_id()
            block["content"] = copy.deepcopy(block["content"])
            block["children"] = self.match_list(node.children, [])
            out[i] = self.finish(block, node.line)
        return [block for block in out if block is not None]

    def assign(self, nodes: list[_Node]) -> list[Block]:
        # Abschnittsgrenzen sind nur abbildbare Ueberschriften: eine gesperrte
        # Ueberschrift erscheint als Marker und ist im Markdown keine Grenze.
        base_sections: dict[str, list[Block]] = {}
        key = _PREAMBLE
        for block in self.base:
            if block.get("type") == "heading" and block_representability(block) == "ok":
                key = str(block.get("id"))
                base_sections.setdefault(key, [])
                continue
            base_sections.setdefault(key, []).append(block)
        result: list[Block] = []
        items: list[_Node] = []
        section_key: str | None = _PREAMBLE
        for node in [*nodes, None]:
            if node is not None and not (
                node.block is not None and node.block["type"] == "heading"
            ):
                items.append(node)
                continue
            candidates = base_sections.get(section_key, []) if section_key is not None else []
            result.extend(self.match_list(items, candidates))
            items = []
            if node is None:
                break
            heading = self.take_heading(node)
            result.append(heading)
            anchor = node.block.get("id") if node.block is not None else None
            section_key = anchor if isinstance(anchor, str) else None
        return result


def _check_explicit_ids(nodes: list[_Node]) -> set[str]:
    seen: dict[str, int] = {}

    def visit(node: _Node) -> None:
        explicit = node.explicit_id
        if explicit is not None:
            if explicit in seen:
                raise MarkdownConversionError(
                    "anchor_duplicate",
                    f"ID {explicit} steht mehrfach im Dokument (zuerst Zeile {seen[explicit]})",
                    line=node.line,
                    block_id=explicit,
                )
            seen[explicit] = node.line
        for child in node.children:
            visit(child)

    for node in nodes:
        visit(node)
    return set(seen)


def from_markdown(
    md: str,
    base: list[Block] | None = None,
    *,
    allow_tables: bool = False,
    resolve_label: Callable[[str, str], str | None] | None = None,
    new_id: Callable[[set[str]], str] | None = None,
) -> list[Block]:
    """Baut BlockNote-Bloecke aus Markdown, IDs stabil gegen `base` (ADR-0058 §4).

    Args:
        md: Markdown im Dialekt aus §3.2, Normalform nicht erforderlich.
        base: gespeicherte Bloecke der Version, auf die geschrieben wird;
            `None` bei `create_*` (dann ist jeder Anker und Marker unbekannt).
        allow_tables: Tabellen neu anlegen oder aendern (nur Resource, §3.4).
            Unveraenderte Tabellen der Basis bleiben auch ohne bitgleich.
        resolve_label: liefert das Label einer neuen Pill aus dem Namen des
            Ziels (API mit DB-Zugriff, §3.2). Unveraenderte Pills behalten ihr
            Label aus `base`; ohne Treffer gilt `kind:target_id`.
        new_id: ID-Vergabe fuer neue Bloecke (Tests: deterministisch).

    Raises:
        MarkdownConversionError: `markdown_unsupported`, `block_not_representable`,
            `anchor_unknown` oder `anchor_duplicate` (P2 -> 422).
    """
    nodes = _parse_nodes(md)
    explicit = _check_explicit_ids(nodes)
    matcher = _Matcher(
        base=[b for b in (base or []) if isinstance(b, dict)],
        allow_tables=allow_tables,
        resolve_label=resolve_label,
        new_id=new_id or default_new_block_id,
    )
    matcher.reserved |= explicit
    matcher.reserved_explicit = explicit
    return matcher.assign(nodes)


__all__ = [
    "BLOCKNOTE_VERSION",
    "MAX_HEADING_LEVEL",
    "NON_REPRESENTABLE_BLOCK_TYPES",
    "REPRESENTABLE_BLOCK_TYPES",
    "SUPPORTED_STYLES",
    "MarkdownConversionError",
    "block_representability",
    "default_new_block_id",
    "from_markdown",
    "normalize",
    "to_markdown",
    "visible_content",
]
