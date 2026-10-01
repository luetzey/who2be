- Mandantentrennung ist jetzt ein CI-Gate für jede REST-Route und jedes MCP-Tool.

  `test_tenant_isolation_api.py` ruft jede Route und `test_tenant_isolation_mcp.py`
  jedes MCP-Tool als Mandant A mit Objekt-IDs von Mandant B auf. Geprüft werden
  Abweisung (403/404), kein Datenleck in der Antwort, kein Existenz-Orakel
  (fremde IDs wie unbekannte), kein Schreibzugriff bei B (Zeilen-Fingerabdruck)
  und eine Gegenprobe mit eigenen IDs. Neue Routen oder Tools ohne Eintrag
  machen den Test rot. Ersetzt die manuelle IDOR-Stichprobe (ADR-0055 §7).
