# D2a — Service Fälle (Kanban t_e6df8095)

Basis: origin/main 73ce3277 (D1a + D1b gemergt). Nur Service-Schicht;
Router/OpenAPI = D2b, convert/promote = D2c, MCP = D4, Muster = D5.

## Completion-Condition

1. `services/case_service.py` neu: melden, lesen (Liste, Zähler, Detail),
   Übergänge (ohne Maßnahme), Zuordnung, Schilderung, Löschen.
2. Neue `ProblemReason`-Werte `case_not_found`, `case_transition_forbidden`,
   `case_transition_human_only`, `case_statement_not_subject` + Titel in
   `_PROBLEM_TITLES`; `test_every_problem_reason_has_a_title` grün.
3. Service-Tests mit echter DB (App-Rolle, RLS): jede Kante erlaubt/verboten,
   Rechte je Rolle, Pflichtfelder je Übergang.
4. Mutationsproben rot: `is_agent_bound`-Prüfung raus; viewer-Filter raus;
   Zuordnungspflicht bei `triaged` raus.
5. Python-DoD mit `WHO2BE_REQUIRE_DB=1`, 0 skipped; CI `all-green`.

## Dateien (Budget 8)

1. `apps/api/src/who2be_api/services/case_service.py` (neu)
2. `apps/api/src/who2be_api/repositories/case_repository.py` (Lookups)
3. `packages/models/src/who2be_models/errors.py`
4. `apps/api/src/who2be_api/main.py`
5. `apps/api/tests/test_case_service.py` (neu)
6. `changelog.d/t-e6df8095-case-service.added.md`
7. `docs/reference/openapi.json` (nur das `ProblemReason`-Enum; CI-Drift-Check)

## Entscheidungen (aus Repo/ADR belegt)

- **Kanten.** Diagramm 3.3 (inkl. `in_progress -> dismissed`, der
  Pfeil aus `in_progress` in `dismissed` im Diagramm) plus `triaged ->
  addressed`. Begründung: die
  Tabelle 3.3 nennt für `addressed` neben dem System-Pfad „sonst Mensch
  `editor`“ (ohne Maßnahme); ohne diese Kante wären `addressed` und damit
  `reopened` in D2 unerreichbar, die Karte listet beide als D2-Umfang.
  `in_progress` und `verified` enden mit `case_transition_forbidden`,
  `params.requires = "phase_e"` (Phase E). Eine mitgeschickte `measure_id`
  ebenso.
- **Agent als Richter.** `addressed`, `verified`, `dismissed` (F-W7) und
  zusätzlich `reopened`: 3.3 nennt für `reopened` nur Mensch `editor` und
  System (Nachschau, Phase E). Gleicher Fehler `case_transition_human_only`.
- **Pflichtfelder** (Begründung, Version, Zuordnung) verletzt →
  `case_transition_forbidden` (409) mit `params.missing`. 6.1 kennt keinen
  eigenen Grund dafür; 3.3 führt die Pflicht in derselben Übergangstabelle.
- **Reihenfolge der Prüfungen:** Sichtbarkeit (404) → Agent als Richter (403
  `case_transition_human_only`, vor jeder Kantenprüfung, damit die Regel nicht
  vom Status abhängt) → Rolle/Capability → Kante/Phase E (409) → Pflichtfelder
  (409/404).
- **Lesen „eigene“.** Mensch `viewer`: selbst gemeldete (`reporter_user_id`).
  Agent ohne `case_triage`: Fälle ÜBER sich selbst (`agent_id`) — Parallele
  zu 6.5 `list_cases … # case_triage; ohne: eigene` und 3.2 Prüffälle
  „eigener Agent“; die Schilderung (nur betroffener Agent) setzt Lesen voraus.
  Nicht lesbar = `case_not_found` (kein Enumerieren).
- **Melder-Art.** Agent-Token mit `case_triage` → `builder` (3.3 Rechte und
  3.8: „Builder mit `case_triage`“, „im Builder-Seed an“), sonst `agent`.
- **Löschen.** Mensch ab `editor` (Q6). Agent-Tokens nie (3.3 gibt Agenten
  kein Löschrecht) → `missing_capability`, `actionable_by=none`. Löschlogik
  samt umgewandeltem Lernvorschlag kommt unverändert aus D1b
  (`PgCaseRepository.delete_case`).
- **Elemente.** Existenz je Ziel im Workspace geprüft (persona … external_tool
  über die Identitätstabelle, `memory` über `agent_memory`); `tool_policy`
  und `model_limit` ohne Entity. Unbekannt → `<typ>_not_found` bzw.
  `memory_not_found`.
- **Version bei `addressed`** muss zum Workspace gehören, sonst
  `entity_version_not_found`.

- **Nebenläufigkeit.** Kantenprüfung und Event-Insert dürfen nicht
  auseinanderfallen (Check-then-act). Neue Repo-Methode `append_transition`:
  nimmt dieselbe Advisory-Sperre je Fall wie `set_elements`, prüft darunter
  den erwarteten Ausgangsstatus und (bei `triaged`) die Zuordnung und schreibt
  erst dann. Weicht der Stand ab, liefert sie `None`; der Service liest neu und
  antwortet mit dem passenden Fehler. Damit serialisieren sich auch
  „Zuordnung leeren“ und „triagieren“.

## Verifikation (lokal, 2026-10-08)

- `test_case_service.py`: 10 passed (echte DB, App-Rolle).
- Mutationsproben (je einzeln, danach `git checkout`):
  M1 `is_agent_bound`-Prüfung raus → `test_transition_rights_per_role` rot;
  M2a viewer-Filter Liste raus → `test_read_visibility_per_role` rot;
  M2b viewer-Filter Detail raus → `test_read_visibility_per_role`,
  `test_elements_rights_and_existence` rot;
  M3 Zuordnungspflicht `triaged` raus → `test_required_fields_per_transition` rot.
- ruff/format/mypy grün; Lizenz-Gate ok; Wirkungsprüfung ok.
- Volle Suite `WHO2BE_REQUIRE_DB=1 --cov`: 2927 passed, 0 skipped, Coverage
  93,06 %. 9 rot in `test_org_transfer.py`, Ursache die geteilte lokale DB
  (veralteter Migrationseintrag `0091_self_account_function.sql`); Diff
  berührt weder Migrationen noch `org_transfer.py`, Beleg über CI.
