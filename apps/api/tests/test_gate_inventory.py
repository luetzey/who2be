"""Waechter: das Gate-Inventar der POST-Routen gegen ein Golden-File (Bericht W8/P3, Option C).

**Warum dieser Test existiert.** Eine Messung mit sechs gezielten Auslassungen
(`/home/luetzey/recherche/pro-feature-architektur-2026-09-24.md` §3.3) hat
gezeigt: nimmt man `Depends(enforce_entity_quota)` von **einer** Route weg,
faengt das nur ruff — und nur zufaellig, weil der Import dadurch unbenutzt wird.
Haengt eine zweite Route am selben Import (zwei Ingest-Routen teilen
`enforce_storage_quota`), merkt auch ruff nichts mehr: die volle Suite, ruff und
mypy laufen gruen, waehrend die Speichergrenze in der Cloud umgehbar ist.

Der Test friert deshalb das Inventar `(Pfad, Name, Gates)` aller POST-Routen als
Golden ein — dasselbe Muster, das `apps/api/tests/test_openapi_contract.py` fuer
die API-Oberflaeche schon benutzt. Verschwindet ein Gate, bricht der Diff. Und,
der eigentliche Punkt: eine **neue** ungegatete Create-Route erscheint als neue
`ungated`-Zeile und muss von Hand begruendet werden, statt stillschweigend
ungegatet zu bleiben.

Golden aktualisieren (ein Befehl):

    REGEN=1 uv run pytest apps/api/tests/test_gate_inventory.py

Der Regen-Lauf uebernimmt bestehende Begruendungen und laesst neue Zeilen leer —
eine leere Begruendung haelt den Test rot. Das ist Absicht: ein Golden mit ueber
vierzig `ungated`-Zeilen koennte sonst zur Gewohnheit werden, die man blind
regeneriert.

## Zwei Grenzen der Methode, damit niemand danach sucht

1. **Zwei Routen tragen ein Gate, das hier nicht sichtbar ist.**
   `POST /tokens` und `POST /v1/organizations/{organization_id}/workspaces`
   stehen als `ungated`, obwohl sie gedeckelt sind: ihr Gate sitzt im Service
   (`TokenService._enforce_token_quota` bzw.
   `WorkspaceService._enforce_workspace_quota`) und nicht als FastAPI-Dependency,
   ist ueber `route.dependant` also nicht auslesbar. Das ist eine Grenze dieses
   Tests, **kein Befund** — die beiden Zeilen tragen das als Begruendung. Wird
   ein solches Service-Gate entfernt, faengt dieser Test es nicht.
2. **`ungated` ist keine Befundliste.** Die meisten Eintraege sind zu Recht
   ohne Quota-Gate (`/oauth/token`, Invitation-Accept, alle
   `versions/…/transition`-Routen, die nichts Neues anlegen). Der Wert der Liste
   ist, dass sie kurz und stabil ist.

**Kopplung an FastAPI-Interna, bewusst:** der Test liest
`route.dependant.dependencies` und traversiert `_IncludedRouter.original_router`.
Ein FastAPI-Upgrade kann das brechen — dann bricht es aber laut und in einer
Testdatei, nicht still in Produktion.

**Die Traversierungsfalle, einmal gemessen:** die FastAPI-Version dieses Repos
legt in `app.routes` nicht die Endpunkte ab, sondern `_IncludedRouter`-Wrapper.
Naives `isinstance(r, APIRoute)` liefert **1 Route statt 187**. Deshalb
traversiert `_walk` rekursiv ueber `.original_router`.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from fastapi.routing import APIRoute

from who2be_api.main import app

_GOLDEN = Path(__file__).parent / "contract" / "gate_inventory.json"

# Die drei ueber `route.dependant` sichtbaren Quota-Gates — genau die
# `enforce_*`-Funktionen, die es im Repo als FastAPI-Dependency gibt
# (`services/entity_quota_service.py`, `services/storage_quota_service.py`,
# `services/mcp_limit_service.py`). Kommt ein viertes Dependency-Gate hinzu,
# gehoert es hier hinein, sonst erscheint seine Route als `ungated`.
_GATES = frozenset(
    {
        "enforce_entity_quota",
        "enforce_storage_quota",
        "enforce_mcp_read_limit",
    }
)


def _walk(routes: Any) -> list[APIRoute]:
    """Alle `APIRoute`-Objekte, rekursiv durch `_IncludedRouter`-Wrapper hindurch."""
    found: list[APIRoute] = []
    for route in routes:
        if isinstance(route, APIRoute):
            found.append(route)
            continue
        inner = getattr(route, "original_router", None)
        if inner is not None:
            found.extend(_walk(inner.routes))
    return found


def _live_inventory() -> dict[str, list[dict[str, Any]]]:
    gated: list[dict[str, Any]] = []
    ungated: list[dict[str, Any]] = []
    for route in _walk(app.routes):
        if "POST" not in (route.methods or set()):
            continue
        gates = sorted(
            dep.call.__name__
            for dep in route.dependant.dependencies
            if dep.call is not None and getattr(dep.call, "__name__", "") in _GATES
        )
        if gates:
            gated.append({"path": route.path, "name": route.name, "gates": gates})
        else:
            ungated.append({"path": route.path, "name": route.name, "reason": ""})
    gated.sort(key=lambda e: (e["path"], e["name"]))
    ungated.sort(key=lambda e: (e["path"], e["name"]))
    return {"gated": gated, "ungated": ungated}


def _merge_reasons(
    live: dict[str, list[dict[str, Any]]], golden: dict[str, list[dict[str, Any]]]
) -> dict[str, list[dict[str, Any]]]:
    """Traegt die Begruendungen des Golden in das frische Inventar zurueck.

    Ohne diesen Schritt wuerde ein `REGEN=1`-Lauf die Handarbeit an ueber vierzig
    Zeilen wegwerfen und den Test danach mit lauter leeren Begruendungen rot
    lassen.
    """
    known = {(e["path"], e["name"]): e.get("reason", "") for e in golden.get("ungated", [])}
    for entry in live["ungated"]:
        entry["reason"] = known.get((entry["path"], entry["name"]), "")
    return live


def _read_golden() -> dict[str, list[dict[str, Any]]]:
    data: dict[str, list[dict[str, Any]]] = json.loads(_GOLDEN.read_text(encoding="utf-8"))
    return data


@pytest.mark.contract
def test_gate_inventory_matches_golden() -> None:
    live = _live_inventory()
    if os.environ.get("REGEN") == "1":
        previous = _read_golden() if _GOLDEN.exists() else {"gated": [], "ungated": []}
        merged = _merge_reasons(live, previous)
        _GOLDEN.write_text(
            json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        live = merged
    golden = _read_golden()

    live_gated = {(e["path"], e["name"]): e["gates"] for e in live["gated"]}
    golden_gated = {(e["path"], e["name"]): e["gates"] for e in golden["gated"]}
    lost = sorted(k for k in golden_gated if k not in live_gated)
    assert not lost, (
        f"Gegatete POST-Route(n) aus dem Inventar verschwunden: {lost}. Entweder ist "
        "die Route weg — dann Golden neu erzeugen (REGEN=1 pytest …) — oder ihr Gate "
        "ist weg, und dann ist die Grenze in der Cloud wirkungslos."
    )
    changed = {
        k: (golden_gated[k], live_gated[k])
        for k in golden_gated
        if live_gated[k] != golden_gated[k]
    }
    assert not changed, (
        f"Gate-Bestueckung geaendert (Golden -> live): {changed}. Beabsichtigt? "
        "Golden neu erzeugen (REGEN=1 pytest …) und committen."
    )

    live_ungated = {(e["path"], e["name"]) for e in live["ungated"]}
    golden_ungated = {(e["path"], e["name"]) for e in golden["ungated"]}
    newly_ungated = sorted(live_ungated - golden_ungated)
    assert not newly_ungated, (
        f"Neue POST-Route(n) ohne erkennbares Quota-Gate: {newly_ungated}. Soll die "
        "Route gedeckelt werden, fehlt das Gate. Soll sie es nicht, Golden neu "
        "erzeugen (REGEN=1 pytest …) und die Begruendung in die neue Zeile "
        "schreiben."
    )
    disappeared = sorted(golden_ungated - live_ungated)
    assert not disappeared, (
        f"POST-Route(n) aus der ungated-Liste verschwunden: {disappeared}. Route "
        "entfernt oder jetzt gegatet? Golden neu erzeugen (REGEN=1 pytest …)."
    )


@pytest.mark.contract
def test_every_ungated_route_carries_a_reason() -> None:
    """Jede `ungated`-Zeile im Golden braucht eine Begruendung.

    Die Liste ist lang; ohne diese Zusicherung wuerde sie zur Gewohnheit, die man
    blind regeneriert. Eine Zeile ohne Begruendung ist eine Route, die niemand
    bewusst bestaetigt hat.
    """
    missing = sorted(
        (e["path"], e["name"]) for e in _read_golden()["ungated"] if not e.get("reason", "").strip()
    )
    assert not missing, (
        f"ungated-Zeile(n) ohne Begruendung im Golden: {missing}. Warum braucht diese "
        "POST-Route kein Quota-Gate? Ein Satz in `reason` — das ist der Moment, in dem "
        "eine fehlende Grenze auffaellt."
    )
