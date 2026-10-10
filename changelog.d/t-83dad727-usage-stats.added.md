- API: Nutzungszähler je Element. `GET /v1/workspaces/{ws}/usage/{entity_type}/{entity_id}`
  (Persona, Playbook, Resource) liefert `uses_7d`, `uses_30d`, `last_used_at`,
  `distinct_agents_30d` und eine Tagesreihe über 30 Tage. `GET /v1/workspaces/{ws}/usage`
  liefert dieselben Zähler ohne Tagesreihe für alle Elemente, optional nach
  `entity_type` gefiltert. Gezählt werden nur Auslieferungen an Agenten, die
  Fenster sind Kalendertage in UTC. Jede Antwort nennt den Zählbeginn
  `counting_since` (2026-10-08). Lesbar ab der Rolle viewer, nicht mit
  agent-gebundenen Tokens.
- API: `GET /feedback-overview` liefert zusätzlich `last_used_at` (nur
  Auslieferungen) und `last_feedback_at` getrennt. `last_activity_at` bleibt
  unverändert.
