- MCP-Werkzeuge für Fälle (ADR-0053 6.5, Paket D4): `report_case` (ohne
  `subject_agent_id` über den eigenen Agenten, braucht `feedback_write`),
  `submit_case_statement` (nur der betroffene Agent), `list_cases` und
  `assign_case_elements` (beide nur mit `case_triage` in `tools/list`).
  `list_cases` antwortet standardmäßig als Markdown mit gekürzten Feldern,
  `format="full"` liefert die Fälle als JSON. Damit hat der MCP-Server
  90 Werkzeuge.
- `record_usage` über MCP verlangt jetzt `outcome` (`applied`, `skipped`
  oder `error`). Die REST-Route `POST /usage-events` bleibt unverändert.
