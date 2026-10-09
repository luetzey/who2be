- Worker: Runner und Befehl `who2be-worker` (ADR-0057, Paket P1c).
  `who2be-worker run` prüft etwa alle 30 Sekunden die fälligen Zeitpläne,
  belegt je Slot genau einen Lauf und hält währenddessen den Advisory-Lock der
  Routine. Läuft dieselbe Routine gerade als CLI- oder manueller Lauf, endet
  der geplante Lauf als `skipped`. Jede Routine läuft mit ihrem Timeout; im
  Protokoll steht bei einem Fehler nur die Exception-Klasse. Routinen mit
  `catch_up` holen nach einem Ausfall beim Start genau einen Lauf nach.

  Weitere Befehle: `who2be-worker check` (Container-Healthcheck: eigener
  Heartbeat jünger als 2 Minuten), `who2be-worker list` (effektive
  Zeitplan-Tabelle) und `who2be-worker run-once <name> [--force]` (ein
  manueller Lauf mit der Startzeit als Slot). Auf SIGTERM belegt der Worker
  keine neuen Slots und lässt die laufende Routine bis zum Timeout enden; ein
  zweites Signal bricht sie ab und markiert den Lauf als `failed`.
  `WHO2BE_WORKER_ENABLED=false` hält den Prozess am Leben, ohne Slots zu
  belegen. Es sind noch keine Routinen angebunden, und der Dienst steht noch
  in keiner Compose-Datei; an laufenden Installationen ändert sich nichts.
