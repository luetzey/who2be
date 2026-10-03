# Plan: `kpis.pending_memories` aus GET /dashboard entfernen

Karte t_de77db11 (Eltern t_c7d08ac6, PM-Entscheidung (a) "entfernen").

## Warum

`_ATTENTION_COUNTS` (dashboard_repository.py) zaehlte jede pending Zeile in
`agent_memory` des Workspaces, also auch `kind='lesson'` und das
Nutzergedaechtnis anderer Mitglieder. Die Zahl ging per `GET /dashboard` an
jede Rolle. Nach ADR-0053 3.1.1 darf fremdes Nutzergedaechtnis nicht nach
aussen, auch nicht als Zahl. Einen Konsumenten gibt es nicht mehr: seit #808
zaehlt das Web ueber `/memories/counts`.

## Schritte

1. Repository: `pending_memories` aus `_ATTENTION_COUNTS` (SQL) und
   `attention_counts` streichen. Rueckgabe ist nur noch die Zahl der
   System-Prompt-Reviews (`int`), das Protocol entsprechend.
2. Service: Mapping entfernen.
3. Modell `DashboardKpis`: Feld entfernen.
4. `docs/reference/openapi.json` per `scripts/export_openapi.py` neu erzeugen.
5. Web: `types.ts`, Fixtures in `DashboardPage.test.tsx`, Kommentar in
   `DashboardPage.tsx`.
6. Tests: vorhandene Assertions umbauen; Rot-Probe in
   `test_dashboard_endpoint.py` (viewer + editor, Seed mit pending
   Nutzergedaechtnis eines anderen Mitglieds und pending lesson; KPIs
   identisch zur Baseline vor dem Seed, Schluessel fehlt).
7. `changelog.d/dashboard-pending-memories.removed.md`.
8. Python- und Web-DoD.

## Freigaben

- 10 Dateien (PM, Kommentar auf der Karte).
- Inventar gilt als nicht gefuehrt: GET /dashboard bleibt in PROBES von
  `test_tenant_isolation_api.py`, eine Liste der Zaehlungen gibt es nicht.
