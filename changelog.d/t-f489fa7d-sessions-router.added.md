- REST-Routen für Gesprächsprotokolle und Maßnahmen (ADR-0053 6.6, Paket
  E2b-3): `POST /feedback-sessions` reicht ein Protokoll samt Fällen und
  Maßnahmen ein, `GET /feedback-sessions` listet Protokolle (Filter
  `agent_id` und `case_id`, nächste Seite über `X-Next-Cursor`),
  `GET /feedback-sessions/{id}` liefert ein Protokoll mit seinen Maßnahmen.
  An der Maßnahme: `POST /measures/{id}/link-draft` (Entwurf verknüpfen),
  `GET /measures/{id}/follow-up` (Nachschau-Kennzahlen als Rohzahlen),
  `POST /measures/{id}/review` (Einstufung) und `POST /measures/{id}/withdraw`
  (Zurückziehen, mit Begründung). Einreichen, Lesen, Verknüpfen und die
  Kennzahlen dürfen Menschen ab `editor` und Agenten mit `case_triage`;
  Einstufen und Zurückziehen nur Menschen ab `editor`. Schreibende Routen
  sind ratenbegrenzt. Die OpenAPI-Referenz ist neu erzeugt.
