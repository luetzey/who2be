- Gedächtnis: REST-Endpunkte für Änderungs- und Löschvorschläge, Historie,
  Rückgängig, Bestätigen, Reaktivieren und das eigene Nutzergedächtnis
  (ADR-0053 6.4/6.4.1, Paket C3b).

  Agenten reichen Vorschläge über `POST /agent-memory-proposals` ein
  (agent-gebundener Token); der Vorschlag entsteht immer `pending` und ändert
  den Eintrag nicht. Menschen sehen Vorschläge unter
  `GET /agents/{agent_id}/memory-proposals` und workspace-weit unter
  `GET /memory-proposals` und entscheiden mit
  `POST /memory-proposals/{id}/decide`. Für das Agentengedächtnis gibt es
  `…/memories/{id}/history`, `rollback`, `confirm` und `reactivate`
  (ab `editor`), für das eigene Nutzergedächtnis dieselben Pfade unter
  `/me/memories/{id}/…` sowie `GET /me/memories`, Triage, Bearbeiten und
  Löschen (jede Rolle ab `viewer`). Alle Verwaltungs-Endpunkte sind Menschen
  vorbehalten. Das Nutzergedächtnis einer anderen Person ist über keinen
  Endpunkt sichtbar, auch nicht für `admin` — es antwortet mit
  `memory_not_found`.
