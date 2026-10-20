"""Block-IDs und nicht abbildbare Bloecke im Markdown-Konverter (ADR-0058 §3.3, §4.2, §4.3).

Tabellentests mit erwarteter ID-Liste: umbenennen, verschieben, einfuegen,
loeschen, doppelte Absaetze. Dazu die Anker-Fehler und die geschuetzten
Marker fuer nicht abbildbare Bloecke.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from who2be_models.blocknote_markdown import (
    NON_REPRESENTABLE_BLOCK_TYPES,
    REPRESENTABLE_BLOCK_TYPES,
    MarkdownConversionError,
    block_representability,
    default_new_block_id,
    from_markdown,
    to_markdown,
)

_DEFAULT = {"textColor": "default", "backgroundColor": "default", "textAlignment": "left"}


def _txt(text: str, **styles: bool) -> dict[str, Any]:
    return {"type": "text", "text": text, "styles": styles}


def _h(block_id: str, text: str, level: int = 2) -> dict[str, Any]:
    return {
        "id": block_id,
        "type": "heading",
        "props": {**_DEFAULT, "level": level},
        "content": [_txt(text)],
        "children": [],
    }


def _p(block_id: str, text: str, block_type: str = "paragraph", **props: Any) -> dict[str, Any]:
    return {
        "id": block_id,
        "type": block_type,
        "props": {**_DEFAULT, **props},
        "content": [_txt(text)],
        "children": [],
    }


def _ids(blocks: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for block in blocks:
        out.append(block["id"])
        out.extend(f"{block['id']}/{child}" for child in _ids(block["children"]))
    return out


def _new_ids() -> Any:
    counter = iter(range(1, 1000))
    return lambda existing: f"n{next(counter)}"


BASE = [
    _p("intro", "Einleitung"),
    _h("h-a", "Abschnitt A"),
    _p("a1", "Erster Absatz"),
    _p("a2", "Zweiter Absatz"),
    _p("a3", "Punkt", "bulletListItem"),
    _h("h-b", "Abschnitt B"),
    _p("b1", "Gleich"),
    _p("b2", "Gleich"),
]

_BASE_MD = to_markdown(BASE)


def test_base_markdown_shape() -> None:
    assert _BASE_MD == (
        "Einleitung\n\n"
        "## Abschnitt A [#h-a]\n\n"
        "Erster Absatz\n\n"
        "Zweiter Absatz\n\n"
        "- Punkt\n\n"
        "## Abschnitt B [#h-b]\n\n"
        "Gleich\n\n"
        "Gleich"
    )


_CASES: list[tuple[str, str, list[str]]] = [
    ("unveraendert", _BASE_MD, ["intro", "h-a", "a1", "a2", "a3", "h-b", "b1", "b2"]),
    (
        "Ueberschrift umbenannt und Ebene geaendert",
        _BASE_MD.replace("## Abschnitt A [#h-a]", "### Neuer Name [#h-a]"),
        ["intro", "h-a", "a1", "a2", "a3", "h-b", "b1", "b2"],
    ),
    (
        "Abschnitte vertauscht",
        "Einleitung\n\n## Abschnitt B [#h-b]\n\nGleich\n\nGleich\n\n"
        "## Abschnitt A [#h-a]\n\nErster Absatz\n\nZweiter Absatz\n\n- Punkt",
        ["intro", "h-b", "b1", "b2", "h-a", "a1", "a2", "a3"],
    ),
    (
        "Absatz geaendert an gleicher Stelle",
        _BASE_MD.replace("Zweiter Absatz", "Zweiter Absatz, neu"),
        ["intro", "h-a", "a1", "a2", "a3", "h-b", "b1", "b2"],
    ),
    (
        "Absatz im Abschnitt verschoben",
        _BASE_MD.replace("Erster Absatz\n\nZweiter Absatz", "Zweiter Absatz\n\nErster Absatz"),
        ["intro", "h-a", "a2", "a1", "a3", "h-b", "b1", "b2"],
    ),
    (
        "Absatz geaendert und verschoben bekommt neue ID",
        _BASE_MD.replace(
            "Erster Absatz\n\nZweiter Absatz\n\n- Punkt",
            "- Punkt\n\nErster Absatz, neu\n\nZweiter Absatz",
        ),
        ["intro", "h-a", "a3", "n1", "a2", "h-b", "b1", "b2"],
    ),
    (
        "Absatz eingefuegt",
        _BASE_MD.replace("Erster Absatz\n\n", "Erster Absatz\n\nEingeschoben\n\n"),
        ["intro", "h-a", "a1", "n1", "a2", "a3", "h-b", "b1", "b2"],
    ),
    (
        "Absatz geloescht",
        _BASE_MD.replace("Zweiter Absatz\n\n", ""),
        ["intro", "h-a", "a1", "a3", "h-b", "b1", "b2"],
    ),
    (
        "neue Ueberschrift ohne Anker",
        _BASE_MD + "\n\n## Abschnitt C\n\nNeu",
        ["intro", "h-a", "a1", "a2", "a3", "h-b", "b1", "b2", "n1", "n2"],
    ),
    (
        "doppelte Absaetze der Reihe nach",
        _BASE_MD + "\n\nGleich",
        ["intro", "h-a", "a1", "a2", "a3", "h-b", "b1", "b2", "n1"],
    ),
    (
        "erster von zwei gleichen Absaetzen geloescht",
        _BASE_MD.replace("Gleich\n\nGleich", "Gleich"),
        ["intro", "h-a", "a1", "a2", "a3", "h-b", "b1"],
    ),
    (
        "Absatz in anderen Abschnitt verschoben bekommt neue ID",
        _BASE_MD.replace("Erster Absatz\n\n", "") + "\n\nErster Absatz",
        ["intro", "h-a", "a2", "a3", "h-b", "b1", "b2", "n1"],
    ),
    (
        "Ueberschrift entfernt: Absaetze ruecken in den vorigen Abschnitt",
        _BASE_MD.replace("## Abschnitt B [#h-b]\n\n", ""),
        ["intro", "h-a", "a1", "a2", "a3", "n1", "n2"],
    ),
    (
        "Typwechsel an gleicher Stelle: neue ID",
        _BASE_MD.replace("- Punkt", "1. Punkt"),
        ["intro", "h-a", "a1", "a2", "n1", "h-b", "b1", "b2"],
    ),
]


@pytest.mark.parametrize(("name", "md", "expected"), _CASES, ids=[c[0] for c in _CASES])
def test_id_assignment(name: str, md: str, expected: list[str]) -> None:
    assert _ids(from_markdown(md, base=BASE, new_id=_new_ids())) == expected


def test_unchanged_block_keeps_props_markdown_does_not_show() -> None:
    sparse = {
        "id": "x",
        "type": "paragraph",
        "props": {},
        "content": [_txt("knapp")],
        "children": [],
    }
    base = [_h("h", "Kopf"), sparse]
    assert from_markdown(to_markdown(base), base=base)[1] is not sparse
    assert from_markdown(to_markdown(base), base=base)[1] == sparse


def test_changed_block_keeps_base_props_and_takes_visible_ones() -> None:
    base = [_p("c1", "offen", "checkListItem", checked=False)]
    result = from_markdown("- [x] erledigt", base=base)
    assert result == [
        {
            "id": "c1",
            "type": "checkListItem",
            "props": {**_DEFAULT, "checked": True},
            "content": [_txt("erledigt")],
            "children": [],
        }
    ]


def test_heading_change_keeps_children_and_section() -> None:
    parent = _p("li", "Eltern", "numberedListItem")
    parent["children"] = [
        _p("k1", "Kind eins", "bulletListItem"),
        _p("k2", "Kind zwei", "bulletListItem"),
    ]
    base = [_h("h", "Kopf"), parent]
    md = to_markdown(base).replace("Kind zwei", "Kind zwei, neu")
    result = from_markdown(md, base=base)
    assert _ids(result) == ["h", "li", "li/k1", "li/k2"]
    # Nur das Kind hat sich geaendert: der Elternblock bleibt bitgleich bis auf die Kinder.
    assert result[1]["content"] == parent["content"]
    assert result[1]["props"] is not parent["props"]
    assert result[1]["children"][0] == parent["children"][0]


def test_new_pill_gets_label_from_resolver_known_pill_keeps_label() -> None:
    pill = {
        "type": "placeholder",
        "props": {"kind": "persona-field", "target_id": "name", "label": "Persona: Name"},
    }
    base = [{**_p("p", ""), "content": [_txt("Du bist "), pill]}]
    md = to_markdown(base) + " und {{playbook:0f8c}}"
    result = from_markdown(md, base=base, resolve_label=lambda kind, target: f"Playbook {target}")
    content = result[0]["content"]
    assert content[1]["props"]["label"] == "Persona: Name"
    assert content[3]["props"] == {
        "kind": "playbook",
        "target_id": "0f8c",
        "label": "Playbook 0f8c",
    }
    unresolved = from_markdown("{{date:}}", resolve_label=lambda kind, target: None)
    assert unresolved[0]["content"][0]["props"]["label"] == "date:"


def test_resource_section_pill_round_trips() -> None:
    md = "Siehe {{resource:3f1c#h-zweck}}"
    result = from_markdown(md, new_id=_new_ids())
    assert result[0]["content"][1]["props"]["target_id"] == "3f1c#h-zweck"
    assert to_markdown(result) == md


# --- Anker-Fehler (§4.2) -----------------------------------------------------


def test_unknown_anchor_is_rejected() -> None:
    with pytest.raises(MarkdownConversionError) as err:
        from_markdown("## Erfunden [#gibt-es-nicht]", base=BASE)
    assert err.value.reason == "anchor_unknown"
    assert err.value.block_id == "gibt-es-nicht"
    assert err.value.line == 1


def test_any_anchor_on_create_is_unknown() -> None:
    with pytest.raises(MarkdownConversionError) as err:
        from_markdown("## Kopiert [#h-a]\n\nText", base=None)
    assert err.value.reason == "anchor_unknown"


def test_anchor_pointing_to_a_paragraph_is_unknown() -> None:
    with pytest.raises(MarkdownConversionError) as err:
        from_markdown("## Kein Kopf [#a1]", base=BASE)
    assert err.value.reason == "anchor_unknown"


def test_duplicate_anchor_is_rejected() -> None:
    with pytest.raises(MarkdownConversionError) as err:
        from_markdown("## A [#h-a]\n\n## B [#h-a]", base=BASE)
    assert err.value.reason == "anchor_duplicate"
    assert err.value.line == 3


def test_new_ids_do_not_collide_with_base_or_anchors() -> None:
    taken = {"intro", "h-a", "a1", "a2", "a3", "h-b", "b1", "b2"}
    seen: list[set[str]] = []

    def spy(existing: set[str]) -> str:
        seen.append(set(existing))
        return default_new_block_id(existing)

    result = from_markdown(_BASE_MD + "\n\nNeu", base=BASE, new_id=spy)
    assert taken <= seen[0]
    assert result[-1]["id"] not in taken
    assert len(result[-1]["id"]) == 8


def test_default_new_block_id_avoids_existing() -> None:
    first = default_new_block_id(set())
    assert len(first) == 8 and first.isalnum()


# --- Nicht abbildbare Bloecke (§3.3) ------------------------------------------


def _image(block_id: str) -> dict[str, Any]:
    return {
        "id": block_id,
        "type": "image",
        "props": {**_DEFAULT, "url": "https://who2be.de/a.png", "caption": "Logo"},
        "content": None,
        "children": [],
    }


def _underlined(block_id: str) -> dict[str, Any]:
    return {
        "id": block_id,
        "type": "paragraph",
        "props": dict(_DEFAULT),
        "content": [_txt("wichtig", underline=True), _txt(" Hinweis")],
        "children": [],
    }


def test_type_lists_cover_blocknote_default_schema() -> None:
    # @blocknote/core 0.56.0, `defaultBlockSpecs` (BLOCKNOTE_VERSION haelt der Golden-Test fest).
    assert REPRESENTABLE_BLOCK_TYPES | NON_REPRESENTABLE_BLOCK_TYPES == {
        "audio",
        "bulletListItem",
        "checkListItem",
        "codeBlock",
        "divider",
        "file",
        "heading",
        "image",
        "numberedListItem",
        "paragraph",
        "quote",
        "table",
        "toggleListItem",
        "video",
    }
    assert not REPRESENTABLE_BLOCK_TYPES & NON_REPRESENTABLE_BLOCK_TYPES


@pytest.mark.parametrize(
    ("block", "expected"),
    [
        (_p("ok", "Text"), "ok"),
        (_image("img"), "block"),
        ({**_p("q", "Zitat"), "type": "quote"}, "block"),
        ({**_p("t", "Toggle"), "type": "toggleListItem"}, "block"),
        ({**_p("x", "Neu"), "type": "kommtNochTyp"}, "block"),
        (_underlined("u"), "locked"),
        ({**_p("c", "Farbe"), "props": {**_DEFAULT, "textColor": "red"}}, "locked"),
        ({**_p("r", "rechts"), "props": {**_DEFAULT, "textAlignment": "right"}}, "locked"),
        (_h("h4", "tief", level=4), "locked"),
        ({**_p("e", "leer"), "content": []}, "locked"),
        ({**_p("w", "x"), "content": [_txt(" Leerraum vorn")]}, "locked"),
        ({**_p("n", "x"), "content": [_txt("a\n  eingerueckt")]}, "locked"),
        ({**_p("s", "x"), "content": [_txt("a``b", code=True)]}, "locked"),
        ({**_p("k", "x"), "content": [_txt("a"), {"type": "mention", "props": {}}]}, "locked"),
        ({**_p("z", "x"), "extra": 1}, "locked"),
        ({**_p("start", "x", "numberedListItem"), "props": {**_DEFAULT, "start": 3}}, "locked"),
    ],
)
def test_representability(block: dict[str, Any], expected: str) -> None:
    assert block_representability(block) == expected


def _doc_with_protected() -> list[dict[str, Any]]:
    return [_h("h", "Kopf"), _p("a", "davor"), _image("img"), _underlined("u"), _p("b", "danach")]


def test_protected_blocks_render_as_markers() -> None:
    assert to_markdown(_doc_with_protected()) == (
        "## Kopf [#h]\n\n"
        "davor\n\n"
        "<!-- w2b:block img image -->\n\n"
        "<!-- w2b:locked u -->\n"
        "> wichtig Hinweis\n\n"
        "danach"
    )


def test_marker_unchanged_keeps_block_bitgleich() -> None:
    doc = _doc_with_protected()
    md = to_markdown(doc).replace("davor", "davor, geaendert")
    result = from_markdown(md, base=doc)
    assert result[2] == doc[2]
    assert result[3] == doc[3]
    assert result[1]["content"] == [_txt("davor, geaendert")]


def test_marker_removed_deletes_block() -> None:
    doc = _doc_with_protected()
    md = to_markdown(doc).replace("<!-- w2b:block img image -->\n\n", "")
    assert _ids(from_markdown(md, base=doc)) == ["h", "a", "u", "b"]


def test_marker_moved_keeps_block() -> None:
    doc = _doc_with_protected()
    md = (
        "## Kopf [#h]\n\n<!-- w2b:block img image -->\n\ndavor\n\n"
        "<!-- w2b:locked u -->\n> wichtig Hinweis\n\ndanach"
    )
    result = from_markdown(md, base=doc)
    assert _ids(result) == ["h", "img", "a", "u", "b"]
    assert result[1] == doc[2]


def test_locked_text_changed_is_rejected() -> None:
    doc = _doc_with_protected()
    md = to_markdown(doc).replace("> wichtig Hinweis", "> wichtig Hinweis, geaendert")
    with pytest.raises(MarkdownConversionError) as err:
        from_markdown(md, base=doc)
    assert err.value.reason == "block_not_representable"
    assert err.value.block_id == "u"


@pytest.mark.parametrize(
    "marker",
    [
        "<!-- w2b:block unbekannt image -->",
        "<!-- w2b:block img video -->",
        "<!-- w2b:locked img -->",
        "<!-- w2b:block a paragraph -->",
    ],
)
def test_marker_with_unknown_id_or_wrong_kind_is_rejected(marker: str) -> None:
    doc = _doc_with_protected()
    with pytest.raises(MarkdownConversionError) as err:
        from_markdown(f"## Kopf [#h]\n\n{marker}", base=doc)
    assert err.value.reason == "block_not_representable"


def test_anchor_into_protected_subtree_is_a_duplicate() -> None:
    # Die Ueberschrift lebt im Teilbaum eines erhaltenen Bildblocks; ein Anker
    # auf sie wuerde denselben Block ein zweites Mal ins Dokument holen.
    parent = _image("img")
    parent["children"] = [_h("hk", "Kind")]
    doc = [_h("h", "Kopf"), parent]
    with pytest.raises(MarkdownConversionError) as err:
        from_markdown(to_markdown(doc) + "\n\n## Kind [#hk]", base=doc)
    assert err.value.reason == "anchor_duplicate"
    assert err.value.block_id == "hk"


def test_marker_twice_is_rejected() -> None:
    doc = _doc_with_protected()
    md = to_markdown(doc) + "\n\n<!-- w2b:block img image -->"
    with pytest.raises(MarkdownConversionError) as err:
        from_markdown(md, base=doc)
    assert err.value.reason == "anchor_duplicate"


def test_protected_children_are_kept_and_cannot_be_edited() -> None:
    parent = _image("img")
    parent["children"] = [_p("kind", "unter dem Bild")]
    doc = [_h("h", "Kopf"), parent]
    md = to_markdown(doc)
    assert md == "## Kopf [#h]\n\n<!-- w2b:block img image -->\n> unter dem Bild"
    assert from_markdown(md, base=doc) == doc
    with pytest.raises(MarkdownConversionError):
        from_markdown(md + "\n\n  eingeschoben", base=doc)


def test_locked_heading_is_no_section_boundary() -> None:
    locked = _h("h4", "tief", level=4)
    doc = [_h("h", "Kopf"), _p("a", "eins"), locked, _p("b", "zwei")]
    md = to_markdown(doc)
    assert "<!-- w2b:locked h4 -->" in md
    edited = md.replace("zwei", "zwei, neu")
    assert _ids(from_markdown(edited, base=doc)) == ["h", "a", "h4", "b"]
    with pytest.raises(MarkdownConversionError) as err:
        from_markdown("## Kopf [#h4]", base=doc)
    assert err.value.reason == "block_not_representable"


def test_base_is_not_mutated() -> None:
    doc = _doc_with_protected()
    snapshot = copy.deepcopy(doc)
    from_markdown(to_markdown(doc).replace("davor", "neu") + "\n\n{{date:}}", base=doc)
    assert doc == snapshot
