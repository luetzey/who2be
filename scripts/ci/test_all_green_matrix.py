#!/usr/bin/env python3
"""Lokale Wahrheitstabelle fuer den Auswertungs-Step des `all-green`-Jobs.

Der Aggregat-Job in ``.github/workflows/ci.yml`` ist dazu bestimmt, der einzige
Required Check auf ``main`` zu werden. Seine Auswertungslogik entscheidet, ob
ein ``skipped`` eines Vorgaengers legitim ist (Doku-Allowlist) oder ein stilles
falsches Gruen waere (kaputter Gate-Job). Diese Unterscheidung laesst sich in
CI nur teuer herstellen — hier wird sie billig und vollstaendig geprueft.

Das Shell-Skript wird direkt aus ``ci.yml`` gelesen, nicht kopiert: eine Kopie
wuerde von der CI wegdriften und genau dann gruen bleiben, wenn es darauf
ankommt.

Die Struktur-Zusicherung kennt eine benannte Ausnahme: ``UNGATED_BY_DESIGN``
listet Jobs, die waehrend ihrer Einfuehrung absichtlich noch nicht an
``all-green`` haengen. Die Liste ist selbst geprueft (Job muss existieren, darf
nicht verdrahtet sein und muss ``continue-on-error: true`` fuehren) — ein
vergessener Job faellt dadurch weiterhin auf.

Aufruf aus dem Repo-Root: ``uv run python scripts/ci/test_all_green_matrix.py``
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, NamedTuple

import yaml

CI_YML = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml"

OK = "success"
SKIP = "skipped"
RED = "failure"
STOP = "cancelled"

# Reihenfolge der fuenf pfadgefilterten Jobs in `gated`.
GATED_JOBS = ("python", "web", "compose-smoke", "e2e", "e2e-billing-cloud")

# Jobs, die ABSICHTLICH nicht in `all-green.needs` stehen.
#
# Die Struktur-Zusicherung unten verlangt sonst jeden Job der Datei in `needs`.
# Das ist die richtige Vorgabe: ein Vorgaenger, den der Aggregat-Job nicht
# kennt, kann rot sein, ohne ihn rot zu faerben. Genau diese Wirkung wird
# waehrend der Einfuehrung eines neuen Profils aber gebraucht — ein frisch
# eingefuehrter Job soll melden, nicht sofort jeden PR blockieren.
#
# Damit das eine benannte Ausnahme bleibt und kein stilles Schlupfloch:
#   * Der Eintrag steht hier als Einzelfall MIT Begruendung, nicht als Muster.
#   * Er wird nicht blind durchgewunken — der Job muss zusaetzlich
#     `continue-on-error: true` fuehren (siehe `check_structure`). Ein
#     versehentlich vergessener Job faellt dadurch weiterhin auf: ihm fehlt
#     diese Markierung.
#   * Jeder Eintrag ist Schulden auf Zeit. Wird der Job scharfgestellt, muss er
#     in `all-green.needs` UND in den Auswertungs-Step aufgenommen und hier
#     entfernt werden.
UNGATED_BY_DESIGN: dict[str, str] = {
    "e2e-mobile": (
        "Welle 7 / K1: die drei Mobile-/Tablet-Playwright-Profile laufen, "
        "melden aber nur. Scharfstellen ist K3 — dann faellt dieser Eintrag weg."
    ),
}


class Case(NamedTuple):
    """Ein Ergebnis-Szenario der Vorgaenger-Jobs."""

    name: str
    changes: str
    code: str
    gated: tuple[str, str, str, str, str]
    audit: str
    expected_exit: int
    changelog_guard: str = OK

    def env(self) -> dict[str, str]:
        python, web, compose_smoke, e2e, e2e_billing_cloud = self.gated
        return {
            "CHANGES_RESULT": self.changes,
            "CODE": self.code,
            "PYTHON_RESULT": python,
            "WEB_RESULT": web,
            "COMPOSE_SMOKE_RESULT": compose_smoke,
            "E2E_RESULT": e2e,
            "E2E_BILLING_CLOUD_RESULT": e2e_billing_cloud,
            "AUDIT_RESULT": self.audit,
            "CHANGELOG_GUARD_RESULT": self.changelog_guard,
        }


ALL_OK: tuple[str, str, str, str, str] = (OK, OK, OK, OK, OK)
ALL_SKIP: tuple[str, str, str, str, str] = (SKIP, SKIP, SKIP, SKIP, SKIP)

CASES: tuple[Case, ...] = (
    # --- die zwei Faelle, die auch in CI belegt werden ---
    Case("Voller Lauf, alles gruen", OK, "true", ALL_OK, OK, 0),
    Case("Doku-PR: gegatete Jobs uebersprungen", OK, "false", ALL_SKIP, OK, 0),
    # --- gewoehnliche Fehlschlaege ---
    Case("Ein Job rot (python)", OK, "true", (RED, OK, OK, OK, OK), OK, 1),
    Case("Ein Job abgebrochen (e2e)", OK, "true", (OK, OK, OK, STOP, OK), OK, 1),
    # --- der Kern-Fall: ein naiver Aggregat-Job ("kein Vorgaenger ist rot")
    #     waere hier GRUEN, obwohl kein einziger Test gelaufen ist ---
    Case("GEFAEHRLICH: changes rot, alle gegateten uebersprungen", RED, "", ALL_SKIP, OK, 1),
    Case("GEFAEHRLICH: changes abgebrochen", STOP, "", ALL_SKIP, OK, 1),
    # --- `audit` haengt an keinem Pfadfilter: muss immer wirklich laufen ---
    Case("audit rot bei Doku-PR", OK, "false", ALL_SKIP, RED, 1),
    Case("audit uebersprungen (darf nie passieren)", OK, "true", ALL_OK, SKIP, 1),
    # --- Ergebnis passt nicht zur Klassifikation ---
    Case("code=true, aber Job uebersprungen", OK, "true", (SKIP, OK, OK, OK, OK), OK, 1),
    Case("code=false, aber Job gelaufen", OK, "false", (OK, SKIP, SKIP, SKIP, SKIP), OK, 1),
    # --- unbekannte Klassifikation: fail-closed ---
    Case("code unbekannt: fail-closed", OK, "weird", ALL_OK, OK, 1),
    Case("code leer: fail-closed", OK, "", ALL_OK, OK, 1),
    # --- `changelog-guard` haengt wie `audit` an keinem Pfadfilter ---
    Case("changelog-guard rot bei Doku-PR", OK, "false", ALL_SKIP, OK, 1, changelog_guard=RED),
    Case(
        "changelog-guard uebersprungen (darf nie passieren)",
        OK,
        "true",
        ALL_OK,
        OK,
        1,
        changelog_guard=SKIP,
    ),
)


def check_structure(jobs: dict[str, Any]) -> list[str]:
    """Zusicherungen, die der Job unabhaengig von seiner Shell-Logik braucht."""
    job = jobs["all-green"]
    problems: list[str] = []
    if job.get("if") != "always()":
        problems.append(
            f"`if: always()` fehlt (ist: {job.get('if')!r}). Ohne ihn setzt GitHub den "
            "Job auf 'skipped', sobald ein Vorgaenger faellt — und skipped gilt als Erfolg."
        )
    if job.get("name") != "all-green":
        problems.append(
            "Der Check-Name ist Teil der Repo-Konfiguration (Required Checks binden per "
            f"exakter Namensgleichheit) — `name:` muss 'all-green' sein, ist {job.get('name')!r}."
        )
    needs = job.get("needs", [])
    missing = [
        name
        for name in jobs
        if name != "all-green" and name not in needs and name not in UNGATED_BY_DESIGN
    ]
    if missing:
        problems.append(
            f"Diese Jobs fehlen in `needs:`: {missing}. Ein Vorgaenger, den der Aggregat-Job "
            "nicht kennt, kann rot sein, ohne ihn rot zu faerben."
        )
    # Die Ausnahmeliste selbst gegenpruefen, sonst waere sie ein Freifahrtschein:
    # ein Eintrag gilt nur, solange der Job existiert, wirklich nicht verdrahtet
    # ist und sich als nicht-blockierend zu erkennen gibt.
    for name, why in UNGATED_BY_DESIGN.items():
        if name not in jobs:
            problems.append(
                f"`UNGATED_BY_DESIGN` nennt '{name}', aber diesen Job gibt es in ci.yml nicht "
                "(mehr). Eintrag entfernen."
            )
        elif name in needs:
            problems.append(
                f"'{name}' steht in `all-green.needs` und gleichzeitig in "
                "`UNGATED_BY_DESIGN`. Wurde der Job scharfgestellt, gehoert der Eintrag hier "
                f"geloescht. Begruendung war: {why}"
            )
        elif jobs[name].get("continue-on-error") is not True:
            problems.append(
                f"'{name}' ist als bewusst nicht-blockierend gelistet, fuehrt aber kein "
                "`continue-on-error: true`. Ohne diese Markierung ist ein fehlender "
                "`needs`-Eintrag von einem Versehen nicht zu unterscheiden."
            )
    unknown = [name for name in needs if name not in jobs]
    if unknown:
        problems.append(f"`needs:` nennt Jobs, die es nicht gibt: {unknown}")
    return problems


def main() -> int:
    workflow: dict[str, Any] = yaml.safe_load(CI_YML.read_text(encoding="utf-8"))
    jobs: dict[str, Any] = workflow["jobs"]

    problems = check_structure(jobs)
    for problem in problems:
        print(f"FAIL  Struktur: {problem}")

    script: str = jobs["all-green"]["steps"][0]["run"]
    with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False, encoding="utf-8") as handle:
        handle.write(script)
        script_path = handle.name

    failures = len(problems)
    try:
        for case in CASES:
            proc = subprocess.run(
                ["bash", script_path],
                env={**os.environ, **case.env(), "GITHUB_OUTPUT": os.devnull},
                capture_output=True,
                text=True,
                check=False,
            )
            ok = proc.returncode == case.expected_exit
            marker = "OK  " if ok else "FAIL"
            print(f"{marker}  exit={proc.returncode} (erwartet {case.expected_exit})  {case.name}")
            if not ok:
                failures += 1
                print(proc.stdout, proc.stderr, sep="\n")
    finally:
        os.unlink(script_path)

    print()
    if failures:
        print(f"{failures} Abweichung(en) — der Aggregat-Job urteilt nicht wie spezifiziert.")
        return 1
    print(f"Alle {len(CASES)} Faelle und die Struktur-Zusicherungen wie erwartet.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
