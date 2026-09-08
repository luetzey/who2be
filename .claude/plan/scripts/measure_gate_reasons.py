"""Misst die Gate-Fehlerflaeche (`ApiGateError`) gegen die Locale-Keys.

Beleg fuer die Zahlen in #504 (Kommentar vom 2026-09-08) und in der
Backlog-Queue #442. Bewusst per `ast` statt `grep`: Regel 18/28 der Queue —
ein Bestandszaehler zaehlt das Konstrukt, nicht seine Schreibweise. Eine
Regex-Zaehlung derselben Flaeche lieferte 75/95 statt 73/92 `ProblemReason`,
weil sie in Kommentaren zitierte Strings mitzaehlte.

Aufruf aus dem Repo-Root:

    uv run python .claude/plan/scripts/measure_gate_reasons.py
"""

from __future__ import annotations

import ast
import collections
import json
import pathlib

API_SRC = pathlib.Path("apps/api/src")
LOCALE_DE = pathlib.Path("apps/web/src/i18n/locales/de.json")
REASONS = pathlib.Path("packages/models/src/who2be_models/errors.py")


def gate_sites() -> list[tuple[str, int, str, str]]:
    """(Datei, Zeile, reason, Form des `detail`) je `ApiGateError(...)`-Aufruf."""
    out: list[tuple[str, int, str, str]] = []
    for path in sorted(API_SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "ApiGateError"
            ):
                continue
            kw = {k.arg: k.value for k in node.keywords}
            reason = kw.get("reason")
            detail = kw.get("detail")
            rname = reason.value if isinstance(reason, ast.Constant) else "?"
            if isinstance(detail, ast.Constant):
                form = "literal"
            elif isinstance(detail, ast.JoinedStr):
                form = "f-string"
            else:
                # Hilfsfunktion mit `detail: str`-Parameter — der Text kommt vom
                # Aufrufer und ist dort haeufig selbst ein f-String.
                form = "durchgereicht"
            out.append((str(path), node.lineno, rname, form))
    return out


def problem_reasons() -> list[str]:
    """Die Werte des `ProblemReason`-Literals — geparst, nicht gegrept."""
    tree = ast.parse(REASONS.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "ProblemReason" for t in node.targets
        ):
            sub = node.value
            if isinstance(sub, ast.Subscript):
                sl = sub.slice
                elts = sl.elts if isinstance(sl, ast.Tuple) else [sl]
                return [e.value for e in elts if isinstance(e, ast.Constant)]
    return []


def main() -> None:
    sites = gate_sites()
    forms = collections.Counter(f for *_, f in sites)
    per_reason = collections.Counter(r for *_, r, _ in sites)
    literal = {r for *_, r, f in sites if f == "literal"}
    variable = {r for *_, r, f in sites if f != "literal"}
    fixed = sorted(literal - variable)
    keys = set(json.loads(LOCALE_DE.read_text())["common"]["errors"])

    values = problem_reasons()
    print(f"ProblemReason: {len(values)} Werte ({len(set(values))} distinkt)")
    print(f"common.errors (de): {len(keys)} Keys")
    print()
    print(f"Gate-Stellen: {len(sites)} · distinkte reasons: {len(per_reason)}")
    for form, count in forms.most_common():
        print(f"  detail {form:15s}: {count}")
    print()
    fixed_sites = sum(per_reason[r] for r in fixed)
    print(
        f"reasons immer literal (ohne `params` uebersetzbar): {len(fixed)} ({fixed_sites} Stellen)"
    )
    for r in fixed:
        mark = "Key vorhanden" if r in keys else "Key fehlt"
        print(f"  {r:26s} {per_reason[r]:2d} Stellen  [{mark}]")
    print()
    missing = [r for r in sorted(per_reason) if r not in keys]
    print(f"Gate-reasons ohne Locale-Key: {len(missing)} von {len(per_reason)}")
    print(
        "  -> jede dieser Meldungen faellt ueber `defaultValue: detail`"
        " auf den deutschen Servertext zurueck"
    )


if __name__ == "__main__":
    main()
