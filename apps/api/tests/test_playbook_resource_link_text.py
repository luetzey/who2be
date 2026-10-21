"""Klartext der Block-Refs (`block_plain_text`, `block_section_text`) mit Tabellen.

Folge #994: Ein Tabellenblock traegt `content` als `tableContent`-Objekt. Die
Vorschau und der Section-Text (den der Resource-Resolver an den Agenten gibt)
uebersahen die Zellen und lieferten leeren Text. Jetzt wird die Tabelle wie in
Renderer und Passagen als GFM-Tabelle ausgegeben (Single Source
`who2be_models.blocknote_text`), auch verschachtelt in `children`.
"""

from who2be_api.repositories.playbook_resource_link_repository import (
    block_plain_text,
    block_section_text,
)


def _text(value: str) -> dict[str, object]:
    return {"type": "text", "text": value, "styles": {}}


def _pill() -> dict[str, object]:
    return {"type": "placeholder", "props": {"kind": "resource", "target_id": "abc"}}


def _table(rows: list[list[object]], block_id: str = "t1") -> dict[str, object]:
    return {
        "id": block_id,
        "type": "table",
        "content": {"type": "tableContent", "rows": [{"cells": cells} for cells in rows]},
        "children": [],
    }


_TABLE = _table(
    [
        [[_text("Name")], {"type": "tableCell", "content": [_text("Wert")]}],
        [[_text("A|B")], [_text("Siehe "), _pill()]],
    ]
)
_GFM = "| Name | Wert |\n| --- | --- |\n| A\\|B | Siehe |"


def test_table_block_renders_as_gfm() -> None:
    assert block_plain_text(_TABLE) == _GFM


def test_table_nested_in_children_is_on_its_own_lines() -> None:
    block = {
        "id": "p1",
        "type": "bulletListItem",
        "content": [_text("Vorher")],
        "children": [_TABLE, {"id": "p2", "type": "paragraph", "content": [_text("Nachher")]}],
    }
    assert block_plain_text(block) == f"Vorher\n{_GFM}\nNachher"


def test_section_text_includes_table_under_heading() -> None:
    heading = {
        "id": "h1",
        "type": "heading",
        "props": {"level": 2},
        "content": [_text("Kapitel")],
    }
    ids, text = block_section_text([heading, _TABLE], "h1")
    assert ids == ["h1", "t1"]
    assert text == f"Kapitel\n\n{_GFM}"


def test_text_only_blocks_unchanged() -> None:
    """Bestand ohne Tabelle: Texte werden weiter ohne Trenner aneinandergehaengt."""
    block = {
        "id": "p1",
        "type": "paragraph",
        "content": [_text("Hallo "), _text("Welt")],
        "children": [{"id": "c1", "type": "paragraph", "content": [_text("!")]}],
    }
    assert block_plain_text(block) == "Hallo Welt!"
