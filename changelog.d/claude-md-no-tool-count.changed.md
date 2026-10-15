- `CLAUDE.md` no longer states the number of MCP tools; `README.md` and
  `ROADMAP.md` remain the only places that name it, and the drift guard in
  `packages/models/tests/test_doc_tool_count.py` checks only those two. Only
  the owner edits `CLAUDE.md`, so every new tool family used to require an
  owner round-trip just to bump a number. A new test fails if a tool count
  ("N Tools gesamt") reappears in `CLAUDE.md`.
