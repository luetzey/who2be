"""FastMCP server for Who2Be.

Phase 0: bootbarer Server mit einem `ping`-Tool als Rauchtest.
Die eigentlichen Tools (`get_persona`, `list_playbooks`, `fetch_playbook`)
folgen in Phase 2, sobald API und Datenmodell stehen.
"""

from fastmcp import FastMCP

mcp: FastMCP = FastMCP("who2be")


@mcp.tool
def ping() -> str:
    """Liveness-Check fuer den Who2Be-MCP-Server."""
    return "pong"


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
