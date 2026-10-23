- Schreibantworten des Markdown-Wegs nennen zu lange Inhalte (ADR-0063,
  Builder schlank B4). Liegt ein Persona-Profil, ein Modus, die Zahl der
  Modi, ein Playbook-Body, die Playbook-Beschreibung mit Triggern oder ein
  Resource-Abschnitt über der Warnschwelle, trägt die Antwort das neue,
  additive Feld `length_hints[]` mit Messwert, Richtwert und einer kurzen
  Meldung, etwa „Profil 1 450 Wörter, Richtwert 400“. Gespeichert wird
  trotzdem. Die MCP-Schreibwerkzeuge zeigen die Hinweise als eine Zeile
  `length_note`. Die Richtwerte stehen einmal in
  `who2be_models.content_budgets`, ein Test hält sie gleich mit den
  Agent-Bau-Konventionen.
