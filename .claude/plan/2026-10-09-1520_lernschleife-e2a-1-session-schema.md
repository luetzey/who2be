# Lernschleife E2a-1 — Schema Gespraechsprotokoll und Massnahme (Migration 0103)

Kanban-Karte t_557f2603, ADR-0053 3.5/3.6, Phase E. Nur Schema, Modelle,
Repository und Test; Service/API folgen in E2b, Compliance-Naben in E2a-2.

## Completion-Condition

- `0103_feedback_session_measure.sql` legt `feedback_session`,
  `feedback_session_case`, `measure`, `measure_case`, `measure_event` an,
  RLS je `workspace_id`, Grants nur SELECT/INSERT.
- `who2be_models.session` + Exporte, `session_repository.py`.
- Neuer Integrationstest gruen mit `WHO2BE_REQUIRE_DB=1`, 0 skipped; DoD aus
  CONTRIBUTING.md gruen; Test gegen origin/main rot (Tabellen fehlen).

## Dateien (6, Grenze 8)

1. `apps/api/src/who2be_api/migrations/0103_feedback_session_measure.sql`
2. `packages/models/src/who2be_models/session.py`
3. `packages/models/src/who2be_models/__init__.py`
4. `apps/api/src/who2be_api/repositories/session_repository.py`
5. `apps/api/tests/test_feedback_session_schema.py`
6. `changelog.d/t-557f2603-lernschleife-e2a-1-protokoll-schema.added.md`

## Vorentschiedene Weichen (mit Beleg)

- Keine DELETE-Grants: die Loeschpfade nach PM-6 sind FK-CASCADE (Fall ->
  Verknuepfung) und Owner-Purge (Agent/Workspace); beide brauchen kein
  DELETE-Recht der App-Rolle (Muster `agent_case_event`, 0100).
- `feedback_session_case` traegt `agent_id` mit Composite-FK auf
  `agent_case (workspace_id, agent_id, id)`: Protokoll-Faelle gehoeren dem
  besprochenen Agenten (3.5 `agent_id` "der besprochene Agent"; Muster
  `agent_case_statement`).
- `supersedes_id` per Composite-FK auf ein Protokoll desselben Agenten.
- `success_criterion`, `counterposition` NOT NULL: in der MCP-Signatur 6.6
  ohne Default.
- `measure_event`-Form als DB-CHECK: Version bei `draft_linked`/`activated`,
  `metrics` genau bei `follow_up_prepared`, `verdict` genau bei `reviewed`,
  `reviewed`/`withdrawn` nur Mensch (F-W7), `activated` nur System (3.6),
  Begruendung bei `withdrawn` und bei `verdict = ineffective` (wird die
  Begruendung von `reopened`, 3.3).
- Kein FK `agent_case_event.measure_id -> measure` in diesem Paket (nicht im
  Kartenumfang; Bestandsdaten koennten ihn brechen) — Hinweis an @pm.
- `measure` und `measure_case` tragen `agent_id` (denormalisiert), damit
  Pruefall und Faelle per Composite-FK beim besprochenen Agenten bleiben.
  Dafuer bekommt `test_case` den UNIQUE `(workspace_id, agent_id, id)` als
  FK-Ziel (pg_constraint-Guard, idempotent).
- `measure.test_case_id` mit ON DELETE CASCADE: Beim Agent-Purge prueft
  Postgres ein NO ACTION vor der Cascade ueber `feedback_session` und bricht
  den Purge ab (im Test belegt). Fuer `who2be_app` ist `test_case` ohnehin
  nicht loeschbar (0089), also faellt eine Massnahme nur mit ihrem Agenten.
- `measures_for_version` wertet nur das juengste `draft_linked` je Massnahme
  aus (QE4 = a).

## Verifikation

- Die gemeinsame Dev-DB `who2be` (Schema public) ist von anderen Branches
  verschmutzt (fremde 0091, alter FK-Stand) und laesst `test_org_transfer`
  auch auf unveraendertem main rot werden. Verifiziert wird gegen die frische
  DB `who2be_t557f` auf demselben Server.

## Offen beim Owner (QE5, QE6)

Beruehren das Schema nicht: QE5 ist eine Statusfolge im Service, QE6 eine
Review-Regel im Service. `target` erlaubt `tool_policy`/`memory` wie 3.6.
Die DB verlangt fuer `reviewed` kein vorheriges `activated` (die Folge prueft
der Service), damit bleibt QE6 = a ohne Migration moeglich.
