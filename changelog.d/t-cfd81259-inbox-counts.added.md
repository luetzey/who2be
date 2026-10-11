- API: `GET /v1/workspaces/{ws}/inbox/counts[?agent_id]` liefert die offenen
  Aufgaben je Art für Glocke, Dashboard und Agent-Überblick in einem Aufruf:
  fällige Nachkontrollen, Gedächtnis zur Freigabe, Versionen und
  System-Prompts zur Freigabe, nicht eingeordnete Rückmeldungen und Muster.
  Die Zahlen folgen der Rolle (viewer nur eigenes Nutzergedächtnis, Versionen
  zählen nur für admin, Muster nie) und entsprechen den Listen. `total` ist
  die Zahl an der Glocke. Nur für Menschen; keine neue Tabelle.
