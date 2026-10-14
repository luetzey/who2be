# E-MCP-2: Werkzeugluecken D7 (Karte t_a04550ab)

Fertig heisst: `get_case`, `list_patterns`, `triage_case`, `create_test_case`,
`get_lesson`, `convert_lesson_to_case` sind MCP-Werkzeuge (nur mit
`case_triage` in `tools/list`), rufen bestehende Routen (keine neue Route),
`list_cases` nimmt `cursor` und liefert `next_cursor` (aus `X-Next-Cursor`);
Werkzeugzahl 94 -> 100 in allen Naben (CLAUDE.md: Owner); Builder-Start
<= 120 000, Katalog <= 180 000, jeder Docstring < 1 100.

## Schritte

1. `clients/learning.py`: sechs REST-Aufrufe + `list_cases` mit Cursor
   (`_request` statt `_get`, Header lesen). Body-Spiegel `CaseTriageBody`
   (to=triaged fest, note optional).
2. `tools/learning.py`: sechs Werkzeuge, `list_cases(cursor?)`.
   Rueckgabe = was die Route liefert; `list_cases` `full` jetzt
   `CasePage(items, next_cursor)` (Muster `MemoryPage`), `text` mit
   Folgezeile `cursor="..."`.
3. `tool_requirements.py` sechs Eintraege `_CASE_TRIAGE`; Resolver `_ToolDoc`.
4. Naben: README, ROADMAP, Registry-Test, Policy-Filter-Zahlen (94->100,
   90->96), Isolationsprobe je Werkzeug (Seed eines Lernvorschlags).
5. Tests in `apps/mcp/tests/test_learning_tools.py`.
6. Fragment `changelog.d/`.

## Entschieden (im Rahmen der Karte)

- Ein Modul: `tools/learning.py` statt `tools/cases.py` — spart `server.py`
  im Dateibudget, die Fall-Werkzeuge D4 liegen schon dort.
- `create_test_case`: `origin_case_id` Pflicht (PM-2 „Pruefall aus Fall“),
  ohne `supersedes_id` (Agenten-Token immer 403, `retire` nur Mensch) und
  ohne `origin_measure_id` (Pruefall zu einer Massnahme entsteht im Protokoll).
  Spart Draht-Bytes im knappen Builder-Budget.
- `triage_case` kennt nur `to=triaged`; Body-Modell mit `Literal`.

## Messung

Vorher (origin/main e9234bab): 94 Werkzeuge, tools/list 109 963 Bytes;
Builder-Start 111 567, Default 31 101 (Start), 29 497 (Liste).
Nachher: 100 Werkzeuge, tools/list 114 203 Bytes (+4 240); Builder-Start
115 807 (<= 120 000), Default 31 101 unveraendert (D7 nur mit `case_triage`).

Abweichung vom Plan: `get_case` ohne `format`/Markdown-Fassung — ein Fall ist
ein Einzelobjekt (Groesse durch Feldgrenzen gedeckelt); ein `format` haette
nach dem Guard `test_every_format_aware_tool_has_a_budget_test` einen eigenen
Budget-Nachweis verlangt, ohne Nutzen. `list_cases` behaelt seine Fassungen.

## Dateibudget

Karte: 15 (genehmigt), Produktivcode <= 5. PM-Kommentar: 8 ohne Plan —
Widerspruch, im Handoff/needs_input benannt.
