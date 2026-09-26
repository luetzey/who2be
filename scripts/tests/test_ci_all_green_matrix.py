"""Bindet die Wahrheitstabelle des ``all-green``-Jobs an die normale Suite.

``scripts/ci/test_all_green_matrix.py`` prueft die Auswertungslogik des
Aggregat-Jobs — die Logik, die entscheidet, ob ein ``skipped`` eines Vorgaengers
legitim ist oder ein stilles falsches Gruen waere. Sie lief bis zur Karte
``t_5c8d5364`` in **keinem** Job: kein Workflow rief sie auf, und ``pytest``
sammelte sie nicht, weil ``testpaths`` in ``pyproject.toml`` ``scripts/tests``
listet und nicht ``scripts/ci``. Ein Waechter, der nur von Hand laeuft, ist
derselbe Befund, den die Karte fuer ``test_backup_alarm.sh`` erhebt.

Ein Wrapper statt eines Umzugs: der Pfad ``scripts/ci/test_all_green_matrix.py``
steht in ``CHANGELOG.md``, in ``changelog.d/`` und in mehreren Plan-Dateien, und
das Skript bleibt als eigenstaendiges Kommando aufrufbar
(``uv run python scripts/ci/test_all_green_matrix.py``) — es gibt eine lesbare
Wahrheitstabelle aus, die man beim Aendern von ``ci.yml`` direkt liest.

Geladen wird per ``importlib``, nicht per ``sys.path``-Anhang und Import: das
Modul heisst ``test_all_green_matrix`` und wuerde von pytest sonst als zweites
Testmodul mit demselben Namen eingesammelt (seine ``CASES`` sind keine
pytest-Faelle, ``check_structure`` ist keine Assertion-Funktion im
pytest-Sinn — der Sammler wuerde daran nichts finden und die Datei nur doppelt
fuehren).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

MATRIX = Path(__file__).resolve().parents[2] / "scripts" / "ci" / "test_all_green_matrix.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("who2be_all_green_matrix", MATRIX)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Registrieren, damit `from __future__`-Annotationen und Dataclass-artige
    # Konstrukte im Modul einen aufloesbaren `__module__` haben.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_matrix_datei_existiert() -> None:
    """Der Pfad ist in CHANGELOG und Plan-Dateien zitiert — ein Umzug faellt hier auf."""
    assert MATRIX.is_file(), f"{MATRIX} fehlt: Wahrheitstabelle verschoben oder geloescht?"


def test_all_green_wahrheitstabelle_und_struktur() -> None:
    """``main()`` faehrt alle Faelle plus die Struktur-Zusicherungen gegen ``ci.yml``."""
    module = _load()
    assert module.main() == 0, (
        "Die Wahrheitstabelle des all-green-Jobs weicht ab. Einzelbefunde stehen in der "
        "Ausgabe oberhalb; direkt nachfahrbar mit "
        "`uv run python scripts/ci/test_all_green_matrix.py`."
    )


def test_jeder_gegatete_job_ist_in_gated_jobs_gelistet() -> None:
    """``GATED_JOBS`` muss die pfadgefilterten Jobs aus ``ci.yml`` vollstaendig kennen.

    Die Wahrheitstabelle prueft nur Jobs, deren Ergebnis sie ueberhaupt setzt.
    Ein neuer Job mit ``if: needs.changes.outputs.code == 'true'``, der hier
    fehlt, laeuft an der Matrix vorbei — genau der Fehler, den diese Karte fuer
    ``backup-alarm`` behoben hat.
    """
    yaml = pytest.importorskip("yaml")
    module = _load()
    workflow = yaml.safe_load(module.CI_YML.read_text(encoding="utf-8"))
    gated_in_yaml = {
        name
        for name, job in workflow["jobs"].items()
        if job.get("if") == "needs.changes.outputs.code == 'true'"
    }
    assert gated_in_yaml == set(module.GATED_JOBS), (
        "GATED_JOBS und die gegateten Jobs in ci.yml weichen ab: "
        f"nur in ci.yml {sorted(gated_in_yaml - set(module.GATED_JOBS))}, "
        f"nur in GATED_JOBS {sorted(set(module.GATED_JOBS) - gated_in_yaml)}"
    )
