- API: `GET /feedback-sessions/{id}` liefert neben `session` und `measures` jetzt
  `superseded_by_id`: das jüngste Protokoll, das dieses korrigiert, sonst `null`.
  Wert und Bedeutung stimmen mit dem gleichnamigen Feld der Liste überein; beide
  kommen aus derselben SQL-Unterabfrage. Das Feld ist additiv, bestehende
  Clients bleiben unverändert lauffähig. Die Review-Ergebnis-Seite im Web liest
  den Nachfolger nun direkt aus dem Detail, statt die Liste des Agenten zu
  durchblättern. Dadurch erscheinen Banner „Ersetzt durch …“ und der Wegfall des
  Korrektur-Kopierblocks auch bei Agenten mit mehr als 1 000 Reviews richtig.
