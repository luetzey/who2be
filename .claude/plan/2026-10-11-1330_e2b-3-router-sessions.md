# E2b-3: Router Protokolle und Massnahmen (Karte t_f489fa7d)

Outcome: die sieben Routen aus ADR-0053 6.6 (ohne Dossier) stehen unter
`/v1/workspaces/{ws}` und reichen nur an `SessionService`/`MeasureService` durch.

Schritte
1. [x] Bestand lesen: Services E2b-1/E2b-2, `routers/cases.py` (Muster), Vertragstests.
2. [x] `routers/sessions.py`: 7 Routen; Schreibrouten `write_limit`; Liste mit Keyset +
       `X-Next-Cursor`; Request-Modelle (link-draft, review, withdraw) mit `extra=forbid`.
       review `ineffective` ohne `note` -> 422 schon im Request-Modell (sonst 500 aus
       `MeasureEventCreate` im Service).
3. [x] `main.py` include_router.
4. [x] Golden: `REGEN=1` fuer gate_inventory/openapi_surface, Begruendungen von Hand;
       `scripts/export_openapi.py`.
5. [x] Isolationstest: Probe je Route, Seed `_session_extras` (Protokoll + Massnahme je Mandant).
6. [x] `test_sessions_api.py`: Rechte-Matrix je Rolle, Fehlergruende, Cursor, fremder Workspace,
       write_limit je Schreibroute, Agent ohne Policy.
7. [x] Mutationsproben 11/11 rot (5x Triage-Recht, 2x human-only, 4x write_limit);
       Gegenprobe gegen origin/main 16 rot. DoD lokal, PR.

Ergebnis lokal: ruff, format, mypy gruen; pytest 3366 passed. Rot nur
`test_org_transfer.py` (9) wegen Fremd-Migration in der lokalen Test-DB
(`0091_self_account_function.sql`, auf main nicht vorhanden; auch ohne diese
Aenderung rot), 1 Skip `who2be_billing` lokal nicht installiert. CI ist massgeblich.

`GET /measures/{id}/follow-up` ohne `write_limit`: fuer Menschen lesend; der
Schreibweg des Builders (`follow_up_prepared`) laeuft ueber die Agent-Schreibrate
im Service.

Nicht im Umfang: `GET /agents/{id}/dossier` (eigene Karte), `due`-Filter und Zeilen-Zaehler
aus QE2 (der Service E2b-1 liefert sie nicht; Folgekarte), `types.ts` (E5).
Dateibudget 8: Router, main.py, openapi.json, gate_inventory, openapi_surface,
Isolationstest, Router-Test, Fragment.
