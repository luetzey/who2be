- ADR-0057 (Accepted) legt fest, wie Who2Be wiederkehrende Routinen selbst
  mitbringt. Nach der Owner-Entscheidung vom 2026-10-08 laufen Purge und
  Gedächtnis-Verfall künftig in einem eigenen Dienst `worker` (gleiches Image
  wie `api`). Betreiber müssen dann keine Crontab-Zeilen und keine
  Dokploy-Schedules mehr anlegen.

  Die ADR beschreibt die Routinen-Registry im Code mit Env-Overrides, das
  Laufprotokoll in Postgres (`routine_run`, genau ein Lauf je Zeitfenster über
  UNIQUE plus Advisory-Lock), Nachholen, Heartbeat, die Sichtbarkeit nur für
  Betreiber und den Migrationspfad. Die CLIs `who2be-purge` und
  `who2be-memory-expire` bleiben als Notfallweg. Es ändert sich noch kein
  Verhalten.
