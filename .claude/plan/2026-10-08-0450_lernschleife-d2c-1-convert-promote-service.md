# D2c-1 — Service + Repository: convert (lesson → Fall) und promote (Alt-Feedback → Fall) (Kanban t_d5033324)

Basis: origin/main 3cf22c43 (D2b gemergt). Schnitt laut PM (Kommentar auf der
Karte, 2026-10-08): diese Karte ist Service + Repository ohne Router; Router,
Isolationsproben und Vertragsdateien kommen mit D2c-2 (t_d659442d).

## Completion-Condition

1. `CaseService.convert_lesson` und `CaseService.promote_feedback` mit
   Repository-Methoden `PgCaseRepository.convert_lesson` /
   `promote_feedback`, je EINE Transaktion.
2. `CaseConvertRequest` (Fall-Felder ohne `agent_id`) in `case.py`
   (PM-Weiche 1).
3. Neue `ProblemReason`-Werte `memory_not_convertible` (409) und
   `feedback_not_promotable` (409) mit Titel (PM-Weiche 2).
4. Tests mit echter DB (App-Rolle, RLS):
   - convert setzt `converted`, `converted_case_id`, `source_memory_id`,
     Gedaechtnis-Event `converted` und Fall-Event `reported`;
   - Abbruch zwischen den Schritten (zwei Stellen) → nichts geaendert;
   - Wiederholung der lesson nach convert (`merge_lesson`) bleibt `converted`;
     zweites convert → `memory_not_convertible`;
   - Nicht-lesson bzw. nicht `pending` → `memory_not_convertible`;
   - promote: Fall mit `source_feedback_id`, Alt-Feedback `addressed` mit
     Verweis im `note`; zweites promote bzw. triagiertes Feedback →
     `feedback_not_promotable`;
   - Agent-Token → 403, viewer → 403, fremder Workspace → 404.
5. Mutationsproben rot (Transaktion entfernt; Status-Pruefung entfernt;
   Agent-Sperre entfernt).
6. Python-DoD mit `WHO2BE_REQUIRE_DB=1`, 0 skipped; CI `all-green`.

## Dateien (Budget 8)

1. `packages/models/src/who2be_models/case.py` (`CaseConvertRequest`)
2. `packages/models/src/who2be_models/errors.py`
3. `apps/api/src/who2be_api/main.py` (Titel)
4. `apps/api/src/who2be_api/repositories/case_repository.py`
5. `apps/api/src/who2be_api/services/case_service.py`
6. `apps/api/tests/test_case_convert_promote.py` (neu)
7. `changelog.d/t-d5033324-case-convert-promote.added.md`
8. `docs/reference/openapi.json` (nur das `ProblemReason`-Enum; CI-Drift)

`CaseConvertRequest` taucht erst mit dem Router (D2c-2) in der OpenAPI auf.

## Entscheidungen

- **Rechte.** Beide Wege Mensch ab `editor`; Agent-gebundene Tokens immer
  403 (`is_agent_bound`, keine Capability; Muster `_require_human` und
  `delete_case`). Reihenfolge wie `delete_case`: erst Agent-Sperre, dann Rolle.
- **Melder.** Der Fall wird vom umwandelnden Menschen gemeldet
  (`reporter_kind='human'`, `reporter_user_id = ctx.user_id`); die Herkunft
  steht in `source_memory_id` bzw. `source_feedback_id`.
- **convert.** Lernvorschlag wird unter `FOR UPDATE` gelesen (besitzer-
  gebunden ueber `agent_id` aus dem Pfad). Nur `kind='lesson'` und
  `status='pending'`; sonst `memory_not_convertible` mit `params={kind,
  status}`. Unbekannter Agent → `agent_not_found`, unbekannter Eintrag →
  `memory_not_found`. Fall-`agent_id` = `agent_id` des Lernvorschlags
  (Composite-FK aus 0100 verlangt denselben Agenten). Gedaechtnis-Event
  `converted` (Mensch, `before`/`after`) ueber `_insert_human_event` aus
  `memory_repository` — eine Quelle fuer die Event-Form.
- **promote.** Nur offenes Alt-Feedback (kein Resolution-Event; ADR 5.2
  „ein offenes Feedback“). `in_progress`/`addressed`/`dismissed` →
  `feedback_not_promotable` mit `params={resolution}`. Unbekannt →
  `feedback_element_not_found` (wie `FeedbackService`). Serialisiert ueber
  eine Advisory-Sperre je Feedback (`who2be_app` hat kein UPDATE auf
  `agent_feedback`, also kein `FOR UPDATE`). Verweis im `note`:
  `case:<uuid>` — sprachneutral und maschinenlesbar.
- **Atomar.** Fall + `reported` + Quellen-Aenderung + Event in einer
  Transaktion; Abbruch an jeder Stelle rollt alles zurueck.

## Verifikation (lokal, 2026-10-08)

- `test_case_convert_promote.py`: 9 passed (echte DB, App-Rolle, RLS).
- Mutationsproben (je einzeln, danach Datei aus Sicherung zurueck):
  M1 Transaktion in `convert_lesson`/`promote_feedback` raus →
  `test_convert_aborted_in_last_step_changes_nothing`,
  `test_promote_aborted_in_last_step_changes_nothing` rot;
  M2 kind/status-Pruefung raus → `test_repetition_after_convert_stays_converted`,
  `test_convert_only_pending_lessons` rot;
  M3 Agent-Sperre (`is_agent_bound`) raus → `test_convert_rights_and_scope`,
  `test_promote_rights_and_scope` rot;
  M4 Pruefung „Feedback offen“ raus → `test_promote_only_open_feedback` rot.
- ruff check/format, mypy (551 Dateien) gruen; Lizenz-Gate ok;
  Wirkungspruefung ok; `export_openapi.py` → nur das Reason-Enum (+2).
- Volle Suite `WHO2BE_REQUIRE_DB=1 --cov`: 2944 passed, 0 skipped
  (Skip-Budget-Gate ok), Coverage 93,11 %. 9 rot in `test_org_transfer.py`:
  identisch auch auf unveraendertem main (Gegenprobe per `git stash -u`),
  Ursache die geteilte lokale DB (veralteter Migrationseintrag
  `0091_self_account_function.sql`), wie in D2a. Beleg ueber CI.
