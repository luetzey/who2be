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

## Drei Kategorien

* `gated` — das Gate haengt als FastAPI-Dependency an der Route und ist ueber
  `route.dependant` auslesbar.
* `service_gated` — das Gate sitzt im Service statt am Router, weil es dort
  hingehoert (siehe `_SERVICE_GATES`). Ueber `route.dependant` ist es nicht
  sichtbar; `test_service_gates_are_wired` prueft es stattdessen per AST am
  Quelltext der aufrufenden Methode.
* `ungated` — kein Quota-Gate, mit Begruendung je Zeile. Das ist **keine**
  Befundliste: die meisten Eintraege gehoeren zu Recht hierher
  (`/oauth/token`, Invitation-Accept, alle `versions/…/transition`-Routen, die
  nichts Neues anlegen). Der Wert der Liste ist, dass sie kurz und stabil ist.

**Eine Grenze, damit niemand danach sucht:** fuer `service_gated` prueft der
AST-Test, dass der Aufruf im Quelltext **steht** — nicht, dass er zur Laufzeit
feuert. Letzteres leisten die Verhaltenstests (`test_token_quota_service.py`,
`test_workspace_quota.py`, `test_tokens.py`). Die Arbeitsteilung ist gewollt:
hier faellt das *Verschwinden* einer Verdrahtung auf, dort ihr *Verhalten*.

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

import ast
import json
import os
from pathlib import Path
from typing import Any, NamedTuple

import pytest
from fastapi.routing import APIRoute

from who2be_api.main import app

_GOLDEN = Path(__file__).parent / "contract" / "gate_inventory.json"
_SRC = Path(__file__).resolve().parents[1] / "src" / "who2be_api"

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


class _ServiceGate(NamedTuple):
    """Ein Quota-Gate, das im Service sitzt statt als Router-Dependency.

    `module`/`cls`/`method` zeigen auf die Methode, die das Gate aufrufen MUSS;
    `call` ist der Name der aufgerufenen `_enforce_*`-Methode. `issue` und
    `why` sind Doku fuer den, der hier spaeter steht.
    """

    module: str
    cls: str
    method: str
    call: str
    issue: str
    why: str


# Routen, deren Deckel bewusst im Service verdrahtet ist. Jeder Eintrag wird
# von `test_service_gates_are_wired` per AST gegen den Quelltext geprueft —
# ohne diese Registry waeren die beiden Routen hier `ungated` und ihr Gate
# koennte still verschwinden.
_SERVICE_GATES: dict[tuple[str, str], _ServiceGate] = {
    ("/tokens", "create_token"): _ServiceGate(
        module="services/token_service.py",
        cls="TokenService",
        method="create",
        call="_enforce_token_quota",
        issue="#538",
        why=(
            "Im Service, weil dort bereits die uebrigen Anlage-Gates sitzen "
            "(Rolle, MFA, Agent-Bindung) und der Service auch ausserhalb des "
            "Routers aufrufbar bleiben soll."
        ),
    ),
    (
        "/v1/organizations/{organization_id}/workspaces",
        "create_organization_workspace",
    ): _ServiceGate(
        module="services/workspace_service.py",
        cls="WorkspaceService",
        method="create",
        call="_enforce_workspace_quota",
        issue="#576",
        why=(
            "Im Service, weil die Grenze org-scoped ist: zum Zeitpunkt der "
            "Anlage gibt es noch keinen WorkspaceContext, an dem eine "
            "Dependency haengen koennte."
        ),
    ),
}


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
    service_gated: list[dict[str, Any]] = []
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
            continue
        known = _SERVICE_GATES.get((route.path, route.name))
        if known is not None:
            service_gated.append(
                {
                    "path": route.path,
                    "name": route.name,
                    "gate": f"{known.cls}.{known.call}",
                    "issue": known.issue,
                }
            )
            continue
        ungated.append({"path": route.path, "name": route.name, "reason": ""})
    gated.sort(key=lambda e: (e["path"], e["name"]))
    service_gated.sort(key=lambda e: (e["path"], e["name"]))
    ungated.sort(key=lambda e: (e["path"], e["name"]))
    return {"gated": gated, "service_gated": service_gated, "ungated": ungated}


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

    live_service = {(e["path"], e["name"]) for e in live["service_gated"]}
    golden_service = {(e["path"], e["name"]) for e in golden.get("service_gated", [])}
    assert live_service == golden_service, (
        "service_gated-Liste geaendert (Golden -> live): "
        f"neu {sorted(live_service - golden_service)}, weg "
        f"{sorted(golden_service - live_service)}. Eine Route faellt hier heraus, "
        "wenn sie ein Router-Gate bekommen hat (dann gehoert sie nach `gated`) "
        "oder aus `_SERVICE_GATES` verschwunden ist — im zweiten Fall ist ihr "
        "Deckel ungeprueft. Golden neu erzeugen (REGEN=1 pytest …)."
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


def _method_body(tree: ast.Module, cls: str, method: str) -> ast.AST | None:
    """Der AST-Knoten von `cls.method`, oder `None` wenn es ihn nicht gibt."""
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != cls:
            continue
        for item in node.body:
            if isinstance(item, ast.AsyncFunctionDef | ast.FunctionDef) and item.name == method:
                return item
    return None


@pytest.mark.contract
@pytest.mark.parametrize(
    ("route", "gate"),
    [pytest.param(k, v, id=f"{k[0]}::{v.call}") for k, v in _SERVICE_GATES.items()],
)
def test_service_gates_are_wired(route: tuple[str, str], gate: _ServiceGate) -> None:
    """Jedes Gate aus `_SERVICE_GATES` wird in seiner Methode auch aufgerufen.

    Das ist die Zusicherung, die `test_gate_inventory_matches_golden` fuer diese
    zwei Routen nicht geben kann: ihr Deckel haengt nicht am Router, sondern im
    Service, und ist ueber `route.dependant` unsichtbar. Ohne diesen Test waere
    das Entfernen von `await self._enforce_token_quota(ctx)` eine Zeile, die
    weder Suite noch ruff noch mypy bemerken — gemessen, nicht vermutet.

    Geprueft wird per AST der Quelltext, nicht das Laufzeitverhalten: dass der
    Aufruf **steht**. Dass er richtig WIRKT, pruefen `test_token_quota_service.py`
    und `test_workspace_quota.py`.
    """
    source = _SRC / gate.module
    assert source.is_file(), (
        f"{gate.module} gibt es nicht (mehr). Wurde der Service verschoben, zeigt "
        f"`_SERVICE_GATES` in test_gate_inventory.py ins Leere und der Deckel von "
        f"POST {route[0]} ist ungeprueft — Eintrag nachziehen."
    )
    tree = ast.parse(source.read_text(encoding="utf-8"))
    node = _method_body(tree, gate.cls, gate.method)
    assert node is not None, (
        f"{gate.cls}.{gate.method} gibt es in {gate.module} nicht (mehr). Umbenannt "
        f"oder verschoben? `_SERVICE_GATES` nachziehen — sonst ist der Quota-Deckel "
        f"von POST {route[0]} ({gate.issue}) ungeprueft."
    )
    called = {
        sub.func.attr
        for sub in ast.walk(node)
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
    }
    assert gate.call in called, (
        f"POST {route[0]} hat seinen Quota-Deckel verloren: {gate.cls}.{gate.method} "
        f"ruft `{gate.call}` nicht mehr auf ({gate.module}, Issue {gate.issue}). "
        f"{gate.why} Ist der Aufruf absichtlich weg, ist die Grenze in der Cloud "
        f"wirkungslos. Ist er nur umbenannt oder in einen Helfer gewandert, gehoert "
        f"`_SERVICE_GATES` in dieser Datei nachgezogen — der Test prueft den "
        f"Methodennamen, nicht das Laufzeitverhalten."
    )
