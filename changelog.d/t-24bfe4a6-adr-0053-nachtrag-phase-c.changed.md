- ADR-0053 um den Zuschnitt von Phase C (Gedächtnis 2.0) ergänzt. Ein
  wiederholter Lernvorschlag wird auch mit abgelehnten und schon in einen
  Fall überführten Vorschlägen zusammengeführt; deren Status ändert sich
  dabei nie, die Wiederholung wird gezählt und als Event `merged` in der
  Historie vermerkt. Das Nutzergedächtnis bekommt eine Obergrenze von 500
  Einträgen je Nutzer und Workspace (gesetzte Annahme, Fehler
  `memory_cap_reached` mit `scope: 'user'`). Anhang A nennt die Pakete
  C1a bis C6 so, wie sie umgesetzt werden. Es ändert sich noch kein
  Verhalten.
