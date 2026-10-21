# Lernschleife E-API: Builder darf convert und Lernvorschlaege lesen (PM-4)

Karte t_3ce80c39, ADR-0053 Phase E. Voraussetzung fuer die MCP-Werkzeuge
`convert_lesson_to_case` und `get_lesson` (PM-2).

## Done heisst

1. `POST /agents/{agent_id}/memories/{memory_id}/convert`: Agent-Token mit
   `case_triage` -> 201, Fall mit `reporter_kind=pattern`,
   `reporter_agent_id` = Builder, `source_memory_id` gesetzt; Gedaechtnis-Event
   `converted` mit `actor_kind=agent`. Agent ohne Policy / ohne `case_triage`
   -> 403. Mensch unveraendert (editor, `reporter_kind=human`).
2. `GET /memories/{memory_id}` (bestehende Route, keine neue): Agent-Token mit
   `case_triage` liest `kind=lesson` (`scope=agent`) jedes Agenten im
   Workspace. Andere kinds, fremder Workspace, unbekannte ID -> 404
   `memory_not_found`. Agent ohne `case_triage` -> 403 wie bisher. Route
   bekommt `enforce_mcp_read_limit` (agent-facing Read, SEC-2-Paritaet).
3. Tests (Service + Router) mit Mutationsprobe je Rechteregel; Fragment.

## Dateien (Budget 8)

case_service.py, case_repository.py, memory_service.py, routers/memory.py,
routers/cases.py (Kommentar), test_case_convert_promote.py,
test_case_convert_promote_api.py, changelog.d-Fragment. openapi.json nur,
falls sich das Schema aendert (erwartet: nein, Router ohne Docstrings).

## Entscheidungen

- `GET /memories/{memory_id}` statt `GET /agents/{agent_id}/memories`: die
  Karte verlangt Lesen per ID; die Liste je Agent wuerde alle kinds liefern
  und braeuchte einen Filter im Service.
- `reporter_agent_id` = Builder beim Agent-convert: nachvollziehbar, wer den
  Fall formuliert hat (3.7 „wenn der Builder ... ihn formuliert“); das
  `reported`-Event bleibt `system` (bestehende Regel `_reporter_actor`).
