- `DELETE /v1/workspaces/{workspace_id}` antwortet jetzt mit `409`
  (`reason: concurrent_conflict`) statt mit `500`, wenn ein Agent des
  Workspaces Einträge im Zugriffsprotokoll hat.

  Das Zugriffsprotokoll ist append-only und überlebt Agenten bewusst
  (ADR-0047). Der Workspace-Delete entfernt zuerst die Agenten und lief deshalb
  auf dieselbe Sperre wie der Agent-Delete; er bekommt jetzt dieselbe Antwort.
  In diesem Fall wird nichts gelöscht — Workspace, Agenten und Protokoll
  bleiben vollständig. Workspaces ohne protokollierte Zugriffe lassen sich
  weiterhin löschen.
