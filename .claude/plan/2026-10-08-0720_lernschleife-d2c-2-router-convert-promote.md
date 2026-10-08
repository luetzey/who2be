# D2c-2 — Router convert und promote (Kanban t_d659442d)

Basis: origin/main 97a827f1 (D2c-1 gemergt, Service `convert_lesson` /
`promote_feedback`). Nur die HTTP-Schicht + Vertrag.

## Completion-Condition

1. `routers/cases.py`:
   `POST /agents/{agent_id}/memories/{memory_id}/convert` (201, Body
   `CaseConvertRequest`, ohne `agent_id`) und
   `POST /feedback/{feedback_id}/promote` (201, Body `CaseCreate`).
   Beide mit `write_limit`.
2. Router-Tests (echte DB): Agent-Token 403 (auch mit `case_triage`),
   viewer 403, editor 201; Wiederholung 409 `memory_not_convertible` bzw.
   `feedback_not_promotable`; fremder Workspace 404.
3. Isolationsproben je Route, `gate_inventory.json` (ungated mit
   Begruendung), `openapi_surface.json`, `openapi.json` regeneriert.
4. Python-DoD mit `WHO2BE_REQUIRE_DB=1`, 0 skipped; CI 18/18.

## Dateien (Budget 7)

1. `apps/api/src/who2be_api/routers/cases.py`
2. `apps/api/tests/test_case_convert_promote_api.py` (neu)
3. `apps/api/tests/test_tenant_isolation_api.py`
4. `apps/api/tests/contract/gate_inventory.json`
5. `apps/api/tests/contract/openapi_surface.json`
6. `docs/reference/openapi.json`
7. `changelog.d/t-d659442d-case-convert-promote-router.added.md`

(+ dieser Plan, wie bei D2b/D2c-1.)

## Entscheidungen

- **Beide Routen im Fall-Router** (`cases.py`), nicht in `memory.py` /
  `feedback.py`: beide rufen ausschliesslich `CaseService`, liefern einen
  `CaseRead` und teilen dessen Abhaengigkeit `get_case_service`. In
  `feedback.py` haette promote eine zweite Service-Fabrik und den
  Fall-Vertrag in einen Router gezogen, der sonst nur Feedback kennt
  (Karte: „begruende, falls doch feedback.py“ — nicht noetig). ADR-0053
  D2-Zeile nennt `feedback.py`; die Karte (PM 2026-10-08) entscheidet
  spezifischer.
- **201** wie `POST /cases`: es entsteht ein neuer Fall.
- **Isolationsprobe:** vorhandene Seeds (`memory_id` = user_fact,
  `feedback_id`) genuegen: die Gegenprobe als B endet fachlich mit 409
  (`memory_not_convertible`) bzw. 201/409 — beides nach dem Lookup, also
  bestanden (`control_passes`). Kein zusaetzlicher Seed noetig.
- Q2 bleibt: kein Element-Feld im Body (`extra=forbid` in beiden Modellen).
