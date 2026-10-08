# Lernschleife D5b — Router `GET /patterns`, OpenAPI

Kanban: t_704f8aab · ADR-0053 6.5 (`GET /patterns?agent_id`, `editor` /
`case_triage`), Anhang A.2 (D5 fasst `RT/cases.py` an). Baut auf D5a
(`PatternService`, #857) auf.

## Ziel (fertig heisst)

`GET /v1/workspaces/{ws}/patterns?agent_id` liefert
`PatternList {threshold, window_days, patterns}` aus `PatternService`.
Rechte im Service (`require_triage_right`), der Router reicht durch.

## Entscheidungen

- **Ort:** `routers/cases.py`, nicht ein eigener Router. ADR A.2 sieht D5 in
  `RT/cases.py` vor; eine einzelne lesende Route rechtfertigt keine zweite
  Mount-Stelle in `main.py` (und bliebe im Dateibudget).
- **Antwortform:** Objekt statt nackter Liste, weil `threshold` und
  `window_days` mitgehen (PM-Entscheidung Q8). Keine Paginierung: die Sicht ist
  berechnet und klein (Spec, Abschnitt Muster).
- **Isolation:** Probe mit `filters=True` wie `/cases`: fremde `agent_id`
  filtert auf leer statt 404.

## Schritte

1. [x] `PatternList` in `who2be_models/pattern.py`.
2. [x] Route + Dependency in `routers/cases.py`.
3. [x] `test_patterns_api.py`: Rollen, Antwortform, Filter, fremder Workspace.
4. [x] Isolationsprobe, `openapi_surface.json` (REGEN), `openapi.json` (Export).
   `gate_inventory.json` unveraendert (erfasst nur POST-Routen).
5. [x] Mutationsproben: Filter ignoriert, Rechtepruefung entfernt,
   `window_days` vertauscht — je rot.
6. [x] DoD aus CONTRIBUTING.
