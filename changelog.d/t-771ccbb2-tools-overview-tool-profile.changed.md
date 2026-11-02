- The `tools-overview` block of an agent's system prompt now honours the
  agent's tool profile (ADR-0059 Q4). It lists only tools that rights AND
  profile allow — the same formula the MCP filter applies to `tools/list` —
  so the prompt never names a tool the agent cannot see. Entries the profile
  allows only partly show just the allowed tools; descriptions and notes that
  name a hidden tool are left out. Agents on "All" render as before.
