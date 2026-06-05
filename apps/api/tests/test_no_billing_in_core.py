"""Build-Isolations-Guard (ADR-0029): der Kern kennt die Billing-Schreibseite nicht.

Statische Pruefungen (DB-frei), die das Akzeptanzkriterium des Vorhabens absichern:
der On-Prem-Build darf KEINEN Mollie-/Billing-Code enthalten.

1. `apps/api/src/who2be_api` enthaelt **keinen** statischen Import von
   `who2be_billing` und **keinen** Import des Mollie-SDK.
2. `apps/api/pyproject.toml` listet weder `mollie-api-python` noch `who2be-billing`
   als Dependency.

Die dynamische, optionale Discovery (`importlib`-basiert in `main` /
`core.migrations`) ist erlaubt und faellt nicht unter diese Verbote.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

_API_SRC = Path(__file__).resolve().parents[1] / "src" / "who2be_api"
_API_PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"

# Statische Import-Statements (nicht: String-Argumente an importlib.find_spec).
_FORBIDDEN_IMPORT = re.compile(
    r"^\s*(from\s+(who2be_billing|mollie)(\.\w+)*\s+import\s|import\s+(who2be_billing|mollie)\b)",
    re.MULTILINE,
)


def test_core_has_no_static_billing_or_mollie_import() -> None:
    offenders: list[str] = []
    for path in _API_SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if _FORBIDDEN_IMPORT.search(text):
            offenders.append(str(path.relative_to(_API_SRC.parent)))
    assert not offenders, (
        f"Kern (who2be_api) importiert die Billing-Schreibseite statisch: {sorted(offenders)}"
    )


def test_core_pyproject_does_not_depend_on_billing_or_mollie() -> None:
    data = tomllib.loads(_API_PYPROJECT.read_text(encoding="utf-8"))
    deps = data.get("project", {}).get("dependencies", [])
    names = {re.split(r"[<>=!~ \[]", d, maxsplit=1)[0].strip().lower() for d in deps}
    assert "mollie-api-python" not in names, "apps/api darf nicht von Mollie abhaengen."
    assert "who2be-billing" not in names, "apps/api darf nicht von who2be-billing abhaengen."
