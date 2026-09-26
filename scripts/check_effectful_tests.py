#!/usr/bin/env python3
"""Neue Tests darauf pruefen, dass sie Wirkung ausfuehren (Karte t_3a17f078).

Beobachtetes Problem: ein Test liest eine Datei, sichert eine Zeichenkette darin
zu und laeuft nie durch den Prueflung. Er ist gruen, solange der Text steht --
auch dann, wenn die Sache, die der Text beschreibt, nicht funktioniert. An
einem Tag ist dieser Fehlertyp dreimal aufgetreten und zweimal durch alle Gates
gekommen; einmal konnten dreizehn bestehende Testfaelle einen abgeschnittenen
Datenbank-Dump prinzipbedingt nicht fangen.

**Warum ein Pruefer und keine Regel in einem Dokument.** Gemessen wurde, dass
die Anweisungs-Dokumente in 89 % der Laeufe nicht im Kontext sind. Eine Regel,
die niemand liest, wirkt nicht. Dieser Schritt greift auch dann, wenn kein
Dokument gelesen wurde -- das ist sein ganzer Zweck.

**Der Pruefer aendert nichts.** Er parst Python zu einem AST, liest ``git``
ausschliesslich lesend (``diff``/``show``) und meldet. Kein Fix-Modus: ein
Pruefer, der repariert, verwischt genau die Information, die der Mensch sehen
soll. Denselben Zuschnitt hat ``scripts/check_code_refs.py``.

Markiert wird eine Testfunktion, wenn ALLE DREI Bedingungen zutreffen:

1. Sie liest Dateiinhalte -- direkt oder ueber einen lokalen Helfer (transitiv).
2. Sie ruft keine Wirkung auf: kein erstparteilich importiertes Symbol, kein
   Prozess-Start, kein HTTP-Aufruf gegen die App, auch nicht ueber einen Helfer.
3. Alle ihre Zusicherungen sind Vergleiche oder Containment-Pruefungen.

Die transitive Auflösung ueber Helfer ist nicht Kosmetik. Ohne sie schluepft ein
Test durch, dessen Lesevorgang zwei Helferebenen tief liegt -- genau diese Form
hatte einer der drei historischen Faelle, und der erste Prototyp uebersah ihn.

**Grenze, ausdruecklich benannt:** Dieser Pruefer sieht Python. Die
Backup-Testsuite (``deploy/hetzner/tests/test_backup_alarm.sh``) ist in Bash
geschrieben; der dritte der drei historischen Faelle liegt dort und wird hier
NICHT erfasst. Das ist eine Methodengrenze, keine Kalibrierungsfrage.

**Diff-basiert, mit Absicht.** Gegen den Gesamtbestand markiert die Heuristik
rund 1,5 % aller Testfunktionen -- darunter legitime Faelle, die nie behoben
werden sollen. Geprueft werden deshalb nur Funktionen, die im Diff gegen die
Basis NEU sind. Kein Baseline-Bestand, keine Alt-Last-Welle.

Ausnahmeweg (Pflicht, sonst wird der Schritt nach dem dritten Fehlalarm
abgeschaltet): ein Kommentar in oder unmittelbar ueber der ``def``-Zeile.

    # effect-exempt: prueft eine Doku-Zusage, hat keinen Prueflung
    def test_documented_tool_count_matches_registry() -> None: ...

Die Begruendung ist Pflicht -- ein leerer Marker zaehlt nicht. Markdown- und
Doku-Konformitaetspruefungen SIND zulaessigerweise Zeichenketten-Tests; der
Marker ist fuer sie da, nicht fuer Bequemlichkeit.

Exit-Codes: 0 = nichts zu melden ODER meldender Modus (Default), 1 = Funde im
Modus ``--strict``, 2 = Aufrufsfehler.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from pathlib import Path

# --- Was als "eigener Code" gilt ---------------------------------------------

# Ein Aufruf in eines dieser Pakete ist Wirkung: da laeuft der Prueflung.
# Relative Importe (``from .conftest import ...``) zaehlen ebenfalls, weil
# Testhelfer im selben Paket den Prueflung kapseln.
_FIRST_PARTY_PREFIXES = (
    "who2be_api",
    "who2be_mcp",
    "who2be_models",
    "who2be_billing",
    "scripts",
    "check_code_refs",
    "changelog_fragments",
    "check_effectful_tests",
    "conflict_hotspots",
)

# Lesende Zugriffe auf Dateiinhalte.
_READ_ATTRS = frozenset({"read_text", "read_bytes", "readlines", "readline", "read"})

# Ein Prozess-Start IST Wirkung -- egal was er startet. Ein Test, der
# ``scripts/foo.py`` per subprocess faehrt, prueft dessen Verhalten.
_SUBPROCESS_STARTERS = frozenset(
    {"run", "check_output", "check_call", "call", "Popen", "getoutput", "getstatusoutput"}
)

# HTTP gegen die App. Bewusst an den Namen gebunden, unter denen TestClient und
# httpx-Clients in diesem Repo gefuehrt werden -- ein nackter ``.get`` waere zu
# breit (``dict.get`` ist kein HTTP-Aufruf).
_HTTP_CLIENT_NAMES = frozenset(
    {"client", "app", "ac", "async_client", "http", "test_client", "api", "anon", "authed"}
)
_HTTP_METHODS = frozenset({"get", "post", "put", "patch", "delete", "head", "request"})

# Der Ausnahmemarker. Die Begruendung hinter dem Doppelpunkt ist Pflicht: ohne
# sie ist der Marker ein stilles Abschalten, und genau das soll er nicht sein.
_EXEMPT_RE = re.compile(r"#\s*effect-exempt\s*:\s*(?P<reason>\S.*?)\s*$")

_TEST_FILE_RE = re.compile(r"(?:^test_.*\.py$|_test\.py$)")


@dataclass
class Finding:
    """Eine markierte Testfunktion."""

    file: str
    line: int
    test: str
    why: str


# --- AST-Werkzeug ------------------------------------------------------------


class _ModuleIndex:
    """Was ein Modul ueber sich selbst verraet: Importe und lokale Helfer."""

    def __init__(self, tree: ast.Module) -> None:
        self.first_party_names: set[str] = set()
        self.helpers: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                # ``node.level > 0`` ist ein relativer Import -- im Testpaket
                # sind das die Fixtures und Helfer, die den Prueflung kapseln.
                if node.level > 0 or module.startswith(_FIRST_PARTY_PREFIXES):
                    for alias in node.names:
                        self.first_party_names.add(alias.asname or alias.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(_FIRST_PARTY_PREFIXES):
                        self.first_party_names.add((alias.asname or alias.name).split(".")[0])

        # Nur Helfer auf Modulebene. Eine Methode in einer Testklasse ueber
        # ``self`` aufzuloesen waere eine Genauigkeit, die diese Heuristik nicht
        # braucht -- und ein Test in einer Klasse hat ohnehin ``self`` als
        # Aufrufweg, den Punkt 2 unten bereits als unbekannt behandelt.
        for node in tree.body:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                self.helpers[node.name] = node


def _calls(node: ast.AST) -> Iterator[ast.Call]:
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            yield child


def _call_parts(call: ast.Call) -> tuple[str | None, str | None]:
    """``(Wurzelname, Attributname)`` eines Aufrufs.

    ``foo()`` -> ``("foo", None)`` · ``a.b.c()`` -> ``("a", "c")``. Die Wurzel
    ist der aeusserste Name, weil daran haengt, WESSEN Code laeuft.
    """
    func = call.func
    if isinstance(func, ast.Name):
        return func.id, None
    if isinstance(func, ast.Attribute):
        node: ast.expr = func.value
        while True:
            if isinstance(node, ast.Attribute):
                node = node.value
            elif isinstance(node, ast.Call):
                node = node.func
            elif isinstance(node, ast.Subscript):
                node = node.value
            else:
                break
        return (node.id if isinstance(node, ast.Name) else None), func.attr
    return None, None


def _shell_reads_only(call: ast.Call) -> bool:
    """Ein ``subprocess``-Aufruf, der bloss liest (``grep``/``cat``).

    ``subprocess.run(["grep", ...])`` startet einen Prozess, fuehrt aber nichts
    aus dem Prueflung aus -- es ist ein Dateilesevorgang mit Umweg. Ein
    ``subprocess.run(["bash", "deploy.sh"])`` dagegen ist Wirkung.
    """
    for arg in ast.walk(call):
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            token = arg.value.strip().split("/")[-1]
            if token in {"grep", "cat", "rg", "head", "tail", "sed", "awk"}:
                return True
    return False


def _reads_files(fn: ast.AST, index: _ModuleIndex, seen: frozenset[str] = frozenset()) -> bool:
    """Liest die Funktion Dateiinhalte -- direkt oder ueber einen Helfer?"""
    for call in _calls(fn):
        root, attr = _call_parts(call)
        if root == "open" and attr is None:
            return True
        if attr in _READ_ATTRS:
            return True
        if root == "subprocess" and attr in _SUBPROCESS_STARTERS and _shell_reads_only(call):
            return True
        if root and attr is None and root in index.helpers and root not in seen:
            if _reads_files(index.helpers[root], index, seen | {root}):
                return True
    return False


def _executes_effect(fn: ast.AST, index: _ModuleIndex, seen: frozenset[str] = frozenset()) -> bool:
    """Ruft die Funktion irgendwo echtes Verhalten auf?

    Vier Wege gelten als Wirkung. Sie sind bewusst weit gefasst: ein Test, der
    IRGENDETWAS ausfuehrt, ist nicht der Fehlertyp, den dieser Pruefer sucht --
    und ein Fehlalarm kostet hier mehr als ein uebersehener Fall.
    """
    for call in _calls(fn):
        root, attr = _call_parts(call)

        # 1. Eigener Code wird aufgerufen.
        if root and root in index.first_party_names:
            return True

        # 2. Ein Prozess wird gestartet (und liest nicht bloss).
        if root == "subprocess" and attr in _SUBPROCESS_STARTERS:
            if not _shell_reads_only(call):
                return True

        # 3. HTTP-Aufruf gegen die App.
        if attr in _HTTP_METHODS and root in _HTTP_CLIENT_NAMES:
            return True

        # 4. Ein lokaler Helfer, der selbst Wirkung ausfuehrt.
        if root and attr is None and root in index.helpers and root not in seen:
            if _executes_effect(index.helpers[root], index, seen | {root}):
                return True

    return False


def _asserts_only_compare_text(fn: ast.AST) -> tuple[bool, int]:
    """Sind ALLE Zusicherungen Vergleiche/Containment? Plus deren Anzahl.

    Geprueft wird die STRUKTUR der Zusicherung, nicht ob darin ein Aufruf
    steht. Ein Aufruf ist hier kein Ausschlussgrund, weil der Lesevorgang
    selbst einer ist: ``assert "x" in path.read_text()`` ist die haeufigste
    Form des gesuchten Fehlertyps. Ob ein Aufruf Wirkung AUSFUEHRT, entscheidet
    ``_executes_effect`` -- und ein ``assert normalise(raw) == y`` faellt dort
    heraus, weil ``normalise`` erstparteilich ist.

    Ein erster Entwurf verwarf jeden Aufruf in der Zusicherung und uebersah
    dadurch drei der vier historischen Faelle. Die Tests dieser Datei haben es
    gemeldet.
    """
    asserts = [node for node in ast.walk(fn) if isinstance(node, ast.Assert)]
    if not asserts:
        return False, 0

    for node in asserts:
        test = node.test
        if isinstance(test, ast.Compare | ast.BoolOp | ast.Name | ast.Attribute | ast.Call):
            continue
        if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
            continue
        return False, len(asserts)

    return True, len(asserts)


def _exempt_reason(
    source_lines: list[str], node: ast.FunctionDef | ast.AsyncFunctionDef
) -> str | None:
    """Begruendung des Ausnahmemarkers, falls einer gesetzt ist.

    Gesucht wird in der ``def``-Zeile selbst, in den Dekorator-Zeilen und in
    den beiden Zeilen unmittelbar darueber. Bewusst ein engeres Fenster als
    "irgendwo in der Funktion": ein Marker muss dort stehen, wo ihn der
    Reviewer des Diffs sieht.
    """
    first = min([node.lineno, *(d.lineno for d in node.decorator_list)])
    start = max(1, first - 2)
    for raw in source_lines[start - 1 : node.lineno]:
        match = _EXEMPT_RE.search(raw)
        if match:
            return match.group("reason")
    return None


def analyse_source(source: str, path: str) -> list[Finding]:
    """Alle markierten Testfunktionen eines Modulquelltexts."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        # Ein Syntaxfehler ist nicht unser Befund -- Lint und Typecheck melden
        # ihn lauter und fruehper. Still weiterzugehen ist hier richtig.
        return []

    index = _ModuleIndex(tree)
    lines = source.splitlines()
    findings: list[Finding] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        if not node.name.startswith("test"):
            continue
        if _exempt_reason(lines, node) is not None:
            continue
        if not _reads_files(node, index):
            continue
        if _executes_effect(node, index):
            continue
        text_only, count = _asserts_only_compare_text(node)
        if not text_only:
            continue

        findings.append(
            Finding(
                file=path,
                line=node.lineno,
                test=node.name,
                why=(
                    f"liest Dateiinhalte und macht {count} Zusicherung(en) darauf, "
                    "ruft aber nichts auf"
                ),
            )
        )

    return sorted(findings, key=lambda f: (f.file, f.line))


# --- git (nur lesend) --------------------------------------------------------


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=False)


def _changed_test_files(base: str) -> list[str]:
    merge_base = _git("merge-base", base, "HEAD").stdout.strip()
    ref = merge_base or base
    result = _git("diff", "--name-only", ref, "HEAD")
    if result.returncode != 0:
        raise RuntimeError(f"git diff gegen {ref!r} fehlgeschlagen: {result.stderr.strip()}")
    return [
        name
        for name in result.stdout.splitlines()
        if name.endswith(".py") and _TEST_FILE_RE.search(Path(name).name)
    ]


def _blob(ref: str, path: str) -> str | None:
    result = _git("show", f"{ref}:{path}")
    return result.stdout if result.returncode == 0 else None


def new_findings_against(base: str) -> list[Finding]:
    """Befunde, die es in der Basis noch nicht gab.

    Verglichen wird nach Testnamen, nicht nach Zeilennummer: ein Test, der
    bloss nach unten gewandert ist, ist kein neuer Befund.
    """
    merge_base = _git("merge-base", base, "HEAD").stdout.strip() or base
    findings: list[Finding] = []

    for path in _changed_test_files(base):
        after_source = Path(path).read_text(encoding="utf-8") if Path(path).exists() else None
        if after_source is None:
            continue
        after = analyse_source(after_source, path)
        if not after:
            continue
        before_source = _blob(merge_base, path)
        before_names = (
            {f.test for f in analyse_source(before_source, path)} if before_source else set()
        )
        findings.extend(f for f in after if f.test not in before_names)

    return sorted(findings, key=lambda f: (f.file, f.line))


def all_findings(roots: list[str]) -> list[Finding]:
    """Befunde im Gesamtbestand -- fuer die Messung, nicht fuer das Gate."""
    findings: list[Finding] = []
    skip = {".git", ".venv", "node_modules", "__pycache__", ".worktrees", "dist", "build"}
    for root in roots:
        for path in sorted(Path(root).rglob("*.py")):
            if any(part in skip for part in path.parts):
                continue
            if not _TEST_FILE_RE.search(path.name):
                continue
            findings.extend(analyse_source(path.read_text(encoding="utf-8"), str(path)))
    return findings


# --- Bericht -----------------------------------------------------------------

_GUIDANCE = (
    "Ein Test, der nur Zeichenketten in einer Datei prueft, bleibt gruen, solange\n"
    "der Text steht -- auch wenn die beschriebene Sache nicht funktioniert.\n"
    "Behebung: den Prueflung aufrufen und sein VERHALTEN zusichern. Ist der Test\n"
    "zurecht eine Textpruefung (Doku-Konformitaet, Konfigurations-Drift), setze\n"
    "einen begruendeten Ausnahmemarker -- siehe docs/effectful-tests.md:\n"
    "    # effect-exempt: <warum dieser Test keinen Prueflung hat>"
)


def report(findings: list[Finding], *, strict: bool, as_json: bool) -> int:
    if as_json:
        print(json.dumps([asdict(f) for f in findings], indent=2, ensure_ascii=False))
        return 1 if (strict and findings) else 0

    if not findings:
        print("Wirkungs-Pruefung: keine neuen Tests, die nur Zeichenketten pruefen.")
        return 0

    label = "error" if strict else "warning"
    print(f"Wirkungs-Pruefung: {len(findings)} neue(r) Test(s) ohne Wirkungsaufruf.\n")
    for finding in findings:
        print(f"  {finding.file}:{finding.line}  {finding.test}")
        print(f"      {finding.why}")
        # GitHub-Annotation: landet als Hinweis an der Codezeile im PR.
        print(
            f"::{label} file={finding.file},line={finding.line},"
            f"title=Test ohne Wirkungsaufruf::{finding.test}: {finding.why}"
        )
    print()
    print(_GUIDANCE)
    return 1 if strict else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--base",
        help=(
            "Basis-Ref fuer den Diff-Modus (z. B. origin/main). "
            "Ohne --base wird der Gesamtbestand geprueft."
        ),
    )
    parser.add_argument(
        "--roots",
        nargs="*",
        default=["apps", "packages", "scripts"],
        help="Verzeichnisse fuer die Bestandspruefung (Default: apps packages scripts).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Funde faerben den Lauf rot. Ohne dieses Flag ist der Schritt meldend.",
    )
    parser.add_argument("--json", action="store_true", help="Befunde als JSON ausgeben.")
    args = parser.parse_args(argv)

    try:
        findings = new_findings_against(args.base) if args.base else all_findings(args.roots)
    except RuntimeError as exc:
        print(f"Aufrufsfehler: {exc}", file=sys.stderr)
        return 2

    return report(findings, strict=args.strict, as_json=args.json)


if __name__ == "__main__":
    raise SystemExit(main())
