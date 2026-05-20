# apps/mcp

FastMCP-Server fuer Who2Be.

Phase 0: bootbarer Server mit `ping`-Tool. Die Tools `get_persona`,
`list_playbooks` (Tag-/Trigger-Filter) und `fetch_playbook` folgen in Phase 2.
Importiert geteilte Pydantic-Models aus `packages/models/`.

## Lokal starten

```bash
uv run python -m who2be_mcp.server
```
