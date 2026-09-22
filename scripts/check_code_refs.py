#!/usr/bin/env python3
"""Code-Referenzen in Markdown maschinell gegen den Baum pruefen (P7).

Beobachtetes Problem: Karten und Plaene zitieren Fundstellen zeilengenau
(``webhook.py:441``). Die Datei waechst, der Zeiger wandert, und er zeigt
stillschweigend auf Nachbarcode — die teuerste Sorte Fehler, weil sie wie eine
gueltige Angabe aussieht. GitHub beschreibt die Ursache fuer Links selbst:
„The version of a file at the head of branch can change as new commits are
made, so if you were to copy the normal URL, the file contents might not be
the same when someone looks at it later." Ein Link mit Commit-SHA dagegen
„replaces main with a specific commit ID and the file content will not change."

Die Konvention dazu steht in ``docs/code-references.md``; dieses Skript ist ihr
maschineller Pruefer. Es ersetzt das Nachmessen von Hand, das bisher in jedem
Aufbereitungslauf noetig war.

**Dieses Skript aendert nichts.** Es liest Dateien, ruft ``git`` ausschliesslich
lesend auf (``cat-file``/``show``) und meldet. Kein Fix-Modus, kein Cache,
keine Schreiboperation — mit Absicht: ein Pruefer, der repariert, verwischt
genau die Information, die der Mensch sehen soll.

Erkannte Formen (nur innerhalb von ``inline code``-Spannen, siehe
``_iter_code_spans``):

    pfad/datei.py@a1b2c3d              SHA-Permalink
    pfad/datei.py#symbol               Symbolanker
    pfad/datei.py@a1b2c3d#symbol       beides
    pfad/datei.py#symbol:441           Zeile nur ZUSAETZLICH (nie als Beleg)
    pfad/datei.py:441                  Altlast -> severity ``legacy``

Severity-Modell:

- ``error``  — eine Referenz in Konventionsform loest nicht auf (Datei fehlt,
  Symbol fehlt, SHA unbekannt). Exit-Code 1.
- ``legacy`` — nackter ``datei:zeile``-Zeiger ohne SHA und ohne Symbol. Wird
  gemeldet, faerbt den Lauf aber NICHT rot: die Bestandskorrektur alter
  Zeiger ist ausdruecklich nicht Ziel dieses Schritts. ``--strict`` hebt
  ``legacy`` auf ``error`` — fuer den Tag, an dem die Altlast abgebaut ist.

Exit-Codes: 0 = keine Fehler, 1 = mindestens ein ``error``, 2 = Aufrufsfehler.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from collections.abc import Iterator, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path

# --- Grammatik ---------------------------------------------------------------

# Ein Pfad muss eine Dateiendung tragen. Ohne diese Einschraenkung wuerde jedes
# ``foo:1`` in Prosa als Referenz gelten.
_PATH = r"[A-Za-z0-9_./-]+\.[A-Za-z0-9_]+"
_SHA = r"[0-9a-fA-F]{7,40}"
# Symbolnamen duerfen Bindestriche tragen: YAML-Jobs und npm-Skripte heissen
# ``compose-smoke`` oder ``e2e-billing-cloud``. Ohne den Bindestrich schneidet
# die Grammatik mitten im Namen ab und meldet ausgerechnet eine
# konventionskonforme Referenz als Fehler. Das letzte Zeichen ist bewusst auf
# Wortzeichen begrenzt, damit Satzzeichen hinter der Referenz (``…#helper.``)
# nicht in den Symbolnamen wandern.
_SYMBOL = r"[A-Za-z_](?:[A-Za-z0-9_.-]*[A-Za-z0-9_])?"

_REFERENCE_RE = re.compile(
    rf"(?P<path>{_PATH})"
    rf"(?:@(?P<sha>{_SHA}))?"
    rf"(?:\#(?P<symbol>{_SYMBOL}))?"
    rf"(?::(?P<line>\d+))?"
)

# Dateien, in denen wir Symbole aufloesen koennen. Alles andere wird auf
# Dateiexistenz geprueft; ein Symbolanker darin gilt als nicht aufloesbar
# (``status: unsupported``) und ist kein Fehler.
_PY_SUFFIXES = {".py", ".pyi"}
_REGEX_SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".sh", ".sql", ".yml", ".yaml"}

_SKIP_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    "coverage",
    ".worktrees",
}

# URLs werden vor dem Matchen ausgeblendet. Ohne das greift die Grammatik mitten
# in einen GitHub-Permalink hinein (…/blob/<sha>/pfad.py#L20) und meldet den
# URL-Rest als nicht aufloesbaren Pfad — der Pruefer wuerde ausgerechnet die
# empfohlene Referenzform als Fehler melden.
_URL_RE = re.compile(r"(?:[a-z][a-z0-9+.-]*:)?//[^\s)>\]]+", re.IGNORECASE)

# Inline-Code nach CommonMark: der schliessende Backtick-Run muss genauso lang
# sein wie der oeffnende, und der Inhalt darf kuerzere Runs enthalten. Genau das
# ist die Markdown-Form fuer „Backticks im Code\" (`` `x` ``) — unsere
# Konventionstabelle in ``docs/code-references.md`` setzt ihre Beispiele so.
# Eine Grammatik mit ``[^`\n]+`` sieht diese Referenzen gar nicht und laesst
# ausgerechnet das vorbildliche Dokument ungeprueft.
_CODE_SPAN_RE = re.compile(r"(?P<fence>`+)(?P<body>.+?)(?P=fence)(?!`)")


@dataclass
class Finding:
    """Ein einzelner Befund zu genau einer erkannten Referenz."""

    file: str
    line: int
    reference: str
    path: str
    sha: str | None
    symbol: str | None
    line_hint: int | None
    status: str
    severity: str
    message: str


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)
    scanned_files: int = 0

    def counts(self) -> dict[str, int]:
        counts = {"ok": 0, "legacy": 0, "unsupported": 0, "error": 0}
        for finding in self.findings:
            counts[finding.severity] = counts.get(finding.severity, 0) + 1
        return counts


# --- Markdown: nur Inline-Code betrachten ------------------------------------


def _iter_code_spans(text: str) -> Iterator[tuple[int, str]]:
    """Liefert ``(zeilennummer, inhalt)`` je Inline-Code-Span und Codeblock-Zeile.

    Codestellen werden in unseren Karten und Dokumenten konsequent in Backticks
    gesetzt. Diese Einschraenkung ist der Unterschied zwischen einem Pruefer,
    der brauchbar ist, und einem, der jede Prosa-Erwaehnung eines Dateinamens
    anschleppt.
    """
    in_fence = False
    for lineno, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if in_fence:
            yield lineno, raw
            continue
        for match in _CODE_SPAN_RE.finditer(raw):
            yield lineno, match.group("body")


# --- Symbolaufloesung ---------------------------------------------------------


def _python_symbols(source: str) -> set[str]:
    """Alle definierten Namen eines Python-Moduls, inklusive ``Klasse.methode``."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()

    names: set[str] = set()

    def walk(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                qualified = f"{prefix}{child.name}"
                names.add(child.name)
                names.add(qualified)
                walk(child, f"{qualified}.")
            elif isinstance(child, ast.Assign):
                for target in child.targets:
                    if isinstance(target, ast.Name):
                        names.add(target.id)
                        names.add(f"{prefix}{target.id}")
            elif isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
                names.add(child.target.id)
                names.add(f"{prefix}{child.target.id}")

    walk(tree, "")
    return names


def _regex_symbol_present(source: str, symbol: str) -> bool:
    """Definitions-Heuristik fuer Nicht-Python-Dateien.

    Bewusst konservativ: gesucht wird eine *Definition*, nicht irgendein
    Vorkommen — sonst wuerde ein Aufruf des Symbols den Anker gueltig machen,
    auch wenn die Definition laengst woanders steht.
    """
    name = re.escape(symbol.split(".")[-1])
    patterns = [
        rf"\b(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+{name}\b",
        rf"\b(?:export\s+)?(?:abstract\s+)?class\s+{name}\b",
        rf"\b(?:export\s+)?(?:const|let|var)\s+{name}\b",
        rf"\b(?:export\s+)?(?:type|interface|enum)\s+{name}\b",
        rf"^\s*{name}\s*\(\)\s*\{{",  # shell function
        rf"^\s*(?:function\s+)?{name}\s*:",  # yaml key / object member
        rf"\bdef\s+{name}\b",
    ]
    return any(re.search(p, source, re.MULTILINE) for p in patterns)


# --- Git (nur lesend) ---------------------------------------------------------


def _git_show(repo_root: Path, sha: str, path: str) -> str | None:
    """Dateiinhalt an einem Commit — oder ``None``, wenn es ihn dort nicht gibt."""
    result = subprocess.run(
        ["git", "-C", str(repo_root), "show", f"{sha}:{path}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def _git_has_commit(repo_root: Path, sha: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "cat-file", "-e", f"{sha}^{{commit}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


# --- Pruefung einer Referenz --------------------------------------------------


def check_reference(
    repo_root: Path,
    path: str,
    sha: str | None,
    symbol: str | None,
) -> tuple[str, str]:
    """Prueft eine Referenz und liefert ``(status, meldung)``."""
    if sha is not None:
        if not _git_has_commit(repo_root, sha):
            return "unknown-sha", f"Commit {sha} ist in diesem Repo nicht bekannt."
        source = _git_show(repo_root, sha, path)
        if source is None:
            return "missing-file", f"{path} existiert im Commit {sha} nicht."
    else:
        target = repo_root / path
        if not target.is_file():
            return "missing-file", f"{path} existiert im Arbeitsbaum nicht."
        try:
            source = target.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            if symbol is None:
                return "ok", ""
            return "unsupported", f"{path} ist nicht als Text lesbar — Symbol ungeprueft."

    if symbol is None:
        return "ok", ""

    suffix = Path(path).suffix
    if suffix in _PY_SUFFIXES:
        if symbol in _python_symbols(source):
            return "ok", ""
        return "missing-symbol", f"{symbol} ist in {path} nicht definiert."
    if suffix in _REGEX_SUFFIXES:
        if _regex_symbol_present(source, symbol):
            return "ok", ""
        return "missing-symbol", f"{symbol} ist in {path} nicht als Definition auffindbar."
    return "unsupported", f"Symbolaufloesung fuer {suffix or 'diese Dateiart'} nicht unterstuetzt."


def _severity(status: str, has_anchor: bool, strict: bool) -> str:
    if status in {"missing-file", "missing-symbol", "unknown-sha"}:
        return "error"
    if status == "unsupported":
        return "unsupported"
    if not has_anchor:
        return "error" if strict else "legacy"
    return "ok"


def scan_text(
    repo_root: Path,
    text: str,
    origin: str,
    strict: bool = False,
) -> list[Finding]:
    findings: list[Finding] = []
    seen: set[tuple[int, str]] = set()
    for lineno, span in _iter_code_spans(text):
        # URLs ausblenden, Laenge erhalten (Offsets bleiben stimmig).
        span = _URL_RE.sub(lambda m: " " * len(m.group(0)), span)
        for match in _REFERENCE_RE.finditer(span):
            path = match.group("path")
            sha = match.group("sha")
            symbol = match.group("symbol")
            line_hint = match.group("line")
            # Eine blosse Dateinennung ohne Anker und ohne Zeile ist keine
            # Code-Referenz, sondern Prosa — sie wird nicht geprueft.
            if sha is None and symbol is None and line_hint is None:
                continue
            reference = match.group(0)
            key = (lineno, reference)
            if key in seen:
                continue
            seen.add(key)

            has_anchor = sha is not None or symbol is not None
            if has_anchor:
                status, message = check_reference(repo_root, path, sha, symbol)
            else:
                # Ein nackter ``datei:zeile``-Zeiger ist IMMER nur ``legacy`` —
                # auch wenn der Pfad gar nicht aufloest. Die Altlast alter
                # Karten und Reviews (oft abgekuerzte Dateinamen) nachtraeglich
                # zu korrigieren ist ausdruecklich nicht Ziel dieses Pruefers;
                # wer sie angeht, schaltet ``--strict`` ein und bekommt sie
                # geschlossen als Fehler.
                hint = (
                    "Datei aufloesbar"
                    if (repo_root / path).is_file()
                    else "Pfad loest im Arbeitsbaum nicht auf"
                )
                status = "legacy"
                message = (
                    f"{reference} nennt nur Datei und Zeile ({hint}) — Zeiger driftet. "
                    "Konvention: SHA-Permalink und/oder Symbolanker "
                    "(docs/code-references.md)."
                )

            findings.append(
                Finding(
                    file=origin,
                    line=lineno,
                    reference=reference,
                    path=path,
                    sha=sha,
                    symbol=symbol,
                    line_hint=int(line_hint) if line_hint else None,
                    status=status,
                    severity=_severity(status, has_anchor, strict),
                    message=message,
                )
            )
    return findings


# --- Eingabesammlung ----------------------------------------------------------


def iter_markdown_files(targets: Sequence[Path]) -> Iterator[Path]:
    for target in targets:
        if target.is_file():
            yield target
            continue
        for candidate in sorted(target.rglob("*.md")):
            if any(part in _SKIP_DIRS for part in candidate.parts):
                continue
            yield candidate


def _repo_root(start: Path) -> Path:
    result = subprocess.run(
        ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return start
    return Path(result.stdout.strip())


# --- Ausgabe ------------------------------------------------------------------


def render_text(report: Report, show_ok: bool) -> str:
    lines: list[str] = []
    for finding in report.findings:
        if finding.severity == "ok" and not show_ok:
            continue
        lines.append(
            f"{finding.file}:{finding.line}: {finding.severity}: "
            f"{finding.reference} — {finding.message or 'ok'}"
        )
    counts = report.counts()
    lines.append(
        f"{report.scanned_files} Datei(en) geprueft; "
        f"{len(report.findings)} Referenz(en): "
        f"{counts['ok']} ok, {counts['legacy']} legacy, "
        f"{counts['unsupported']} unsupported, {counts['error']} error."
    )
    return "\n".join(lines)


def render_json(report: Report, show_ok: bool) -> str:
    findings = [f for f in report.findings if show_ok or f.severity != "ok"]
    payload = {
        "summary": {
            "scanned_files": report.scanned_files,
            "references": len(report.findings),
            **report.counts(),
        },
        "findings": [asdict(f) for f in findings],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


# --- CLI ----------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="check_code_refs.py",
        description=(
            "Prueft Code-Referenzen (datei@sha#symbol) in Markdown gegen das Repo. "
            "Read-only: das Skript aendert nichts."
        ),
    )
    parser.add_argument(
        "targets",
        nargs="*",
        default=["."],
        help="Dateien oder Verzeichnisse (rekursiv *.md). '-' liest von stdin. Default: .",
    )
    parser.add_argument("--json", action="store_true", help="Maschinenlesbare Ausgabe.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Nackte datei:zeile-Zeiger als Fehler werten (Default: 'legacy', nicht rot).",
    )
    parser.add_argument(
        "--show-ok",
        action="store_true",
        help="Auch aufgeloeste Referenzen ausgeben.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repo-Wurzel, gegen die aufgeloest wird (Default: git rev-parse --show-toplevel).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    targets = [Path(t) for t in (args.targets or ["."])]

    repo_root = (args.repo_root or _repo_root(Path.cwd())).resolve()
    report = Report()

    if targets == [Path("-")]:
        report.scanned_files = 1
        report.findings.extend(scan_text(repo_root, sys.stdin.read(), "<stdin>", args.strict))
    else:
        for target in targets:
            if not target.exists():
                print(f"Pfad existiert nicht: {target}", file=sys.stderr)
                return 2
        for md in iter_markdown_files(targets):
            report.scanned_files += 1
            try:
                text = md.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            try:
                origin = str(md.resolve().relative_to(repo_root))
            except ValueError:
                origin = str(md)
            report.findings.extend(scan_text(repo_root, text, origin, args.strict))

    output = render_json(report, args.show_ok) if args.json else render_text(report, args.show_ok)
    print(output)
    return 1 if report.counts()["error"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
