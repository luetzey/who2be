- API: `GET /v1/workspaces/{ws}/feedback-overview` nimmt die optionalen
  Filter `agent_id` (nur Nutzung und Feedback dieses Agenten) und `days`
  (1..365, nur die letzten N Tage) an, einzeln oder kombiniert. Grundlage für
  die Kachel „Feedback zu seinen Bausteinen · 30 Tage" im Agent-Überblick.
  Ohne Parameter bleibt die Antwort unverändert; Rechte weiter ab editor.
  Unbekannter Agent: 404.
