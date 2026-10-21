- `GET /feedback-sessions` kennt den Filter `due=true`: nur Protokolle mit
  mindestens einer fälligen Maßnahme (Nachschau-Datum heute oder früher,
  weder eingestuft noch zurückgezogen; der Server rechnet mit dem heutigen
  Datum). Er lässt sich mit `agent_id`, `case_id` und dem Cursor kombinieren.
  Jede Zeile der Liste trägt jetzt `case_count`, `measure_count`,
  `due_measure_count`, `next_follow_up_at` (frühestes Nachschau-Datum der
  offenen Maßnahmen) und `superseded_by_id` (die jüngste Korrektur). Die
  OpenAPI-Referenz ist neu erzeugt.
