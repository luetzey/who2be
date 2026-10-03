- Der Gedaechtnis-Abruf eines Agenten (`GET /agent-memories/search`,
  `GET /agent-memories`) liefert jetzt neben dem Agentengedaechtnis auch das
  Nutzergedaechtnis des Token-Besitzers — nie das eines anderen Menschen und
  nie Lernvorschlaege (`kind=lesson`). Jeder Treffer traegt zusaetzlich
  `kind`, `scope` und `confirmed`; `confirmed=false` heisst automatisch aktiv,
  aber von keinem Menschen bestaetigt (ADR-0053 C4a).

  Der Laufzeit-Push in `get_persona` zeigt nur noch bestaetigte Eintraege;
  automatisch aktive, unbestaetigte erreicht der Agent nur ueber den Abruf auf
  Anfrage. `POST /agent-memories` dokumentiert die Antwort `200` mit
  `merged_into` fuer eine wiederholte Lektion jetzt auch in der OpenAPI-Spec.
