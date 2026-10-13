- Datenschutz: Das Agenten-Zugriffslog (`agent_access_log`) hat jetzt eine
  Löschfrist von 13 Monaten ab dem Zugriffstag (Owner-Entscheidung E4c-b,
  gleich wie die Nutzungs-Rohdaten). Die bestehende Worker-Routine
  `usage-retention` (täglich 04:10 UTC) löscht beide Tabellen in getrennten
  Transaktionen und meldet den neuen Zähler `deleted_access_log` in der
  Betreiber-Übersicht. Scheitert ein Teil, läuft der andere trotzdem, der Lauf
  endet dann `failed` mit beiden Zählern. Die App-Rolle darf das Log weiterhin
  nur lesen und ergänzen.
