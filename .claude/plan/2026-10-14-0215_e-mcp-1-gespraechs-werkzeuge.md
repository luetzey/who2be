# E-MCP-1: Gespraechs-Werkzeuge + Budget 180k (Karte t_2e3f1968)

Fertig heisst: `get_dossier`, `submit_session_protocol`, `link_measure_draft`,
`get_follow_up` sind als MCP-Werkzeuge registriert (nur mit `case_triage` in
`tools/list`), rufen die E2b-/E1-Routen aus `routers/sessions.py`, reichen
Problem-Gruende durch; Werkzeugzahl 90 -> 94 in allen Naben ausser `CLAUDE.md`
(Owner-Handgriff); `_PAYLOAD_BUDGET_BYTES` = 180_000 mit Verweis W-E1 b.

## Schritte

1. `clients/sessions.py`: REST-Aufrufe + Spiegelmodelle der Antworten, die
   nur in der API leben (`SessionSubmitResult`, `CaseUnchanged`,
   `FollowUpReport`, `VersionReport`, `RunRate`). Drift-Schutz: Schema-
   Vergleich nicht als eigener Test (Dateibudget), siehe unten.
2. `tools/sessions.py`: vier Werkzeuge, Docstrings < 1 100, erster Satz <= 100.
   Rueckgabe = was die Route liefert (wie D4 bei `assign_case_elements`):
   `submit_session_protocol` -> `SessionSubmitResult`, `link_measure_draft` ->
   `MeasureEventRead`.
3. `server.py` register; `tool_requirements.py` vier Eintraege `_CASE_TRIAGE`;
   Resolver `_ToolDoc`.
4. Naben: README, ROADMAP, Tests (Registry-Zahl, Policy-Filter-Zahlen,
   Isolationsprobe je Werkzeug mit DB-Seed einer Massnahme), Budget-Test +
   `docs/mcp-payload-budget.md`.
5. Tests `apps/mcp/tests/test_session_tools.py` (Client gemockt).
6. Fragment `changelog.d/`.

## Messung

Payload vorher (origin/main 37d339ca): 90 Werkzeuge, 104 290 Bytes; Builder
104 290, Default 29 497. Nachher: 94 Werkzeuge, 109 963 Bytes; Builder 109 963
(Start mit `instructions` 111 567), Default 29 497 (unveraendert, die vier
Werkzeuge brauchen `case_triage`).

## Offen (needs_input an @pm)

1. `test_agent_start_meets_target_per_profile`: Builder-Start 111 567 >
   Ziel 110 000 (`_START_TARGET_BYTES`, Test sagt „nicht das Ziel anheben“).
   Die Karte regelt nur das Katalog-Budget. Schnitt erst nach Entscheidung.
2. `test_doc_tool_count[CLAUDE.md]`: Zeile 98 „90 Tools gesamt“ -> „94“
   (Owner-Handgriff laut Karte).

## Drift-Schutz Spiegelmodelle

`FollowUpReport` mit `extra="forbid"`; die Gegenproben im Isolationstest
parsen echte API-Antworten aller vier Werkzeuge. Kein eigener Paritaetstest
(Dateibudget).

## Dateibudget

15 Dateien (genehmigt), davon 5 Produktivcode.
