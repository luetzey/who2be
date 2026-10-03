- `GET /v1/workspaces/{ws_id}/dashboard` liefert `kpis.pending_memories` nicht
  mehr. Die Zahl enthielt das Nutzergedächtnis aller Mitglieder und die
  Lernvorschläge und ging an jede Rolle (ADR-0053 3.1.1). Die Zahl der
  Einträge zur Freigabe kommt rollengerecht aus
  `GET /v1/workspaces/{ws_id}/memories/counts`.
