- Tool profiles (ADR-0059 Q5-0): `GET /tool-profiles` now returns
  `agent_ids` (the agents using each profile) and `is_modified` (a built-in
  profile whose groups or tools differ from its shipped default). The new
  endpoint `GET /agents/{agent_id}/tool-profile/preview` returns the effective
  tool list of an agent, with profile, exceptions and permissions per tool.
  The server computes it with the same formula as the MCP filter, so clients
  do not need their own copy of the built-in profiles. Any workspace member
  can read it.
