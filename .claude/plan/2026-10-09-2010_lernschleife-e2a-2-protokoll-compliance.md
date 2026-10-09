# E2a-2 — Compliance-Naben für Protokoll und Maßnahme (Kanban t_40fc27ec)

Basis: origin/main 733f2a1c (enthält E2a-1, Migration 0103). Vorlage: D1b
(#848, `2026-10-08-0030_lernschleife-d1b-fall-compliance.md`).

## Completion-Condition

1. GDPR-Export enthält je Workspace `feedback_sessions`; jede Sitzung mit
   `case_ids` und `measures`, jede Maßnahme mit `case_ids` und `events`.
   Sichtregel nach ADR-0053 6.6 (`GET /feedback-sessions` ab `editor`), Muster
   D1: ab `editor` alle Protokolle des Workspace, darunter nur die, die die
   Person eingereicht hat (`submitted_by_kind = 'human'`) oder an denen sie
   teilgenommen hat (menschlicher Eintrag in `participants` oder `dissent`,
   oder ein menschliches `measure_event` an einer Maßnahme der Sitzung).
   Maßnahmen, Fälle-Verknüpfungen und Events werden nur für exportierte
   Sitzungen GELADEN. `export_manifest.feedback_sessions` nennt die Regel.
2. `purge_account_data` anonymisiert `feedback_session.submitted_by` (nur
   `human`), menschliche IDs in `participants` (und in `dissent`, s. u.) und
   `measure_event.actor_id` (nur `human`) auf den Sentinel; Agent-Einträge mit
   gleicher UUID bleiben; idempotent.
3. VVT (V23 + Datenkategorie + Frist) und Löschkonzept (§2-Zeilen, §4e, §6,
   §7) nach PM-6.
4. Python-DoD mit `WHO2BE_REQUIRE_DB=1`, 0 skipped; Gegenprobe gegen
   origin/main rot.

## Entscheidung `dissent`

PM-6 nennt „menschliche participants-IDs“. `dissent` trägt dieselbe Person als
`{participant_kind: human, participant_id}` (ADR 3.5). Bliebe die ID dort
stehen, wäre die Anonymisierung der Teilnehmerliste wirkungslos. Deshalb
werden beide Listen gleich behandelt. Im Handoff ausdrücklich genannt.

## Dateien (Budget 8, geplant 6)

1. `apps/api/src/who2be_api/services/gdpr_export_service.py`
2. `apps/api/src/who2be_api/repositories/account_repository.py`
3. `apps/api/tests/test_feedback_session_compliance.py` (neu)
4. `docs/compliance/vvt.md`
5. `docs/compliance/data-retention-and-erasure.md`
6. `changelog.d/t-40fc27ec-lernschleife-e2a-2-protokoll-compliance.added.md`
