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
from _pytest.outcomes import Failed

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
    """Ein Skript wirklich auszufuehren ist Wirkung, auch ohne Python-Import.

    Der Fall liest absichtlich auch eine Datei und sichert Text darauf zu. Ohne
    das waere er gruen, weil Bedingung 1 nie greift -- er wuerde auch dann
    gruen bleiben, wenn ``_executes_effect`` nie wieder Wirkung erkennt, und
    seine eigene Begruendung nicht belegen. Der Gegenbeweis steht als eigener
    Testfall direkt darunter.
    """
    source = """
import subprocess
from pathlib import Path

def test_rotation_script_deletes_old_generations() -> None:
    assert "find" in Path("rotate.sh").read_text()
    result = subprocess.run(["bash", "rotate.sh"], capture_output=True)
    assert result.returncode == 0
"""
    assert _names(source) == set()


def test_the_same_case_without_the_process_start_is_flagged() -> None:
    """Gegenprobe zum Fall darueber: der Prozess-Start ist der Grund.

    Derselbe Quelltext ohne die ``subprocess``-Zeile wird markiert. Erst
    dadurch belegt der Fall darueber seine Begruendung, statt sie bloss im
    Docstring zu behaupten.
    """
    source = """
import subprocess
from pathlib import Path

def test_rotation_script_deletes_old_generations() -> None:
    assert "find" in Path("rotate.sh").read_text()
"""
    assert _names(source) == {"test_rotation_script_deletes_old_generations"}


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


def test_assertion_whose_root_is_a_call_is_still_a_text_check() -> None:
    """``assert read_text().startswith("x")`` ist derselbe Fehlertyp.

    Der Wurzelknoten der Zusicherung ist hier ein Aufruf, kein Vergleich --
    inhaltlich prueft der Test aber weiterhin nur Text in einer Datei. Faellt
    ``ast.Call`` aus der Liste zulaessiger Zusicherungs-Strukturen, schluepft
    jeder Test durch, der seine Textpruefung als ``.startswith``/``.endswith``
    schreibt.
    """
    source = """
from pathlib import Path

def test_unit_file_starts_with_the_header() -> None:
    assert Path("who2be.service").read_text().startswith("[Unit]")
"""
    assert _names(source) == {"test_unit_file_starts_with_the_header"}


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


def test_bare_open_without_a_read_attribute_counts_as_reading() -> None:
    """``open(...)`` als Argument zaehlt, auch ohne ``.read()`` daran.

    ``yaml.safe_load(open(p))`` liest eine Datei, ohne dass irgendwo ein
    ``read``-Attribut im Quelltext steht. Ohne den eigenen Zweig fuer ``open``
    faellt diese Form durch -- und sie ist die uebliche Schreibweise, wenn
    Konfiguration gegen eine Datei geprueft wird.
    """
    source = """
import yaml

def test_registry_lists_the_tool() -> None:
    data = yaml.safe_load(open("registry.yml"))
    assert "who2be" in data["tools"]
"""
    assert _names(source) == {"test_registry_lists_the_tool"}


def test_test_that_reads_nothing_is_not_flagged() -> None:
    source = """
def test_two_plus_two() -> None:
    assert 2 + 2 == 4
"""
    assert _names(source) == set()


def test_every_script_module_counts_as_first_party() -> None:
    """Jedes Skript unter ``scripts/`` gilt als eigener Code, ohne Pflegeliste.

    Vorher war das eine handgepflegte Aufzaehlung, die vier von neun Skripten
    nannte. Ein neu angelegtes Skript fehlte darin zwangslaeufig, und dessen
    Tests waeren fortan markiert worden, obwohl sie den Prueflung aufrufen --
    ein Fehlalarm, an den nichts im Repo erinnert haette.
    """
    from check_effectful_tests import _FIRST_PARTY_PREFIXES

    on_disk = {
        path.stem
        for path in (_REPO_ROOT / "scripts").glob("*.py")
        if path.stem.isidentifier() and not path.stem.startswith("_")
    }
    assert on_disk, "Vorbedingung: unter scripts/ liegen importierbare Module"
    missing = on_disk - set(_FIRST_PARTY_PREFIXES)
    assert not missing, f"Skripte gelten nicht als eigener Code: {sorted(missing)}"


def test_a_script_under_test_is_not_flagged() -> None:
    """Ein Test, der ein Repo-Skript aufruft, ist kein Befund.

    Die Wirkung laeuft hier ueber ein Modul, dessen Name erst aus dem
    Verzeichnis abgeleitet wird -- faellt die Ableitung aus, meldet dieser Fall.
    """
    source = """
from pathlib import Path
from conflict_hotspots import summarise

def test_hotspot_summary_counts_the_file() -> None:
    raw = Path("log.txt").read_text()
    assert summarise(raw)["a.py"] == 3
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
#
# Die SHAs muessen auf `main` liegen, nicht auf einem Arbeitsbranch. Der erste
# Entwurf nannte hier einen Branch-Commit; lokal war er im Klon vorhanden und
# alles gruen, in der CI fehlte er und der Fall wurde uebersprungen. Ein
# uebersprungener Kalibrierungsfall ist genau die Sorte stilles Gruen, gegen
# die dieser Pruefer gebaut ist -- deshalb weiter unten ein `fail` statt eines
# `skip`, wenn ein SHA nicht aufloest.
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
        "c405ca2c",
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
    """Die Datei in der Fassung von ``ref``.

    Loest der Ref nicht auf, ist das ein FEHLER, kein Skip. Ein
    uebersprungener Kalibrierungsfall liesse die Suite gruen, ohne dass die
    Heuristik an ihren Begruendungsfaellen gemessen wurde -- also genau das,
    wogegen dieser Pruefer gebaut ist. Die CI checkt den `python`-Job mit
    ``fetch-depth: 0`` aus, damit die Historie da ist.
    """
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        capture_output=True,
        text=True,
        check=False,
        cwd=_REPO_ROOT,
    )
    if result.returncode != 0:
        pytest.fail(
            f"{ref}:{path} loest nicht auf — {result.stderr.strip()}\n"
            "Liegt der SHA auf main und ist die Historie vollstaendig geholt "
            "(fetch-depth: 0)? Ein Skip waere hier stilles Gruen."
        )
    return result.stdout


def test_every_history_sha_lives_on_main() -> None:
    """Jeder Kalibrierungs-SHA liegt auf ``main``, nicht auf einem Arbeitsbranch.

    Genau hier lag ein Fehler dieses PRs: ein Branch-Commit war lokal im Klon
    vorhanden (alles gruen), in der CI fehlte er. Dieser Test macht die
    Bedingung pruefbar, statt sie im Kommentar zu behaupten.
    """
    for param in _HISTORY:
        ref = param.values[0]
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", str(ref), "origin/main"],
            capture_output=True,
            text=True,
            check=False,
            cwd=_REPO_ROOT,
        )
        if result.returncode == 128:
            pytest.skip(f"origin/main im Klon nicht verfuegbar: {result.stderr.strip()}")
        assert result.returncode == 0, (
            f"{ref} liegt nicht auf origin/main — in einem frischen CI-Klon "
            "fehlt der Commit und der Kalibrierungsfall faellt aus."
        )


def test_unresolvable_ref_fails_instead_of_skipping() -> None:
    """Ein nicht aufloesbarer SHA faerbt rot -- er wird nicht uebersprungen.

    Ohne diesen Fall waere die Skip-statt-Fehler-Entscheidung oben eine
    Behauptung. Ein uebersprungener Kalibrierungsfall ist stilles Gruen, und
    stilles Gruen ist der Fehlertyp, gegen den dieser Pruefer gebaut ist.
    """
    with pytest.raises(Failed):
        _blob_at("0000000000000000000000000000000000000000", "README.md")


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


# --- Diff-Modus: nur NEUE Befunde --------------------------------------------

# ``new_findings_against`` ist der Pfad, den die CI faehrt. Er zieht die Befunde
# ab, die in der Basis schon standen -- ohne diesen Abzug meldete der Schritt
# statt einer Handvoll Diff-Treffer den gesamten Altbestand an jedem PR, also
# genau das Gate, das nach dem dritten Fehlalarm abgeschaltet wird. Diese Regel
# laesst sich nur an einem echten Repository mit zwei Commits belegen; der
# Testfall baut sich deshalb eines.

_STRING_ONLY_TEST = """
from pathlib import Path


def test_alpha_is_documented() -> None:
    assert "alpha" in Path("notes.md").read_text()
"""

_ADDED_STRING_ONLY_TEST = """

def test_beta_is_documented() -> None:
    assert "beta" in Path("notes.md").read_text()
"""


def _git_in(cwd: Path, *args: str) -> str:
    """Ein git-Kommando im Wegwerf-Repo -- Fehler faerben rot, nicht still."""
    result = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def test_finding_already_in_the_base_is_not_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein Befund aus der Basis wird nicht gemeldet, ein neu hinzugefuegter schon.

    Beides in EINEM Fall, weil die Behauptung erst dann traegt: die Datei
    enthaelt am Ende zwei markierungswuerdige Tests, und gemeldet werden darf
    nur der, der im Diff dazugekommen ist. Die Zwischenzusicherung auf
    ``analyse_source`` haelt fest, dass die Heuristik tatsaechlich beide sieht
    -- sonst koennte der Fall gruen sein, weil der Abzug wirkt, oder weil die
    Heuristik den zweiten Test gar nicht faengt.
    """
    from check_effectful_tests import new_findings_against

    repo = tmp_path / "repo"
    repo.mkdir()
    _git_in(repo, "init", "-b", "main")

    test_file = repo / "test_thing.py"
    test_file.write_text(_STRING_ONLY_TEST, encoding="utf-8")
    _git_in(repo, "add", "test_thing.py")
    _git_in(repo, "commit", "-m", "basis")
    base_sha = _git_in(repo, "rev-parse", "HEAD")

    test_file.write_text(_STRING_ONLY_TEST + _ADDED_STRING_ONLY_TEST, encoding="utf-8")
    _git_in(repo, "add", "test_thing.py")
    _git_in(repo, "commit", "-m", "neuer stringtest")

    head_names = {
        f.test for f in analyse_source(test_file.read_text(encoding="utf-8"), "x_test.py")
    }
    assert head_names == {"test_alpha_is_documented", "test_beta_is_documented"}, (
        "Vorbedingung des Falls: die Heuristik muss BEIDE Tests sehen, sonst "
        f"belegt er den Basisabzug nicht. Gesehen: {sorted(head_names)}"
    )

    monkeypatch.chdir(repo)
    reported = {f.test for f in new_findings_against(base_sha)}
    assert reported == {"test_beta_is_documented"}, (
        "Nur der neu hinzugefuegte Befund darf gemeldet werden. Gemeldet: "
        f"{sorted(reported)} -- steht 'test_alpha_is_documented' dabei, fehlt "
        "der Basisabzug und der Schritt meldet den Altbestand an jedem PR."
    )


def test_unchanged_test_file_yields_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein Commit, der die Testdatei nicht anfasst, meldet nichts.

    Der Bestandsbefund bleibt dabei unveraendert im Baum liegen -- ein Lauf,
    der ihn hier melden wuerde, meldete ihn an jedem folgenden PR erneut.
    """
    from check_effectful_tests import new_findings_against

    repo = tmp_path / "repo"
    repo.mkdir()
    _git_in(repo, "init", "-b", "main")
    (repo / "test_thing.py").write_text(_STRING_ONLY_TEST, encoding="utf-8")
    _git_in(repo, "add", "test_thing.py")
    _git_in(repo, "commit", "-m", "basis")
    base_sha = _git_in(repo, "rev-parse", "HEAD")

    (repo / "README.md").write_text("nur Prosa\n", encoding="utf-8")
    _git_in(repo, "add", "README.md")
    _git_in(repo, "commit", "-m", "doku")

    monkeypatch.chdir(repo)
    assert new_findings_against(base_sha) == []


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
