"""FastMCP server for Who2Be.

Stellt Agenten Lese-Zugriff auf Personae und Playbooks bereit. Die Tools
sind duenne Adapter: sie rufen die Who2Be-REST-API (ADR-0005) und reichen
die Modelle durch — keine Geschaeftslogik im MCP-Server.
"""

from uuid import UUID

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import BaseModel

from who2be_mcp.client import ApiClient
from who2be_mcp.config import get_settings
from who2be_mcp.core_logging import configure_logging, with_tool_log
from who2be_models import PersonaRead, PlaybookRead

mcp: FastMCP = FastMCP("who2be")


class PersonaWithPlaybooks(BaseModel):
    """Eine Persona samt der mit ihr verknuepften Playbooks."""

    persona: PersonaRead
    playbooks: list[PlaybookRead]


def build_client() -> ApiClient:
    """Baut den API-Client aus der Konfiguration."""
    settings = get_settings()
    return ApiClient(settings.api_base_url, settings.api_token)


@mcp.tool
@with_tool_log("ping")
def ping() -> str:
    """Liveness-Check fuer den Who2Be-MCP-Server."""
    return "pong"


@mcp.tool
@with_tool_log("get_persona")
async def get_persona(identifier: str) -> PersonaWithPlaybooks:
    """Laedt eine Persona (per UUID oder Name) samt verknuepfter Playbooks."""
    client = build_client()
    persona = await client.get_persona(identifier)
    playbooks = await client.get_persona_playbooks(persona.id)
    return PersonaWithPlaybooks(persona=persona, playbooks=playbooks)


@mcp.tool
@with_tool_log("list_playbooks")
async def list_playbooks(
    tag: str | None = None, trigger: str | None = None
) -> list[PlaybookRead]:
    """Listet Playbooks, optional gefiltert nach Tag und/oder Trigger."""
    return await build_client().list_playbooks(tag, trigger)


@mcp.tool
@with_tool_log("fetch_playbook")
async def fetch_playbook(playbook_id: str) -> PlaybookRead:
    """Laedt ein einzelnes Playbook per UUID."""
    try:
        parsed = UUID(playbook_id)
    except ValueError as exc:
        raise ToolError(f"Ungueltige Playbook-UUID: '{playbook_id}'.") from exc
    return await build_client().get_playbook(parsed)


def main() -> None:
    configure_logging(get_settings().log_format)
    mcp.run()


if __name__ == "__main__":
    main()
