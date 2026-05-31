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
from who2be_models import (
    AgentWithRenderedPrompt,
    PersonaRead,
    PlaybookRead,
    ResourceLinkRead,
    ResourceRead,
    TriggerOverview,
)

logger = logging.getLogger(__name__)

mcp: FastMCP = FastMCP("who2be")

_BOOTSTRAP_LOCK = asyncio.Lock()
_cached_workspace_id: UUID | None = None


class PersonaWithPlaybooks(BaseModel):
    """Eine Persona samt der mit ihr verknuepften Playbooks."""

    persona: PersonaRead
    playbooks: list[PlaybookRead]


class ResourceSummary(BaseModel):
    """Kompakte Resource-Uebersicht fuer `list_resources`."""

    id: UUID
    name: str
    block_count: int


class PlaybookWithResources(BaseModel):
    """Ein Playbook samt seiner Resource-Verweise.

    `linked_blocks` traegt alle Links als Pointer (Backward-Compat zum
    ADR-0021-Vertrag) — sowohl Block-Anker als auch Resource-Volldokument-
    Refs (`link_scope='resource'`, `block_id` None). `linked_resources`
    haelt fuer letztere zusaetzlich das vollstaendige Dokument inline,
    damit Agenten den Snippet-Fetch sparen koennen.
    """

    playbook: PlaybookRead
    linked_blocks: list[ResourceLinkRead]
    linked_resources: list[ResourceRead]


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
                raise ToolError("WHO2BE_WORKSPACE_ID ist keine gueltige UUID.") from exc
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
async def list_playbooks(tag: str | None = None, trigger: str | None = None) -> list[PlaybookRead]:
    """Listet Playbooks, optional gefiltert nach Tag und/oder Trigger."""
    client = await build_client()
    return await client.list_playbooks(tag, trigger)


@mcp.tool
@with_tool_log("list_triggers")
async def list_triggers() -> list[TriggerOverview]:
    """Welle 5: Discovery-Liste aller Trigger im Workspace mit Playbook-Verweis.

    Liefert pro Trigger-Keyword die zugehoerigen Playbooks (id + name).
    Ideal als ersten Schritt im Agent-Flow: erkenne aus einer User-Frage, ob
    ein Trigger zutrifft, bevor du `list_playbooks` oder `fetch_playbook`
    aufrufst.
    """
    client = await build_client()
    return await client.list_triggers()


@mcp.tool
@with_tool_log("fetch_playbook")
async def fetch_playbook(playbook_id: str) -> PlaybookWithResources:
    """Laedt ein Playbook per UUID samt seiner Resource-Verweise.

    `linked_blocks` enthaelt alle Verweise als Pointer (resource_id +
    block_id, Verfuegbarkeit, Section-Preview) — kein Auto-Inline fuer
    Block-Refs (ADR-0021). Fuer `link_scope='resource'`-Eintraege wird die
    Ziel-Resource zusaetzlich als Volldokument in `linked_resources`
    ausgeliefert; Block-Refs bleiben Pointer und werden bei Bedarf ueber
    `fetch_resource` nachgeladen.
    """
    try:
        parsed = UUID(playbook_id)
    except ValueError as exc:
        raise ToolError(f"Ungueltige Playbook-UUID: '{playbook_id}'.") from exc
    client = await build_client()
    playbook = await client.get_playbook(parsed)
    linked = await client.get_playbook_resource_links(parsed)
    resource_scope_ids: list[UUID] = []
    seen: set[UUID] = set()
    for link in linked:
        if link.link_scope == "resource" and link.resource_id not in seen:
            seen.add(link.resource_id)
            resource_scope_ids.append(link.resource_id)
    resources = [await client.get_resource(rid) for rid in resource_scope_ids]
    return PlaybookWithResources(
        playbook=playbook,
        linked_blocks=linked,
        linked_resources=resources,
    )


@mcp.tool
@with_tool_log("list_resources")
async def list_resources() -> list[ResourceSummary]:
    """Listet die aktiven Resources des Workspaces (id, name, block_count)."""
    client = await build_client()
    resources = await client.list_resources()
    return [
        ResourceSummary(id=r.id, name=r.name, block_count=len(r.content.blocks)) for r in resources
    ]


@mcp.tool
@with_tool_log("fetch_agent")
async def fetch_agent(agent_id: str) -> AgentWithRenderedPrompt:
    """Laedt einen Agent samt Persona + gerendertem Systemprompt (Placeholder bereits expandiert).

    Der System-Prompt wird serverseitig expandiert: alle Placeholder-Bloecke
    (Playbook, Resource, Persona-Feld, Datum) sind bereits aufgeloest und als
    Plain-Text eingebettet. MCP-Konsumenten sehen den fertigen Prompt.
    """
    try:
        parsed = UUID(agent_id)
    except ValueError as exc:
        raise ToolError(f"Ungueltige Agent-UUID: '{agent_id}'.") from exc
    client = await build_client()
    return await client.get_agent_rendered(parsed)


@mcp.tool
@with_tool_log("fetch_resource")
async def fetch_resource(resource_id: str, block_ids: list[str] | None = None) -> ResourceRead:
    """Laedt die aktive Version einer Resource (per UUID).

    Ist `block_ids` gesetzt, werden nur diese Bloecke (in angefragter
    Reihenfolge) zurueckgegeben; sonst das ganze Dokument.
    """
    try:
        parsed = UUID(resource_id)
    except ValueError as exc:
        raise ToolError(f"Ungueltige Resource-UUID: '{resource_id}'.") from exc
    client = await build_client()
    resource = await client.get_resource(parsed)
    if block_ids is not None:
        by_id = {block.id: block for block in resource.content.blocks}
        resource.content.blocks = [by_id[bid] for bid in block_ids if bid in by_id]
    return resource


def main() -> None:
    configure_logging(get_settings().log_format)
    mcp.run()


if __name__ == "__main__":
    main()
