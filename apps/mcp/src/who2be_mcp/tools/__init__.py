"""Tool-Submodule des MCP-Servers (Architektur-Entscheidung 3.2, ADR-0047).

Der Bestand bleibt in `server.py`; neue Domains registrieren ihre Tools als
`tools/<domain>.py` mit einer `register(mcp: FastMCP) -> None`-Funktion, die
`server.py` an EINER Stelle aufruft. Muster (WP8 legt es fest):

- Die Tool-Funktionen sind modulweite async-Funktionen, dekoriert nur mit
  `@with_tool_log("<name>")` — dadurch bleiben sie fuer Tests direkt
  importier- und aufrufbar (Test-Muster A: Funktion + httpx.MockTransport +
  monkeypatch von `server.build_client`).
- `register` haengt sie per `mcp.tool(output_schema=None)(fn)` an den Server
  (`output_schema=None` ist Pflicht — Payload-Budget, siehe server.py).
- API-Aufrufe liegen im Schwester-Modul `clients/<domain>.py`; jedes Tool
  braucht einen Eintrag in `who2be_models.tool_requirements` und in
  `services/placeholders/resolvers/tools.py::_TOOLS`.
"""
