- Kopieren zählt jetzt gegen das Entity-Kontingent: `POST /personas/{id}/duplicate`,
  `POST /resources/{id}/duplicate` und `POST /agents/{id}/copy` tragen dasselbe
  `enforce_entity_quota`-Gate wie ihre Create-Geschwister.

  **Verhaltensänderung:** in der Cloud-Edition kann eine Kopier-Anfrage am
  Free-Limit jetzt mit `402` (`entity_quota_exceeded`) antworten — bisher galt
  der Deckel nur am Neu-Anlegen, obwohl eine Kopie eine echte neue
  `persona`/`resource`/`agent`-Zeile ist und damit mitzählt. Bestehende Inhalte
  bleiben unverändert les- und editierbar (Plan §3.2, kein Datenverlust);
  On-Premise/OSS ist wie bisher unbegrenzt.
