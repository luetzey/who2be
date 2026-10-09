# Worker P2: Routinen anbinden (Karte t_0065d36b, ADR-0057 §4/§6/§8/§10)

Completion-Condition: `who2be-worker list` zeigt purge, memory-expire,
routine-run-retention; `who2be-purge`/`who2be-memory-expire` schreiben
`routine_run` mit trigger='cli', nehmen den Routinen-Lock (belegt → skipped,
Exit 0); bestehende Purge-/Verfall-Tests unveraendert gruen; neue Tests gruen
mit `WHO2BE_REQUIRE_DB=1`, 0 skipped.

## Schritte

1. [x] `worker/store.py`: `ROUTINE_RUN_RETENTION` (90 d), `delete_runs_before`,
   `external_schedules` (cli-Laeufe an zwei aufeinanderfolgenden UTC-Tagen,
   7-Tage-Fenster) — wiederverwendbar fuer P4b.
2. [ ] `worker/routines.py` (neu): drei Routinen + `run_as_cli(name)`.
   Zeitplaene aus RUNBOOK/Cloud-Inbetriebnahme: purge `30 3 * * *`,
   memory-expire `45 3 * * *`; retention `15 4 * * *` (nach beiden, vor der
   Log-Rotation 04:30). Retention loggt die WARN-Zeile „Externer Zeitplan“.
   CLI-Pfad nutzt `Runner.execute(..., "cli", dodge=True)` — derselbe Claim,
   dasselbe Ausweichen (PM-W5), derselbe Lock, kein Zweitcode.
3. [ ] `worker/runner.py`: CLI-Lauf schreibt keinen `worker_heartbeat` (sonst
   saehe die Betreiber-Sicht einen CLI-Host als Worker); catch_up-Nit
   (juengster Slot `skipped` → wie `failed` einmal nachholen).
4. [ ] `worker/cli.py`: Routinen-Modul importieren (Registrierung).
5. [ ] `core/purge.py`, `core/memory_expiry.py`: `cli()` ueber `run_as_cli`;
   Ausgabe unveraendert, skipped mit klarer Meldung und Exit 0; Fehler wie
   bisher mit Traceback (Protokoll traegt nur die Klasse).
6. [ ] Tests `tests/test_worker_routines.py`: Contract (list), Allowlist (AST,
   transitiv), DB (CLI waehrend Worker-Lauf → skipped, Slotgrenze, Retention 90 d,
   externer Zeitplan, catch_up nach skipped).
7. [ ] Fragment `changelog.d/t-0065d36b-worker-routinen.added.md`.

Dateibudget: 8 (routines, store, runner, cli, purge, memory_expiry, Test, Fragment).
