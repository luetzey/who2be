- `GET /v1/workspaces/{workspace_id}/patterns?agent_id` liefert die berechnete
  Musterliste der Lernschleife (ADR-0053 6.5): Muster aus offenen Faellen
  (gleicher Agent, gleiche Zuordnung) und aus aehnlichen Lernvorschlaegen.
  Lesen duerfen `editor` und Agenten mit `case_triage`. Die Antwort traegt
  `threshold` und `window_days`, damit die Oberflaeche die Schwelle anzeigt
  statt sie fest zu kodieren.
