"""Tests fuer ``scripts/conflict_hotspots.py``.

Gemessen wird mit git, entschieden wird in reinen Funktionen
(:func:`conflicting_paths`, :func:`classify_diff`) — diese Tests halten sie
gegen handgeschriebene Ausgabetexte statt gegen ein nachgebautes Repo, genau
wie ``test_changelog_fragments.py`` es fuer ``render`` tut.

Zwei der Tests sind Regressionstests fuer Messfehler, die in der Karte
``t_6324bea8`` erst ein falsches Ergebnis erzeugt haben. Sie stehen hier, weil
ein Messwerkzeug, das still falsch misst, schlimmer ist als keines.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conflict_hotspots import (  # noqa: E402
    DEFAULT_KIND_PATHS,
    Change,
    MeasureError,
    classify_diff,
    conflicting_paths,
    main,
)

# --------------------------------------------------------------------------
# conflicting_paths — die Konflikt-Erkennung
# --------------------------------------------------------------------------

MERGE_TREE_MIT_KONFLIKT = """\
c5e8171a3598ca88c24c8a8b65a92f474de13b6e
100644 0a059e533f257c376fa227468bcfd4e47f74a9c8 1\tdocs/branch-protection-main.md

Auto-merging .claude/context/DECISIONS.md
Auto-merging .claude/context/STATE.md
Auto-merging ROADMAP.md
Auto-merging docs/branch-protection-main.md
CONFLICT (content): Merge conflict in docs/branch-protection-main.md
"""


def test_konflikt_pfad_wird_erkannt() -> None:
    assert conflicting_paths(MERGE_TREE_MIT_KONFLIKT) == ["docs/branch-protection-main.md"]


def test_auto_merging_ist_kein_konflikt() -> None:
    """Regression: ``Auto-merging <pfad>`` darf nicht als Konflikt zaehlen.

    Der Kern des Messfehlers in ``t_6324bea8``: eine Erkennung per
    ``pfad in ausgabe`` hielt ``STATE.md`` fuer konfliktbehaftet, weil git die
    erfolgreiche Zusammenfuehrung derselben Datei meldet. Das Ergebnis war das
    genaue Gegenteil der Wahrheit — ``STATE.md`` mergt sauber.
    """
    found = conflicting_paths(MERGE_TREE_MIT_KONFLIKT)
    assert ".claude/context/STATE.md" not in found
    assert ".claude/context/DECISIONS.md" not in found
    assert "ROADMAP.md" not in found


def test_konfliktfreier_merge_nennt_keinen_pfad() -> None:
    assert conflicting_paths("abc123\n\nAuto-merging CHANGELOG.md\n") == []


def test_mehrere_konflikte_sortiert_und_dedupliziert() -> None:
    out = (
        "CONFLICT (content): Merge conflict in b.txt\n"
        "CONFLICT (content): Merge conflict in a.txt\n"
        "CONFLICT (add/add): Merge conflict in b.txt\n"
    )
    assert conflicting_paths(out) == ["a.txt", "b.txt"]


@pytest.mark.parametrize(
    "art",
    ["content", "add/add", "modify/delete", "rename/rename"],
)
def test_konfliktarten_werden_alle_erkannt(art: str) -> None:
    """Die Klammer traegt je nach Fall verschiedene Woerter — alle zaehlen."""
    assert conflicting_paths(f"CONFLICT ({art}): Merge conflict in x/y.md") == ["x/y.md"]


def test_pfad_mit_leerzeichen_bleibt_vollstaendig() -> None:
    out = "CONFLICT (content): Merge conflict in docs/mein bericht.md"
    assert conflicting_paths(out) == ["docs/mein bericht.md"]


# --------------------------------------------------------------------------
# classify_diff — Anhaengsel oder Umbau
# --------------------------------------------------------------------------

ANHAENGSEL = """\
@@ -3,0 +4,3 @@ _Stand: 2026-09-19_
+## Ein neuer Abschnitt
+
+Text dazu.
"""

UMBAU = """\
@@ -2234,3 +2234,3 @@ Branch-Namen, DoD-Belege
-- **81 Tools** (58 + 23 aus WorkArea/KB/Tabellen, ADR-0047)
+- **83 Tools** (58 + 25 aus WorkArea/KB/Tabellen, ADR-0047)
@@ -2419,3 +2419,3 @@ Arbeitsbereich
-- **MCP:** 58 -> **81 Tools**
+- **MCP:** 58 -> **83 Tools**
"""

MEHRSTELLIG = """\
@@ -10,0 +11,1 @@
+Zusatz oben.
@@ -80,0 +82,1 @@
+Zusatz unten.
"""


def test_anhaengsel_erkannt() -> None:
    change = classify_diff("abc", ANHAENGSEL)
    assert (change.added, change.removed, change.hunks) == (3, 0, 1)
    assert change.kind == "anhaengsel"


def test_bestands_umbau_erkannt() -> None:
    """Der Fall, den ein Fragment-Verfahren *nicht* loesen kann.

    ``d50d6108`` korrigierte "81 Tools" zu "83 Tools" an zwei Stellen tief im
    Dokument. Ein Fragment kann eine vorhandene Zeile nicht ersetzen — genau
    darum trug die Praemisse zu ``STATE.md`` nicht.
    """
    change = classify_diff("abc", UMBAU)
    assert change.removed == 2
    assert change.hunks == 2
    assert change.kind == "umbau"


def test_nur_zusatz_an_mehreren_stellen_ist_kein_anhaengsel() -> None:
    change = classify_diff("abc", MEHRSTELLIG)
    assert change.removed == 0
    assert change.hunks == 2
    assert change.kind == "mehrstellig"


def test_leerer_diff_zaehlt_nichts() -> None:
    """Ein Merge-Commit ohne ``-m --first-parent`` liefert genau das.

    Regression: die erste Messung meldete fuer fuenf von sechs
    ``STATE.md``-Aenderungen "+0/-0", weil ``git show`` fuer Merge-Commits den
    combined diff zeigt. Der Zaehler ist hier korrekt — der Aufrufer muss die
    richtigen git-Flags setzen, und :func:`change_for` tut das dokumentiert.
    """
    change = classify_diff("abc", "")
    assert (change.added, change.removed, change.hunks) == (0, 0, 0)


def test_dateikopf_zeilen_zaehlen_nicht_als_aenderung() -> None:
    diff = """\
--- a/x.md
+++ b/x.md
@@ -1,0 +2,1 @@
+Eine Zeile.
"""
    change = classify_diff("abc", diff)
    assert (change.added, change.removed) == (1, 0)


def test_change_ist_unveraenderlich() -> None:
    with pytest.raises(AttributeError):
        Change(sha="a", added=1, removed=0, hunks=1).added = 2  # type: ignore[misc]


# --------------------------------------------------------------------------
# CLI-Verdrahtung
# --------------------------------------------------------------------------


def test_default_pfade_enthalten_nabe_und_massstab() -> None:
    """``CHANGELOG.md`` gehoert in die Default-Messung als Vergleichsmassstab.

    Dort laeuft das Fragment-Verfahren; ohne diese Spalte fehlt der Bezug, an
    dem sich eine behauptete Konfliktnabe messen laesst.
    """
    assert ".claude/context/STATE.md" in DEFAULT_KIND_PATHS
    assert "CHANGELOG.md" in DEFAULT_KIND_PATHS
    assert ".github/workflows/ci.yml" in DEFAULT_KIND_PATHS


def test_ohne_unterkommando_bricht_ab() -> None:
    with pytest.raises(SystemExit):
        main([])


def test_kind_meldet_zu_kleines_fenster_lesbar(monkeypatch: pytest.MonkeyPatch) -> None:
    import conflict_hotspots

    monkeypatch.setattr(conflict_hotspots, "git", lambda *args: "sha1\nsha2\n")
    assert main(["kind", "--window", "60", "CHANGELOG.md"]) == 1


def test_measure_error_wird_zu_exit_1(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import conflict_hotspots

    def explode(*args: str) -> str:
        raise MeasureError("git ist nicht verfuegbar")

    monkeypatch.setattr(conflict_hotspots, "git", explode)
    assert main(["resolved"]) == 1
    assert "nicht verfuegbar" in capsys.readouterr().err
