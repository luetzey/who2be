"""Erzeugte Dokumente und Escaping-Faelle fuer den Markdown-Konverter (ADR-0058 §5.3).

Ein Generator mit `random.Random(seed)` baut Blockbaeume ueber die Grammatik
aus §3.2: Typen, Ebenen, Verschachtelung, Stil-Kombinationen, Links, Pills und
Sonderzeichen wie `*`, `_`, `` ` ``, `#`, `[`, `{{` im Text. Keine neue
Abhaengigkeit (Hypothesis steht nicht in den Lock-Dateien, ADR-0033). Bei
einem Fehler nennt die Meldung Seed und Markdown.
"""

from __future__ import annotations

import copy
import random
import re
from typing import Any

import pytest

import who2be_models.blocknote_markdown as converter
from who2be_models.blocknote_markdown import (
    MarkdownConversionError,
    block_representability,
    from_markdown,
    normalize,
    to_markdown,
    visible_content,
)

SEEDS = range(400)
_ANCHOR_RE = re.compile(r" \[#[^\]\s]+\]$", re.MULTILINE)
_WORDS = [
    "Agent",
    "snake_case",
    "a*b",
    "2 * 3",
    "`tick`",
    "#tag",
    "[eckig]",
    "{{kein:token",
    "}}",
    "Ä-Umlaut",
    "1.",
    "- strich",
    "> pfeil",
    "~tilde~",
    "\\pfad\\",
    "<b>",
    "&amp;",
    "a|b",
    "!",
    "(klammer)",
    "x]",
    "**",
    "_",
    "+",
    "=",
    "{{date:}}",
    "https://who2be.de",
]
_STYLE_SETS: list[dict[str, bool]] = [
    {},
    {},
    {},
    {"bold": True},
    {"italic": True},
    {"strike": True},
    {"code": True},
    {"bold": True, "italic": True},
    {"bold": True, "strike": True},
    {"italic": True, "code": True},
    {"bold": True, "italic": True, "strike": True},
]
_DEFAULT: dict[str, Any] = {
    "textColor": "default",
    "backgroundColor": "default",
    "textAlignment": "left",
}


class _Gen:
    def __init__(self, seed: int) -> None:
        self.rng = random.Random(seed)
        self.counter = 0

    def next_id(self) -> str:
        self.counter += 1
        return f"g{self.counter}"

    def phrase(self, *, allow_break: bool) -> str:
        words = [self.rng.choice(_WORDS) for _ in range(self.rng.randint(1, 4))]
        text = " ".join(words)
        if allow_break and self.rng.random() < 0.1:
            text += "\n" + self.rng.choice(_WORDS)
        return text

    def inlines(self, *, pills: bool, allow_break: bool) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for _ in range(self.rng.randint(1, 5)):
            roll = self.rng.random()
            if pills and roll < 0.12:
                kind = self.rng.choice(["date", "persona-field", "resource", "playbook"])
                target = self.rng.choice(["", "name", "abc#h-1", "0f8c2b9e"])
                items.append(
                    {
                        "type": "placeholder",
                        "props": {"kind": kind, "target_id": target, "label": f"L {kind}"},
                    }
                )
            elif roll < 0.2:
                items.append(
                    {
                        "type": "link",
                        "href": self.rng.choice(["https://who2be.de", "https://who2be.de/a_(b)"]),
                        "content": [
                            {
                                "type": "text",
                                "text": self.phrase(allow_break=False),
                                "styles": dict(self.rng.choice(_STYLE_SETS[:6])),
                            }
                        ],
                    }
                )
            else:
                styles = dict(self.rng.choice(_STYLE_SETS))
                text = self.phrase(allow_break=allow_break and "code" not in styles)
                if "code" in styles:
                    text = text.replace("``", "`'")
                lead = " " if items and self.rng.random() < 0.5 else ""
                items.append({"type": "text", "text": lead + text, "styles": styles})
        return items

    def block(self, depth: int, *, tables: bool) -> dict[str, Any]:
        roll = self.rng.random()
        if roll < 0.15:
            level = self.rng.choice([1, 2, 3])
            return {
                "id": self.next_id(),
                "type": "heading",
                "props": {**_DEFAULT, "level": level},
                "content": self.inlines(pills=True, allow_break=False),
                "children": [],
            }
        if roll < 0.22:
            code = "\n".join(self.phrase(allow_break=False) for _ in range(self.rng.randint(1, 3)))
            if self.rng.random() < 0.2:
                code += "\n```\n" + "``x``"
            return {
                "id": self.next_id(),
                "type": "codeBlock",
                "props": {"language": self.rng.choice(["json", "markdown", "text", "python"])},
                "content": [{"type": "text", "text": code, "styles": {}}],
                "children": [],
            }
        if tables and roll < 0.27:
            width = self.rng.randint(1, 3)
            cell_props: dict[str, Any] = {**_DEFAULT, "colspan": 1, "rowspan": 1}
            rows = [
                {
                    "cells": [
                        {
                            "type": "tableCell",
                            "props": dict(cell_props),
                            "content": self.inlines(pills=False, allow_break=False),
                        }
                        for _ in range(width)
                    ]
                }
                for _ in range(self.rng.randint(1, 3))
            ]
            return {
                "id": self.next_id(),
                "type": "table",
                "props": {"textColor": "default"},
                "content": {
                    "type": "tableContent",
                    "columnWidths": [self.rng.choice([None, 120]) for _ in range(width)],
                    "rows": rows,
                },
                "children": [],
            }
        block_type = self.rng.choice(
            ["paragraph", "paragraph", "bulletListItem", "numberedListItem", "checkListItem"]
        )
        props: dict[str, Any] = dict(_DEFAULT)
        if block_type == "checkListItem":
            props["checked"] = self.rng.random() < 0.5
        children: list[dict[str, Any]] = []
        if depth < 2 and block_type != "paragraph" and self.rng.random() < 0.3:
            children = [self.block(depth + 1, tables=False) for _ in range(self.rng.randint(1, 2))]
            children = [c for c in children if c["type"] != "heading"]
        return {
            "id": self.next_id(),
            "type": block_type,
            "props": props,
            "content": self.inlines(pills=True, allow_break=True),
            "children": children,
        }

    def document(self, *, tables: bool = False) -> list[dict[str, Any]]:
        return [self.block(0, tables=tables) for _ in range(self.rng.randint(1, 8))]


def _has_markers(blocks: list[dict[str, Any]]) -> bool:
    for block in blocks:
        if block_representability(block) != "ok" or _has_markers(block.get("children") or []):
            return True
    return False


def _strip_ids(content: list[Any]) -> list[Any]:
    out: list[Any] = []
    for entry in content:
        if entry[0] == "marker":
            out.append(entry)
            continue
        block_type, props, inline, children = entry
        out.append(
            (
                block_type,
                {k: v for k, v in props.items() if k != "id"},
                inline,
                _strip_ids(children),
            )
        )
    return out


def _counter_ids() -> Any:
    counter = iter(range(1, 1_000_000))
    return lambda existing: f"neu{next(counter)}"


def check_generated(seed: int) -> None:
    doc = _Gen(seed).document(tables=seed % 3 == 0)
    original = copy.deepcopy(doc)
    md = to_markdown(doc)
    context = f"seed={seed}\n{md}"
    assert from_markdown(md, base=doc, allow_tables=True) == original, f"G1 {context}"
    assert normalize(md) == md, f"G2 Normalform {context}"
    assert normalize(normalize(md)) == normalize(md), f"G2 idempotent {context}"
    if _has_markers(doc):
        return
    unanchored = _ANCHOR_RE.sub("", md)
    rebuilt = from_markdown(unanchored, allow_tables=True, new_id=_counter_ids())
    assert _ANCHOR_RE.sub("", to_markdown(rebuilt)) == unanchored, f"G2 {context}"
    assert _strip_ids(visible_content(rebuilt)) == _strip_ids(visible_content(original)), (
        f"Verlust {context}"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_generated_documents_round_trip(seed: int) -> None:
    check_generated(seed)


def test_generator_covers_the_grammar() -> None:
    # Der Generator muss die Grammatik auch wirklich treffen, sonst prueft er nichts.
    seen: set[str] = set()
    for seed in SEEDS:
        md = to_markdown(_Gen(seed).document(tables=seed % 3 == 0))
        for name, needle in {
            "heading": "\n## ",
            "bold": "**",
            "italic_or_strike": "~~",
            "code_span": "`",
            "fence": "```",
            "pill": "{{",
            "link": "](https://who2be.de",
            "check": "- [x] ",
            "numbered": "1. ",
            "nested": "\n  - ",
            "table": "| --- |",
            "break": "\\\n",
        }.items():
            if needle in md:
                seen.add(name)
    assert seen >= {
        "heading",
        "bold",
        "italic_or_strike",
        "code_span",
        "fence",
        "pill",
        "link",
        "check",
        "numbered",
        "nested",
        "table",
        "break",
    }, seen


def test_red_probe_generator_sees_lost_italic(monkeypatch: pytest.MonkeyPatch) -> None:
    # Ein verlustbehafteter Konverter faellt entweder an einer Pruefung oder
    # erzeugt Markdown, das er selbst nicht mehr lesen kann; beides ist rot.
    monkeypatch.setattr(converter, "_RENDER_STYLES", ("bold", "strike"))
    failures = 0
    for seed in range(60):
        try:
            check_generated(seed)
        except (AssertionError, MarkdownConversionError):
            failures += 1
    assert failures >= 10, failures


# --- Escaping: Text, der wie Markdown aussieht, bleibt Text (§5.3) -------------

_ESCAPE_CASES = [
    "1. kein Listenpunkt",
    "1) auch keiner",
    "- kein Strich",
    "+ kein Plus",
    "# keine Ueberschrift",
    "> kein Zitat",
    "**ohne Gegenstueck",
    "*",
    "a * b * c",
    "snake_case_name",
    "__init__",
    "`einzeln",
    "{{ohne gueltiges Token",
    "{{date:}}",
    "{{Kind:gross}}",
    "[Text](https://who2be.de)",
    "![kein Bild](x.png)",
    "<div>kein HTML</div>",
    "<!-- kein Kommentar -->",
    "&amp; keine Entity",
    "Pfad C:\\Temp\\neu",
    "| keine | Tabelle |",
    "---",
    "___",
    "===",
    "~~kein Strich~~",
    "Text [#keinAnker]",
    "```",
    "Ende mit Backslash\\",
    "<https://who2be.de>",
]


@pytest.mark.parametrize("text", _ESCAPE_CASES)
def test_markdown_lookalike_text_stays_text(text: str) -> None:
    block = {
        "id": "p1",
        "type": "paragraph",
        "props": dict(_DEFAULT),
        "content": [{"type": "text", "text": text, "styles": {}}],
        "children": [],
    }
    md = to_markdown([block])
    rebuilt = from_markdown(md, new_id=lambda existing: "neu")
    assert rebuilt == [{**block, "id": "neu"}], md
    assert normalize(md) == md


@pytest.mark.parametrize(
    ("md", "construct"),
    [
        ("<b>fett</b>", "HTML"),
        ("Text <span>x</span>", "HTML"),
        ("<!-- frei -->", "HTML-Kommentar"),
        ("#### Ebene 4", "Ueberschrift Ebene 4"),
        ("> Zitat", "Zitat"),
        ("***", "Trennlinie"),
        ("![Bild](x.png)", "Bild"),
        ("&uuml;", "HTML-Entity"),
        ("[a]: https://who2be.de", "Referenz-Link-Definition"),
        ("Titel\n===", "Setext-Ueberschrift"),
        ("Absatz [#id-1]", "Anker an einem Block, der keine Ueberschrift ist"),
        ("```\nnie zu", "nicht geschlossene Code-Fence"),
        ("\tTab", "Tabulator-Einrueckung"),
        ("[a [b](x)](y)", "verschachtelter Link"),
        ("[{{date:}}](https://who2be.de)", "Platzhalter in Link"),
        ("| a |\n| :-- |", "Tabellen-Ausrichtung"),
        ("<https://who2be.de>", "HTML"),
        # Review R1 (G3): gaengiges Markdown, das CommonMark/GFM als Struktur
        # liest, darf nicht still zu Text werden.
        ("a | b\n--- | ---\n1 | 2", "Tabellenzeile ohne aeussere Pipes"),
        ("| a | b |\n| --- | --- |\n1 | 2", "Tabellenzeile ohne aeussere Pipes"),
        ("| a | b |\n| --- | --- |\n| 1 | 2 |\nweiter", "Tabellenzeile ohne aeussere Pipes"),
        ("| a | b |\n| --- |", "Tabellen-Trennzeile mit anderer Spaltenzahl als die Kopfzeile"),
        ('[Doku](https://who2be.de "Titel")', "Link mit Titel oder Leerraum im Ziel"),
        ("[Doku](https://who2be.de 'Titel')", "Link mit Titel oder Leerraum im Ziel"),
        ("[Doku](<https://who2be.de>)", "Link-Ziel in spitzen Klammern"),
        ("[Doku](https://who2be.de", "nicht geschlossenes Link-Ziel"),
        ("![Bild](x.png 'Titel')", "Bild"),
        ("_kursiv_", "Hervorhebung mit Unterstrich"),
        ("__fett__ und mehr", "Hervorhebung mit Unterstrich"),
        ("Text _kursiv?_ Ende", "Hervorhebung mit Unterstrich"),
        ("    eingerueckter Code", "eingerueckter Code-Block"),
        ("- Punkt\n\n      zu tief", "eingerueckter Code-Block"),
        ("1. [ ] Aufgabe", "Checkbox in nummerierter Liste"),
    ],
)
def test_unsupported_markdown_is_an_error_not_a_loss(md: str, construct: str) -> None:
    with pytest.raises(MarkdownConversionError) as err:
        from_markdown(md, allow_tables=True)
    assert err.value.reason == "markdown_unsupported"
    assert err.value.construct == construct
    assert err.value.line is not None


def test_gfm_table_without_outer_pipes_is_an_error_even_without_allow_tables() -> None:
    # Ohne Tabellenerlaubnis darf die Struktur ebensowenig still verschwinden.
    with pytest.raises(MarkdownConversionError) as err:
        from_markdown("a | b\n--- | ---\n1 | 2")
    assert err.value.reason == "markdown_unsupported"
    assert err.value.line == 1


@pytest.mark.parametrize(
    ("md", "href"),
    [
        ("[Doku](https://who2be.de/a(b))", "https://who2be.de/a(b)"),
        ("[Doku](https://who2be.de/a\\(b)", "https://who2be.de/a(b"),
        ("[Doku](https://who2be.de/a_(b)_c)", "https://who2be.de/a_(b)_c"),
    ],
)
def test_link_target_with_parentheses_is_kept(md: str, href: str) -> None:
    # CommonMark: ausgeglichene Klammern gehoeren zum Ziel, maskierte ebenso.
    blocks = from_markdown(md, new_id=lambda existing: "neu")
    link = blocks[0]["content"][0]
    assert link["type"] == "link"
    assert link["href"] == href
    assert from_markdown(to_markdown(blocks), base=blocks) == blocks


def test_two_space_hard_break_is_a_line_break() -> None:
    # Entscheidung: zwei Leerzeichen am Zeilenende sind in CommonMark ein
    # harter Umbruch wie `\` (§3.2). Der Dialekt kennt den Umbruch, also wird
    # er abgebildet statt abgelehnt; die Normalform schreibt `\`.
    blocks = from_markdown("Zeile eins  \nZeile zwei", new_id=lambda existing: "neu")
    assert blocks[0]["content"] == [
        {"type": "text", "text": "Zeile eins\nZeile zwei", "styles": {}}
    ]
    assert to_markdown(blocks) == "Zeile eins\\\nZeile zwei"


@pytest.mark.parametrize(
    ("md", "text"),
    [
        ("## Titel ##", "Titel"),
        ("## Titel #####   ", "Titel"),
        ("## C#", "C#"),
        ("## Titel \\#", "Titel #"),
    ],
)
def test_heading_closing_hashes_follow_commonmark(md: str, text: str) -> None:
    blocks = from_markdown(md, new_id=lambda existing: "h1")
    assert blocks[0]["content"] == [{"type": "text", "text": text, "styles": {}}]
    # Rundlauf: ein # am Textende bleibt Text und wird maskiert ausgegeben.
    assert from_markdown(to_markdown(blocks), base=blocks) == blocks


def test_heading_hash_before_anchor_stays_text() -> None:
    # Mit Anker steht die #-Folge nicht am Zeilenende: sie bleibt Text.
    assert normalize("## Titel # [#h1]") == "## Titel \\# [#h1]"


@pytest.mark.parametrize("text", ["_x_", "__init__", "a _b_ c", "Ende_", "___"])
def test_underscore_text_round_trips(text: str) -> None:
    block = {
        "id": "p1",
        "type": "paragraph",
        "props": dict(_DEFAULT),
        "content": [{"type": "text", "text": text, "styles": {}}],
        "children": [],
    }
    md = to_markdown([block])
    assert from_markdown(md, new_id=lambda existing: "neu") == [{**block, "id": "neu"}], md


def test_error_names_the_line() -> None:
    with pytest.raises(MarkdownConversionError) as err:
        from_markdown("## Kopf\n\nText\n\n<b>x</b>")
    assert err.value.line == 5
    assert "Zeile 5" in str(err.value)


def test_lenient_input_is_normalized() -> None:
    md = (
        "* eins\n+ zwei\n3) drei\n\nsnake_case und \\_\\_init\\_\\_\n\n```\nx\n```"
        "\n\nZeile  \nweiter\n\n## Titel ##"
    )
    assert normalize(md) == (
        "- eins\n\n- zwei\n\n1. drei\n\nsnake_case und \\_\\_init__\n\n```text\nx\n```"
        "\n\nZeile\\\nweiter\n\n## Titel"
    )
