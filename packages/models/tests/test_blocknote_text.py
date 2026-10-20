"""Tests fuer die Klartext-Serialisierung von BlockNote-Dokumenten (ADR-0056).

Das Modul ist die eine Quelle fuer Blocks→Text; API (`placeholders._core`,
`services/content_text`) und MCP (`text_view`) nutzen es. Die API-Seite
pruefen weiter ihre eigenen Tests (`apps/api/tests/test_content_text.py`)
ueber die re-exportierten Namen.
"""

import json

from who2be_models.blocknote_text import (
    block_plain_text,
    blocknote_body_text,
    blocks_plain_text,
    format_link,
    format_table,
    parse_blocknote_blocks,
    placeholder_token_inline,
    table_cells,
    text_inline_only,
)


def _para(block_id: str, text: str) -> dict[str, object]:
    return {
        "id": block_id,
        "type": "paragraph",
        "props": {"textAlignment": "left"},
        "content": [{"type": "text", "text": text, "styles": {}}],
        "children": [],
    }


def _pill(kind: str, target_id: str) -> dict[str, object]:
    return {"type": "placeholder", "props": {"kind": kind, "target_id": target_id}}


def test_block_plain_text_concatenates_inlines_and_recurses_children() -> None:
    block: dict[str, object] = {
        "id": "b1",
        "type": "bulletListItem",
        "content": [
            {"type": "text", "text": "Eltern ", "styles": {}},
            {"type": "text", "text": "Text", "styles": {"bold": True}},
        ],
        "children": [_para("c1", "Kind eins"), _para("c2", "Kind zwei")],
    }
    assert block_plain_text(block) == "Eltern Text\nKind eins\nKind zwei"


def test_blocks_plain_text_skips_empty_blocks_and_non_lists() -> None:
    blocks = [_para("b1", "Eins"), _para("b2", "   "), "kein dict", _para("b3", "Drei")]
    assert blocks_plain_text(blocks) == "Eins\n\nDrei"
    assert blocks_plain_text(None) == ""
    assert blocks_plain_text("alter String") == ""


def test_default_inline_renderer_drops_pills() -> None:
    block: dict[str, object] = {
        "id": "b1",
        "type": "paragraph",
        "content": [_pill("playbook", "abc")],
    }
    assert text_inline_only(_pill("playbook", "abc")) == ""
    assert block_plain_text(block) == ""


def test_token_inline_renderer_shows_pills_as_stable_tokens() -> None:
    assert placeholder_token_inline(_pill("resource", "r-1")) == "{{resource:r-1}}"
    assert placeholder_token_inline({"type": "mention"}) == ""
    assert placeholder_token_inline({"type": "placeholder", "props": "kaputt"}) == "{{:}}"


def test_parse_blocknote_blocks_accepts_both_shapes() -> None:
    array_body = json.dumps([_para("b1", "A")])
    wrapper_body = json.dumps({"content": [_para("b1", "A")]})
    assert parse_blocknote_blocks(array_body)[0] == [_para("b1", "A")]
    assert parse_blocknote_blocks(wrapper_body)[0] == [_para("b1", "A")]


def test_parse_blocknote_blocks_returns_raw_for_non_documents() -> None:
    assert parse_blocknote_blocks("") == (None, "")
    assert parse_blocknote_blocks("  nur Text  ") == (None, "nur Text")
    assert parse_blocknote_blocks("42") == (None, "42")


def test_blocknote_body_text_renders_pills_as_tokens_by_default() -> None:
    body = json.dumps(
        [
            {
                "id": "b1",
                "type": "paragraph",
                "content": [{"type": "text", "text": "Nutze "}, _pill("playbook", "p-1")],
            },
            _para("b2", 'Mit "Anfuehrungszeichen" und / Slash'),
        ]
    )
    text = blocknote_body_text(body)
    assert text == 'Nutze {{playbook:p-1}}\n\nMit "Anfuehrungszeichen" und / Slash'
    # Kein Editor-JSON im Ergebnis.
    assert '"type"' not in text


def test_blocknote_body_text_accepts_other_inline_renderer() -> None:
    inlines = [{"type": "text", "text": "A"}, _pill("x", "y")]
    body = json.dumps([{"id": "b1", "type": "paragraph", "content": inlines}])
    assert blocknote_body_text(body, text_inline_only) == "A"


def test_blocknote_body_text_falls_back_to_raw_text() -> None:
    assert blocknote_body_text("kein json") == "kein json"


# --- Tabellen und Links (Editor-Fix) ----------------------------------------


def _txt(text: str) -> dict[str, object]:
    return {"type": "text", "text": text, "styles": {}}


def _link(text: str, href: str) -> dict[str, object]:
    return {"type": "link", "href": href, "content": [_txt(text)]}


def _table(block_id: str, rows: list[list[object]]) -> dict[str, object]:
    return {
        "id": block_id,
        "type": "table",
        "props": {},
        "content": {
            "type": "tableContent",
            "columnWidths": [None, None],
            "rows": [{"cells": cells} for cells in rows],
        },
        "children": [],
    }


def test_table_block_renders_as_gfm_table() -> None:
    table = _table(
        "t1",
        [
            [[_txt("Stufe")], [_txt("Frist")]],
            [[_txt("Mahnung")], [_txt("14 "), _txt("Tage")]],
            [[_txt("Pipe | drin")]],
        ],
    )
    assert block_plain_text(table) == (
        "| Stufe | Frist |\n| --- | --- |\n| Mahnung | 14 Tage |\n| Pipe \\| drin |  |"
    )


def test_table_accepts_tablecell_objects_and_flattens_newlines() -> None:
    cell = {"type": "tableCell", "props": {}, "content": [_txt("zwei\nZeilen")]}
    assert block_plain_text(_table("t1", [[cell]])) == "| zwei Zeilen |\n| --- |"


def test_table_cells_render_links_and_pills_per_inline_renderer() -> None:
    table = _table("t1", [[[_link("Doku", "https://x.de")], [_pill("resource", "r-1")]]])
    assert block_plain_text(table) == "| Doku (https://x.de) |  |\n| --- | --- |"
    assert block_plain_text(table, placeholder_token_inline) == (
        "| Doku (https://x.de) | {{resource:r-1}} |\n| --- | --- |"
    )


def test_nested_table_in_children_and_in_block_list() -> None:
    parent = _para("p1", "Vorher")
    parent["children"] = [_table("t1", [[[_txt("A")], [_txt("B")]]])]
    assert blocks_plain_text([parent, _para("p2", "Nachher")]) == (
        "Vorher\n| A | B |\n| --- | --- |\n\nNachher"
    )


def test_empty_or_broken_table_and_unknown_content_yield_no_text() -> None:
    assert block_plain_text(_table("t1", [])) == ""
    broken: dict[str, object] = {
        "id": "t2",
        "type": "table",
        "content": {"type": "tableContent", "rows": "x"},
    }
    assert block_plain_text(broken) == ""
    assert block_plain_text({"id": "i", "type": "image", "content": "kaputt"}) == ""
    assert block_plain_text({"id": "c", "type": "paragraph", "children": "kaputt"}) == ""


def test_link_renders_as_text_with_url_in_both_inline_renderers() -> None:
    block: dict[str, object] = {
        "id": "b1",
        "type": "paragraph",
        "content": [_txt("Siehe "), _link("Doku", "https://x.de")],
    }
    assert block_plain_text(block) == "Siehe Doku (https://x.de)"
    assert block_plain_text(block, placeholder_token_inline) == "Siehe Doku (https://x.de)"


def test_link_edge_cases() -> None:
    assert text_inline_only(_link("https://x.de", "https://x.de")) == "https://x.de"
    empty_text: dict[str, object] = {"type": "link", "href": "https://x.de", "content": []}
    assert text_inline_only(empty_text) == "https://x.de"
    assert text_inline_only({"type": "link", "content": [_txt("ohne Ziel")]}) == "ohne Ziel"
    string_content: dict[str, object] = {"type": "link", "href": "https://x.de", "content": "Kurz"}
    assert text_inline_only(string_content) == "Kurz (https://x.de)"


def test_format_helpers() -> None:
    assert format_link(" Text ", " https://x.de ") == "Text (https://x.de)"
    assert format_table([]) == ""
    assert format_table([["a"], ["b", "c"]]) == "| a |  |\n| --- | --- |\n| b | c |"
    assert table_cells([{"type": "text"}]) is None
    broken_cell = {"type": "tableContent", "rows": [{"cells": [{"content": "x"}]}]}
    assert table_cells(broken_cell) == [[[]]]
