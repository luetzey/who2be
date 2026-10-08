- REST-Endpunkte für zwei Wege zum Fall (ADR-0053 6.4/6.5, Paket D2c-2)
  unter `/v1/workspaces/{workspace_id}`:
  `POST /agents/{agent_id}/memories/{memory_id}/convert` wandelt einen
  offenen Lernvorschlag in einen Fall um (Body = Fall-Felder ohne
  `agent_id`, der Agent kommt aus dem Lernvorschlag),
  `POST /feedback/{feedback_id}/promote` übernimmt ein offenes Alt-Feedback
  in einen Fall (Body = Fall-Felder mit `agent_id`). Beide antworten mit
  201 und dem neuen Fall, nur für Menschen ab der Rolle `editor`
  (Agent-Tokens und `viewer` 403). Ein zweiter Versuch endet mit 409
  `memory_not_convertible` bzw. `feedback_not_promotable`.
