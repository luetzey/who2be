"""SessionStart-Hook muss dieselbe Umgebung herstellen wie CI (Issue #495).

Statische Pruefung (DB-frei): jeder `uv sync`-Aufruf in
`scripts/install_pkgs.sh` traegt `--group billing`. CLAUDE.md §Befehle nennt
`uv sync --group billing` als DEN Befehl, `.github/workflows/ci.yml:104`
fuehrt ihn ebenso aus — weicht der Hook davon ab, misst die Session weniger
als CI.

Anlass (#495): der Hook synct bis dahin mit blossem `uv sync`. Dadurch fehlte
das optionale Billing-Paket in Cloud-Sessions, `who2be_billing` war nicht
importierbar und 89 Tests wurden **still** nicht gesammelt — 1812 statt 1901,
ohne Fehler, ohne Skip, bei sogar steigender Coverage. Genau diese Rueckkehr
verhindert der Guard: die Abweichung faellt nicht auf, weil nichts rot wird.
"""

from __future__ import annotations

import re
from pathlib import Path

_INSTALL_PKGS_SH = Path(__file__).resolve().parents[3] / "scripts" / "install_pkgs.sh"

_UV_SYNC = re.compile(r"uv sync\b[^;\n]*")


def test_install_pkgs_sh_syncs_with_billing_group() -> None:
    text = _INSTALL_PKGS_SH.read_text(encoding="utf-8")
    calls = _UV_SYNC.findall(text)
    assert calls, f"Kein `uv sync`-Aufruf in {_INSTALL_PKGS_SH} gefunden."
    offenders = [call for call in calls if "--group billing" not in call]
    assert not offenders, (
        "scripts/install_pkgs.sh synct ohne `--group billing` "
        f"({offenders}) — die Session misst damit weniger als CI "
        "(.github/workflows/ci.yml:104) und CLAUDE.md §Befehle."
    )
