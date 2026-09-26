### Added

- `fetch_playbook` (MCP) accepts `format="text"`: the response then carries the
  rendered procedure in `body_rendered` and leaves `content.body` — the raw
  BlockNote editor JSON — out. Both hold the same procedure, so for a client
  that only reads the text the editor copy is redundant and dominates the
  payload of a large playbook; dropping it keeps the response inside the
  runtime's result budget.

  The default `format="full"` is unchanged and still returns the editor JSON,
  so consumers that process the body structurally (editor, diff) keep it.
