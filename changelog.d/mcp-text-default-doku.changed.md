- The tool overview in rendered system prompts (`tools-overview`) and the
  `persona-ref` briefing now describe the Markdown default of the MCP read
  tools: modes are found under `## Modi` in the `get_persona` response, and the
  structured `content.modes` is only available with `format="full"`. The MCP
  documentation
  (`docs/mcp-payload-budget.md`, `docs/mcp-claude-code.md`,
  `docs/agent-axes.md`) reflects `format="text"` as the default (ADR-0056).
