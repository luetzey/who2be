#!/usr/bin/env python3
"""Konflikt-Hotspots messen statt vermuten.

Warum es das gibt
-----------------
Die Frage "welche Datei ist unsere Konfliktnabe?" wurde in diesem Repo
wiederholt aus dem Gedaechtnis beantwortet — und lag falsch. Karte
``t_6324bea8`` sollte ``.claude/context/STATE.md`` als Konfliktquelle
strukturell beseitigen; die Messung ergab fuer ``STATE.md`` **null** Konflikte
und wies die Last ``.github/workflows/ci.yml`` und den Lockfiles zu. Ohne
Messung waere ein Verfahren fuer die falsche Datei gebaut worden.

Dieses Skript macht die Messung wiederholbar. Es aendert **nichts**:
``git merge-tree --write-tree`` fuehrt den Merge im Objektspeicher aus, ohne
Arbeitsverzeichnis, ohne Ref, ohne Commit.

Was gemessen wird, und warum gerade das
---------------------------------------
``hotspots``  Welche Pfade loest git beim Merge zweier offener PRs *nicht*
              selbst auf. Das ist die belastbarste Sicht auf die *aktuelle*
              Last, weil sie den Merge wirklich ausfuehrt statt Diffs zu
              zaehlen. Eine Datei, die zwei PRs anfassen, ohne zu kollidieren,
              ist kein Problem.

``resolved``  An welchen Pfaden wurden in der *History* real Konflikte von Hand
              aufgeloest. Der combined diff eines Merge-Commits
              (``git show --cc``) listet per Definition nur Dateien, die
              gegenueber **beiden** Eltern abweichen — also genau das, was der
              Mergende angefasst hat. Das ist ein Nachweis, waehrend "wie oft
              wurde die Datei geaendert" nur ein Verdacht ist.

``kind``      Anhaengsel oder Bestands-Umbau. Ein Fragment-Verfahren nach dem
              Muster von ``changelog.d/`` beseitigt **nur** Anhaengsel: neue
              Zeilen an einer Stelle, ohne Bestand zu entfernen. Wer eine
              vorhandene Zeile korrigiert, muss die Sammeldatei anfassen, auch
              mit Fragmenten. Diese Unterscheidung entscheidet, ob ein
              Verfahren traegt — sie fehlte in der Vermutung zu ``STATE.md``.

Kommandos
---------
``hotspots``  offene PRs paarweise und gegen die Basis mergen (braucht ``gh``).
``resolved``  aufgeloeste Konflikte der History zaehlen.
``kind``      Aenderungen an genannten Dateien klassifizieren.
"""

from __future__ import annotations

import argparse
import collections
import itertools
import json
import re
import subprocess
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

#: Zeile, mit der ``git merge-tree --messages`` einen echten Konflikt meldet.
#: Bewusst streng verankert: die harmlose Meldung ``Auto-merging <pfad>`` nennt
#: denselben Pfad, und ein ``pfad in ausgabe``-Test haelt darum jeden
#: Auto-Merge fuer einen Konflikt. Genau dieser Fehler hat die erste Messung
#: zu ``STATE.md`` unbrauchbar gemacht.
CONFLICT_LINE = re.compile(r"^CONFLICT \([^)]+\): .*? in (.+)$", re.M)

#: Kopfzeile eines Diff-Hunks, gezaehlt als "Stelle" im Sinne von ``kind``.
HUNK_LINE = re.compile(r"^@@ ", re.M)


class MeasureError(Exception):
    """Die Messung kann nicht durchgefuehrt werden — mit nennbarem Grund."""


def _run(argv: Sequence[str]) -> str:
    """Ein Kommando aufrufen und stdout zurueckgeben.

    :raises MeasureError: wenn es fehlschlaegt, mit Kommando und stderr — ein
        Fehlschlag soll ohne Nachstellen lesbar sein.
    """
    try:
        proc = subprocess.run(  # noqa: S603 - festes Argv, keine Shell
            list(argv),
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        raise MeasureError(f"{argv[0]} ist nicht verfuegbar") from None
    # `git merge-tree` liefert 1 fuer "Konflikt" — ein Ergebnis, kein Fehler.
    if proc.returncode not in (0, 1):
        raise MeasureError(f"{' '.join(argv)} fehlgeschlagen: {proc.stderr.strip()}")
    return proc.stdout


def git(*args: str) -> str:
    return _run(["git", *args])


def conflicting_paths(output: str) -> list[str]:
    """Die Pfade, die ``git merge-tree --messages`` als Konflikt meldet.

    Rein funktional ueber den Ausgabetext, damit die Erkennung unter pytest
    steht statt nur im Lauf.
    """
    return sorted({match.group(1).strip() for match in CONFLICT_LINE.finditer(output)})


def merge_conflicts(a: str, b: str) -> list[str]:
    """Pfade, die git beim Merge von ``a`` und ``b`` nicht selbst aufloest."""
    return conflicting_paths(git("merge-tree", "--write-tree", "--messages", a, b))


@dataclass(frozen=True)
class Change:
    """Eine Aenderung an einer Datei, klassifiziert."""

    sha: str
    added: int
    removed: int
    hunks: int

    @property
    def kind(self) -> str:
        """``anhaengsel``, ``mehrstellig`` oder ``umbau``.

        Nur ``anhaengsel`` — neue Zeilen an genau einer Stelle, ohne dass
        bestehende verschwinden — beseitigt ein Fragment-Verfahren. ``umbau``
        aendert Bestand und bleibt konfliktfaehig; ``mehrstellig`` fuegt nur
        hinzu, aber an mehreren Stellen, und traegt damit dasselbe Risiko wie
        jede Datei, die zwei Karten an verschiedenen Punkten anfassen.
        """
        if self.removed:
            return "umbau"
        if self.hunks > 1:
            return "mehrstellig"
        return "anhaengsel"


def classify_diff(sha: str, diff: str) -> Change:
    """Einen Diff-Text in eine :class:`Change` uebersetzen.

    Rein funktional, damit die Klassifikation ohne Repo testbar ist.
    """
    lines = diff.split("\n")
    added = sum(1 for line in lines if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in lines if line.startswith("-") and not line.startswith("---"))
    return Change(sha=sha, added=added, removed=removed, hunks=len(HUNK_LINE.findall(diff)))


def change_for(sha: str, path: str) -> Change:
    """Die Aenderung, die ``sha`` an ``path`` vornimmt.

    ``-m --first-parent`` ist nicht optional: fuer einen **Merge**-Commit
    liefert ``git show`` sonst einen leeren Diff (der combined diff zeigt nur
    Konflikt-Hunks). Dieses Repo mergt ohne Squash, die PR-Commits waeren also
    genau die unsichtbaren — ein Fehler, der eine erste Messung zu ``STATE.md``
    mit "+0/-0" beantwortet hat.
    """
    return classify_diff(
        sha, git("show", "-m", "--first-parent", "--format=", "-U0", sha, "--", path)
    )


def open_pull_requests(limit: int) -> list[int]:
    """Die Nummern der offenen PRs, via ``gh``."""
    raw = _run(["gh", "pr", "list", "--state", "open", "--limit", str(limit), "--json", "number"])
    try:
        return [int(item["number"]) for item in json.loads(raw)]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise MeasureError(f"unerwartete Antwort von 'gh pr list': {exc}") from None


def cmd_hotspots(base: str, limit: int) -> int:
    numbers = open_pull_requests(limit)
    if len(numbers) < 2:
        print(f"Nur {len(numbers)} offene(r) PR — fuer eine Paar-Messung zu wenig.")
        return 0

    refs: dict[int, str] = {}
    for number in numbers:
        ref = f"refs/pull/{number}/head"
        local = f"conflict-hotspots/pr{number}"
        git("fetch", "origin", f"{ref}:{local}", "--force", "--quiet")
        refs[number] = local

    print(f"### jeder offene PR gegen {base} ###")
    for number in numbers:
        found = merge_conflicts(base, refs[number])
        print(f"  #{number:<6} {', '.join(found) if found else 'konfliktfrei'}")

    print(f"\n### die {len(numbers)} offenen PRs paarweise ###")
    tally: collections.Counter[str] = collections.Counter()
    for a, b in itertools.combinations(numbers, 2):
        found = merge_conflicts(refs[a], refs[b])
        if found:
            print(f"  #{a} x #{b}: {', '.join(found)}")
            tally.update(found)
    if not tally:
        print("  keine")

    print("\n### Hotspots (Paar-Messung) ###")
    for path, count in tally.most_common():
        print(f"  {count:>3}x  {path}")
    if not tally:
        print("  keine — die offenen PRs kollidieren nirgends.")
    return 0


def cmd_resolved(base: str, window: int) -> int:
    merges = [
        line.split()[0]
        for line in git(
            "log", "--first-parent", "--merges", "--format=%H", f"{base}~{window}..{base}"
        ).splitlines()
        if line.strip()
    ]
    print(f"Merge-Commits im Fenster (letzte {window} first-parent auf {base}): {len(merges)}\n")

    tally: collections.Counter[str] = collections.Counter()
    for sha in merges:
        touched = [
            p
            for p in git("show", "--cc", "--format=", "--name-only", sha).splitlines()
            if p.strip()
        ]
        if touched:
            subject = git("show", "-s", "--format=%ad %s", "--date=short", sha).strip()
            print(f"  {sha[:8]} {subject[:60]}")
            for path in touched:
                print(f"           handverlesen: {path}")
            tally.update(touched)

    print(f"\n### Dateien mit real aufgeloesten Konflikten ({len(tally)}) ###")
    for path, count in tally.most_common():
        print(f"  {count:>3}x  {path}")
    if not tally:
        print("  keine — in diesem Fenster wurde kein Konflikt von Hand aufgeloest.")
    return 0


def cmd_kind(base: str, window: int, paths: Iterable[str]) -> int:
    start = git("log", "--first-parent", "--format=%H", base).splitlines()
    if len(start) <= window:
        raise MeasureError(f"{base} hat weniger als {window} first-parent-Commits")
    span = f"{start[window]}..{base}"
    print(f"Fenster: letzte {window} first-parent-Commits auf {base} ({start[window][:8]}..)\n")

    for path in paths:
        shas = [
            s
            for s in git("log", "--first-parent", "--format=%H", span, "--", path).splitlines()
            if s
        ]
        print(f"===== {path} — {len(shas)} Aenderung(en) =====")
        tally: collections.Counter[str] = collections.Counter()
        for sha in shas:
            change = change_for(sha, path)
            subject = git("show", "-s", "--format=%ad %s", "--date=short", sha).strip()
            tally[change.kind] += 1
            print(
                f"  {sha[:8]} +{change.added:<4}-{change.removed:<4} "
                f"{change.hunks:>2} Stelle(n)  {change.kind:<12} {subject[:52]}"
            )
        print(f"  -> {dict(tally) or 'nie geaendert'}\n")
    return 0


#: Die Sammeldateien, die in diesem Repo wiederholt als Konfliktnabe gelten.
#: Default fuer ``kind``, damit die Messung ohne Argumentliste reproduzierbar
#: ist; ``CHANGELOG.md`` steht als Vergleichsmassstab dabei (dort laeuft das
#: Fragment-Verfahren, siehe ``scripts/changelog_fragments.py``).
DEFAULT_KIND_PATHS: tuple[str, ...] = (
    ".claude/context/STATE.md",
    ".claude/context/DECISIONS.md",
    "CONTRIBUTING.md",
    "CHANGELOG.md",
    ".github/workflows/ci.yml",
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="conflict_hotspots",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--base",
        default="origin/main",
        help="Vergleichsbasis bzw. gemessener Zweig (Default: origin/main)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    hotspots = sub.add_parser("hotspots", help="offene PRs gegeneinander mergen (braucht gh)")
    hotspots.add_argument(
        "--limit", type=int, default=80, help="max. Anzahl offener PRs (Default: 80)"
    )

    resolved = sub.add_parser("resolved", help="in der History aufgeloeste Konflikte zaehlen")
    resolved.add_argument(
        "--window", type=int, default=60, help="first-parent-Fenster (Default: 60)"
    )

    kind = sub.add_parser("kind", help="Aenderungen als Anhaengsel oder Umbau klassifizieren")
    kind.add_argument("--window", type=int, default=60, help="first-parent-Fenster (Default: 60)")
    kind.add_argument(
        "paths", nargs="*", default=list(DEFAULT_KIND_PATHS), help="zu messende Dateien"
    )

    args = parser.parse_args(argv)
    try:
        if args.command == "hotspots":
            return cmd_hotspots(args.base, args.limit)
        if args.command == "resolved":
            return cmd_resolved(args.base, args.window)
        return cmd_kind(args.base, args.window, args.paths or list(DEFAULT_KIND_PATHS))
    except MeasureError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
