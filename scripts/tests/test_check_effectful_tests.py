"""Der Wirkungs-Pruefer selbst geprueft (Karte t_3a17f078).

Ein Gate, das Tests auf Wirkung prueft, muss sich zuerst an sich selbst
messen lassen. Deshalb hat diese Datei drei Sorten Testfaelle:

1. **Rot-Probe** — ein absichtlich schlechter Test wird markiert, ein guter
   nicht. Das ist der Nachweis, dass die Heuristik ueberhaupt unterscheidet;
   ohne ihn wuerde ein Pruefer, der einfach nie etwas findet, gruen bleiben.
2. **Historien-Beleg** — die Faelle, um derer willen dieser Pruefer existiert,
   liegen in der git-Historie. Die Heuristik muss sie markieren, und zwar
   nachgemessen an der damaligen Fassung statt behauptet. Faelle, die sie NICHT
   fasst, sind hier ebenso festgehalten: eine benannte Grenze ist brauchbar,
   eine stille nicht.
3. **Ausnahmeweg** — der Marker wirkt, und ein leerer Marker wirkt nicht.

Die Faelle unter (1) und (3) arbeiten auf Quelltext-Zeichenketten in dieser
Datei, nicht auf Dateien im Baum: sie rufen ``analyse_source`` mit echtem
Python-Text auf und pruefen dessen Rueckgabe. Das IST ein Wirkungsaufruf --
dieser Pruefer markiert seine eigenen Tests nicht.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from check_effectful_tests import (  # noqa: E402
    Finding,
    analyse_source,
    main,
)


def _names(source: str) -> set[str]:
    return {finding.test for finding in analyse_source(source, "x_test.py")}


# --- Rot-Probe: schlecht wird markiert, gut nicht ----------------------------


def test_string_only_test_is_flagged() -> None:
    """Der Fehlertyp, um den es geht: lesen, Text zusichern, nichts aufrufen."""
    source = """
from pathlib import Path

def test_config_enables_the_thing() -> None:
    text = Path("deploy/config.yml").read_text()
    assert "feature_enabled: true" in text
"""
    assert _names(source) == {"test_config_enables_the_thing"}


def test_test_that_calls_the_subject_is_not_flagged() -> None:
    """Derselbe Lesevorgang, aber der Prueflung laeuft -- kein Befund."""
    source = """
from pathlib import Path
from who2be_api.core.config import load_config

def test_config_enables_the_thing() -> None:
    text = Path("deploy/config.yml").read_text()
    config = load_config(text)
    assert config.feature_enabled is True
"""
    assert _names(source) == set()


def test_test_that_starts_a_process_is_not_flagged() -> None:
    """Ein Skript wirklich auszufuehren ist Wirkung, auch ohne Python-Import."""
    source = """
import subprocess
from pathlib import Path

def test_rotation_script_deletes_old_generations() -> None:
    Path("/tmp/old.log").write_text("x")
    result = subprocess.run(["bash", "rotate.sh"], capture_output=True)
    assert result.returncode == 0
    assert not Path("/tmp/old.log").exists()
"""
    assert _names(source) == set()


def test_grep_shellout_counts_as_reading_not_as_effect() -> None:
    """``subprocess.run(["grep", ...])`` ist ein Lesevorgang mit Umweg.

    Ohne diese Unterscheidung waere jeder Texttest durch ein vorgeschaltetes
    ``grep`` vom Gate befreit -- der billigste denkbare Umgehungsweg.
    """
    source = """
import subprocess

def test_runbook_mentions_the_procedure() -> None:
    out = subprocess.run(["grep", "-n", "mtime", "RUNBOOK.md"], capture_output=True, text=True)
    assert "mtime" in out.stdout
"""
    assert _names(source) == {"test_runbook_mentions_the_procedure"}


def test_http_call_against_the_app_is_effect() -> None:
    source = """
from pathlib import Path

def test_health_route_answers(client) -> None:
    expected = Path("docs/health.md").read_text()
    response = client.get("/health")
    assert response.status_code == 200
    assert "ok" in expected
"""
    assert _names(source) == set()


def test_call_inside_the_assertion_is_effect() -> None:
    """``assert normalise(text) == x`` prueft Verhalten, nicht bloss Text.

    Der erste Entwurf sah nur den Wurzelknoten der Zusicherung (ein
    ``Compare``) und liess diese Form durch -- ein Test, der sehr wohl Code
    ausfuehrt, waere als wirkungslos gemeldet worden.
    """
    source = """
from pathlib import Path
from who2be_api.core.config import normalise

def test_issuer_is_normalised() -> None:
    raw = Path("config.json").read_text()
    assert normalise(raw) == "https://host/"
"""
    assert _names(source) == set()


def test_reading_through_two_helper_levels_is_still_reading() -> None:
    """Der Lesevorgang darf sich nicht hinter Helfern verstecken koennen.

    Genau diese Form hatte einer der drei historischen Faelle: der Test ruft
    ``_directives()``, das ``_text()`` ruft, das erst liest. Eine Heuristik,
    die nur eine Ebene tief sieht, uebersieht ihn.
    """
    source = """
from pathlib import Path

def _text() -> str:
    return Path("Caddyfile").read_text()

def _directives() -> str:
    return "\\n".join(l for l in _text().splitlines() if not l.startswith("#"))

def test_roll_size_is_set() -> None:
    assert "roll_size" in _directives()
"""
    assert _names(source) == {"test_roll_size_is_set"}


def test_effect_through_a_helper_is_still_effect() -> None:
    """Und umgekehrt: ein Helfer, der den Prueflung faehrt, zaehlt auch."""
    source = """
from pathlib import Path
from who2be_api.core.config import load_config

def _loaded():
    return load_config(Path("config.yml").read_text())

def test_feature_is_on() -> None:
    assert _loaded().feature_enabled is True
"""
    assert _names(source) == set()


def test_test_without_any_assertion_is_not_flagged() -> None:
    """Ein Test ohne Zusicherung ist ein anderes Problem als dieses hier.

    Er waere ebenfalls wertlos, aber ihn hier mitzumelden hiesse, zwei Befunde
    unter einer Meldung zu fuehren -- und die Meldung sagte dann nicht mehr,
    was sie meint.
    """
    source = """
from pathlib import Path

def test_file_is_readable() -> None:
    Path("config.yml").read_text()
"""
    assert _names(source) == set()


def test_test_that_reads_nothing_is_not_flagged() -> None:
    source = """
def test_two_plus_two() -> None:
    assert 2 + 2 == 4
"""
    assert _names(source) == set()


# --- Ausnahmeweg -------------------------------------------------------------


def test_exempt_marker_suppresses_the_finding() -> None:
    source = """
from pathlib import Path

# effect-exempt: prueft eine Doku-Zusage, hat keinen Prueflung
def test_readme_states_the_tool_count() -> None:
    assert "83 Werkzeuge" in Path("README.md").read_text()
"""
    assert _names(source) == set()


def test_exempt_marker_works_on_the_def_line() -> None:
    source = """
from pathlib import Path

def test_readme_states_the_tool_count() -> None:  # effect-exempt: Doku-Zusage
    assert "83 Werkzeuge" in Path("README.md").read_text()
"""
    assert _names(source) == set()


def test_exempt_marker_without_a_reason_does_not_count() -> None:
    """Ein begruendungsloser Marker ist ein stilles Abschalten.

    Genau das soll der Ausnahmeweg nicht sein: er ist da, damit zulaessige
    Textpruefungen den Lauf nicht verstopfen -- nicht, damit man eine Warnung
    wegklickt.
    """
    source = """
from pathlib import Path

# effect-exempt:
def test_readme_states_the_tool_count() -> None:
    assert "83 Werkzeuge" in Path("README.md").read_text()
"""
    assert _names(source) == {"test_readme_states_the_tool_count"}


def test_exempt_marker_far_above_the_def_does_not_count() -> None:
    """Der Marker muss dort stehen, wo der Reviewer des Diffs ihn sieht."""
    source = """
from pathlib import Path

# effect-exempt: gilt fuer irgendwas hier oben


def test_readme_states_the_tool_count() -> None:
    assert "83 Werkzeuge" in Path("README.md").read_text()
"""
    assert _names(source) == {"test_readme_states_the_tool_count"}


# --- Historien-Beleg ---------------------------------------------------------

# Die Faelle, um derer willen dieser Pruefer existiert -- mit der Fassung, in
# der sie damals eingecheckt wurden. Nachgemessen statt behauptet: ein Gate,
# das seine Begruendungsfaelle nicht mehr faengt, ist ein leeres Versprechen.
_HISTORY = [
    pytest.param(
        "8d4161cf",
        "apps/api/tests/test_compose_hardening.py",
        "test_caddy_access_log_rotates_by_size",
        id="access-logs-groessengrenze",
    ),
    pytest.param(
        "8d4161cf",
        "apps/api/tests/test_compose_hardening.py",
        "test_access_log_retention_is_enforced_by_a_documented_cron",
        id="access-logs-loeschfrist",
    ),
    pytest.param(
        "22371628",
        "apps/api/tests/test_compose_hardening.py",
        "test_retention_threshold_stays_below_the_promised_period",
        id="access-logs-nachschaerfung",
    ),
    pytest.param(
        "d00c1088",
        "apps/api/tests/test_single_writer_guard.py",
        "test_deploy_skript_prueft_die_container_anzahl",
        id="deploy-waechter",
    ),
]


def _blob_at(ref: str, path: str) -> str:
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        capture_output=True,
        text=True,
        check=False,
        cwd=_REPO_ROOT,
    )
    if result.returncode != 0:
        pytest.skip(f"{ref}:{path} nicht im Klon (shallow?) — {result.stderr.strip()}")
    return result.stdout


@pytest.mark.parametrize(("ref", "path", "test_name"), _HISTORY)
def test_historical_case_is_flagged(ref: str, path: str, test_name: str) -> None:
    """Die Heuristik markiert den Test, der damals gruen blieb."""
    findings = analyse_source(_blob_at(ref, path), path)
    flagged = {finding.test for finding in findings}
    assert test_name in flagged, (
        f"{test_name} ({ref}) wird NICHT markiert — die Heuristik faengt einen "
        f"ihrer eigenen Begruendungsfaelle nicht mehr. Markiert: {sorted(flagged)}"
    )


def test_backup_case_is_out_of_reach_and_says_so() -> None:
    """Der dritte historische Fall liegt in Bash und wird NICHT erfasst.

    Dreizehn Testfaelle konnten einen abgeschnittenen Datenbank-Dump
    prinzipbedingt nicht fangen -- sie stehen in
    ``deploy/hetzner/tests/test_backup_alarm.sh``. Dieser Pruefer parst Python.
    Die Grenze steht hier als Testfall, damit sie nicht spaeter als „geloest"
    missverstanden wird: wer sie schliessen will, braucht einen zweiten
    Pruefer fuer Shell, keinen Parameter an diesem.
    """
    shell_suite = _REPO_ROOT / "deploy" / "hetzner" / "tests" / "test_backup_alarm.sh"
    assert shell_suite.exists(), "Pfad der Shell-Testsuite geaendert — Grenze neu bewerten"
    findings = analyse_source(shell_suite.read_text(encoding="utf-8"), str(shell_suite))
    assert findings == [], "Shell wird nicht geparst — dieser Befund waere ein Zufall"


# --- Aufruf ------------------------------------------------------------------


def test_reporting_mode_does_not_fail_the_run(capsys: pytest.CaptureFixture[str]) -> None:
    """Ohne ``--strict`` bleibt der Lauf gruen -- der Schritt startet meldend.

    Erst Signalqualitaet messen, dann entscheiden, ob es haerter wird. Ein
    Gate, das am ersten Tag blockt und am dritten abgeschaltet wird, hat
    nichts geschuetzt.
    """
    exit_code = main(["--roots", "apps", "packages", "scripts"])
    assert exit_code == 0
    assert "Wirkungs-Pruefung" in capsys.readouterr().out


def test_strict_mode_fails_when_there_are_findings(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--strict`` faerbt rot — der Weg fuer den Tag, an dem das Signal traegt."""
    exit_code = main(["--roots", "apps", "packages", "scripts", "--strict"])
    assert exit_code == 1, "Bestand enthaelt Befunde, --strict muss rot sein"
    assert "::error" in capsys.readouterr().out


def test_empty_result_reports_green(capsys: pytest.CaptureFixture[str]) -> None:
    """Kein Befund, auch mit ``--strict``: Exit 0 und eine klare Meldung."""
    from check_effectful_tests import report

    assert report([], strict=True, as_json=False) == 0
    assert "keine neuen Tests" in capsys.readouterr().out


def test_json_output_carries_every_field(capsys: pytest.CaptureFixture[str]) -> None:
    """Die JSON-Form traegt Datei, Zeile, Name und Grund."""
    import json

    from check_effectful_tests import report

    finding = Finding(file="a_test.py", line=7, test="test_x", why="weil")
    report([finding], strict=False, as_json=True)
    payload = json.loads(capsys.readouterr().out)
    assert payload == [{"file": "a_test.py", "line": 7, "test": "test_x", "why": "weil"}]


def test_unknown_base_ref_is_an_invocation_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Ein unbekannter Basis-Ref endet in Exit 2, nicht in stillem Gruen.

    Ein Pruefer, der gruen wird, weil er nicht pruefen konnte, ist schlimmer
    als gar keiner -- dieselbe Regel wie beim OSV-Schritt in der CI.
    """
    exit_code = main(["--base", "refs/heads/gibt-es-nicht-xyz"])
    assert exit_code == 2
    assert "Aufrufsfehler" in capsys.readouterr().err
