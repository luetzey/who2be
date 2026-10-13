- API: `GET /v1/workspaces/{ws}/agents/{agent_id}/dossier` liefert das Dossier
  eines Agenten zur Vorbereitung eines Feedback-Gesprächs (ADR-0053 6.6, Paket E1).
  Zugriff haben Menschen ab `editor` und Agenten mit `case_triage`. Für alle
  anderen gibt es 403, für einen fremden oder unbekannten Agenten 404
  `agent_not_found`. Das Dossier enthält:
  - offene Fälle mit Zählern je Status und den schwersten Fällen,
  - je Baustein und Version die Rohzahlen zu Nutzungen, Ergebnissen, Signalen
    und Fällen, dazu `min_uses` und `insufficient`,
  - eine Zusammenfassung des Zugriffslogs ohne Einzelzeilen und ohne Objekt-IDs,
  - frühere Maßnahmen mit Einstufung,
  - den Verlauf der Aktivierungen (`generations`, 15 je Seite, `?cursor`).

  Alle Listen sind gedeckelt und Freitexte gekürzt, weil die Antwort auch an
  Modelle geht.
