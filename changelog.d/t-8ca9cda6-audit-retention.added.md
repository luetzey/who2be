- Datenschutz: Neue Worker-Routine `audit-retention` (täglich 04:00 UTC,
  holt einen verpassten Lauf beim Start nach). Sie löscht Audit-Log-Einträge
  gelöschter Workspaces und Organisationen 12 Monate nach ihrer
  Anonymisierung (Owner-Entscheidung E1a). Das Audit-Log bestehender
  Workspaces bleibt unberührt. Zeitplan und Schalter lassen sich wie bei den
  anderen Routinen über `WHO2BE_ROUTINE_AUDIT_RETENTION_SCHEDULE` und
  `WHO2BE_ROUTINE_AUDIT_RETENTION_ENABLED` überschreiben.
