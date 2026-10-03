- Gedaechtnis: `GET /memories`, `GET /memories/counts` und `POST /memories/batch`
  (Filter-Modus) nehmen fuer `status`, `kind` und `origin` mehrere Werte.
  Im Query-String wiederholt man den Parameter (`?status=active&status=pending`),
  im `filter` von `batch` steht eine Liste; ein Einzelwert gilt weiter.
  Innerhalb eines Feldes gilt ODER, zwischen den Feldern UND. Neu ist
  `exclude_status` (wiederholbar), das Status ausschliesst. Die Standardansicht
  der Gedaechtnisverwaltung ist `exclude_status=rejected`. Die Zaehler-Gruppe
  `status` laesst Auswahl und Ausschluss weg, damit auch ein ausgeschlossener
  Status seine Zahl hat. Liste, Zaehler und Stapel meinen dieselbe Menge
  (Gedaechtnisverwaltung §6.2, ADR-0053 6.4.1).
