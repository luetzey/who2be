# Plan: API- und MCP-Isolationstests je Endpunkt (Cross-Tenant) als CI-Gate

Karte: t_40307837 (Welle 8, Owner-Entscheidung Mandantentrennung = b, ADR-0055 §7).
Basis: origin/main 30b2f83d.

## Ziel

Automatischer Nachweis, dass kein REST-Endpunkt und kein MCP-Tool mit
Objekt-IDs eines fremden Mandanten Daten liefert oder aendert. Die manuelle
Stichprobe vom 2026-09-30 (16 REST-Aufrufe, 5 MCP-Tools) wird zum CI-Gate
ueber **alle** Routen und Tools.

## Fertig heisst

1. Jede Route aus dem Router-Baum (193 heute) und jedes MCP-Tool (85 heute)
   ist entweder geprueft oder mit Begruendung ausgenommen. Eine neue Route
   oder ein neues Tool ohne Eintrag macht den Test rot, ebenso ein Eintrag
   ohne Route (veraltet).
2. Integrationslauf mit zwei echten Mandanten A und B:
   - **V1 fremder Workspace:** jede workspace-gebundene Route als A mit
     `wsB` im Pfad und B-Objekt-IDs -> 403/404.
   - **V2 eigener Workspace, fremde IDs:** jede Route mit Objekt-Referenz
     (Pfad, Query oder Body) als A in `wsA` mit B-IDs -> 403/404.
   - **V3 Listen-/Suchscan:** jede lesende Route ohne Objekt-Referenz als A
     in `wsA` -> Antwort enthaelt keine B-ID und keinen B-Marker.
   - **Schreibschutz:** Fingerprint aller Zeilen von B (jede Tabelle mit
     `workspace_id`, dazu Org/Member) vor und nach allen A-Aufrufen identisch.
   - **Positivkontrolle:** dieselbe Route als B mit B-IDs in `wsB` endet
     nicht in 401/403/404/5xx — die 404 von A entsteht also an der
     Mandantengrenze und nicht an einer kaputten Probe.
   - **Null geprueft = rot:** Mindestzahlen je Variante werden zugesichert.
3. MCP: jedes Tool mit ID-Argument als A-Agent-Token mit B-IDs -> Tool-Fehler,
   und der zugrunde liegende API-Aufruf endete in 403/404; Tools ohne ID ->
   Ergebnis ohne B-Marker. Positivkontrolle mit B-Token.
4. Rot-Probe: Mandantenfilter in einem Repository entfernt -> Test rot,
   Ausgabe im Handoff.
5. Laeuft im `python`-Job (Teil von `all-green`), `WHO2BE_REQUIRE_DB=1`,
   0 skipped.

## Out of Scope

- RLS-Pruefung auf DB-Ebene (bestehend: `test_rls_isolation.py`).
- Export/Import je Org (t_18cb3e8b).
- ADR-0055 §7 nachziehen: Folgekarte (Dateibudget), siehe Handoff.

## Zuschnitt (<= 8 Dateien)

1. dieser Plan
2. `apps/api/src/who2be_api/testing/tenant_pair.py` — Seed A/B + Fingerprint
3. `apps/api/tests/test_tenant_isolation_api.py` — Inventar + REST-Lauf
4. `apps/api/tests/test_tenant_isolation_mcp.py` — Inventar + MCP-Lauf
5. `changelog.d/tenant-isolation-tests.added.md`
6.-8. nur falls der Lauf einen Befund zeigt: Fix + Test (Befunde stehen in
   der Karte, nicht hier).

## Verifikation

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy .
WHO2BE_REQUIRE_DB=1 uv run pytest --cov --cov-fail-under=85
python3 scripts/ci/assert_skips_within_budget.py junit-python.xml
```

## Fortschritt

- [x] Inventar REST + MCP (ohne DB) — 193 Routen, alle MCP-Tools; beide Richtungen rot
- [x] Seed A/B + Fingerprint (`testing/tenant_pair.py`)
- [x] REST V1/V2/V2-mix/V3 + Gegenprobe + Orakel-Vergleich
- [x] MCP-Lauf (In-Memory-Client, ASGI-Transport mit Status-Mitschnitt)
- [x] Rot-Probe: Workspace-Filter in `versioned_repository.py` entfernt -> 2 failed,
      41 Befundzeilen (u. a. `GET .../personas/{id}/versions` liefert B-Daten an A)
- [x] DoD auf Basis 30b2f83d (inkl. M1 #747): ruff/format/mypy gruen, 2583 passed,
      0 skipped, 93,06 %, Lizenz-Gate und Wirkungs-Pruefung ohne Befund
- [x] Rot-Probe wiederholt auf dieser Basis: 2 failed (REST + MCP), 6 Leck-Befunde
- [x] PR

## Befunde (als Folgekarten, im Test als `known` markiert)

Zwei Routen tragen einen `known`-Eintrag mit Verweis auf je eine Folgekarte
(t_977db967, t_19169bdd); die Einzelheiten stehen auf den Karten, nicht im
oeffentlichen Repo.

`known` lockert nur Orakel und Gegenprobe der einen Route; verschwindet die
Abweichung, wird der Test rot, bis der Eintrag entfernt ist.

## Abweichungen vom Plan

- V1 entfaellt im MCP-Teil: der Agent-Token ist an seinen Workspace gebunden,
  `build_client` setzt genau diesen. "Token A, Pfad B" deckt V1 im REST-Test ab.
- KB-Anker (`node:<id>`, `<artifact>#<block>`) werden mit 422
  `anchor_unresolvable` abgewiesen, fuer fremde und unbekannte Anker gleich —
  dort gilt `ANCHOR_DENIED` (403/404/422), der Orakel-Vergleich bleibt aktiv.
- Die Tests liegen beide unter `apps/api/tests/`, weil sie die App und den
  Seed der API brauchen (wie `test_rest_mcp_parity.py`).
