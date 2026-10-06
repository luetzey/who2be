- MCP read tools `fetch_resource`, `get_system_prompt`, `list_system_prompts`,
  `get_external_tool`, `list_external_tools`, `list_versions`, `get_version`
  and `diff_versions` now return a Markdown document by default
  (`format="text"`): a short metadata header followed by the content as plain
  text, without editor JSON. List tools return one header per entry without
  the content; `diff_versions` keeps the change paths and the readable
  before/after text but drops the raw `before`/`after` values. `format="full"`
  returns the previous structured response unchanged (ADR-0056).
  **Breaking:** clients that read these tools as JSON without passing
  `format` must pass `format="full"`; `list_versions(format="text")` now
  returns Markdown instead of versions with emptied content.
