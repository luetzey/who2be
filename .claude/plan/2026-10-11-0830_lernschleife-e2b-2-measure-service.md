# E2b-2 — Service Massnahme: link-draft, follow-up, review, withdraw (Kanban t_5aa42fb2)

Stand: 2026-10-11. Basis: origin/main 06ddb3fb (CI/Deploy gruen).

## Ziel (Completion-Condition)

`MeasureService.link_draft/follow_up/review/withdraw` mit Rechten nach 6.6,
Event-Folge nach QE4 a / QE6 a, Fall-Ruecksetzung nach QE5 a und den
Kennzahlen nach 6.6 / QE8 a. Dazu der Paralleltest der Fall-Sperre aus dem
Review E2b-1 (PM-Kommentar a). DB-Service-Tests gruen mit
`WHO2BE_REQUIRE_DB=1`, 0 skipped; DoD aus CONTRIBUTING.md gruen.

## Dateien (8, Grenze 8)

1. `apps/api/src/who2be_api/services/measure_service.py` (neu; session_service
   bleibt beim Protokoll, die Karte erlaubt eine eigene Datei)
2. `apps/api/src/who2be_api/repositories/session_repository.py`
   (`lock_measure`, `version_ref`, `reset_cases_after_withdraw`,
   `follow_up_figures`)
3. `packages/models/src/who2be_models/errors.py` (`measure_transition_forbidden`)
4. `apps/api/src/who2be_api/main.py` (`_PROBLEM_TITLES`)
5. `docs/reference/openapi.json` (generiert, Enum `reason`)
6. `apps/api/tests/test_measure_service.py` (neu)
7. `apps/api/tests/test_session_service.py` (Paralleltest Fall-Sperre)
8. `changelog.d/t-5aa42fb2-measure-service.added.md`

## Entscheidungen

- **409-Grund:** `measure_transition_forbidden` mit `params.state` (und
  `params.action`). Die Karte sagt „case_transition_forbidden bzw. ein
  passender bestehender Grund, keinen neuen erfinden“; der spaetere
  PM-Kommentar QE3 = a (2026-10-09) legt `measure_transition_forbidden`
  (409, params.state) ausdruecklich fest. Er ist also entschieden, nicht
  erfunden.
- **Event-Folge (QE4 a):** link-draft nur in `agreed`/`draft_linked`
  (beliebig oft, der juengste gilt). review genau einmal und erst nach
  `activated`; Ausnahme QE6 a: Ziele ohne Versionen (`tool_policy`,
  `memory`) ab Faelligkeit auch ohne `activated`. Nach `reviewed` oder
  `withdrawn` nur noch Lesen. withdraw in jedem offenen Zustand.
- **QE5 a (Owner 2026-10-09):** withdraw setzt Faelle der Massnahme von
  `in_progress` auf `triaged` zurueck (System-Event mit `measure_id` und der
  Begruendung), sofern keine andere offene Massnahme sie enthaelt. In
  derselben Transaktion, unter der Fall-Sperre in fester Reihenfolge.
- **review durch Agent:** immer 403 `missing_capability`
  (`actionable_by=none`), geprueft ueber `is_agent_bound` vor jeder Capability
  — Muster `_delete_forbidden_for_agents`. withdraw genauso.
- **Massnahmen-Sperre:** `pg_advisory_xact_lock` je Massnahme, damit
  „genau einmal“ auch bei zwei gleichzeitigen Einstufungen haelt.
- **Kennzahlen (QE8 a, Rohzahlen):** alte Version = die zuletzt vor der
  Aktivierung (bzw. jetzt) aktive andere Version laut `status_history`,
  sonst die aktuell aktive andere Version. Pruefall-Quote je Seite = juengster
  `test_run` des Pruefalls der Massnahme (3.2: „Es zaehlt das letzte
  Ergebnis“). Fallrate: Faelle desselben Agenten am selben Element im
  Zeitfenster der Version gegen Nutzungen `usage_event` mit
  `source='server'` und `version` (3.4). Wiederauftreten: neue Faelle am
  selben Element nach `activated` (Ziele ohne Versionen: nach Anlage der
  Massnahme), ohne die Faelle der Massnahme.
- **min_uses = 50 (gesetzte Annahme):** einzige Zahl in der Spec S9d
  („nach weiteren 50 Nutzungen“); `insufficient` = Nutzungen seit Aktivierung
  < min_uses oder kein Vergleich moeglich. Im Handoff als Annahme markiert.
- **follow_up_prepared:** nur wenn ein Agent aufruft, die Massnahme
  einstufbar ist (sonst stuende der Zustand vor `activated`) und sich die
  Kennzahlen seit dem letzten Schnappschuss geaendert haben.
- Fallstatus-Folgen von review (verified/reopened) baut E3, hier nur das Event.

## Verifikation

- `uv run ruff check . && uv run ruff format --check . && uv run mypy .`
- `WHO2BE_REQUIRE_DB=1 uv run pytest --cov --cov-fail-under=85 --junitxml=junit-python.xml`
- `python3 scripts/ci/assert_skips_within_budget.py junit-python.xml`
- Gegenprobe: neue Tests gegen origin/main rot (Modul fehlt).
- Mutationen: Sperre in `start_cases` entfernt -> Paralleltest rot;
  `is_agent_bound`-Pruefung in review entfernt -> Rechtetest rot.
