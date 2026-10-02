- Gedaechtnis: workspace-weite Liste und Zaehler auf der Service-Ebene
  (ADR-0053 6.4.1, Paket C3c-1a). Die Liste zeigt Eintraege ueber alle Agenten
  und Status. Sie filtert nach Status, Art, Geltungsbereich, Agent, Herkunft,
  Kanal, Gesundheit (`health`), zurueckgehalten (`held`), Freitext (`q`) und
  Anlagezeitpunkt (`created_after`). Sortiert wird nach `newest` oder `oldest`
  mit Cursor-Seiten zu hoechstens 50 Eintraegen. `status=pending` ist die
  Warteschlange und zaehlt Lernvorschlaege nicht mit.

  Die Zaehler nennen die Gesamtzahl und je Gruppe (`agent`, `kind`, `status`,
  `origin`, `source`, `health`) die Anzahl je Wert, jeweils ohne den eigenen
  Filter der Gruppe. Liste und Zaehler meinen dieselbe Menge.

  Sichtbar ist ab `viewer` das eigene Nutzergedaechtnis und ab `editor`
  zusaetzlich das Agentengedaechtnis aller Agenten. Das Nutzergedaechtnis
  anderer Personen erscheint nie, auch nicht fuer `admin`. Er bekommt davon nur
  die Anzahl je Person (`group_by=subject_user_id`). Die REST-Endpunkte
  `GET /memories` und `GET /memories/counts` folgen mit C3c-1b.
