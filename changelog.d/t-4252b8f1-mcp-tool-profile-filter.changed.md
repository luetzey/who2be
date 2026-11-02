- The MCP server now applies an agent's tool profile on top of its rights
  (ADR-0059 Q3). `tools/list` hides the tools the agent's profile leaves out;
  the core tools `ping`, `whoami` and `report_problem` always stay, and rights
  still win, so a profile can only hide tools, never reveal one. Calling a tool
  that only the profile hides returns a message that names the profile and
  points to `report_problem` with `category="tool_request"`; a tool hidden by
  rights keeps the existing message. Without a `tool_profile` in `whoami`
  nothing changes, and resolution failures still fall open.
- Rights and profile changes now reach a connected agent within 60 seconds
  instead of five minutes (whoami cache TTL 300 s -> 60 s). The server
  instructions mention the tool profile and the `tool_request` reporting path.
- The managed Builder with the "Builder" profile starts at 94,218 bytes instead
  of 110,085 (−14.4 %); the payload budget test holds a 104,000-byte target for
  it and `payload_report` prints the effect.
