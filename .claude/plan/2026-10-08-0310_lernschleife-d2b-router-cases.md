# D2b — Router /cases (Kanban t_1f315c65)

Basis: origin/main ce1f46e3 (D2a gemergt). Router + OpenAPI auf `CaseService`.
Nicht hier: promote/convert (D2c), patterns (D5b), MCP (D4),
`GET /test-cases?origin_case_id=` (Q5, eigener Router/Service, außerhalb Budget).

## Completion-Condition

1. `routers/cases.py` neu, in `main.py` eingebunden:
   `POST /cases` (201), `GET /cases?agent_id&status&target&cursor&limit`,
   `GET /cases/counts?agent_id` (Q1), `GET /cases/{id}` (CaseDetail),
   `POST /cases/{id}/transition`, `PUT /cases/{id}/elements` (Replace),
   `POST /cases/{id}/statement` (201), `DELETE /cases/{id}` (204, Q6).
2. Härtung `_require_triage_right`: agent-gebunden ohne Policy -> 403
   `missing_capability` (PM-Kommentar 2026-10-08). Mutationsprobe rot.
3. Router-Tests (echte DB): Status je Rolle, 404 fremder Workspace,
   Replace-Semantik, je Filter (agent_id, status, target) Ergebnis != ungefiltert.
   Mutationsprobe: Filter im Router auf None -> rot.
4. Isolationsproben je Route, `gate_inventory.json`, `openapi_surface.json`,
   `openapi.json` (regeneriert).
5. Python-DoD mit `WHO2BE_REQUIRE_DB=1`, 0 skipped; CI `all-green`.

## Dateien (Budget 9 + 1)

1. `apps/api/src/who2be_api/routers/cases.py` (neu)
2. `apps/api/src/who2be_api/main.py`
3. `apps/api/tests/test_cases_api.py` (neu)
4. `apps/api/tests/test_tenant_isolation_api.py`
5. `apps/api/tests/contract/gate_inventory.json`
6. `apps/api/tests/contract/openapi_surface.json`
7. `docs/reference/openapi.json`
8. `changelog.d/t-1f315c65-cases-router.added.md`
9. `apps/api/src/who2be_api/services/case_service.py` (+1, Härtung)

## Entscheidungen

- **Paginierung:** Repo-Konvention `X-Next-Cursor`-Header + `list[CaseRead]`
  (`core/pagination.py`, agents/personas/playbooks); `limit` 1..200, Default 50
  (Spec S7). Peek mit `limit + 1` im Router, Service unverändert.
- **Zähler:** `GET /cases/counts` -> `dict[CaseStatus, int]` je Status (auch 0),
  dieselbe Sichtbarkeit wie die Liste (Service `count_by_status`).
- **DELETE:** Q6 (PM 2026-10-07, „betroffen hier“) — Service aus D2a,
  sonst toter Code. 204.
- **Elemente-Body:** `{"elements": [...]}`, höchstens 50 Einträge.
- **Rate-Limit:** `write_limit` auf jeder Mutation (wie test_cases).
- **Härtung lokal im Service**, nicht in `require_capability` (53 Aufrufer;
  PM: nicht ausweiten).
