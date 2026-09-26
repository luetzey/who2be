- Der Retention-Lauf (`who2be-purge`) überspringt Area-Dateien des
  Tabellen-Stores mit kürzlicher Schreibaktivität (Karenzfrist, 24 h). Bisher
  konnte er die Datei einer gerade gelöschten Area entfernen, während noch auf
  sie geschrieben wurde; der Schreibvorgang meldete Erfolg, das Ergebnis war
  danach nicht mehr erreichbar.

  Als Frischemaß gilt das jüngste `mtime` aus `.sqlite`, `-wal` und `-shm` —
  im WAL-Modus liegt die Schreibspur in der `-wal`-Seitendatei. Eine
  übersprungene Datei ist kein Rückstand: sie wird protokolliert und im
  nächsten Lauf erneut betrachtet, Dateien ohne Schreibaktivität verschwinden
  unverändert im selben Lauf. Messwerte, verworfene Alternativen und die Grenze
  der Lösung (Heuristik, kein Lock) stehen im ADR-0049-Nachtrag 2026-09-26;
  der Backup-Pfad ist gemessen unbedenklich und bleibt unverändert.
