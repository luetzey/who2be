"""OpenAPI-Contract-Snapshot (ADR-0032, Phase 3).

Friert die **oeffentliche API-Oberflaeche** (Methode + Pfad + operationId) als
Golden-File ein. Ein versehentlicher Drift (umbenannte Route, geloeschter
Endpoint, geaenderte operationId) bricht den Test — bewusste Aenderungen werden
durch Neugenerieren des Golden bestaetigt:

    uv run python -m apps.api.tests.contract.regen   # (oder REGEN=1 pytest …)

Bewusst nur die *Oberflaeche*, nicht das volle Schema: der Volldump waere zu
brittle (jede Feld-Reihenfolge), die Oberflaeche faengt genau die
Vertrags-relevanten Aenderungen. Laeuft ohne DB (reiner Schema-Aufbau).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from who2be_api.main import app

_GOLDEN = Path(__file__).parent / "contract" / "openapi_surface.json"
_HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def _live_surface() -> list[dict[str, Any]]:
    schema = app.openapi()
    surface: list[dict[str, Any]] = []
    for path, item in schema["paths"].items():
        for method, op in item.items():
            if method in _HTTP_METHODS:
                surface.append(
                    {
                        "method": method.upper(),
                        "path": path,
                        "operationId": op.get("operationId"),
                    }
                )
    surface.sort(key=lambda e: (e["path"], e["method"]))
    return surface


def test_openapi_surface_matches_golden() -> None:
    live = _live_surface()
    if os.environ.get("REGEN") == "1":
        _GOLDEN.write_text(json.dumps(live, indent=2, ensure_ascii=False) + "\n")
    golden = json.loads(_GOLDEN.read_text())

    live_keys = {(e["method"], e["path"]) for e in live}
    golden_keys = {(e["method"], e["path"]) for e in golden}
    added = sorted(live_keys - golden_keys)
    removed = sorted(golden_keys - live_keys)
    assert not added and not removed, (
        "API-Oberflaeche driftet vom Golden ab. "
        f"Neu: {added}. Entfernt: {removed}. "
        "Beabsichtigt? Golden neu erzeugen (REGEN=1 pytest …) und committen."
    )
    # operationId-Stabilitaet pro Route (Codegen-/Client-Vertrag).
    live_ops = {(e["method"], e["path"]): e["operationId"] for e in live}
    golden_ops = {(e["method"], e["path"]): e["operationId"] for e in golden}
    changed = {k: (golden_ops[k], live_ops[k]) for k in golden_ops if live_ops[k] != golden_ops[k]}
    assert not changed, f"operationId(s) geaendert: {changed}"


def test_every_operation_has_operation_id_and_responses() -> None:
    """Invariante: jede Operation hat operationId + mindestens eine Response.

    Schuetzt Client-Codegen und verhindert versehentlich undokumentierte Routen.
    """
    schema = app.openapi()
    offenders: list[str] = []
    for path, item in schema["paths"].items():
        for method, op in item.items():
            if method not in _HTTP_METHODS:
                continue
            if not op.get("operationId"):
                offenders.append(f"{method.upper()} {path}: keine operationId")
            if not op.get("responses"):
                offenders.append(f"{method.upper()} {path}: keine responses")
    assert not offenders, "OpenAPI-Invariante verletzt:\n" + "\n".join(offenders)
