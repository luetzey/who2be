#!/usr/bin/env python3
"""Hilfe-Drift-Warnung: UI geaendert, Hilfe nicht (Doku-Drift Stufe 2).

Ein PR, der nutzersichtbare Web-Pfade aendert, ohne die In-App-Hilfe unter
``apps/web/src/help/`` anzufassen, bekommt eine GitHub-Annotation ``warning``
und eine Zeile im Job-Summary. Ausweg ist eine Zeile in der PR-Beschreibung::

    Hilfe: n/a – <Grund>

mit einem Grund aus der festen Liste ``REASONS``. Hintergrund (Recherche
``clients-und-doku-drift-2026-10.md`` §6.1): ein Freitextfeld ohne Pruefung
wird zum Ritual (Kubernetes, PR #142175), eine Bot-Regel mit klarer Ausnahme
funktioniert. Deshalb ist der Grund eine Kategorie, kein Freitext.

Bewusst eine **Warnung**, kein Block (Owner-Entscheidung W-B1, 2026-10-22):
das Skript endet immer mit Exit 0, auch bei eigenen Fehlern. Eine Sperre
kommt erst, wenn die Warnung oft ignoriert wird.

Die Pfadtabelle ist eng gehalten, weil eine grobe Regel (jede Aenderung unter
``features/``) so viele Fehlalarme erzeugt, dass sie niemand mehr liest:

* ``apps/web/src/features/<feature>/components/**`` ohne Testdateien;
* ``apps/web/src/i18n/locales/*.json``, aber nur Schluessel, die vorher und
  nachher existieren und deren **Wert** sich geaendert hat. Ein neuer
  Schluessel ist neuer Text, kein umbenannter Knopf, auf den die Hilfe schon
  zeigt.

Die Entscheidung steht in reinen Funktionen (``ui_component_hits``,
``changed_locale_values``, ``parse_declaration``, ``evaluate``); ``main`` misst
nur mit git und schreibt die Ausgabe. Tests: ``scripts/tests/test_help_drift.py``.

Nutzung (im CI-Job ``changes``)::

    PR_BODY="$BODY" python3 scripts/ci/help_drift.py --base <sha> --head <sha>
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal

HELP_PREFIX = "apps/web/src/help/"
LOCALES_DIR = "apps/web/src/i18n/locales/"

_COMPONENT = re.compile(r"^apps/web/src/features/[^/]+/components/.+")
_TEST_FILE = re.compile(r"(\.test\.|\.spec\.|/__tests__/|/__snapshots__/)")
_LOCALE = re.compile(r"^apps/web/src/i18n/locales/[^/]+\.json$")

# Feste Grundliste. `Folgekarte` verlangt eine Kennung: Kanban-Karte (t_…)
# oder GitHub-Issue (#…), damit der Grund nachpruefbar ist.
REASONS = ("intern", "kein UI-Text", "nur Tests", "Folgekarte <id>")
_REASON = re.compile(
    r"^(?P<cat>intern|kein UI-Text|nur Tests|Folgekarte\s+(?:t_[0-9a-f]+|#\d+))"
    # Optional eine Erlaeuterung hinter der Kategorie, abgesetzt durch
    # Doppelpunkt, Klammer, Komma oder Gedankenstrich.
    r"(?:\s*(?:[:(,]|\s[–—-]\s).*)?\.?$",
    re.IGNORECASE,
)
_HELP_LINE = re.compile(r"^[ \t]*Hilfe:[ \t]*(?P<value>.*?)[ \t]*$", re.MULTILINE)
_NA = re.compile(r"^n/?a\s*[–—-]\s*(?P<reason>.*)$", re.IGNORECASE)
_CHANGED = re.compile(r"^ge(?:ä|ae)ndert\.?$", re.IGNORECASE)
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)

MAX_LISTED = 10


@dataclass(frozen=True)
class Declaration:
    """Was die PR-Beschreibung zur Hilfe sagt."""

    kind: Literal["missing", "changed", "na", "invalid"]
    value: str = ""


@dataclass(frozen=True)
class Verdict:
    warn: bool
    summary: str


def ui_component_hits(paths: list[str]) -> list[str]:
    """Geaenderte Komponenten-Dateien, ohne Tests und Snapshots."""
    return sorted(p for p in paths if _COMPONENT.match(p) and not _TEST_FILE.search(p))


def _flatten(node: object, prefix: str = "") -> dict[str, object]:
    if isinstance(node, dict):
        out: dict[str, object] = {}
        for key, value in node.items():
            out.update(_flatten(value, f"{prefix}.{key}" if prefix else str(key)))
        return out
    if isinstance(node, list):
        out = {}
        for i, value in enumerate(node):
            out.update(_flatten(value, f"{prefix}[{i}]"))
        return out
    return {prefix: node}


def changed_locale_values(base_text: str | None, head_text: str | None) -> list[str]:
    """Schluessel, die in Basis und Head stehen und deren Wert sich aenderte.

    Fehlt eine Seite (Datei neu oder geloescht), gibt es keinen *geaenderten*
    Wert. Ist eine Seite kein gueltiges JSON, wird das als Treffer ``<ungueltiges
    JSON>`` gemeldet: lieber eine Warnung zu viel als ein stilles Uebersehen.
    """
    if base_text is None or head_text is None:
        return []
    try:
        base = _flatten(json.loads(base_text))
        head = _flatten(json.loads(head_text))
    except ValueError:
        return ["<ungueltiges JSON>"]
    return sorted(k for k in base.keys() & head.keys() if base[k] != head[k])


def parse_declaration(body: str | None) -> Declaration:
    """Liest die erste ``Hilfe:``-Zeile ausserhalb von HTML-Kommentaren."""
    text = _HTML_COMMENT.sub("", body or "")
    match = _HELP_LINE.search(text)
    if match is None:
        return Declaration("missing")
    value = match.group("value").strip()
    if _CHANGED.match(value):
        return Declaration("changed", value)
    na = _NA.match(value)
    if na and _REASON.match(na.group("reason").strip()):
        return Declaration("na", na.group("reason").strip())
    return Declaration("invalid", value)


def _listing(items: list[str]) -> str:
    shown = ", ".join(items[:MAX_LISTED])
    rest = len(items) - MAX_LISTED
    return f"{shown} (+{rest} weitere)" if rest > 0 else shown


def evaluate(
    ui_hits: list[str], locale_hits: list[str], help_changed: bool, decl: Declaration
) -> Verdict:
    """Die eigentliche Regel. ``locale_hits`` traegt ``datei: schluessel``."""
    hits = ui_hits + locale_hits
    allowed = " | ".join(REASONS)
    if not hits:
        return Verdict(False, "Hilfe-Drift: keine nutzersichtbaren UI-Pfade geändert.")
    if help_changed:
        return Verdict(False, "Hilfe-Drift: UI geändert, Hilfe ebenfalls geändert.")
    if decl.kind == "na":
        return Verdict(False, f"Hilfe-Drift: UI geändert, Ausnahme „{decl.value}“ angegeben.")
    lead = f"UI geändert, Hilfe nicht: {_listing(hits)}."
    if decl.kind == "invalid":
        why = f"Die Zeile „Hilfe: {decl.value}“ nennt keinen Grund aus der Liste ({allowed})."
    elif decl.kind == "changed":
        why = (
            "Die PR-Beschreibung sagt „Hilfe: geändert“, "
            f"unter {HELP_PREFIX} ist aber nichts geändert."
        )
    else:
        why = "Die PR-Beschreibung hat keine Zeile „Hilfe:“."
    fix = f"Hilfe unter {HELP_PREFIX} nachziehen oder „Hilfe: n/a – <Grund>“ eintragen ({allowed})."
    return Verdict(True, f"{lead} {why} {fix}")


# --------------------------------------------------------------------------
# Messung und Ausgabe
# --------------------------------------------------------------------------


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def _show(rev: str, path: str) -> str | None:
    try:
        return _git("show", f"{rev}:{path}")
    except subprocess.CalledProcessError:
        return None


def _escape(message: str) -> str:
    # Workflow-Kommando-Daten: %, CR und LF muessen kodiert werden.
    return message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def measure(base: str, head: str) -> tuple[list[str], list[str], bool]:
    merge_base = _git("merge-base", base, head).strip()
    paths = [
        p for p in _git("diff", "--name-only", "--no-renames", merge_base, head).splitlines() if p
    ]
    locale_hits: list[str] = []
    for path in paths:
        if _LOCALE.match(path):
            name = PurePosixPath(path).name
            keys = changed_locale_values(_show(merge_base, path), _show(head, path))
            locale_hits.extend(f"{name}: {k}" for k in keys)
    help_changed = any(p.startswith(HELP_PREFIX) for p in paths)
    return ui_component_hits(paths), locale_hits, help_changed


def _emit(verdict: Verdict) -> None:
    if verdict.warn:
        print(f"::warning title=Hilfe-Drift::{_escape(verdict.summary)}")
    else:
        print(verdict.summary)
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        mark = "⚠️ " if verdict.warn else ""
        with open(summary_file, "a", encoding="utf-8") as fh:
            fh.write(f"{mark}{verdict.summary}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hilfe-Drift-Warnung (immer Exit 0).")
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    args = parser.parse_args(argv)
    try:
        ui_hits, locale_hits, help_changed = measure(args.base, args.head)
        decl = parse_declaration(os.environ.get("PR_BODY"))
        _emit(evaluate(ui_hits, locale_hits, help_changed, decl))
    except Exception as exc:  # Warnung darf nie den Job faerben
        print(f"::notice title=Hilfe-Drift::Prüfung nicht möglich: {_escape(str(exc))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
