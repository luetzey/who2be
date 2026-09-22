"""Der Code-Referenz-Pruefer (P7): Grammatik, Severity-Modell, Read-only-Zusage.

`scripts/check_code_refs.py` ersetzt das Nachmessen von Hand, das bisher in
jedem Aufbereitungslauf noetig war. Vier Eigenschaften tragen diesen Zweck und
sind je einzeln leicht zu verlieren:

1. **Die Grammatik trennt Zeiger von Prosa.** Nur Backtick-Spannen werden
   betrachtet, und nur mit Anker oder Zeile. Ohne diese Einschraenkung meldet
   der Pruefer jede Erwaehnung eines Dateinamens und wird ignoriert.
2. **Symbolaufloesung ist eine *Definitions*-Pruefung.** Ein Aufruf des Symbols
   darf den Anker nicht gueltig machen — sonst bestaetigt der Pruefer genau die
   Zeiger, deren Definition laengst woanders steht.
3. **Das Severity-Modell haelt die Altlast aus dem Rot heraus.** Nackte
   `datei:zeile`-Zeiger sind `legacy`, nicht `error`; die Bestandskorrektur ist
   ausdruecklich nicht Ziel. Faellt das um, ist der Pruefer im Repo unbenutzbar
   rot und wird abgeschaltet.
4. **Das Skript aendert nichts.** Ein Pruefer, der repariert, verwischt die
   Information, die ein Mensch sehen soll.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO_ROOT / "scripts" / "check_code_refs.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_code_refs", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_code_refs"] = module
    spec.loader.exec_module(module)
    return module


checker = _load_script()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Ein winziges echtes Git-Repo — SHA-Aufloesung braucht `git`, nicht Mocks."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "t"], check=True)
    (tmp_path / "mod.py").write_text(
        "CONSTANT = 1\n"
        "\n"
        "\n"
        "class Widget:\n"
        "    def render(self) -> None: ...\n"
        "\n"
        "\n"
        "def helper() -> int:\n"
        "    return CONSTANT\n",
        encoding="utf-8",
    )
    (tmp_path / "ui.ts").write_text(
        "export function mount(): void {}\nconst other = mount;\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "init"], check=True)
    return tmp_path


def _head(repo: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _scan(repo: Path, text: str, strict: bool = False) -> list[Any]:
    """Findings fuer einen Kartentext.

    Rueckgabetyp ``Any``: das Skript wird per ``importlib`` geladen, seine
    ``Finding``-Klasse ist fuer den Typchecker daher nicht erreichbar.
    """
    findings: list[Any] = checker.scan_text(repo, text, "card.md", strict)
    return findings


# --- 1. Grammatik: Zeiger vs. Prosa ------------------------------------------


def test_prose_outside_backticks_is_not_a_reference(repo: Path) -> None:
    """Ein Dateiname in Fliesstext ist kein Zeiger und darf nicht gemeldet werden."""
    assert _scan(repo, "Wir haben mod.py:7 angepasst, siehe oben.") == []


def test_bare_filename_without_anchor_or_line_is_ignored(repo: Path) -> None:
    """`mod.py` allein ist eine Nennung, keine Code-Referenz."""
    assert _scan(repo, "Die Datei `mod.py` ist betroffen.") == []


def test_line_only_pointer_is_legacy_not_error(repo: Path) -> None:
    findings = _scan(repo, "Siehe `mod.py:7`.")
    assert [f.severity for f in findings] == ["legacy"]


def test_legacy_stays_legacy_even_when_path_does_not_resolve(repo: Path) -> None:
    """Altlast-Zeiger nennen oft abgekuerzte Pfade — das ist trotzdem kein Fehler.

    Genau hier bricht die naive Implementierung: sie stuft den nicht
    aufloesbaren Pfad als `missing-file` ein, faerbt den Lauf rot und macht
    den Pruefer im Bestand unbenutzbar.
    """
    findings = _scan(repo, "Siehe `voellig/unbekannt.py:12`.")
    assert [f.severity for f in findings] == ["legacy"]


def test_strict_promotes_legacy_to_error(repo: Path) -> None:
    findings = _scan(repo, "Siehe `mod.py:7`.", strict=True)
    assert [f.severity for f in findings] == ["error"]


def test_code_fence_content_is_scanned(repo: Path) -> None:
    text = "```\nmod.py#helper\n```\n"
    findings = _scan(repo, text)
    assert [f.severity for f in findings] == ["ok"]


def test_urls_are_not_torn_apart(repo: Path) -> None:
    """Ein GitHub-Permalink ist die empfohlene Form — er darf nicht als Fehler gelten.

    Ohne Ausblendung greift die Grammatik mitten in die URL
    (``…/blob/<sha>/pfad.py#L20``) und meldet den Rest als nicht aufloesbaren
    Pfad. Der Pruefer wuerde damit ausgerechnet das Muster anschleppen, zu dem
    die Konvention raet.
    """
    url = "https://github.com/luetzey/who2be/blob/39dcdf4/apps/api/main.py#L20-L28"
    assert _scan(repo, f"Siehe `{url}`.") == []
    assert _scan(repo, f"Siehe {url} im Browser.") == []


# --- 2. Symbolaufloesung ------------------------------------------------------


@pytest.mark.parametrize("symbol", ["helper", "Widget", "Widget.render", "CONSTANT"])
def test_python_symbols_resolve(repo: Path, symbol: str) -> None:
    findings = _scan(repo, f"Siehe `mod.py#{symbol}`.")
    assert [f.status for f in findings] == ["ok"]


def test_missing_python_symbol_is_error(repo: Path) -> None:
    findings = _scan(repo, "Siehe `mod.py#nicht_da`.")
    assert findings[0].status == "missing-symbol"
    assert findings[0].severity == "error"


def test_typescript_definition_resolves(repo: Path) -> None:
    findings = _scan(repo, "Siehe `ui.ts#mount`.")
    assert [f.status for f in findings] == ["ok"]


def test_typescript_usage_alone_does_not_resolve(repo: Path) -> None:
    """`other` ist eine Zuweisung; `renderTwice` kommt gar nicht vor."""
    findings = _scan(repo, "Siehe `ui.ts#renderTwice`.")
    assert findings[0].status == "missing-symbol"


def test_unsupported_file_kind_is_not_an_error(repo: Path) -> None:
    (repo / "notes.rst").write_text("nichts\n", encoding="utf-8")
    findings = _scan(repo, "Siehe `notes.rst#irgendwas`.")
    assert findings[0].status == "unsupported"
    assert findings[0].severity == "unsupported"


# --- 3. SHA-Aufloesung --------------------------------------------------------


def test_sha_permalink_resolves(repo: Path) -> None:
    findings = _scan(repo, f"Siehe `mod.py@{_head(repo)}`.")
    assert [f.status for f in findings] == ["ok"]


def test_sha_plus_symbol_plus_line_resolves(repo: Path) -> None:
    findings = _scan(repo, f"Siehe `mod.py@{_head(repo)}#helper:8`.")
    assert findings[0].status == "ok"
    assert findings[0].line_hint == 8


def test_unknown_sha_is_error(repo: Path) -> None:
    findings = _scan(repo, "Siehe `mod.py@0123abc`.")
    assert findings[0].status == "unknown-sha"
    assert findings[0].severity == "error"


def test_file_absent_at_that_commit_is_error(repo: Path) -> None:
    (repo / "spaeter.py").write_text("x = 1\n", encoding="utf-8")
    findings = _scan(repo, f"Siehe `spaeter.py@{_head(repo)}`.")
    assert findings[0].status == "missing-file"


def test_missing_file_in_worktree_is_error(repo: Path) -> None:
    findings = _scan(repo, "Siehe `weg.py#helper`.")
    assert findings[0].status == "missing-file"
    assert findings[0].severity == "error"


# --- 4. Read-only ------------------------------------------------------------


def _tree_fingerprint(root: Path) -> dict[str, str]:
    def walk() -> Iterator[tuple[str, str]]:
        for path in sorted(root.rglob("*")):
            if ".git" in path.parts or not path.is_file():
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            yield str(path.relative_to(root)), digest

    return dict(walk())


def test_leaves_tree_untouched(repo: Path) -> None:
    """Der Pruefer meldet — er repariert nicht, legt keinen Cache an, schreibt nichts."""
    (repo / "card.md").write_text(
        "`mod.py#helper` und `mod.py:7` und `weg.py#x` und `mod.py@0123abc`\n",
        encoding="utf-8",
    )
    before = _tree_fingerprint(repo)
    checker.main([str(repo / "card.md"), "--repo-root", str(repo), "--json"])
    assert _tree_fingerprint(repo) == before


# --- CLI ----------------------------------------------------------------------


def test_json_output_is_machine_readable(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (repo / "card.md").write_text("`mod.py#helper` `mod.py:7` `weg.py#x`\n", encoding="utf-8")
    exit_code = checker.main([str(repo / "card.md"), "--repo-root", str(repo), "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1  # wegen weg.py
    assert payload["summary"]["references"] == 3
    assert payload["summary"]["error"] == 1
    assert payload["summary"]["legacy"] == 1
    assert {f["reference"] for f in payload["findings"]} == {"mod.py:7", "weg.py#x"}


def test_exit_zero_when_only_legacy(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Der Kern des Severity-Modells: Altlast blockiert nicht."""
    (repo / "card.md").write_text("`mod.py:7` `andere/datei.py:99`\n", encoding="utf-8")
    assert checker.main([str(repo / "card.md"), "--repo-root", str(repo)]) == 0
    assert "legacy" in capsys.readouterr().out


def test_directory_scan_finds_markdown_recursively(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (repo / "docs").mkdir()
    (repo / "docs" / "a.md").write_text("`mod.py#helper`\n", encoding="utf-8")
    (repo / "docs" / "b.md").write_text("`mod.py#helper`\n", encoding="utf-8")
    (repo / "docs" / "ignored.txt").write_text("`mod.py#nicht_da`\n", encoding="utf-8")

    assert checker.main([str(repo / "docs"), "--repo-root", str(repo), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["scanned_files"] == 2


def test_nonexistent_target_exits_two(repo: Path) -> None:
    assert checker.main([str(repo / "gibtsnicht"), "--repo-root", str(repo)]) == 2


def test_repository_itself_has_no_reference_errors(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Akzeptanzkriterium 2: der Pruefer laeuft auf diesem Repo fehlerfrei durch.

    Ein Regressionstest, kein Ritual: er faellt in dem Moment, in dem jemand
    eine Referenz in Konventionsform schreibt, die nicht aufloest — also genau
    dann, wenn die Konvention gebrochen wird.
    """
    exit_code = checker.main([str(_REPO_ROOT), "--repo-root", str(_REPO_ROOT), "--json"])
    payload = json.loads(capsys.readouterr().out)
    errors = [f for f in payload["findings"] if f["severity"] == "error"]
    assert exit_code == 0, f"Referenz-Fehler im Repo: {errors}"
