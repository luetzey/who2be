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

# Reihenfolge der sieben pfadgefilterten Jobs in `gated`.
GATED_JOBS = (
    "python",
    "web",
    "compose-smoke",
    "e2e",
    "e2e-billing-cloud",
    "e2e-mobile",
    "backup-alarm",
)

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
#
# Die Liste ist derzeit LEER. Der einzige Eintrag war `e2e-mobile` waehrend
# Welle 7 / K1-K2c; K3 hat den Job an beiden Stellen verdrahtet und den Eintrag
# damit eingeloest. Die Mechanik bleibt stehen, weil die naechste Einfuehrung
# sie wieder braucht — ein leeres Dict ist hier die staerkere Aussage als eine
# geloeschte Funktion.
UNGATED_BY_DESIGN: dict[str, str] = {}


class Case(NamedTuple):
    """Ein Ergebnis-Szenario der Vorgaenger-Jobs."""

    name: str
    changes: str
    code: str
    gated: Gated
    audit: str
    expected_exit: int
    changelog_guard: str = OK

    def env(self) -> dict[str, str]:
        if len(self.gated) != len(GATED_JOBS):
            raise AssertionError(
                f"Fall {self.name!r} nennt {len(self.gated)} gegatete Ergebnisse, "
                f"GATED_JOBS kennt {len(GATED_JOBS)}: {GATED_JOBS}"
            )
        # Die Env-Namen werden aus den Job-Ids ABGELEITET, nicht zweitgepflegt:
        # eine zweite Liste von Hand driftet genau dann von `ci.yml` weg, wenn
        # ein Job hinzukommt — der Fall, den diese Datei bewachen soll.
        env = {
            f"{job.upper().replace('-', '_')}_RESULT": result
            for job, result in zip(GATED_JOBS, self.gated, strict=True)
        }
        env.update(
            {
                "CHANGES_RESULT": self.changes,
                "CODE": self.code,
                "AUDIT_RESULT": self.audit,
                "CHANGELOG_GUARD_RESULT": self.changelog_guard,
            }
        )
        return env


Gated = tuple[str, ...]

ALL_OK: Gated = tuple(OK for _ in GATED_JOBS)
ALL_SKIP: Gated = tuple(SKIP for _ in GATED_JOBS)


def gated_with(**overrides: str) -> Gated:
    """`ALL_OK`, aber die benannten Jobs tragen ein anderes Ergebnis.

    Positionsbehaftete Tupel wurden mit jedem neuen Job laenger und die Faelle
    damit unlesbar — schlimmer: ein vergessenes Element verschob stillschweigend
    alle folgenden Zuordnungen. Hier steht der Job-Name am Ergebnis.
    """
    keyed = {job.replace("-", "_"): job for job in GATED_JOBS}
    results: dict[str, str] = dict(zip(GATED_JOBS, ALL_OK, strict=True))
    for key, value in overrides.items():
        results[keyed[key]] = value
    return tuple(results[job] for job in GATED_JOBS)


CASES: tuple[Case, ...] = (
    # --- die zwei Faelle, die auch in CI belegt werden ---
    Case("Voller Lauf, alles gruen", OK, "true", ALL_OK, OK, 0),
    Case("Doku-PR: gegatete Jobs uebersprungen", OK, "false", ALL_SKIP, OK, 0),
    # --- gewoehnliche Fehlschlaege ---
    Case("Ein Job rot (python)", OK, "true", gated_with(python=RED), OK, 1),
    Case("Ein Job abgebrochen (e2e)", OK, "true", gated_with(e2e=STOP), OK, 1),
    # --- Welle 7 / K3: das Mobile-Gate ist scharf. Vor K3 war dieser Fall
    #     gruen — der Job stand weder in `needs` noch im Auswertungs-Step. ---
    Case("Mobile-Profil rot (e2e-mobile)", OK, "true", gated_with(e2e_mobile=RED), OK, 1),
    Case(
        "Mobile-Job uebersprungen trotz code=true",
        OK,
        "true",
        gated_with(e2e_mobile=SKIP),
        OK,
        1,
    ),
    # --- Karte t_5c8d5364: die Backup-Alarm-Suite ist gebunden. Vor dieser
    #     Karte lief sie in keinem Job; beide Faelle waeren gruen gewesen, weil
    #     der Job in `needs` und im Auswertungs-Step fehlte. ---
    Case("Backup-Alarm rot", OK, "true", gated_with(backup_alarm=RED), OK, 1),
    Case(
        "Backup-Alarm uebersprungen trotz code=true",
        OK,
        "true",
        gated_with(backup_alarm=SKIP),
        OK,
        1,
    ),
    # --- der Kern-Fall: ein naiver Aggregat-Job ("kein Vorgaenger ist rot")
    #     waere hier GRUEN, obwohl kein einziger Test gelaufen ist ---
    Case("GEFAEHRLICH: changes rot, alle gegateten uebersprungen", RED, "", ALL_SKIP, OK, 1),
    Case("GEFAEHRLICH: changes abgebrochen", STOP, "", ALL_SKIP, OK, 1),
    # --- `audit` haengt an keinem Pfadfilter: muss immer wirklich laufen ---
    Case("audit rot bei Doku-PR", OK, "false", ALL_SKIP, RED, 1),
    Case("audit uebersprungen (darf nie passieren)", OK, "true", ALL_OK, SKIP, 1),
    # --- Ergebnis passt nicht zur Klassifikation ---
    Case("code=true, aber Job uebersprungen", OK, "true", gated_with(python=SKIP), OK, 1),
    Case(
        "code=false, aber Job gelaufen",
        OK,
        "false",
        tuple(OK if job == "python" else SKIP for job in GATED_JOBS),
        OK,
        1,
    ),
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


def check_playwright_projects(jobs: dict[str, Any]) -> list[str]:
    """Jeder Playwright-Job muss sein Projekt explizit waehlen.

    `playwright test` ohne `--project` faehrt ALLE Projekte der Config. Solange
    es genau ein Projekt gab, war das harmlos; seit die Config vier fuehrt
    (Welle 7 / K1), zieht ein ungefilterter Aufruf im scharfen `e2e`-Gate die
    noch meldenden Mobile-Profile in eine blockierende Rolle — lautlos, denn
    der Job heisst weiterhin `e2e` und sieht unveraendert aus.

    Der Fehler ist in genau dieser Form schon einmal passiert (Run 35921243967:
    `e2e` meldete 40 statt 12 Tests). Deshalb steht er hier als Zusicherung und
    nicht als Kommentar.
    """
    problems: list[str] = []
    for job_name, job in jobs.items():
        for step in job.get("steps") or []:
            run = step.get("run") or ""
            if "playwright test" not in run and "npm run e2e" not in run:
                continue
            # `e2e:install` laedt nur Browser-Binaries, fuehrt keine Tests aus.
            if "e2e:install" in run:
                continue
            # Ein benannter Spec-Pfad zaehlt NICHT als Filter: er waehlt
            # Dateien, Playwright kreuzt sie weiterhin mit allen Projekten.
            if "--project" in run:
                continue
            problems.append(
                f"Job '{job_name}': Playwright wird ohne `--project` aufgerufen "
                f"({run.strip().splitlines()[-1]!r}). Ohne Filter laufen ALLE Projekte der "
                "Config — ein Gate-Job wuerde damit still auch die noch meldenden "
                "Mobile-Profile erzwingen."
            )
    return problems


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
    # Ein verdrahteter Job mit `continue-on-error: true` ist ein Gate, das
    # vollstaendig aussieht und nichts durchsetzt: GitHub meldet den Job dann
    # als `success`, auch wenn seine Steps fallen — `needs.<job>.result` traegt
    # diesen `success` in den Auswertungs-Step, und die `expect`-Zeile winkt ihn
    # durch. Die beiden anderen Stellen (`needs`, `expect`) sind oben bewacht;
    # ohne diese dritte waere die Verdrahtung durch eine einzige zurueckgelassene
    # Zeile lautlos wirkungslos. (Aufgefallen bei der Mutationsprobe zu Welle 7
    # / K3: die Probe rutschte hier als einzige durch.)
    soft = [name for name in needs if jobs.get(name, {}).get("continue-on-error") is True]
    if soft:
        problems.append(
            f"Diese Jobs stehen in `all-green.needs`, fuehren aber `continue-on-error: true`: "
            f"{soft}. GitHub meldet sie dann als 'success', auch wenn ihre Steps fallen — der "
            "Aggregat-Job prueft einen Wert, der nie 'failure' werden kann."
        )
    return problems


def check_expect_wiring(jobs: dict[str, Any]) -> list[str]:
    """Jeder verdrahtete Vorgaenger braucht `env` UND eine `expect`-Zeile.

    Ein Job wird an drei Stellen scharf: `needs`, eine eigene `env`-Variable und
    eine eigene `expect`-Zeile im Auswertungs-Step. Je zwei davon allein setzen
    nichts durch — `needs` ohne `expect` prueft einen Wert, den niemand liest;
    `expect` ohne `env` liest eine leere Variable und vergleicht sie gegen die
    Erwartung, was zwar rot faerbt, aber aus dem falschen Grund.

    Bisher stand diese Regel nur als Kommentar an `e2e-mobile` in `ci.yml` und
    wurde bei jedem neuen Job von Hand nachgezogen. Hier wird sie geprueft.
    """
    step: dict[str, Any] = jobs["all-green"]["steps"][0]
    script: str = step["run"]
    env: dict[str, Any] = step.get("env") or {}
    problems: list[str] = []
    for name in jobs["all-green"].get("needs", []):
        if name == "changes":
            # Sonderfall mit eigener Behandlung oben im Skript (harter Abbruch
            # statt `expect`), weil ohne das Tor jede weitere Aussage wertlos ist.
            continue
        var = f"{name.upper().replace('-', '_')}_RESULT"
        if var not in env:
            problems.append(
                f"Job '{name}' steht in `all-green.needs`, aber der Auswertungs-Step hat kein "
                f"`env`-Feld '{var}'. Ohne die Variable wird sein Ergebnis nie gelesen."
            )
        if f"expect {name} " not in script and f"expect {name}\n" not in script:
            problems.append(
                f"Job '{name}' steht in `all-green.needs`, aber der Auswertungs-Step hat keine "
                f"`expect {name} …`-Zeile. `needs` allein prueft nichts."
            )
    return problems


def main() -> int:
    workflow: dict[str, Any] = yaml.safe_load(CI_YML.read_text(encoding="utf-8"))
    jobs: dict[str, Any] = workflow["jobs"]

    problems = check_structure(jobs) + check_playwright_projects(jobs) + check_expect_wiring(jobs)
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
