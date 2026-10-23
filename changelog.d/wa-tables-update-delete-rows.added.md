- New MCP tools `update_rows` and `delete_rows` (and the REST routes
  `POST /wa-tables/{id}/rows/update` and `.../rows/delete`) correct or remove
  rows of a WorkArea table.

  Rows are selected by an equality `match` (column -> value, AND, schema
  columns only; an empty `match` is rejected). At most 100 rows per call; an
  optional `expected_count` aborts with 409 when the hit count differs.
  Nothing is changed on 409. A changed dedupe column recomputes the dedupe
  hash; a changed match column re-runs the category rules. The category
  column itself cannot be set. Same gates as `insert_rows`
  (`workarea_write`). The MCP catalog now has 103 tools (ADR-0049, addendum
  2026-10-23).
