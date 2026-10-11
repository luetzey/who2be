# E2b-1 — Service Protokoll einreichen und lesen (Kanban t_01089881)

Stand: 2026-10-11. Basis: origin/main 25e8b1ac.

## Ziel (Completion-Condition)

`SessionService.submit_protocol/get_session/list_sessions` mit Rechten,
Pruefungen, Atomaritaet und in_progress-Automatik; vier neue Fehlergruende
(plus `session_not_found`, QE3 = a) in `ProblemReason` und `_PROBLEM_TITLES`;
DB-Service-Tests gruen mit `WHO2BE_REQUIRE_DB=1`, 0 skipped; DoD aus
CONTRIBUTING.md gruen.

## Dateien (7, Grenze 8)

1. `apps/api/src/who2be_api/services/session_service.py` (neu)
2. `apps/api/src/who2be_api/repositories/session_repository.py` (`begin`,
   `submit_refs`, `start_cases`)
3. `packages/models/src/who2be_models/errors.py`
4. `apps/api/src/who2be_api/main.py` (`_PROBLEM_TITLES`)
5. `docs/reference/openapi.json` (generiert, Enum `reason`)
6. `apps/api/tests/test_session_service.py` (neu)
7. `changelog.d/t-01089881-session-service.added.md`

`case_service.py` bleibt unberuehrt (E3).

## Entscheidungen

- **open -> in_progress (Karte: „gegen ADR 3.3 entscheiden“).** 3.3 kennt
  keine Kante `open -> in_progress`; `-> triaged` verlangt eine Zuordnung,
  `-> in_progress` eine `measure_id`. Beide Rechte („Mensch `editor`; Builder
  mit `case_triage`“) hat jeder, der einreichen darf. Also: Fall `open` bzw.
  `reopened` mit Zuordnung -> zwei Events (`triaged`, `in_progress`); ohne
  Zuordnung bleibt der Fall und steht in `cases_unchanged`. Kein needs_input
  noetig, die Kanten sind eindeutig.
- `measure_id` am Event: die erste Massnahme des Protokolls, die den Fall
  enthaelt.
- Fall-Sperre und Event-Form aus `case_repository` (`_lock_case`,
  `_insert_event`, `_STATUS_SQL`) — eine Quelle; Sperren in fester
  Reihenfolge nach `case_id`.
- `supersedes_id` eines anderen Agenten -> `session_not_found`
  (`params.field = supersedes_id`, QE3 = a), kein neuer Grund.
- Lesen: Mensch ab `editor` oder Agent mit `case_triage` (Karte erweitert
  6.6 „editor“ um den Builder).
- Ratenbegrenzung: `require_write_rate` nur fuer Agenten, wie `report_case`.

## Verifikation

- `uv run ruff check . && uv run ruff format --check . && uv run mypy .`
- `WHO2BE_REQUIRE_DB=1 uv run pytest --cov --cov-fail-under=85 --junitxml=junit-python.xml`
- `python3 scripts/ci/assert_skips_within_budget.py junit-python.xml`
- Gegenprobe: `test_session_service.py` gegen origin/main rot (Modul fehlt).
