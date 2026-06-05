"""Ueberspringt die Billing-Test-Suite, wenn das optionale who2be_billing fehlt.

Der On-Prem-Kern laeuft bewusst ohne `--group billing` (siehe CLAUDE.md). Ohne
diesen Hook bricht `pytest` schon bei der Collection mit `ModuleNotFoundError`
ab, weil die Module hier `who2be_billing.*` auf Modulebene importieren. Mit
`collect_ignore_glob` wird die gesamte Suite sauber uebersprungen, sobald das
Paket nicht installiert ist (mit Gruppe laeuft sie unveraendert).
"""

from __future__ import annotations

import importlib.util

collect_ignore_glob: list[str] = []

if importlib.util.find_spec("who2be_billing") is None:
    collect_ignore_glob.append("*")
