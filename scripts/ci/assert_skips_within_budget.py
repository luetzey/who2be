#!/usr/bin/env python3
"""Skip-Budget-Gate: ein gruener Lauf, der nichts ausgefuehrt hat, ist rot.

Hintergrund (P4): ohne Postgres/Docker ueberspringt die Suite lokal 485 Tests
und meldet trotzdem Exit 0. Mehrfach wurde ein solcher Lauf als Nachweis
gemeldet, obwohl die tragenden Tests nie liefen. pytest hat dafuer *keinen*
eingebauten Schalter — Maintainer-Aussage aus pytest-dev/pytest#1364:

    "If you want the test to fail if a dependency is not installed then you
    shouldn't be using skip IMHO."

Dieses Skript schliesst die Luecke auf der Auswertungsseite: es liest die
JUnit-XML (``--junitxml``) statt die Textausgabe zu parsen — die XML nennt je
Test den Skip-*Grund*, die Zusammenfassungszeile nur eine Zahl.

Zwei getrennte Budgets, weil zwei verschiedene Dinge gemeint sind:

* **Infrastruktur-Skips** (``INFRA_SKIP_PATTERN``): fehlende DB, fehlendes
  Docker, fehlender Service-Container. In CI ist das *immer* ein Fehler — die
  Infrastruktur steht dort per Service-Container. Budget hart 0, nicht
  konfigurierbar.
* **Uebrige Skips**: plattformbedingt (windows-only), optionale Extras, bewusst
  ausgelassene Faelle. Budget per ``--max-other-skips``, Default 0, weil im
  Repo aktuell null davon existieren (gemessen 2026-09-22). Eine Anhebung ist
  damit eine sichtbare Diff-Zeile mit Begruendung statt stillem Wachstum.

Nutzung::

    python scripts/ci/assert_skips_within_budget.py junit-python.xml
    python scripts/ci/assert_skips_within_budget.py junit-python.xml --max-other-skips 3
    python scripts/ci/assert_skips_within_budget.py apps/web/junit-web.xml

Der dritte Aufruf ist der Vitest-Pfad (P4b): dieselbe Logik, dieselben Budgets.
``INFRA_SKIP_PATTERN`` greift dort erwartbar nie — die Web-Suite laeuft in jsdom
ohne DB, Docker oder Service-Container. Der Schutz kommt auf der Web-Seite allein
aus dem Rest-Budget 0; das Muster bleibt ein wirkungsloser, aber harmloser
Durchlaufposten und wird bewusst nicht web-spezifisch aufgebohrt.
"""

from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

# Skip-Gruende, die auf fehlende Infrastruktur deuten. Bewusst breit und
# case-insensitive: ein falsch-positiver Treffer kostet eine Diskussion, ein
# falsch-negativer kostet ein stilles falsches Gruen — genau die Fehlerklasse,
# gegen die dieses Gate antritt.
INFRA_SKIP_PATTERN = re.compile(
    r"(erreichbare[rn]?\s+(datenbank|db)"
    r"|keine\s+db"
    r"|database.*(not\s+)?(reachable|available)"
    r"|postgres"
    r"|docker"
    r"|testcontainer"
    r"|service\s+container"
    r"|connection\s+refused"
    r"|WHO2BE_REQUIRE_DB)",
    re.IGNORECASE,
)

MAX_LISTED = 15


def _parse(xml_path: Path) -> tuple[int, list[str]]:
    """Zahl der Testfaelle und alle Skip-Gruende aus einer JUnit-XML.

    Ein Eintrag in der Liste je uebersprungenem Test.

    Produzenten-Unterschied, der hier abgefangen wird: pytest schreibt den Grund
    als ``<skipped message="...">``, Vitest schreibt ein nacktes ``<skipped/>``
    ohne jedes Attribut. Ohne Fallback meldete der Report dann N-mal denselben
    Platzhalter und waere zum Debuggen wertlos. Fehlt der Grund, tritt der
    Testname an seine Stelle — er identifiziert den uebersprungenen Fall
    wenigstens eindeutig. Der pytest-Pfad ist davon unberuehrt: dort gewinnt
    ``message`` weiterhin, und nur wenn beide Attribute fehlen, greift der Name.
    """
    root = ET.parse(xml_path).getroot()  # noqa: S314 — eigene CI-Artefakte, kein Fremdinput
    cases = list(root.iter("testcase"))
    reasons: list[str] = []
    for case in cases:
        for skipped in case.findall("skipped"):
            reason = (skipped.get("message") or skipped.get("type") or "").strip()
            if not reason:
                name = (case.get("name") or "").strip()
                reason = f"<ohne Grund> {name}" if name else "<ohne Grund>"
            reasons.append(reason)
    return len(cases), reasons


def _report(title: str, counter: Counter[str]) -> None:
    print(title)
    for reason, count in counter.most_common(MAX_LISTED):
        print(f"  {count:5d}x  {reason[:160]}")
    if len(counter) > MAX_LISTED:
        print(f"  … und {len(counter) - MAX_LISTED} weitere Gruende")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "junit_xml",
        type=Path,
        help="Pfad zur JUnit-XML aus `pytest --junitxml=...`",
    )
    parser.add_argument(
        "--max-other-skips",
        type=int,
        default=0,
        help=(
            "Budget fuer nicht-infrastrukturelle Skips (Default 0). "
            "Anhebung bitte im PR begruenden."
        ),
    )
    args = parser.parse_args(argv)

    if not args.junit_xml.is_file():
        # Fail-closed: eine fehlende XML heisst, dass pytest gar nicht bis zum
        # Schreiben kam. Das als "nichts zu beanstanden" zu werten, waere
        # dieselbe Luege wie ein Skip als Pass zu werten.
        print(f"::error::JUnit-XML nicht gefunden: {args.junit_xml} — lief pytest ueberhaupt?")
        return 2

    total_cases, reasons = _parse(args.junit_xml)
    if total_cases == 0:
        # Ebenfalls fail-closed: eine XML ohne einen einzigen Testfall entsteht
        # z. B., wenn der WHO2BE_REQUIRE_DB-Guard in conftest.py die Collection
        # abbricht. Null ausgefuehrte Tests sind kein "nichts zu beanstanden".
        print(
            f"::error::{args.junit_xml} enthaelt keinen einzigen Testfall — "
            "die Suite wurde nicht ausgefuehrt (abgebrochene Collection?). "
            "Null ausgefuehrte Tests sind kein bestandener Lauf."
        )
        return 2

    infra = Counter(r for r in reasons if INFRA_SKIP_PATTERN.search(r))
    other = Counter(r for r in reasons if not INFRA_SKIP_PATTERN.search(r))
    infra_total = sum(infra.values())
    other_total = sum(other.values())

    print(
        f"Skip-Budget-Gate: {total_cases} Testfaelle, {len(reasons)} uebersprungen "
        f"({infra_total} infrastrukturbedingt, {other_total} uebrige; "
        f"Budget: 0 / {args.max_other_skips})"
    )

    failed = False
    if infra_total:
        _report("Infrastrukturbedingte Skips (Budget 0):", infra)
        print(
            f"::error::{infra_total} Test(s) wegen fehlender Infrastruktur uebersprungen. "
            "In CI steht die DB per Service-Container — ein Skip hier heisst, dass das Setup "
            "kaputt ist, nicht dass der Test verzichtbar waere. Lokal reproduzieren mit "
            "`WHO2BE_REQUIRE_DB=1 uv run pytest`."
        )
        failed = True

    if other_total > args.max_other_skips:
        _report(f"Uebrige Skips ({other_total} > Budget {args.max_other_skips}):", other)
        print(
            f"::error::{other_total} uebersprungene Test(s) ueber dem Budget von "
            f"{args.max_other_skips}. Entweder den Grund beheben oder das Budget im "
            "CI-Aufruf bewusst anheben und im PR begruenden."
        )
        failed = True
    elif other_total:
        _report(f"Uebrige Skips ({other_total} <= Budget {args.max_other_skips}, geduldet):", other)

    if failed:
        return 1
    print("OK: kein uebersprungener Test ueber Budget.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
