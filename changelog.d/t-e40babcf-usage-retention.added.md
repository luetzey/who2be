- Datenschutz: Neue Worker-Routine `usage-retention` (täglich 04:10 UTC,
  holt einen verpassten Lauf beim Start nach). Sie löscht die rohen
  Nutzungsdaten (`usage_event`, eine Zeile je Auslieferung an einen Agenten)
  nach 13 Monaten (Owner-Entscheidung E4b). Die Nutzungszähler für 7 und 30
  Tage bleiben unverändert; „zuletzt genutzt“ reicht höchstens 13 Monate
  zurück. Zeitplan und Schalter lassen sich über
  `WHO2BE_ROUTINE_USAGE_RETENTION_SCHEDULE` und
  `WHO2BE_ROUTINE_USAGE_RETENTION_ENABLED` überschreiben.
