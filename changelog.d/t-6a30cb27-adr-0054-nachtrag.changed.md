- ADR-0054 (Orchestrator) um einen Nachtrag zur Feldspezifikation ergänzt.

  Die Owner-Entscheidung vom 2026-10-06 nimmt alle vierzehn Weichen S1–S14
  der Spezifikation O1 so an, wie empfohlen: unter anderem eigene
  Versionstabelle `delegation_version`, Capability `delegation_write`,
  eigene Spalte `agent.run_limits`, Server-Urteil bei `tool_trace` und der
  Persona-Tag `coding` als Kriterium für den AGENTS.md-Export. Korrigiert
  ist §4.1: Die Who2Be-Kennung einer Delegationsvorlage steht in
  `Message.metadata`, nicht in `Task.metadata`. Die Migrationsnummern der
  Welle sind fest vergeben (0097 `run_limits`, 0098 `tool_trace`,
  0099 Delegation). Reine Doku-Änderung.
