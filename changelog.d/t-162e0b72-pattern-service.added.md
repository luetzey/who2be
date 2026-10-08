- Service-Schicht für Muster (ADR-0053 3.7, Paket D5a): eine berechnete,
  deterministische Sicht ohne eigenes Aggregat. Lernvorschläge im Status
  `pending`, die einander nach der Dublettenprüfung (Trigram/Vektor) ähneln,
  bilden je Agent ein Cluster; ab Zähler n = 3 ist es ein Muster. Fälle
  bilden ein Muster, wenn mindestens drei noch nicht abgeschlossene Fälle
  (`open`, `triaged`, `in_progress`, `reopened`) desselben Agenten mit
  derselben Zuordnung in den letzten 30 Tagen angelegt wurden. n und das
  Zeitfenster sind gesetzte Annahmen aus ADR-0053 Anhang B. Lesen dürfen
  `editor` und Agenten mit `case_triage`. Ein Muster legt nichts an und
  aktiviert nichts. Die HTTP-Route folgt mit D5b.
