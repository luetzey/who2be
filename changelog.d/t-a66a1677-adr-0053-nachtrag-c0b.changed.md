- ADR-0053 um den Nachtrag C0b ergänzt (Owner-Entscheidungen vom
  2026-10-01). Das Gedächtnis bekommt eine workspace-weite Liste
  `GET /memories` mit Filtern, Zählern (`GET /memories/counts`) und Stapel
  (`POST /memories/batch`); `GET /memories?status=pending` ist die
  Warteschlange, aus der auch der Dashboard-Zähler kommt. Die
  Notfall-Rücknahme `POST /memories/revoke-auto` setzt automatisch
  freigegebene Einträge zurück auf „Zur Freigabe“ (neues Event
  `auto_revoked`, rücknehmbar per Rollback). Nutzergedächtnis anderer
  Personen bleibt für alle unsichtbar; ein Admin sieht nur die Anzahl und
  kann es löschen. Umsetzung in C3, Oberfläche in C5a/C5b. Es ändert sich
  noch kein Verhalten.
