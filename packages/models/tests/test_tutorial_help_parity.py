"""Paritaet Tutorial-Katalog (JSON) <-> Tutorial-Text (Markdown je Sprache).

ADR-0060 §5: Die Schritte eines Tutorials stehen sprachneutral in
``who2be_models/tutorials/<id>.json`` (eine Quelle fuer API und Web). Das Web
traegt nur den Text: ``apps/web/src/help/tutorials/<id>.<lang>.md`` mit
Frontmatter ``tutorial: <id>`` und je Schritt einem Abschnitt
``## Titel [#<step_id>]``. Verlangt wird: Text in jeder Sprache, je step_id ein
Abschnitt in Katalog-Reihenfolge, keine ueberzaehligen Abschnitte, kein
Markdown-Tutorial ohne Katalog-Eintrag.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from who2be_models import tutorial as tutorial_module
from who2be_models.tutorial import load_tutorial_catalog

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CATALOG_DIR = Path(tutorial_module.__file__).resolve().parent / "tutorials"
_HELP_TUTORIALS = _REPO_ROOT / "apps" / "web" / "src" / "help" / "tutorials"
_LOCALES = ("de", "en")
_FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.DOTALL)
_STEP_HEADING = re.compile(r"^##\s+.+?\s+\[#([a-z0-9]+(?:-[a-z0-9]+)*)\]\s*$", re.MULTILINE)
_FENCE = re.compile(r"^(```|~~~).*?^\1", re.DOTALL | re.MULTILINE)


def _read_markdown(path: Path) -> tuple[dict[str, str], list[str]] | None:
    """Frontmatter-Felder und Schritt-Anker (``##``, ausserhalb von Code)."""
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    match = _FRONTMATTER.match(text)
    if match is None:
        return None
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip()
    return fields, _STEP_HEADING.findall(_FENCE.sub("", match.group(2)))


def check_parity(catalog_dir: Path, help_dir: Path) -> list[str]:
    """Ein Befund je Abweichung; leer = Katalog und Text passen zusammen."""
    errors: list[str] = []
    catalog = load_tutorial_catalog(catalog_dir)
    for tutorial_id, definition in catalog.items():
        expected = [step.id for step in definition.steps]
        for locale in _LOCALES:
            path = help_dir / f"{tutorial_id}.{locale}.md"
            if not path.is_file():
                errors.append(f"{path.name}: Text fehlt")
                continue
            parsed = _read_markdown(path)
            if parsed is None:
                errors.append(f"{path.name}: Frontmatter fehlt")
                continue
            fields, anchors = parsed
            if fields.get("tutorial") != tutorial_id:
                errors.append(f"{path.name}: Frontmatter `tutorial` ist nicht {tutorial_id!r}")
            missing = [step_id for step_id in expected if step_id not in anchors]
            extra = [anchor for anchor in anchors if anchor not in expected]
            if missing:
                errors.append(f"{path.name}: Abschnitt fehlt fuer {missing}")
            if extra:
                errors.append(f"{path.name}: ueberzaehlige Abschnitte {extra}")
            if not missing and not extra and anchors != expected:
                errors.append(f"{path.name}: Reihenfolge weicht vom Katalog ab")
    for path in sorted(help_dir.glob("*.md")):
        stem = path.name.removesuffix(".md").rpartition(".")[0]
        if stem not in catalog:
            errors.append(f"{path.name}: kein Katalog-Eintrag {stem!r}")
    return errors


def test_repo_catalog_and_help_text_match() -> None:
    assert _HELP_TUTORIALS.is_dir(), f"{_HELP_TUTORIALS} fehlt"
    assert check_parity(_CATALOG_DIR, _HELP_TUTORIALS) == []


# --- Testdaten: ein neues Tutorial nur aus Dateien --------------------------------


def _write_tutorial(
    catalog: Path, help_dir: Path, steps: list[str], text_steps: dict[str, list[str]]
) -> None:
    catalog.mkdir(exist_ok=True)
    help_dir.mkdir(exist_ok=True)
    (catalog / "demo.json").write_text(
        json.dumps(
            {
                "id": "demo",
                "audience": "everyone",
                "steps": [{"id": step, "type": "manual"} for step in steps],
            }
        ),
        encoding="utf-8",
    )
    for locale, anchors in text_steps.items():
        sections = "\n".join(f"## Schritt {a} [#{a}]\n\nText.\n" for a in anchors)
        (help_dir / f"demo.{locale}.md").write_text(
            f"---\ntutorial: demo\ntitle: Demo\ndescription: D\nduration: 2\n---\n\n"
            f"```\n## Im Code [#kein-schritt]\n```\n\n{sections}",
            encoding="utf-8",
        )


def test_new_tutorial_from_files_only_is_green(tmp_path: Path) -> None:
    catalog, help_dir = tmp_path / "catalog", tmp_path / "help"
    _write_tutorial(
        catalog, help_dir, ["eins", "zwei"], {"de": ["eins", "zwei"], "en": ["eins", "zwei"]}
    )
    assert check_parity(catalog, help_dir) == []


def test_missing_extra_and_reordered_steps_are_red(tmp_path: Path) -> None:
    catalog, help_dir = tmp_path / "catalog", tmp_path / "help"
    _write_tutorial(
        catalog, help_dir, ["eins", "zwei"], {"de": ["eins"], "en": ["zwei", "eins", "drei"]}
    )
    errors = check_parity(catalog, help_dir)
    assert any("demo.de.md: Abschnitt fehlt fuer ['zwei']" in e for e in errors)
    assert any("demo.en.md: ueberzaehlige Abschnitte ['drei']" in e for e in errors)


def test_missing_language_and_orphan_text_are_red(tmp_path: Path) -> None:
    catalog, help_dir = tmp_path / "catalog", tmp_path / "help"
    _write_tutorial(catalog, help_dir, ["eins"], {"de": ["eins"]})
    (help_dir / "verwaist.de.md").write_text("---\ntutorial: verwaist\n---\n", encoding="utf-8")
    errors = check_parity(catalog, help_dir)
    assert "demo.en.md: Text fehlt" in errors
    assert "verwaist.de.md: kein Katalog-Eintrag 'verwaist'" in errors


def test_reordered_steps_are_red(tmp_path: Path) -> None:
    catalog, help_dir = tmp_path / "catalog", tmp_path / "help"
    _write_tutorial(
        catalog, help_dir, ["eins", "zwei"], {"de": ["zwei", "eins"], "en": ["eins", "zwei"]}
    )
    assert check_parity(catalog, help_dir) == ["demo.de.md: Reihenfolge weicht vom Katalog ab"]
