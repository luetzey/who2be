"""Tests fuer ``scripts/ci/assert_skips_within_budget.py`` (Skip-Budget-Gate).

Halten die drei Exit-Pfade fest (XML fehlt / 0 Testfaelle / Gutfall bzw. Skip
ueber Budget) und dass die Fehlermeldung bei fehlender XML kein Werkzeug als
Erzeuger behauptet — das Gate laeuft hinter pytest UND Vitest (Issue #949).
"""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

# Geladen per importlib wie `test_ci_all_green_matrix.py`: `scripts/ci` ist
# kein Paket und steht nicht im mypy_path.
GATE = Path(__file__).resolve().parents[2] / "scripts" / "ci" / "assert_skips_within_budget.py"


def _load_main() -> Callable[[list[str] | None], int]:
    spec = importlib.util.spec_from_file_location("who2be_skip_budget_gate", GATE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    entry: Callable[[list[str] | None], int] = module.main
    return entry


main = _load_main()


def _xml(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "junit.xml"
    path.write_text(f'<?xml version="1.0"?>\n<testsuites>{body}</testsuites>\n', encoding="utf-8")
    return path


def test_fehlende_xml_ist_exit_2_mit_pfad_und_ohne_werkzeugnamen(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "gibtsnicht.xml"

    assert main([str(missing)]) == 2

    out = capsys.readouterr().out
    assert out.startswith("::error::")
    assert str(missing) in out
    # tmp_path selbst enthaelt "pytest-of-…" — nur der Text ohne Pfad zaehlt.
    text = out.replace(str(missing), "<pfad>").lower()
    assert "pytest" not in text
    assert "vitest" not in text


def test_xml_ohne_testfall_ist_exit_2(tmp_path: Path) -> None:
    assert main([str(_xml(tmp_path, "<testsuite/>"))]) == 2


def test_gutfall_ist_exit_0(tmp_path: Path) -> None:
    body = '<testsuite><testcase name="a"/><testcase name="b"/></testsuite>'
    assert main([str(_xml(tmp_path, body))]) == 0


def test_skip_ueber_budget_ist_exit_1(tmp_path: Path) -> None:
    body = '<testsuite><testcase name="a"><skipped message="windows only"/></testcase></testsuite>'
    xml = _xml(tmp_path, body)

    assert main([str(xml)]) == 1
    assert main([str(xml), "--max-other-skips", "1"]) == 0


def test_infrastruktur_skip_ist_immer_exit_1(tmp_path: Path) -> None:
    body = (
        '<testsuite><testcase name="a">'
        '<skipped message="keine erreichbare Datenbank"/></testcase></testsuite>'
    )
    assert main([str(_xml(tmp_path, body)), "--max-other-skips", "5"]) == 1


def test_hilfe_nennt_keinen_einzelnen_erzeuger(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["--help"])
    help_text = capsys.readouterr().out
    assert "pytest --junitxml" not in help_text
    assert "Pfad zur JUnit-XML des vorausgegangenen Testlaufs" in help_text
