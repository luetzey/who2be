"""Golden-Tests des BlockNote<->Markdown-Konverters ueber den Bestand (ADR-0058 §5.3, P1).

Jede verwaltete Inhaltsdatei unter `apps/api/src/who2be_api/repositories/`
(DE und EN, per Glob: eine neue Datei laeuft automatisch mit) muss bestehen:

- **G1** `from_markdown(to_markdown(B), base=B) == B`, bitgleich.
- **G2** `to_markdown` liefert die Normalform (`normalize` aendert nichts),
  und Markdown ohne Anker baut ein Dokument mit demselben sichtbaren Inhalt.
- **Kein stiller Verlust**: ohne Basis zurueckgebaut zeigt das Dokument
  denselben Inhalt wie das Original (`visible_content`). Das ist die Pruefung,
  die die Rot-Probe sieht; G1 allein saehe sie nicht, weil die Zuordnung
  unveraenderte Bloecke aus der Basis uebernimmt.
- **M5**: Markdown als Argument ist mindestens um `M5_MIN_RATIO` kleiner als
  das Editor-JSON (ADR-0058 §8.3).

Dazu die Tabellen-Golden-Faelle aus §3.4 und die Rot-Probe.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

import pytest

import who2be_models.blocknote_markdown as converter
from who2be_models.blocknote_markdown import (
    BLOCKNOTE_VERSION,
    MarkdownConversionError,
    from_markdown,
    normalize,
    to_markdown,
    visible_content,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CONTENT_DIR = _REPO_ROOT / "apps/api/src/who2be_api/repositories"
_CONTENT_FILES = sorted(_CONTENT_DIR.glob("**/*.json"))
_MODE_FIELDS = ("identity_add", "output_style_override", "anti_patterns")
_ANCHOR_RE = re.compile(r" \[#[^\]\s]+\]$", re.MULTILINE)

#: Kleinstes gemessenes Verhaeltnis Editor-JSON/Markdown ueber den Bestand,
#: abgerundet (gemessen 2026-10-20: 1,71 bei
#: `builder_playbook_feedback_session_body.json`, Mittel 2,3). Die Schaetzung
#: der ADR (§8.2/§8.3: 1,8) lag knapp darueber; die Normalform setzt zwischen
#: Listenpunkten eine Leerzeile (§5.2).
M5_MIN_RATIO = 1.7


def _documents(path: Path) -> list[tuple[str, list[dict[str, Any]]]]:
    """Alle BlockNote-Dokumente einer Datei: Body bzw. die drei Felder je Modus."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list) and data and "type" in data[0]:
        return [("body", data)]
    docs: list[tuple[str, list[dict[str, Any]]]] = []
    for mode in data:
        for field in _MODE_FIELDS:
            docs.append((f"{mode['name']}.{field}", mode[field]))
    return docs


def _rel(path: Path) -> str:
    return str(path.relative_to(_CONTENT_DIR))


_DOCS = [
    (f"{_rel(path)}:{label}", blocks)
    for path in _CONTENT_FILES
    for label, blocks in _documents(path)
]


def _counter_ids() -> Any:
    counter = iter(range(1, 1_000_000))
    return lambda existing: f"neu{next(counter)}"


def _strip_heading_ids(content: list[Any]) -> list[Any]:
    """`visible_content` ohne Ueberschriften-IDs (neu gebaute Dokumente haben neue)."""
    out: list[Any] = []
    for entry in content:
        if entry[0] == "marker":
            out.append(entry)
            continue
        block_type, props, inline, children = entry
        if block_type == "heading":
            props = {k: v for k, v in props.items() if k != "id"}
        out.append((block_type, props, inline, _strip_heading_ids(children)))
    return out


def _check_document(blocks: list[dict[str, Any]], *, allow_tables: bool = False) -> None:
    """G1, G2 und kein stiller Verlust fuer ein Dokument (wirft AssertionError)."""
    original = copy.deepcopy(blocks)
    md = to_markdown(blocks)
    assert from_markdown(md, base=blocks, allow_tables=allow_tables) == original, "G1"
    assert blocks == original, "Konverter hat die Basis veraendert"
    assert normalize(md) == md, "G2: to_markdown ist nicht in Normalform"
    unanchored = _ANCHOR_RE.sub("", md)
    rebuilt = from_markdown(unanchored, allow_tables=True, new_id=_counter_ids())
    assert _ANCHOR_RE.sub("", to_markdown(rebuilt)) == unanchored, "G2"
    assert _strip_heading_ids(visible_content(rebuilt)) == _strip_heading_ids(
        visible_content(original)
    ), "Verlust: ohne Basis zurueckgebaut zeigt das Dokument anderen Inhalt"


def test_bestand_is_found() -> None:
    # 17 DE + 17 EN laut ADR-0058 §1.5; der Glob nimmt neue Dateien mit.
    assert len(_CONTENT_FILES) >= 34
    assert any(path.parent.name == "en" for path in _CONTENT_FILES)


@pytest.mark.parametrize(("label", "blocks"), _DOCS, ids=[label for label, _ in _DOCS])
def test_golden_bestand(label: str, blocks: list[dict[str, Any]]) -> None:
    _check_document(blocks)


@pytest.mark.parametrize(("label", "blocks"), _DOCS, ids=[label for label, _ in _DOCS])
def test_bestand_has_no_protected_markers(label: str, blocks: list[dict[str, Any]]) -> None:
    # Der verwaltete Bestand ist vollstaendig abbildbar (§1.5).
    assert "<!-- w2b:" not in to_markdown(blocks)


def test_m5_markdown_argument_is_smaller() -> None:
    ratios: dict[str, float] = {}
    for path in _CONTENT_FILES:
        for label, blocks in _documents(path):
            if label != "body":
                continue
            json_arg = len(json.dumps(json.dumps(blocks)).encode())
            md_arg = len(json.dumps(to_markdown(blocks)).encode())
            ratios[_rel(path)] = json_arg / md_arg
    worst = min(ratios, key=ratios.__getitem__)
    assert ratios[worst] >= M5_MIN_RATIO, f"{worst}: {ratios[worst]:.2f}"


# Haelt die Typlisten des Konverters an der installierten BlockNote-Version
# fest (ADR-0058 §3.3). Ein Update reisst hier, bis jemand
# REPRESENTABLE/NON_REPRESENTABLE_BLOCK_TYPES neu geprueft hat.
# effect-exempt: Versions-Waechter gegen package-lock.json, hat keinen Prueflung
def test_blocknote_version_matches_lockfile() -> None:
    lock = json.loads((_REPO_ROOT / "apps/web/package-lock.json").read_text(encoding="utf-8"))
    assert lock["packages"]["node_modules/@blocknote/core"]["version"] == BLOCKNOTE_VERSION


# --- Tabellen (§3.4) --------------------------------------------------------


def _txt(text: str, **styles: bool) -> dict[str, Any]:
    return {"type": "text", "text": text, "styles": styles}


def _cell(*inlines: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "tableCell",
        "props": {
            "backgroundColor": "default",
            "textColor": "default",
            "textAlignment": "left",
            "colspan": 1,
            "rowspan": 1,
        },
        "content": list(inlines),
    }


def _table(block_id: str, rows: list[list[dict[str, Any]]], **extra: Any) -> dict[str, Any]:
    content: dict[str, Any] = {
        "type": "tableContent",
        "columnWidths": [180, None, 96],
        "headerRows": 1,
        "rows": [{"cells": cells} for cells in rows],
    }
    content.update(extra)
    return {
        "id": block_id,
        "type": "table",
        "props": {"textColor": "default"},
        "content": content,
        "children": [],
    }


def _heading(block_id: str, text: str, level: int = 2) -> dict[str, Any]:
    return {
        "id": block_id,
        "type": "heading",
        "props": {
            "textColor": "default",
            "backgroundColor": "default",
            "textAlignment": "left",
            "level": level,
        },
        "content": [_txt(text)],
        "children": [],
    }


def _golden_table() -> dict[str, Any]:
    link = {"type": "link", "href": "https://who2be.de", "content": [_txt("Doku")]}
    return _table(
        "tab-1",
        [
            [_cell(_txt("Stufe")), _cell(_txt("Regel")), _cell(_txt("Verweis"))],
            [
                _cell(_txt("Mahnung", bold=True)),
                _cell(_txt("a | b")),
                _cell(_txt("Siehe "), link),
            ],
            [_cell(_txt("frist_tage", code=True)), _cell(), _cell(_txt("*nicht* kursiv"))],
        ],
    )


_GOLDEN_TABLE_MD = (
    "| Stufe | Regel | Verweis |\n"
    "| --- | --- | --- |\n"
    "| **Mahnung** | a \\| b | Siehe [Doku](https://who2be.de) |\n"
    "| `frist_tage` |  | \\*nicht\\* kursiv |"
)


def test_table_golden_renders_gfm() -> None:
    assert to_markdown([_golden_table()]) == _GOLDEN_TABLE_MD


def test_table_golden_g1_g2() -> None:
    doc = [_heading("h-tab", "Fristen"), _golden_table()]
    _check_document(doc, allow_tables=True)
    # G1 auch ohne Tabellenrecht: unveraendert bleibt bitgleich (§3.4).
    assert from_markdown(to_markdown(doc), base=doc) == doc


def test_table_edit_keeps_widths_and_header_from_base() -> None:
    doc = [_heading("h-tab", "Fristen"), _golden_table()]
    edited = to_markdown(doc).replace("Mahnung", "Erinnerung")
    result = from_markdown(edited, base=doc, allow_tables=True)
    table = result[1]
    assert table["id"] == "tab-1"
    assert table["content"]["columnWidths"] == [180, None, 96]
    assert table["content"]["headerRows"] == 1
    assert table["content"]["rows"][1]["cells"][0]["content"] == [_txt("Erinnerung", bold=True)]


def test_table_new_column_count_falls_back_to_default_widths() -> None:
    doc = [_heading("h-tab", "Fristen"), _golden_table()]
    md = "## Fristen [#h-tab]\n\n| a | b |\n| --- | --- |\n| 1 | 2 |"
    table = from_markdown(md, base=doc, allow_tables=True)[1]
    assert table["id"] == "tab-1"
    assert table["content"]["columnWidths"] == [None, None]
    assert "headerRows" not in table["content"]


def test_locked_table_with_pill_appears_as_marker() -> None:
    pill = {"type": "placeholder", "props": {"kind": "date", "target_id": "", "label": "Datum"}}
    locked = _table("tab-pill", [[_cell(_txt("Stand ")), _cell(pill)]])
    doc = [_heading("h", "Text"), locked]
    md = to_markdown(doc)
    assert (
        md == "## Text [#h]\n\n<!-- w2b:block tab-pill table -->\n"
        "> | Stand | {{date:}} |\n> | --- | --- |"
    )
    assert from_markdown(md, base=doc) == doc
    with pytest.raises(MarkdownConversionError) as err:
        from_markdown(md.replace("Stand", "Stand neu"), base=doc)
    assert err.value.reason == "block_not_representable"
    assert err.value.block_id == "tab-pill"


def test_table_in_playbook_unchanged_is_bitgleich_changed_is_422() -> None:
    doc = [_heading("h-tab", "Fristen"), _golden_table()]
    md = to_markdown(doc)
    assert from_markdown(md, base=doc, allow_tables=False) == doc
    with pytest.raises(MarkdownConversionError) as err:
        from_markdown(md.replace("Mahnung", "Erinnerung"), base=doc, allow_tables=False)
    assert err.value.reason == "markdown_unsupported"
    with pytest.raises(MarkdownConversionError):
        from_markdown("| a |\n| --- |\n| 1 |", allow_tables=False)


def test_pill_in_new_table_cell_is_rejected() -> None:
    with pytest.raises(MarkdownConversionError) as err:
        from_markdown("| a |\n| --- |\n| {{date:}} |", allow_tables=True)
    assert err.value.reason == "markdown_unsupported"
    assert err.value.construct == "Platzhalter in Tabellenzelle"


# --- Rot-Probe (§5.3) ---------------------------------------------------------


def test_red_probe_lossy_converter_breaks_golden_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ein Konverter, der Fettdruck verwirft, muss die Golden-Tests reissen.

    Der Bestand traegt Fett (298x), aber kein Kursiv; die Rot-Probe fuer
    Kursiv laeuft in `test_blocknote_markdown_generated.py` und am Tabellen-Fall.
    """
    monkeypatch.setattr(converter, "_RENDER_STYLES", ("italic", "strike"))
    broken = [label for label, blocks in _DOCS if _fails(blocks)]
    assert len(broken) >= 20, broken


def test_red_probe_lossy_italic_breaks_table_golden(monkeypatch: pytest.MonkeyPatch) -> None:
    italic_table = _golden_table()
    italic_table["content"]["rows"][2]["cells"][2]["content"] = [_txt("kursiv", italic=True)]
    doc = [_heading("h", "T"), italic_table]
    _check_document(doc, allow_tables=True)
    monkeypatch.setattr(converter, "_RENDER_STYLES", ("bold", "strike"))
    assert _fails(doc, allow_tables=True)


def _fails(blocks: list[dict[str, Any]], *, allow_tables: bool = False) -> bool:
    try:
        _check_document(blocks, allow_tables=allow_tables)
    except AssertionError:
        return True
    return False
