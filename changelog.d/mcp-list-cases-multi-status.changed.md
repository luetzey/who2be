- The MCP tool `list_cases` now takes `status` as a single value **or a list**,
  matching `GET /cases`. A list goes out as a repeated query parameter
  (`?status=open&status=triaged&…`), so all open cases of a pattern
  (`open`, `triaged`, `in_progress`, `reopened`) come back in one call instead
  of one call per status. A single value works as before; an empty list
  applies no status filter.
