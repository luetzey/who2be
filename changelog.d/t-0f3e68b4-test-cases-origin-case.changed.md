- `GET /v1/workspaces/{workspace_id}/test-cases` nimmt den Filter
  `origin_case_id` an und liefert dann nur die Prüffälle, die aus diesem Fall
  abgeleitet wurden. Der Filter lässt sich mit `agent_id`, `entity_type`,
  `entity_id` und `status` kombinieren, die Rechte bleiben unverändert. Eine
  Fall-ID aus einem anderen Workspace liefert eine leere Liste. Der Web-Client
  reicht den Filter über `TestCaseFilters.origin_case_id` durch.
