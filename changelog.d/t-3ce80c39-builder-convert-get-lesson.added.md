- API (Lernschleife Phase E, PM-4): Der Builder, also ein Agent-Token mit
  `case_triage`, darf einen Lernvorschlag per
  `POST /agents/{agent_id}/memories/{memory_id}/convert` in einen Fall
  umwandeln. Der Fall traegt dann `reporter_kind=pattern` und den Builder als
  `reporter_agent_id`; das Gedaechtnis-Ereignis `converted` hat einen
  Agenten als Akteur. Fuer Menschen bleibt alles wie bisher (ab `editor`).
  Ausserdem liest der Builder per `GET /memories/{memory_id}`
  Lernvorschlaege (`kind=lesson`) aller Agenten im Workspace. Jeder andere
  Eintrag ist fuer ihn `memory_not_found` wie eine unbekannte ID. Agent-Tokens
  ohne `case_triage` bekommen auf beiden Wegen weiter 403. Die Route traegt
  jetzt das MCP-Leselimit wie jede agent-gerichtete Leseroute.
