- Service-Schicht für den Verlauf einer Maßnahme (ADR-0053, Paket E2b-2):
  Entwurf verknüpfen, Nachschau-Kennzahlen lesen, einstufen und zurückziehen.
  Verknüpfen und Kennzahlen dürfen Menschen ab `editor` und Agenten mit
  `case_triage`; einstufen und zurückziehen nur Menschen ab `editor`. Ein
  Entwurf lässt sich bis zur Aktivierung beliebig oft neu verknüpfen, der
  jüngste gilt. Eingestuft wird genau einmal und erst nach der Aktivierung,
  bei Zielen ohne Versionen (`tool_policy`, `memory`) ab dem Nachschau-Datum.
  Beim Zurückziehen gehen Fälle `in_progress` auf `triaged` zurück, sofern
  keine andere offene Maßnahme sie enthält. Die Kennzahlen kommen als
  Rohzahlen: letzter Prüffall-Lauf vorher und nachher, Fälle und Nutzungen je
  Version, Wiederauftreten, dazu `min_uses` und `insufficient`. Neuer
  Fehlergrund `measure_transition_forbidden` (409). HTTP-Routen folgen in
  einem eigenen Paket.
