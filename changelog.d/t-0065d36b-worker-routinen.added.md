- Worker: Purge, Gedächtnis-Verfall und Protokoll-Aufbewahrung laufen als
  Routinen im Worker (ADR-0057, Paket P2). `who2be-worker list` zeigt
  `purge` (03:30 UTC, Timeout 1 h), `memory-expire` (03:45 UTC) und
  `routine-run-retention` (04:15 UTC). Purge und Verfall tragen dieselben
  Zeiten wie bisher Crontab und Dokploy-Schedules und holen einen verpassten
  Lauf beim Start einmal nach. `routine-run-retention` löscht Einträge im
  Laufprotokoll, die älter als 90 Tage sind.

  `who2be-purge` und `who2be-memory-expire` bleiben als manueller Auslöser und
  Notfallweg. Sie stehen jetzt im Laufprotokoll (`trigger='cli'`) und nehmen
  denselben Lock wie der Worker. Läuft die Routine gerade, endet der Aufruf mit
  einem Hinweis und Exit-Code 0. Die Ausgaben `Purge: …`, `Retention: …` und
  `Gedaechtnis: …` bleiben unverändert. Laufen CLI-Aufrufe einer Routine an
  zwei aufeinanderfolgenden Tagen, meldet der Worker im Log einen externen
  Zeitplan, der entfernt werden kann. Läuft noch kein Worker, ändert sich für
  Betreiber nichts.
