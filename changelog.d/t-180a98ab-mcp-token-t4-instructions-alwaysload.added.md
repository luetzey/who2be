- Der MCP-Server liefert jetzt Server-`instructions` mit der
  Boot-Reihenfolge (`whoami`, `get_persona`, `search_memory`, Playbooks) und
  den Regeln, die für viele Werkzeuge gelten. `whoami`, `get_persona`,
  `search`, `search_memory` und `record_usage` tragen
  `_meta["anthropic/alwaysLoad"]`, Claude Code lädt sie mit Tool Search also
  sofort. `python -m who2be_mcp.payload_report` zeigt dazu je Profil, was
  beim Start sofort geladen wird. Tests halten die Reihenfolge von
  `tools/list` stabil. Messung und Regeln: `docs/mcp-payload-budget.md`.
