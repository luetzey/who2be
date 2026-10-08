# D6-API2: GET /test-cases?origin_case_id (Karte t_0f3e68b4)

Ziel: Filter `origin_case_id` an `GET /test-cases`, damit das Fall-Detail (D6d)
die aus einem Fall abgeleiteten Pruefaelle findet.

## Schritte
1. Repository `list_cases`: Parameter `origin_case_id`, feste Position `$6`
   (NULL = Filter aus), wie die bestehenden Filter.
2. Service `list_cases`: Parameter durchreichen, Rechte unveraendert.
3. Router: Query `origin_case_id: UUID | None`.
4. Test (test_test_cases_api.py): Pruefaelle mit Fall A, Fall B, ohne Fall;
   Filter liefert genau die passenden, ungefiltert mehr; kombiniert mit
   `status`; fremder Workspace mit eigenem Pruefall auf derselben Fall-ID
   liefert im Ausgangs-Workspace nur die eigenen, und eine Fall-ID, die nur im
   fremden Workspace vorkommt, liefert leer.
5. Web: `TestCaseFilters.origin_case_id`, `listTestCases` setzt den Parameter
   (keine Client-Tests fuer listTestCases vorhanden).
6. openapi.json per scripts/export_openapi.py; Vertragsdateien fuehren keine
   Parameter (openapi_surface.json nur Methode/Pfad/operationId).
7. Fragment changelog.d/t-0f3e68b4-test-cases-origin-case.changed.md.

MCP bleibt unveraendert.

## Dateibudget (8)
router, service, repository, test, types.ts, client.ts, openapi.json, Fragment.

## Verifikation
- `WHO2BE_REQUIRE_DB=1` Python-DoD (CONTRIBUTING), 0 skipped
- Mutationsprobe: Router reicht None durch -> Test rot
- `npx tsc -b`
