"""FastMCP server for Who2Be.

Stellt Agenten Lese-Zugriff auf Personae und Playbooks bereit. Die Tools
sind duenne Adapter: sie rufen die Who2Be-REST-API (ADR-0005) und reichen
die Modelle durch — keine Geschaeftslogik im MCP-Server.

Phase 2.1a-2: Beim ersten Tool-Call wird die Workspace-ID des Tokens via
`GET /v1/me` resolved und fuer den Server-Lifetime gecached; alternativ ueber
`WHO2BE_WORKSPACE_ID` explizit gesetzt. Pfade folgen
`/v1/workspaces/{workspace_id}/...`.
"""

import asyncio
import logging
from uuid import UUID

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import BaseModel

from who2be_mcp.client import ApiClient
from who2be_mcp.config import Settings, get_settings
from who2be_mcp.core_logging import configure_logging, with_tool_log
from who2be_models import PersonaRead, PlaybookRead

logger = logging.getLogger(__name__)

mcp: FastMCP = FastMCP("who2be")

_BOOTSTRAP_LOCK = asyncio.Lock()
_cached_workspace_id: UUID | None = None


class PersonaWithPlaybooks(BaseModel):
    """Eine Persona samt der mit ihr verknuepften Playbooks."""

    persona: PersonaRead
    playbooks: list[PlaybookRead]


async def _resolve_workspace_id(settings: Settings) -> UUID:
    """Resolved die Default-Workspace-ID ueber `GET /v1/me`.

    Cached fuer Server-Lifetime — die WS-Mitgliedschaft eines Tokens kann
    sich ohnehin nicht aendern (Token sind workspace-gepinnt).
    """
    global _cached_workspace_id
    if _cached_workspace_id is not None:
        return _cached_workspace_id
    async with _BOOTSTRAP_LOCK:
        if _cached_workspace_id is not None:
            return _cached_workspace_id
        if settings.workspace_id:
            try:
                _cached_workspace_id = UUID(settings.workspace_id)
            except ValueError as exc:
                raise ToolError(
                    "WHO2BE_WORKSPACE_ID ist keine gueltige UUID."
                ) from exc
            return _cached_workspace_id
        try:
            async with httpx.AsyncClient(
                base_url=settings.api_base_url.rstrip("/"),
                headers={"Authorization": f"Bearer {settings.api_token}"},
                timeout=10.0,
            ) as client:
                response = await client.get("/v1/me")
        except httpx.HTTPError as exc:
            logger.warning("Who2Be-/v1/me nicht erreichbar: %s", type(exc).__name__)
            raise ToolError("Who2Be-API nicht erreichbar.") from exc
        if response.status_code == 401:
            raise ToolError("Nicht autorisiert — WHO2BE_API_TOKEN pruefen.")
        if response.is_error:
            raise ToolError(f"Who2Be-API-Fehler ({response.status_code}).")
        data = response.json()
        ws_id = data.get("default_workspace_id")
        if not isinstance(ws_id, str):
            raise ToolError("Token hat keinen Default-Workspace.")
        _cached_workspace_id = UUID(ws_id)
        return _cached_workspace_id


async def build_client() -> ApiClient:
    """Baut den API-Client aus der Konfiguration (inkl. Workspace-Resolution)."""
    settings = get_settings()
    workspace_id = await _resolve_workspace_id(settings)
    return ApiClient(settings.api_base_url, settings.api_token, workspace_id)


@mcp.tool
@with_tool_log("ping")
def ping() -> str:
    """Liveness-Check fuer den Who2Be-MCP-Server."""
    return "pong"


@mcp.tool
@with_tool_log("get_persona")
async def get_persona(identifier: str) -> PersonaWithPlaybooks:
    """Laedt eine Persona (per UUID oder Name) samt verknuepfter Playbooks."""
    client = await build_client()
    persona = await client.get_persona(identifier)
    playbooks = await client.get_persona_playbooks(persona.id)
    return PersonaWithPlaybooks(persona=persona, playbooks=playbooks)


@mcp.tool
@with_tool_log("list_playbooks")
async def list_playbooks(
    tag: str | None = None, trigger: str | None = None
) -> list[PlaybookRead]:
    """Listet Playbooks, optional gefiltert nach Tag und/oder Trigger."""
    client = await build_client()
    return await client.list_playbooks(tag, trigger)


@mcp.tool
@with_tool_log("fetch_playbook")
async def fetch_playbook(playbook_id: str) -> PlaybookRead:
    """Laedt ein einzelnes Playbook per UUID."""
    try:
        parsed = UUID(playbook_id)
    except ValueError as exc:
        raise ToolError(f"Ungueltige Playbook-UUID: '{playbook_id}'.") from exc
    client = await build_client()
    return await client.get_playbook(parsed)


def main() -> None:
    configure_logging(get_settings().log_format)
    mcp.run()


if __name__ == "__main__":
    main()
