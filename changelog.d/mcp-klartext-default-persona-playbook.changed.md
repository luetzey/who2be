- MCP read tools `get_persona`, `fetch_agent`, `list_playbooks` and
  `fetch_playbook` now return a Markdown document by default (`format="text"`):
  a short metadata header followed by the content as plain text, without
  editor JSON and without JSON escaping. `fetch_playbook` includes the bodies
  of its sub-playbooks and inline resources, `get_persona` and `fetch_agent`
  include the persona modes. `format="full"` returns the previous structured
  response unchanged and is the template for the `update_*` tools (ADR-0056).
  **Breaking:** clients that parsed `format="text"` as JSON must switch to
  `format="full"`.
