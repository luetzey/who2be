- `GET /v1/workspaces/{workspace_id}/playbooks/{playbook_id}/rendered` accepts
  an optional `sections` query parameter (comma-separated anchors) and its
  response carries the body's outline in a new `sections` field. Without the
  parameter the rendered body is byte-identical to before. Passing the parameter
  is always a selection: an empty value selects nothing and yields an empty
  body, so a typo never silently returns the whole document.
