# Worker P1a — Migration 0102 `routine_run` und Store (ADR-0057)

Kanban-Karte t_49b81525. Grundlage: ADR-0057 §5/§6, PM-W1 (0102), PM-W4
(Schwellen 2 min / 5 min).

## Completion-Condition

- `0102_routine_run.sql` laeuft auf frischem Schema und auf dem lokalen
  Bestandsstand durch, zweite Anwendung ist ein No-op.
- DB-Test mit `WHO2BE_REQUIRE_DB=1`, 0 skipped: nebenlaeufiger Slot-Claim
  ergibt genau eine Zeile; Abandoned erst nach der Schwelle; zweiter
  Lock-Versuch `false`; `who2be_app` nur SELECT.
- DoD aus CONTRIBUTING.md gruen.

## Schritte

1. Migration 0102: `routine_run` (UNIQUE (routine, slot), CHECKs fuer
   trigger/status, Konsistenz running <=> finished_at NULL, error_class nur
   bei failed, result nur Zahlen), `worker_heartbeat`. Indizes: letzter Lauf
   je routine, letzter Erfolg je routine, Retention (started_at), offene
   Laeufe (heartbeat_at). Grants: `who2be_app` nur SELECT.
2. `worker/__init__.py`, `worker/store.py`: Schwellen als Konstanten,
   claim_slot, finish_run, touch_run, record_worker_heartbeat,
   mark_abandoned, last_run/last_success/latest_runs, Advisory-Lock
   (try/unlock + Kontextmanager auf eigener Verbindung).
3. Waechter: `core/org_transfer.py#GLOBAL_TABLES` um beide Tabellen
   erweitern — `_classify` ist fail-closed fuer Tabellen ohne
   Mandantenspalte und wuerde sonst jeden Org-Export abbrechen. Der
   RLS-Coverage-Guard erfasst nur Tabellen mit `workspace_id`/`org_id`,
   braucht also keine Ausnahme.
4. `tests/test_worker_store.py` (isoliertes Schema).
5. Changelog-Fragment.

## Dateien (Budget 8)

Migration, `worker/__init__.py`, `worker/store.py`, `core/org_transfer.py`,
Test, Fragment = 6.
