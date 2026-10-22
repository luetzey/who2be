- Agent overview: a new "Connection" card asks where the agent is used
  (Claude, Claude Code, Cursor or VS Code, something else) and offers
  one-click install links without a token (sign-in via OAuth on first
  connect), a ready-to-copy `claude mcp add` command, a manual fallback, and a
  waiting state that recognises the first fetch from the agent's usage
  (every 5 s and on returning to the tab). The connector card moved from
  Settings → Connection into the overview; API tokens stay there. The "Copy"
  button in the agent detail header is now an outline button, so the page
  keeps a single brand action ("Connect with Claude").
