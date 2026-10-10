- API: Nutzungszähler für Agenten. `GET /v1/workspaces/{ws}/agents/{agent_id}/usage`
  liefert die Auslieferungen an den Agenten in 7 und 30 Tagen (gesamt und je
  Persona, Playbook, Resource), die aktiven Tage im 30-Tage-Fenster, eine
  Tagesreihe, „zuletzt genutzt“ (jüngste Auslieferung) und „zuletzt aktiv“
  (jüngster Aufruf mit einem Token des Agenten). Dazu je Arbeitsbereich mit
  Zugriffen dieses Agenten die Zugriffstage in 30 Tagen und das Datum des
  letzten Zugriffs. Ein eigener Zähler für `fetch_agent` entfällt.
- API: Zugriffszähler für Arbeitsbereiche. `GET /v1/workspaces/{ws}/work-areas/{area_id}/usage`
  liefert aus dem Zugriffslog Zugriffstage, Lese- und Schreibzugriffe, die Zahl
  der Agenten und das Datum des letzten Zugriffs (ohne Uhrzeit) samt
  Tagesreihe über 30 Tage. Beide Sichten sind ab der Rolle viewer lesbar, nicht
  mit agent-gebundenen Tokens, und nennen keine Agent-Namen. Ein viewer sieht
  nur geteilte Arbeitsbereiche.
