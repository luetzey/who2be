"""Laengen-Richtwerte und weiche Warnung (ADR-0063).

- Paritaet: die Zahlen in den Agent-Bau-Konventionen des Builders (DE und EN,
  Tabelle `res-conv-tab-laengen-budgets`) stimmen mit `content_budgets` ueberein.
- Zaehlung: Woerter im Markdown ohne Codebloecke, Anker und reine Markdown-Zeichen.
- Schwellen je Element: knapp darunter kein Hinweis, auf bzw. knapp ueber der
  Schwelle ein Hinweis. Die Schwellen stehen hier als Literale (Owner-Werte W2);
  wird eine Konstante um 1 verschoben, wird der Test rot.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from who2be_models import content_budgets as cb
from who2be_models.blocknote_markdown import to_markdown
from who2be_models.content_markdown import MarkdownWriteResult

_REPO_ROOT = Path(__file__).resolve().parents[3]
_REPOS = _REPO_ROOT / "apps" / "api" / "src" / "who2be_api" / "repositories"
_CONVENTIONS = {
    "de": _REPOS / "builder_resource_conventions_body.json",
    "en": _REPOS / "en" / "builder_resource_conventions_body.json",
}

#: Zeilenfolge der Konventionen-Tabelle -> Konstante.
_ROWS: list[cb.Budget] = [
    cb.PERSONA_PROFILE,
    cb.PERSONA_MODE,
    cb.PERSONA_MODE_COUNT,
    cb.PLAYBOOK_BODY,
    cb.PLAYBOOK_SUMMARY,
    cb.RESOURCE_SECTION,
    cb.STARTLOAD_AGENT_KB,
    cb.STARTLOAD_BUILDER_KB,
]


def _cell_text(cell: dict[str, Any]) -> str:
    return "".join(run.get("text", "") for run in cell.get("content", []))


def _table_rows(locale: str) -> list[list[str]]:
    blocks = json.loads(_CONVENTIONS[locale].read_text(encoding="utf-8"))
    table = next(b for b in blocks if b.get("id") == "res-conv-tab-laengen-budgets")
    rows = table["content"]["rows"][table["content"].get("headerRows", 1) :]
    return [[_cell_text(cell) for cell in row["cells"]] for row in rows]


def _number(text: str) -> int | None:
    found = re.findall(r"\d[\d  ,.]*", text)
    return int(re.sub(r"\D", "", found[0])) if found else None


# effect-exempt: Drift-Guard; Konventionen-Tabelle (Builder-Text) gleich den Konstanten
@pytest.mark.parametrize("locale", ["de", "en"])
def test_conventions_table_matches_constants(locale: str) -> None:
    rows = _table_rows(locale)
    assert len(rows) == len(_ROWS), rows
    for (_label, target, warn), budget in zip(rows, _ROWS, strict=True):
        assert _number(target) == budget.target, (locale, _label, target)
        assert _number(warn) == budget.warn, (locale, _label, warn)


# effect-exempt: Drift-Guard; Einheiten der Konventionen-Tabelle gegen die Konstanten
@pytest.mark.parametrize("locale", ["de", "en"])
def test_conventions_table_units_match(locale: str) -> None:
    unit_words = {
        "de": {"words": "Woerter", "chars": "Zeichen"},
        "en": {"words": "words", "chars": "characters"},
    }[locale]
    for (_label, _target, warn), budget in zip(_table_rows(locale), _ROWS, strict=True):
        if budget.unit in unit_words:
            assert unit_words[budget.unit] in warn, (locale, _label, warn)


# --- Zaehlung ----------------------------------------------------------------


def test_count_words_skips_code_blocks_anchors_and_markup() -> None:
    markdown = (
        "## Titel der Seite [#h-titel]\n\n"
        "- eins zwei\n"
        "- drei\n\n"
        "```python\nprint('nicht gezaehlt')\nmehr code\n```\n\n"
        "| Spalte | B |\n| --- | --- |\n| vier | fuenf |\n\n"
        "---\n\n"
        "~~~\nauch nicht\n~~~\n"
        "sechs, `inline` {{resource:abc}}"
    )
    # Titel der Seite (3) + eins zwei drei (3) + Spalte B vier fuenf (4)
    # + sechs, `inline` {{resource:abc}} (3) = 13
    assert cb.count_words(markdown) == 13


def test_count_words_unclosed_fence_counts_nothing_after_it() -> None:
    assert cb.count_words("eins zwei\n```\ndrei vier") == 2


def test_count_words_skips_protection_markers_but_counts_quoted_text() -> None:
    markdown = "<!-- w2b:locked p1 -->\n> rot gefaerbt\n\n  <!-- w2b:block img image -->\n\nnormal"
    assert cb.count_words(markdown) == 3


#: Gemeinsame Fixture mit dem Web-Laengenzaehler (`EditorFooter.test.tsx`).
_PARITY_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "word_count_parity.json"
_PARITY_CASES = json.loads(_PARITY_FIXTURE.read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", _PARITY_CASES, ids=[c["name"] for c in _PARITY_CASES])
def test_count_words_matches_web_fixture(case: dict[str, Any]) -> None:
    """Server zaehlt dieselben Bloecke gleich wie `countWords` im Web."""
    assert cb.count_words(to_markdown(case["blocks"])) == case["expected_words"]


def test_sections_split_at_every_heading_with_anchor() -> None:
    markdown = "Vorwort hier\n\n# Eins [#h-1]\n\na b c\n\n## Zwei [#h-2]\n\nd e\n\n# Drei\n\nf"
    got = [(s.anchor, s.title, s.words) for s in cb.sections(markdown)]
    assert got == [
        (None, "", 2),
        ("h-1", "Eins", 3),
        ("h-2", "Zwei", 2),
        ("", "Drei", 1),
    ]


def test_heading_inside_code_block_is_not_a_section() -> None:
    markdown = "# A [#h-a]\n\n```\n# kein Abschnitt\n```\n\nx"
    assert [s.anchor for s in cb.sections(markdown)] == ["h-a"]


# --- Schwellen je Element ----------------------------------------------------


def _words(n: int) -> str:
    return " ".join(["wort"] * n)


def _elements(hints: list[cb.LengthHint]) -> list[str]:
    return [hint.element for hint in hints]


def test_profile_below_and_at_threshold() -> None:
    assert cb.persona_hints(_words(599), [], "de") == []
    hints = cb.persona_hints(_words(600), [], "de")
    assert _elements(hints) == ["profile"]
    assert hints[0].value == 600
    assert hints[0].target == 400
    assert hints[0].warn == 600


def test_profile_message_names_count_and_target() -> None:
    (hint,) = cb.persona_hints(_words(1450), [], "de")
    assert hint.message == (
        "Profil 1 450 Wörter, Richtwert 400. Abläufe und Nachschlagewissen "
        "in Playbook/Resource auslagern?"
    )
    (hint_en,) = cb.persona_hints(_words(1450), [], "en")
    assert hint_en.message.startswith("Profile 1,450 words, guide value 400.")


def test_mode_counts_all_text_fields_together() -> None:
    below = [("Refiner", [_words(248), _words(1), ""])]
    assert cb.persona_hints("", below, "de") == []
    at = [("Refiner", [_words(248), _words(1), _words(1)])]
    hints = cb.persona_hints("", at, "de")
    assert _elements(hints) == ["mode"]
    assert hints[0].ref == "Refiner"
    assert hints[0].value == 250
    assert hints[0].target == 150
    assert "„Refiner“" in hints[0].message


def test_mode_count_below_and_at_threshold() -> None:
    modes = [(f"m{i}", ["kurz"]) for i in range(4)]
    assert cb.persona_hints("", modes, "de") == []
    modes.append(("extra", ["kurz"]))
    hints = cb.persona_hints("", modes, "de")
    assert _elements(hints) == ["mode_count"]
    assert hints[0].value == 5
    assert hints[0].target == 3


def test_playbook_body_below_and_at_threshold() -> None:
    assert cb.playbook_hints(_words(1499), "", None, "de") == []
    hints = cb.playbook_hints(_words(1500), "", None, "de")
    assert _elements(hints) == ["playbook_body"]
    assert hints[0].unit == "words"
    assert hints[0].target == 1000


def test_playbook_summary_counts_description_and_triggers_in_chars() -> None:
    assert cb.playbook_hints("", "d" * 489, "t" * 10, "de") == []
    hints = cb.playbook_hints("", "d" * 490, "t" * 10, "de")
    assert _elements(hints) == ["playbook_summary"]
    assert hints[0].value == 500
    assert hints[0].target == 300
    assert hints[0].unit == "chars"


def test_resource_section_warns_only_above_threshold() -> None:
    at = f"# Lang [#h-lang]\n\n{_words(600)}"
    assert cb.resource_hints(at, "de") == []
    above = f"# Kurz [#h-kurz]\n\nx\n\n# Lang [#h-lang]\n\n{_words(601)}"
    hints = cb.resource_hints(above, "de")
    assert _elements(hints) == ["resource_section"]
    assert hints[0].ref == "h-lang"
    assert hints[0].target is None
    assert "„Lang“" in hints[0].message


def test_resource_total_has_no_limit() -> None:
    body = "\n\n".join(f"# A{i} [#h-{i}]\n\n{_words(500)}" for i in range(10))
    assert cb.resource_hints(body, "de") == []


def test_write_result_has_empty_length_hints_by_default() -> None:
    field = MarkdownWriteResult.model_fields["length_hints"]
    assert field.default_factory is not None
    assert field.default_factory() == []  # type: ignore[call-arg]


# --- Web-Konstante (B5) ------------------------------------------------------


def test_typescript_constant_carries_every_budget() -> None:
    text = cb.typescript_constant()
    for element, budget in cb.BUDGETS.items():
        target = "null" if budget.target is None else str(budget.target)
        assert f"  {element}: {{ target: {target}, warn: {budget.warn}, " in text, element
    assert "resource_section: { target: null, warn: 600, unit: 'words', strict: true }" in text


def test_web_constant_is_generated_from_python() -> None:
    """Die eingecheckte Web-Konstante ist genau die Ausgabe des Generators."""
    path = _REPO_ROOT / cb.WEB_CONSTANT_PATH
    assert path.read_text(encoding="utf-8") == cb.typescript_constant(), (
        "Web-Konstante veraltet. Behebung im Repo-Root: "
        "uv run python -m who2be_models.content_budgets"
    )
