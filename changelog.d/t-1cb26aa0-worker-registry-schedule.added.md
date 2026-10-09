- Worker: Registry und Zeitpläne der Hintergrund-Routinen (ADR-0057, Paket
  P1b). Routinen melden sich mit `@routine(name, schedule, timeout, catch_up,
  touches_tablestore)` an; ein doppelter oder ungültiger Name scheitert beim
  Import. Ein Zeitplan ist ein Cron-Ausdruck (fünf Felder oder Alias wie
  `@daily`) oder ein Intervall (`@every 15m`), immer in UTC.

  Betreiber können ohne Rebuild überschreiben: `WHO2BE_ROUTINE_<NAME>_SCHEDULE`,
  `WHO2BE_ROUTINE_<NAME>_ENABLED` und global `WHO2BE_WORKER_ENABLED`. Ein
  ungültiger Wert ist ein Startfehler, kein stiller Rückfall auf den
  Code-Wert. Neue Abhängigkeit: `croniter` (MIT). Der Dienst `worker` selbst
  folgt in den nächsten Paketen; an laufenden Installationen ändert sich bis
  dahin nichts.
