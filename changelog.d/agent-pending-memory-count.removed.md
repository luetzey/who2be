- `GET /v1/workspaces/{ws_id}/agents` liefert `pending_memory_count` nicht
  mehr (auch nicht über das MCP-Tool `list_agents`). Die Zahl enthielt
  Lernvorschläge und zeigte jeder Rolle, auch viewern und agent-gebundenen
  Tokens, offenes Agentengedächtnis an (ADR-0053 6.4.1). Die Zahl der offenen
  Einträge je Agent kommt rollengerecht aus
  `GET /v1/workspaces/{ws_id}/memories/counts?status=pending&scope=agent&group_by=agent`.
