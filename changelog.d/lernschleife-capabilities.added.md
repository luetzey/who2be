- Zwei neue Agenten-Capabilities für die Lernschleife (ADR-0053 Abschnitt 3.8).

  `test_report` (Prüffall-Ergebnisse melden) ist standardmäßig an,
  `case_triage` (Fälle aller Agenten triagieren, Prüffälle anlegen)
  standardmäßig aus; der Builder bekommt `case_triage` über den Content-Stand
  16, bestehende Builder ziehen es beim Start-Sync nach. Beide Felder stehen im
  `AgentToolPolicy`-Schema der API und im Anti-Eskalations-Vergleich: ein Agent
  kann sie nur vergeben, wenn er sie selbst hält. Bestands-Policies ohne die
  Felder brauchen keine Migration. Noch gated keine der beiden ein Werkzeug —
  die Endpunkte und MCP-Tools folgen in eigenen Paketen.
