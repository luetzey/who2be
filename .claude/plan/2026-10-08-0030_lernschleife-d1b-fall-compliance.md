# D1b — Compliance-Naben für Fälle (Kanban t_14408571)

Basis: origin/main 410cce41 (enthält D1a, Migration 0100). Vorlagen: B1c (#710),
C1b (#750), #764 (Sichtregel im Export).

## Completion-Condition

1. GDPR-Export enthält je Workspace `cases` mit `events`, `elements`,
   `statements`; Sichtregel nach ADR-0053 3.3 (Rechte): ab `editor` alle Fälle
   des Workspace, darunter nur die selbst gemeldeten (`reporter_user_id` =
   Anfragender). Verlauf/Zuordnung/Schilderung nur für exportierte Fälle
   GELADEN. Test viewer/editor, Mutationsprobe (Filter raus → rot).
2. `purge_account_data` anonymisiert `agent_case.reporter_user_id`,
   `agent_case_event.actor_id` (nur `actor_kind='human'`) und
   `agent_case_element.assigned_by` (nur `assigned_by_kind='human'`) auf den
   Sentinel; idempotent getestet; Personal-Org-/Org-Purge mit umgewandeltem
   Lernvorschlag läuft durch.
3. `delete_case` löscht einen Fall auch dann, wenn ein Lernvorschlag in ihn
   umgewandelt wurde (PM-Hinweis aus #843): der Lernvorschlag fällt in
   derselben Anweisung mit, je Zeile eine inhaltsfreie Audit-Spur.
4. VVT + Löschkonzept ergänzt; Python-DoD mit `WHO2BE_REQUIRE_DB=1` grün.

## Entscheidung Purge-Regel (aus dem Repo belegt, nicht erfunden)

Anonymisieren (Sentinel), nicht löschen und nicht NULL:

- ADR-0053 §3 „Gemeinsame Regeln“: jede Tabelle mit Personenbezug kommt in die
  **Purge-Anonymisierung** (`purge_account_data`).
- Löschkonzept §2/§4b/§4c: Was eine Person **erstellt/gemeldet** hat
  (`agent_feedback.actor_id`, `test_case.created_by`,
  `test_run.reported_by_user_id`) bleibt als Inhalt des Workspace stehen und
  wird anonymisiert; gelöscht wird nur, was **über** die Person ist
  (Nutzergedächtnis). Ein Fall handelt vom Verhalten eines Agenten, nicht von
  der meldenden Person.
- `NULL` scheidet technisch aus: CHECK `agent_case_human_reporter_check`
  (0100, Weiche F2 „kein anonymer Kanal“) verlangt bei `reporter_kind='human'`
  eine `reporter_user_id`. Der Sentinel erfüllt den CHECK und folgt §2.

## Entscheidung umgewandelter Lernvorschlag beim Löschen

Lernvorschlag mitlöschen (statt `converted_case_id` auf NULL):

- NULL verlangt wegen CHECK `converted <=> converted_case_id` (0091) einen
  neuen Status; `rejected` behauptete eine menschliche Ablehnung, die es nie
  gab, `pending` brächte die Lehre zurück in die Triage.
- Der Lernvorschlag ist die Quelle des Fall-Inhalts; bliebe er stehen, bliebe
  genau der Inhalt, den der Löschende entfernen will („Löschen samt Verlauf“,
  Q6/M5).
- Spur wie beim Gedächtnis: `memory.deleted` ohne Inhalt, Historie per Cascade.

## Dateien (Budget 8)

1. `apps/api/src/who2be_api/services/gdpr_export_service.py`
2. `apps/api/src/who2be_api/repositories/account_repository.py`
3. `apps/api/src/who2be_api/repositories/case_repository.py`
4. `apps/api/tests/test_case_compliance.py` (neu)
5. `docs/compliance/vvt.md`
6. `docs/compliance/data-retention-and-erasure.md`
7. `changelog.d/t-14408571-lernschleife-d1b-fall-compliance.added.md`

Keine Migration nötig.

## Schritte

- [ ] Export + Test
- [ ] Purge + Test
- [ ] delete_case + Test
- [ ] Doku
- [ ] DoD, Mutationsprobe, Push, PR
