# W8/P3 — Zwei Waechter-Tests gegen stille Luecken

Karte: `t_80fddf34` · Branch: `who2be/t_80fddf34-w8-p3-zwei-waechter-tests-gegen-stille-l`
Basis: `origin/main` @ `cee6478e` · Quelle: `/home/luetzey/recherche/pro-feature-architektur-2026-09-24.md` §5+§6

## Ziel (Completion-Condition, messbar)

Zwei neue Testdateien existieren, laufen im `python`-Job mit, und **beide sind
in einer nachgewiesenen Rot-Probe ausgeloest worden**:

1. `apps/api/tests/test_entitlement_field_completeness.py` wird rot, wenn
   `workspace_quota` aus dem `ON CONFLICT DO UPDATE` von
   `PgEntitlementRepository.upsert` entfernt wird (Mutation **M4** des Berichts,
   heute gruen durchlaufend).
2. `apps/api/tests/test_gate_inventory.py` wird rot, wenn
   `Depends(enforce_storage_quota)` von **einer** der zwei Ingest-Routen
   entfernt wird (Mutation **M2**, heute gruen durchlaufend).

Nicht erfuellt ohne diese zwei Rot-Laeufe im Transkript.

## Nicht gebaut (Leitplanke aus dem Bericht)

Kein zentrales Entitlement-Register, keine Gate-Abstraktionsschicht. Begruendung
des Berichts: „Der Weg ist nicht zu kompliziert, er ist zu still." Keine Gates
hinzugefuegt oder geaendert, keine Quote angefasst, B1/B2/B3 nicht angefasst.

## Option A — Entitlement-Feldvollstaendigkeit

Datei: `apps/api/tests/test_entitlement_field_completeness.py`

Aufbau:

* Feld-Klassifikation. Jedes Feld aus `Entitlement.model_fields` muss in genau
  einer von zwei Listen im Test stehen: `QUOTA_FIELDS` (Obergrenzen, die den
  ganzen Weg gehen muessen) oder `NON_QUOTA_FIELDS` (Status-/Zeitfelder, mit
  Begruendung im Kommentar). Ein **neues** Feld, das in keiner Liste steht,
  bricht den Test. Damit greift der Waechter auch, wenn ein kuenftiges Feld
  nicht `*_quota*` heisst — das war das im Bericht benannte Muster-Risiko
  (§6 Option A, „Risiko").
* Zusicherung 1 (SQL, alle persistierten Felder): der Quelltext von
  `PgEntitlementRepository.fetch` bzw. `.upsert` wird via `inspect.getsource`
  gelesen und in die **vier** Fragmente zerlegt — `SELECT`,
  `INSERT INTO org_entitlement`-Spaltenliste, `ON CONFLICT DO UPDATE SET`,
  `INSERT INTO entitlement_history`. Jedes Feld muss in jedem der vier
  Fragmente vorkommen. Die Fehlermeldung nennt Feld **und** Fragment.
* Zusicherung 2 (Plan-Metadata, nur Quota-Felder): zu jedem Feld existiert in
  `who2be_billing.plans` ein Modul-Attribut `META_<FELD_GROSS>` mit dem
  Feldnamen als Wert, und der Key erscheint in `Plan.metadata()` von
  `FREE_PLAN` und `PRO_PLAN`.
* Zusicherung 3 (Anzeige, nur Quota-Felder): der Feldname ist ein Feld von
  `EntitlementInfo` (`routers/entitlement.py`).

Keine DB, kein `integration`-Marker — reine Reflexion + Quelltextlesen.

## Option C — Gate-Inventar als Golden File

Dateien:
* `apps/api/tests/test_gate_inventory.py`
* `apps/api/tests/contract/gate_inventory.json` (Golden)

Aufbau:

* Routen-Traversierung rekursiv ueber `.original_router`, uebernommen aus der
  funktionierenden Sonde des Berichts (`test_gate_inventory_probe.py` im
  Belege-Ordner). Naives `isinstance(r, APIRoute)` liefert in dieser
  FastAPI-Version 1 statt 187 Routen — die Falle ist im Modul-Docstring
  festgehalten, damit sie nicht ein zweites Mal gesucht wird.
* Erkannte Gates: die drei ueber `route.dependant.dependencies` sichtbaren
  Dependency-Gates (`enforce_entity_quota`, `enforce_storage_quota`,
  `enforce_mcp_read_limit`) — genau die drei `enforce_*`-Funktionen, die es im
  Repo gibt.
* Golden-Format JSON, zwei Listen: `gated` (Pfad, Name, Gates — rein
  maschinell) und `ungated` (Pfad, Name, **`reason`**). Der Test bricht, wenn
  das Inventar vom Golden abweicht **oder** wenn eine `ungated`-Zeile keine
  Begruendung traegt. Damit ist die im Bericht benannte Gefahr adressiert, ein
  41-zeiliges Golden blind zu regenerieren: eine neue ungegatete POST-Route
  erscheint mit leerer Begruendung und bleibt rot, bis der Autor sie bewusst
  bestaetigt.
* Aktualisierung mit einem Befehl, Muster von `test_openapi_contract.py`:
  `REGEN=1 uv run pytest apps/api/tests/test_gate_inventory.py`. Der
  Regen-Lauf **uebernimmt bestehende Begruendungen** (Merge ueber
  Pfad+Name), damit ein Regen die Handarbeit nicht wegwirft.
* Methodengrenze im Docstring: `POST /tokens` und
  `POST /v1/organizations/{organization_id}/workspaces` stehen als `ungated`,
  obwohl sie ein Gate haben — ihr Gate sitzt im Service
  (`TokenService._enforce_token_quota`, `WorkspaceService._enforce_workspace_quota`)
  und ist ueber `route.dependant` nicht sichtbar. Grenze der Methode, kein
  Befund; die beiden Zeilen tragen das als Begruendung.

## Schritte

1. Plan ablegen (diese Datei).
2. Test A schreiben, gruen laufen lassen.
3. Test C schreiben, Golden erzeugen, 41 Begruendungen von Hand fuellen, gruen.
4. Rot-Probe A: M4 mutieren, Test A rot zeigen, Mutation zuruecknehmen.
5. Rot-Probe C: M2 mutieren, Test C rot zeigen, Mutation zuruecknehmen.
6. Changelog-Fragment `changelog.d/w8p3-waechter-tests.added.md`.
7. DoD (CONTRIBUTING §Definition of Done, Python-Stack) lokal, Skip-Zahlen
   ehrlich nennen; `scripts/check_code_refs.py` wegen dieser Plandatei.
8. Push, PR gegen `main`, Review anfordern. Kein Merge, kein Auto-Merge.

## Auf Zuruf angenommen

Keine Annahmen — die Karte trug alle vier Pflichtfelder (Outcome,
Akzeptanzkriterien inkl. Rot-Probe, Out of Scope, Verifikation via DoD).
