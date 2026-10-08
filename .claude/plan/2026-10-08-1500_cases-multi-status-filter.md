# GET /cases mit mehrfachem status-Filter (Kanban t_570a66ae, ADR-0053 D6-API1)

Status: aktiv

## Ziel
`GET /cases?status=open&status=reopened` filtert serverseitig auf beide Status;
Keyset-Paginierung bleibt intakt. Einzelwert wirkt wie bisher (MCP `list_cases`).

## Schnitt (Dateibudget 8, geplant 6)
1. `apps/api/src/who2be_api/routers/cases.py` — `status_filter: list[CaseStatus] | None`.
2. `apps/api/src/who2be_api/services/case_service.py` — Durchreichen der Liste.
3. `apps/api/src/who2be_api/repositories/case_repository.py` — `x.status = ANY($3::text[])`
   (Protokoll + Postgres-Implementierung), NULL = Filter aus wie bisher.
4. `apps/api/tests/test_cases_api.py` — Router-Test: drei Status-Fixtures
   (open, triaged, reopened), Mehrfachfilter genau beide, != ungefiltert, != Einzelwert;
   Paginierung ueber die Seitengrenze mit Mehrfachfilter.
5. `docs/reference/openapi.json` — per `scripts/export_openapi.py`.
6. `changelog.d/t-570a66ae-cases-multi-status.changed.md`.

Vertragsdateien (`openapi_surface.json`, `gate_inventory.json`) fuehren nur
method/path/operationId bzw. Pfade, keine Parameter: unberuehrt.

## Verifikation
- Neuer Test rot auf origin/main, gruen nach Fix; Mutationsprobe Router-Parameter -> None rot.
- DoD aus CONTRIBUTING.md mit `WHO2BE_REQUIRE_DB=1`, MCP-Tests gruen.
