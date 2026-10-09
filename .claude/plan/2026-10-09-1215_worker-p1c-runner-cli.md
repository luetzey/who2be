# Worker P1c: Runner und CLI `who2be-worker` (ADR-0057 §3, §5, §6)

Karte: t_496026fc. Basis: origin/main @ b675cc6c (P1a Store, P1b Registry/Schedule).

## Completion-Condition

- `worker/runner.py`, `worker/cli.py`, Script-Eintrag, Tests, Fragment im PR (<= 8 Dateien).
- `WHO2BE_REQUIRE_DB=1 uv run pytest apps/api/tests/test_worker_*.py` gruen, 0 skipped.
- DoD aus CONTRIBUTING.md gruen; `who2be-worker run` lokal gegen DB, SIGTERM-Logauszug im PR.

## Entscheidungen (aus Repo belegt)

- Verbindungen: eine Kontrollverbindung (Claim, Abschluss, Heartbeats, Abandoned),
  je Lauf eine eigene Routinen-Verbindung (`RoutineContext.conn`) und der
  Advisory-Lock auf der dedizierten Verbindung aus `store.routine_lock`.
  Waehrend eines Laufs frischt eine Heartbeat-Task `routine_run.heartbeat_at`
  UND `worker_heartbeat` auf, damit der 2-min-Healthcheck auch bei einer
  einstuendigen Routine gruen bleibt.
- Reihenfolge je Lauf: claim_slot, dann Lock; Lock belegt -> `skipped`.
- Fehler: nur Klassenname (`store.finish_run`), Timeout -> `TimeoutError`.
- catch_up nur beim Start: faellig, wenn kein Erfolg existiert oder der Slot
  des letzten Erfolgs vor dem juengsten faelligen Slot liegt (eine Periode
  verpasst). Dann genau ein Lauf: juengster Slot, ist er belegt (z. B.
  abgebrochen), der Startzeitpunkt (+1 µs-Ausweichen). Slots vor dem Start
  ohne catch_up werden nicht nachgeholt.
- SIGTERM/SIGINT: erste Anforderung -> keine neuen Slots, laufende Routine
  laeuft bis Ende/Timeout. Zweite Anforderung -> laufende Routine abbrechen,
  Lauf `failed` mit `WorkerShutdown`.
- `check`: Heartbeat dieses Containers (worker_id-Praefix `<hostname>:`),
  juenger als `WORKER_HEALTHCHECK_MAX_AGE` -> Exit 0.
- `run-once <name> [--force]`: trigger `manual`, Slot = Startzeit, bei
  UNIQUE-Konflikt +1 µs (PM-W5); ohne `--force` Abbruch, wenn Routine oder
  Worker per Env abgeschaltet sind.
- Logging: stdlib `logging` wie `core/purge.py`, `configure_logging(log_format)`.

## Schritte

1. runner.py
2. cli.py + Script-Eintrag
3. tests/test_worker_runner.py (DB, Test-Registry)
4. Fragment, `worker/__init__.py`-Docstring
5. DoD, lokaler Lauf mit SIGTERM, Commit, Push, PR
