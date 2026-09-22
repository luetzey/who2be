#!/usr/bin/env python3
"""Changelog-Fragmente statt Sammeldatei (towncrier-Muster).

Warum es das gibt
-----------------
``CHANGELOG.md`` ist eine *Sammeldatei*: jeder PR schreibt in dieselbe Datei,
meist an dieselbe Stelle (oben unter ``## [Unreleased]``). Genau dort merged
git messbar oft still falsch — ohne Konfliktmarker, ohne Warnung. In einer
Welle dieses Repos stand danach ein Warnabsatz doppelt im CHANGELOG, gefunden
nur durch einen Cherry-pick-Gegencheck der Baum-Identitaet.

Das Gegenmittel ist strukturell, nicht werkzeuggestuetzt: jeder PR legt eine
*eigene kleine Datei* unter ``changelog.d/`` an. Zwei PRs beruehren dann nie
dieselbe Datei, und der Konflikt kann nicht entstehen. Vor dem Release fuehrt
``collect`` die Fragmente in den CHANGELOG zusammen.

Ausdruecklich **nicht** benutzt wird ``merge=union`` in ``.gitattributes``.
Die git-Dokumentation warnt selbst davor ("Do not use this if you do not
understand the implications."), und der dokumentierte Verlauf in scikit-learn
(Issue #21516) ist exakt unser Fehlerfall: ein bereits entfernter Eintrag kam
durch ``union`` zurueck. Es tauscht einen sichtbaren Konflikt gegen einen
stillen Fehler — die falsche Richtung.

Warum ein eigenes Skript statt towncrier
----------------------------------------
towncrier ist das Referenz-Werkzeug fuer dieses Muster, passt hier aber nicht:
Das Repo traegt Python **und** TypeScript, towncrier waere eine reine
Python-Dependency fuer einen CHANGELOG, der beide Staecke beschreibt. Vor
allem aber baut towncrier den CHANGELOG aus einem eigenen Template neu auf und
kennt die *Keep a Changelog*-Struktur dieses Repos (``## [Unreleased]`` mit
``### Fixed``/``### Security``-Unterabschnitten, mehrabsaetzige Fliesstexte
mit Einrueckung) nicht. Der Zusammenbau selbst ist trivial; das Wertvolle am
Muster ist das Verzeichnis, nicht das Werkzeug.

Form eines Fragments
--------------------
``changelog.d/<slug>.<typ>.md``

* ``<slug>``  — frei, sinnvoll ist der Branch- oder PR-Bezug (``oauth-issuer``,
  ``pr-560``). Er taucht im CHANGELOG nicht auf; er sorgt nur dafuer, dass zwei
  PRs verschiedene Dateien anlegen.
* ``<typ>``   — eine der *Keep a Changelog*-Kategorien:
  ``added``, ``changed``, ``deprecated``, ``removed``, ``fixed``, ``security``.
* Inhalt      — der Markdown-Listenpunkt, so wie er im CHANGELOG stehen soll,
  inklusive fuehrendem ``- ``. Mehrere Absaetze: Folgezeilen um zwei
  Leerzeichen einruecken, genau wie im bestehenden CHANGELOG.

Kommandos
---------
``check``    prueft alle Fragmente auf Namensform, bekannten Typ und Inhalt.
``collect``  fuehrt sie in die ``## [Unreleased]``-Sektion ein und loescht sie.
             ``--dry-run`` schreibt nichts und gibt das Ergebnis auf stdout aus.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

#: Kategorien von *Keep a Changelog* 1.1.0 in ihrer kanonischen Reihenfolge.
#: Die Reihenfolge ist normativ: ``collect`` legt fehlende Unterabschnitte
#: genau hier ein, damit der CHANGELOG nicht je nach Fragment-Reihenfolge
#: anders aussieht.
CATEGORIES: tuple[str, ...] = (
    "added",
    "changed",
    "deprecated",
    "removed",
    "fixed",
    "security",
)

#: Ueberschrift, unter der die Fragmente landen.
UNRELEASED_HEADING = "## [Unreleased]"

#: Dateien im Fragment-Verzeichnis, die keine Fragmente sind.
IGNORED_NAMES = frozenset({"README.md", ".gitkeep", ".gitignore"})


def heading_for(category: str) -> str:
    """``### Fixed`` fuer ``fixed`` — die Schreibweise des bestehenden CHANGELOG."""
    return f"### {category.capitalize()}"


@dataclass(frozen=True)
class Fragment:
    """Ein eingelesenes Fragment."""

    path: Path
    category: str
    body: str

    @property
    def slug(self) -> str:
        return self.path.name.split(".")[0]


class FragmentError(Exception):
    """Ein Fragment ist unbrauchbar — mit einer Meldung, die den Pfad nennt."""


def parse_fragment(path: Path) -> Fragment:
    """Liest ein Fragment ein und validiert Name wie Inhalt.

    :raises FragmentError: bei falscher Namensform, unbekanntem Typ oder
        leerem Inhalt. Die Meldung nennt immer den Dateinamen und die
        erwartete Form — sie landet unveraendert in der CI-Ausgabe.
    """
    name = path.name
    parts = name.split(".")
    if len(parts) != 3 or parts[2] != "md":
        raise FragmentError(
            f"{name}: erwartete Form ist <slug>.<typ>.md "
            f"(Typ: {', '.join(CATEGORIES)}), z. B. oauth-issuer.fixed.md"
        )

    slug, category, _ = parts
    if not slug:
        raise FragmentError(f"{name}: der <slug>-Teil vor dem Typ ist leer")
    if category not in CATEGORIES:
        raise FragmentError(
            f"{name}: unbekannter Typ {category!r} — erlaubt sind {', '.join(CATEGORIES)}"
        )

    body = path.read_text(encoding="utf-8").strip("\n")
    if not body.strip():
        raise FragmentError(f"{name}: leer — das Fragment ist der CHANGELOG-Eintrag selbst")
    if not body.lstrip().startswith("- "):
        raise FragmentError(
            f"{name}: muss ein Markdown-Listenpunkt sein und mit '- ' beginnen "
            "(Folgeabsaetze um zwei Leerzeichen eingerueckt)"
        )

    return Fragment(path=path, category=category, body=body)


def collect_fragments(directory: Path) -> list[Fragment]:
    """Alle Fragmente eines Verzeichnisses, nach Dateiname sortiert.

    Sortiert, damit ``collect`` bei gleichem Bestand immer dasselbe Ergebnis
    liefert — die Reihenfolge des Dateisystems ist keine Zusage.

    :raises FragmentError: sammelt *alle* Fehler und meldet sie gemeinsam,
        damit ein Beitragender nicht pro Lauf einen einzelnen Fehler erfaehrt.
    """
    if not directory.is_dir():
        return []

    problems: list[str] = []
    fragments: list[Fragment] = []
    for path in sorted(directory.iterdir()):
        if not path.is_file() or path.name in IGNORED_NAMES:
            continue
        try:
            fragments.append(parse_fragment(path))
        except FragmentError as exc:
            problems.append(str(exc))

    if problems:
        raise FragmentError("\n".join(problems))
    return fragments


def _find_unreleased_bounds(lines: Sequence[str]) -> tuple[int, int]:
    """Index der ``## [Unreleased]``-Zeile und des Endes ihres Abschnitts.

    Das Ende ist die naechste ``## ``-Ueberschrift (also der naechste Release)
    oder das Dateiende.

    :raises FragmentError: wenn es die Sektion nicht gibt — dann stimmt eine
        Annahme dieses Skripts nicht mehr, und stilles Anhaengen waere der
        Fehler, den es verhindern soll.
    """
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == UNRELEASED_HEADING)
    except StopIteration:
        raise FragmentError(
            f"CHANGELOG.md hat keine Zeile {UNRELEASED_HEADING!r} — "
            "ohne sie weiss dieses Skript nicht, wohin die Fragmente gehoeren."
        ) from None

    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("## "):
            end = i
            break
    return start, end


def _section_index(section: Sequence[str], category: str) -> int | None:
    """Index der ``### Typ``-Ueberschrift innerhalb der Unreleased-Sektion."""
    wanted = heading_for(category)
    for i, line in enumerate(section):
        if line.strip() == wanted:
            return i
    return None


def _insert_into_section(section: list[str], category: str, bodies: Iterable[str]) -> list[str]:
    """Traegt Eintraege in den ``### Typ``-Unterabschnitt ein.

    Existiert der Unterabschnitt, werden die Eintraege ans *Ende* angehaengt —
    der Bestand bleibt unveraendert, neue Eintraege stehen unten. Existiert er
    nicht, wird er an der nach :data:`CATEGORIES` richtigen Stelle angelegt.
    """
    block: list[str] = []
    for body in bodies:
        block.extend(body.split("\n"))
        block.append("")

    index = _section_index(section, category)
    if index is not None:
        # Ende des Unterabschnitts: naechste ###/##-Ueberschrift oder Ende.
        end = len(section)
        for i in range(index + 1, len(section)):
            if section[i].startswith("#"):
                end = i
                break
        # Nachlaufende Leerzeilen gehoeren hinter den neuen Block, nicht davor.
        while end > index + 1 and not section[end - 1].strip():
            end -= 1
        return section[:end] + [""] + block[:-1] + section[end:]

    # Neuer Unterabschnitt: vor dem ersten Typ, der in CATEGORIES spaeter kommt.
    order = CATEGORIES.index(category)
    insert_at = len(section)
    for later in CATEGORIES[order + 1 :]:
        found = _section_index(section, later)
        if found is not None:
            insert_at = found
            break
    else:
        # Kein spaeterer Typ vorhanden -> ans Ende, ohne nachlaufende Leerzeilen.
        while insert_at > 1 and not section[insert_at - 1].strip():
            insert_at -= 1

    new_block = ["", heading_for(category), ""] + block[:-1] + [""]
    return section[:insert_at] + new_block + section[insert_at:]


def render(changelog_text: str, fragments: Sequence[Fragment]) -> str:
    """Der CHANGELOG-Text mit eingearbeiteten Fragmenten.

    Rein funktional: liest keine Dateien und schreibt keine. Das macht die
    Einfuegelogik testbar, ohne ein Repo nachzubauen.
    """
    if not fragments:
        return changelog_text

    lines = changelog_text.split("\n")
    start, end = _find_unreleased_bounds(lines)
    section = lines[start:end]

    for category in CATEGORIES:
        bodies = [f.body for f in fragments if f.category == category]
        if bodies:
            section = _insert_into_section(section, category, bodies)

    return "\n".join(lines[:start] + section + lines[end:])


def cmd_check(directory: Path) -> int:
    try:
        fragments = collect_fragments(directory)
    except FragmentError as exc:
        print(f"Fragmente fehlerhaft:\n{exc}", file=sys.stderr)
        return 1

    if not fragments:
        print(f"Keine Fragmente in {directory}/ — in Ordnung.")
        return 0

    print(f"{len(fragments)} Fragment(e) in {directory}/ in Ordnung:")
    for fragment in fragments:
        print(f"  {fragment.path.name:<40} {heading_for(fragment.category)}")
    return 0


def cmd_collect(directory: Path, changelog: Path, *, dry_run: bool) -> int:
    try:
        fragments = collect_fragments(directory)
    except FragmentError as exc:
        print(f"Fragmente fehlerhaft:\n{exc}", file=sys.stderr)
        return 1

    if not fragments:
        print(f"Keine Fragmente in {directory}/ — nichts zu tun.")
        return 0

    try:
        rendered = render(changelog.read_text(encoding="utf-8"), fragments)
    except FragmentError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if dry_run:
        sys.stdout.write(rendered)
        return 0

    changelog.write_text(rendered, encoding="utf-8")
    for fragment in fragments:
        fragment.path.unlink()
    print(f"{len(fragments)} Fragment(e) in {changelog.name} uebernommen und geloescht.")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parent.parent

    parser = argparse.ArgumentParser(
        prog="changelog_fragments",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dir",
        type=Path,
        default=repo_root / "changelog.d",
        help="Fragment-Verzeichnis (Default: changelog.d/ im Repo-Root)",
    )
    parser.add_argument(
        "--changelog",
        type=Path,
        default=repo_root / "CHANGELOG.md",
        help="Ziel-CHANGELOG (Default: CHANGELOG.md im Repo-Root)",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="Fragmente auf Namensform, Typ und Inhalt pruefen")
    collect = sub.add_parser("collect", help="Fragmente in den CHANGELOG uebernehmen")
    collect.add_argument(
        "--dry-run",
        action="store_true",
        help="Ergebnis auf stdout ausgeben, nichts schreiben und nichts loeschen",
    )

    args = parser.parse_args(argv)
    if args.command == "check":
        return cmd_check(args.dir)
    return cmd_collect(args.dir, args.changelog, dry_run=args.dry_run)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
