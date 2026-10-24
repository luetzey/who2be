"""Tests fuer ``scripts/ci/help_drift.py`` (Hilfe-Drift-Warnung, Doku-Drift Stufe 2).

Die Regel steht in reinen Funktionen und wird hier gegen handgeschriebene
Eingaben gehalten: Treffer, Ausnahme, falscher Grund. Zwei Tests fahren
``main`` gegen ein echtes Wegwerf-Repo, weil die Messung (Merge-Base, Locale-
Werte aus ``git show``) sonst ungeprueft bliebe. Ein letzter Test haelt fest,
dass der CI-Step die Warnung nicht zur Sperre machen kann.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ci" / "help_drift.py"
CI_YML = ROOT / ".github" / "workflows" / "ci.yml"


def _load() -> ModuleType:
    # Per importlib wie `test_assert_skips_within_budget.py`: `scripts/ci` ist
    # kein Paket und steht nicht im mypy_path.
    spec = importlib.util.spec_from_file_location("who2be_help_drift", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


hd = _load()

COMPONENT = "apps/web/src/features/agents/components/AgentConnectorSection.tsx"

# --------------------------------------------------------------------------
# Pfadtabelle
# --------------------------------------------------------------------------


def test_component_counts_tests_and_other_paths_do_not() -> None:
    paths = [
        COMPONENT,
        "apps/web/src/features/agents/components/AgentConnectorSection.test.tsx",
        "apps/web/src/features/agents/components/__tests__/x.tsx",
        "apps/web/src/features/agents/hooks/useAgent.ts",
        "apps/web/src/features/agents/api.ts",
        "apps/api/src/who2be_api/main.py",
    ]
    assert hd.ui_component_hits(paths) == [COMPONENT]


def test_locale_only_changed_values_count_not_new_or_removed_keys() -> None:
    base = json.dumps({"a": {"b": "Befehl kopieren", "c": "x"}, "gone": "y"})
    head = json.dumps({"a": {"b": "Kommando kopieren", "c": "x", "new": "z"}})
    assert hd.changed_locale_values(base, head) == ["a.b"]


def test_locale_new_file_or_broken_json() -> None:
    assert hd.changed_locale_values(None, '{"a": "b"}') == []
    assert hd.changed_locale_values('{"a": "b"}', "{kaputt") == ["<ungueltiges JSON>"]


# --------------------------------------------------------------------------
# PR-Beschreibung
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "line",
    [
        "Hilfe: n/a – intern",
        "Hilfe: n/a - kein UI-Text",
        "Hilfe: n/a — nur Tests",
        "Hilfe: n/a – Folgekarte t_0d3f4203",
        "Hilfe: n/a – Folgekarte #1051",
        "Hilfe: n/a – intern: nur Betreiber-Ansicht",
        "Hilfe: NA – Kein UI-Text (Refactoring ohne Textänderung)",
    ],
)
def test_valid_exceptions(line: str) -> None:
    body = f"Issue: n/a (Kanban card t_x, Test)\n\n{line}\n"
    assert hd.parse_declaration(body).kind == "na"


@pytest.mark.parametrize(
    "line",
    [
        "Hilfe: n/a – passt schon",
        "Hilfe: n/a – Folgekarte",
        "Hilfe: n/a",
        "Hilfe: n/a – internes Refactoring",
        "Hilfe: ",
        "Hilfe: geändert | n/a – <Grund>",  # unveraenderte Template-Zeile
    ],
)
def test_wrong_reason_is_invalid(line: str) -> None:
    assert hd.parse_declaration(line).kind == "invalid"


def test_changed_missing_and_template_comment() -> None:
    assert hd.parse_declaration("Hilfe: geändert").kind == "changed"
    assert hd.parse_declaration("Hilfe: geaendert").kind == "changed"
    assert hd.parse_declaration(None).kind == "missing"
    # Das Beispiel im Template-Kommentar zaehlt nicht als Angabe.
    commented = "<!-- Hilfe: n/a – intern -->\nText"
    assert hd.parse_declaration(commented).kind == "missing"


# --------------------------------------------------------------------------
# Regel
# --------------------------------------------------------------------------

NA = hd.Declaration("na", "intern")
MISSING = hd.Declaration("missing")


def test_hit_without_help_warns() -> None:
    verdict = hd.evaluate([COMPONENT], [], False, MISSING)
    assert verdict.warn
    assert COMPONENT in verdict.summary
    assert "keine Zeile" in verdict.summary


def test_wrong_reason_warns_and_names_list() -> None:
    verdict = hd.evaluate([], ["de.json: a.b"], False, hd.Declaration("invalid", "n/a – passt"))
    assert verdict.warn
    assert "kein UI-Text" in verdict.summary and "Folgekarte <id>" in verdict.summary


def test_claimed_change_without_help_change_warns() -> None:
    assert hd.evaluate([COMPONENT], [], False, hd.Declaration("changed", "geändert")).warn


@pytest.mark.parametrize(
    ("ui", "help_changed", "decl"),
    [
        ([], False, MISSING),  # keine UI-Pfade
        ([COMPONENT], True, MISSING),  # Hilfe mitgeaendert
        ([COMPONENT], False, NA),  # gueltige Ausnahme
    ],
)
def test_no_warning(ui: list[str], help_changed: bool, decl: object) -> None:
    assert not hd.evaluate(ui, [], help_changed, decl).warn


def test_long_listing_is_capped() -> None:
    hits = [f"apps/web/src/features/f/components/C{i}.tsx" for i in range(15)]
    assert "(+5 weitere)" in hd.evaluate(hits, [], False, MISSING).summary


# --------------------------------------------------------------------------
# main gegen ein echtes Repo
# --------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def _write(repo: Path, rel: str, text: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str]:
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@example.invalid")
    _git(tmp_path, "config", "user.name", "t")
    _write(tmp_path, "apps/web/src/i18n/locales/de.json", '{"k": "Alt"}')
    _write(tmp_path, COMPONENT, "export {}\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "base")
    base = _git(tmp_path, "rev-parse", "HEAD")
    monkeypatch.chdir(tmp_path)
    return tmp_path, base


def _run(
    repo: Path,
    base: str,
    body: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> tuple[int, str, str]:
    summary = repo / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setenv("PR_BODY", body)
    rc = hd.main(["--base", base, "--head", _git(repo, "rev-parse", "HEAD")])
    return rc, capsys.readouterr().out, summary.read_text(encoding="utf-8")


def test_main_locale_value_change_warns_then_exception_silences(
    repo: tuple[Path, str], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path, base = repo
    _write(path, "apps/web/src/i18n/locales/de.json", '{"k": "Neu", "added": "x"}')
    _git(path, "commit", "-qam", "rename button")

    rc, out, summary = _run(path, base, "Issue: n/a", monkeypatch, capsys)
    assert rc == 0
    assert out.startswith("::warning title=Hilfe-Drift::")
    assert "de.json: k" in out and "added" not in out
    assert "⚠️" in summary

    rc, out, _ = _run(path, base, "Hilfe: n/a – Folgekarte t_abc123", monkeypatch, capsys)
    assert rc == 0
    assert "::warning" not in out


def test_main_help_changed_and_broken_git_never_fail(
    repo: tuple[Path, str], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path, base = repo
    _write(path, COMPONENT, "export const x = 1\n")
    _write(path, "apps/web/src/help/erste-schritte/connect-claude.de.md", "neu\n")
    _git(path, "add", ".")
    _git(path, "commit", "-qm", "ui+help")
    rc, out, _ = _run(path, base, "", monkeypatch, capsys)
    assert rc == 0 and "Hilfe ebenfalls geändert" in out

    # Unbekannte SHA: Hinweis statt Fehler, Exit 0.
    rc = hd.main(["--base", "0" * 40, "--head", "HEAD"])
    assert rc == 0
    assert "::notice title=Hilfe-Drift::" in capsys.readouterr().out


# --------------------------------------------------------------------------
# CI-Verdrahtung: Warnung, nie Sperre
# --------------------------------------------------------------------------


def test_ci_step_cannot_block() -> None:
    workflow = yaml.safe_load(CI_YML.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["changes"]["steps"]
    step = next(s for s in steps if "help_drift.py" in s.get("run", ""))
    assert step["continue-on-error"] is True
    # Der Body kommt ueber env, nie als Template-Ausdruck in die Shell.
    assert step["env"]["PR_BODY"] == "${{ github.event.pull_request.body }}"
    assert "${{" not in step["run"]
    # Die Klassifikation laeuft vorher und unabhaengig.
    assert steps.index(step) > next(i for i, s in enumerate(steps) if s.get("id") == "classify")
