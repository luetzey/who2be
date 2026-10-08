- Der Server zeichnet jetzt selbst auf, welche Persona-, Playbook- und
  Resource-Version ein Agent abgerufen hat (ADR-0053 Abschnitt 3.4, Paket D3):
  jeder Abruf über `GET .../personas/{id}/rendered`,
  `GET .../playbooks/{id}/rendered` und `GET .../resources/{id}` durch ein
  agent-gebundenes Token schreibt eine Zeile in `usage_event` mit der neuen
  Spalte `source = 'server'` (Migration 0101). Abrufe durch Menschen werden
  nicht aufgezeichnet. Schlägt die Aufzeichnung fehl, wird der Abruf trotzdem
  ausgeliefert.
- `record_usage` meldet nur noch das Ergebnis (`applied`, `skipped`, `error`),
  gespeichert als `source = 'agent_report'`. Bestehende Zeilen gelten als
  `agent_report`.
- Die Feedback-Auswertung trennt beide Quellen: `usage_count` in
  `GET .../feedback/{type}/{id}` und `GET .../feedback-overview` zählt nur
  Auslieferungen durch den Server, `by_outcome` nur die Ergebnismeldungen der
  Agenten. Früher zählte jede Ergebnismeldung als Nutzung. Auch die Liste
  `GET .../feedback-unused` versteht unter „genutzt“ jetzt eine Auslieferung.
  Ein Element, das bisher nur per `record_usage` gemeldet wurde, zeigt deshalb
  `usage_count` 0 und erscheint wieder als ungenutzt, bis ein Agent es abruft.
