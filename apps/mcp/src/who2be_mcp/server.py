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
    """Eine Persona samt der mit ihr verknuepften Playbooks.

    `body_rendered` traegt den serverseitig expandierten Persona-Profil-Body
    (Track F): die Katalog-Pills (`playbooks-catalog`/`resources-catalog`) und
    Slash-Refs sind fetch-time gegen die aktiven Playbooks/Resources des
    Workspace aufgeloest. Nutze `body_rendered` als gebrauchsfertigen
    Profil-Text — `persona.content` traegt weiterhin die strukturierten Felder
    (Modi, Tags) fuer die Logik.

    Skills sind derzeit deaktiviert ("Coming Soon", ADR-0026): das deskriptive
    `persona.content.skills`-Feld erscheint nicht im `body_rendered` und ist noch
    nicht nutzbar. Ein versioniertes Agent-Skill-Format folgt.
    """

    persona: PersonaRead
    playbooks: list[PlaybookRead]
    body_rendered: str = ""


class ResourceSummary(BaseModel):
    """Kompakte Resource-Uebersicht fuer `list_resources`.

    `tags` spiegelt `content.tags` der aktuellen Version (E3). Leere Liste =
    keine Tags — Backward-Compat mit Resources, die vor E3 angelegt wurden.
    """

    id: UUID
    name: str
    block_count: int
    tags: list[str] = []


class PlaybookWithResources(BaseModel):
    """Ein Playbook samt seiner Resource-Verweise und geordneter Sub-Playbooks.

    `linked_blocks` traegt alle Links als Pointer (Backward-Compat zum
    ADR-0021-Vertrag) — sowohl Block-Anker als auch Resource-Volldokument-
    Refs (`link_scope='resource'`, `block_id` None). `linked_resources`
    haelt fuer letztere zusaetzlich das vollstaendige Dokument inline,
    damit Agenten den Snippet-Fetch sparen koennen.

    `composed_playbooks` enthaelt die geordneten, aktiven Sub-Playbooks falls
    dieses Playbook ein Composite ist (ADR-0024, Gap 2.1). Nur eine Ebene wird
    inline mitgeliefert; tiefere Ebenen via erneutem `fetch_playbook(child_id)`
    nachladen. Ein Composite-Agent folgt der Reihenfolge in `composed_playbooks`
    Schritt fuer Schritt.
    """

    playbook: PlaybookRead
    linked_blocks: list[ResourceLinkRead]
    linked_resources: list[ResourceRead]
    composed_playbooks: list[PlaybookRead] = []  # geordnete, aktive Kinder
    # B5: serverseitig expandierter Body. Track B (Nur-BlockNote): die Inline-
    # Pills (playbook/resource/…) werden zu Plain-Text aufgeloest. Der Agent
    # nutzt diesen Text statt `playbook.content.body`, da letzterer nur
    # stringifiziertes BlockNote-JSON ist. Additives Feld → bricht den
    # bestehenden ADR-0021-Vertrag nicht.
    body_rendered: str = ""


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
async def get_persona(identifier: str, locale: str = "de") -> PersonaWithPlaybooks:
    """Laedt eine Persona (per UUID oder Name) samt verknuepfter Playbooks.

    `locale` waehlt die Sprachvariante des Inhalts (Default `'de'`); es werden
    weiterhin nur aktive Versionen geliefert. Liegt fuer die Persona keine
    Variante in `locale` vor, antwortet die API mit 404.

    `persona.content.modes` enthaelt ggf. die Modi einer Multi-Modus-Persona
    (Gap 3.4). Jeder Modus traegt `name`, `trigger` (Erkennungs-Keywords),
    `is_default` (Fallback ohne Trigger-Match), `identity_add` (Ergaenzung zur
    Basis-Identitaet) und `output_style_override` (Output-Stil-Anpassung).
    Fehlt das Feld oder ist es leer, ist die Persona single-mode.

    `body_rendered` traegt den fetch-time expandierten Profil-Body (Track F):
    Katalog-Pills (`playbooks-catalog`/`resources-catalog`) und Slash-Refs sind
    bereits zu Plain-Text aufgeloest. Nutze diesen Text als gebrauchsfertiges
    Persona-Briefing.

    Skills sind derzeit deaktiviert ("Coming Soon", ADR-0026) und erscheinen
    nicht im `body_rendered`.
    """
    client = await build_client()
    persona = await client.get_persona(identifier, locale)
    playbooks = await client.get_persona_playbooks(persona.id, locale)
    body_rendered = await client.get_persona_rendered(persona.id, locale)
    return PersonaWithPlaybooks(persona=persona, playbooks=playbooks, body_rendered=body_rendered)


@mcp.tool
@with_tool_log("list_playbooks")
async def list_playbooks(
    tag: str | None = None, trigger: str | None = None, locale: str = "de"
) -> list[PlaybookRead]:
    """Listet Playbooks, optional gefiltert nach Tag und/oder Trigger.

    `locale` waehlt die Sprachvariante des Inhalts (Default `'de'`); es werden
    weiterhin nur aktive Versionen geliefert.
    """
    client = await build_client()
    return await client.list_playbooks(tag, trigger, locale)


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
async def fetch_playbook(playbook_id: str, locale: str = "de") -> PlaybookWithResources:
    """Laedt ein Playbook per UUID samt seiner Resource-Verweise und Sub-Playbooks.

    `locale` waehlt die Sprachvariante von Playbook, Sub-Playbooks und inline
    mitgelieferten Resources (Default `'de'`); es werden weiterhin nur aktive
    Versionen geliefert.

    `linked_blocks` enthaelt alle Verweise als Pointer (resource_id +
    block_id, Verfuegbarkeit, Section-Preview) — kein Auto-Inline fuer
    Block-Refs (ADR-0021). Fuer `link_scope='resource'`-Eintraege wird die
    Ziel-Resource zusaetzlich als Volldokument in `linked_resources`
    ausgeliefert; Block-Refs bleiben Pointer und werden bei Bedarf ueber
    `fetch_resource` nachgeladen.

    Ist das Playbook ein Composite (`is_composite=True`), enthaelt
    `composed_playbooks` die geordneten aktiven Sub-Playbooks (nur eine Ebene,
    ADR-0024). Tiefere Ebenen per `fetch_playbook(child_id)` nachladen. Ein
    Composite-Agent folgt der Sequenz in `composed_playbooks` der Reihe nach.

    `body_rendered` traegt den serverseitig expandierten Playbook-Body (B5):
    Inline-Pills werden zu Plain-Text aufgeloest. Nutze `body_rendered` statt
    `playbook.content.body` — letzterer ist nur stringifiziertes BlockNote-JSON.
    """
    try:
        parsed = UUID(playbook_id)
    except ValueError as exc:
        raise ToolError(f"Ungueltige Playbook-UUID: '{playbook_id}'.") from exc
    client = await build_client()
    playbook = await client.get_playbook(parsed, locale)
    linked = await client.get_playbook_resource_links(parsed)
    # Nur 'resource'-scope-Links mit embedding_mode='inline' ziehen das
    # Volldokument mit; 'lazy'-Links bleiben reine Pointer in `linked_blocks`
    # (Default lazy → kleinerer Kontext, der Agent laedt via fetch_resource nach).
    inline_resource_ids: list[UUID] = []
    seen: set[UUID] = set()
    for link in linked:
        if (
            link.link_scope == "resource"
            and link.embedding_mode == "inline"
            and link.resource_id not in seen
        ):
            seen.add(link.resource_id)
            inline_resource_ids.append(link.resource_id)
    resources = [await client.get_resource(rid, locale) for rid in inline_resource_ids]
    composed = await client.get_playbook_composes(parsed, locale)
    body_rendered = await client.get_playbook_rendered(parsed, locale)
    return PlaybookWithResources(
        playbook=playbook,
        linked_blocks=linked,
        linked_resources=resources,
        composed_playbooks=composed,
        body_rendered=body_rendered,
    )


@mcp.tool
@with_tool_log("list_resources")
async def list_resources(tag: str | None = None, locale: str = "de") -> list[ResourceSummary]:
    """Listet die aktiven Resources des Workspaces, optional nach Tag gefiltert.

    `tag` filtert auf Resources, deren `content.tags` diesen Wert enthalten
    (exakter Treffer, case-sensitiv). Ohne `tag` werden alle aktiven Resources
    zurueckgegeben. `locale` waehlt die Sprachvariante (Default `'de'`).
    """
    client = await build_client()
    resources = await client.list_resources(tag, locale)
    return [
        ResourceSummary(
            id=r.id,
            name=r.name,
            block_count=len(r.content.blocks),
            tags=r.content.tags,
        )
        for r in resources
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
async def fetch_resource(
    resource_id: str, block_ids: list[str] | None = None, locale: str = "de"
) -> ResourceRead:
    """Laedt die aktive Version einer Resource (per UUID).

    `locale` waehlt die Sprachvariante der Resource und ihrer inline
    mitgelieferten Sub-Resources (Default `'de'`).

    Liefert den **eigenen** Body inline plus `sub_resources`: eine Tabelle der
    **direkten** Sub-Resources (je Eintrag: `id`, `name`, `link_scope`,
    `embedding_mode`, optional `block_id` und die fertige `fetch_call`-Anweisung
    `fetch_resource('<id>')`). Standardmaessig (`embedding_mode='lazy'`) werden
    die Kinder **nicht** expandiert — folge `fetch_call`, um eine Sub-Resource
    bei Bedarf nachzuladen (Track E §3.3).

    Sub-Resources mit `embedding_mode='inline'` (link_scope='resource') liefert
    der Server zusaetzlich als Volldokument in `inline_sub_resources` (eine
    Ebene, keine Rekursion) — der Agent spart den Nachlade-Fetch. Sie bleiben
    parallel als Pointer in `sub_resources` gelistet.

    Ist `block_ids` gesetzt, werden nur diese Bloecke (in angefragter
    Reihenfolge) des eigenen Bodys zurueckgegeben; `sub_resources` und
    `inline_sub_resources` bleiben davon unberuehrt.
    """
    try:
        parsed = UUID(resource_id)
    except ValueError as exc:
        raise ToolError(f"Ungueltige Resource-UUID: '{resource_id}'.") from exc
    client = await build_client()
    resource = await client.get_resource(parsed, locale)
    if block_ids is not None:
        by_id = {block.id: block for block in resource.content.blocks}
        resource.content.blocks = [by_id[bid] for bid in block_ids if bid in by_id]
    # Direkte Sub-Resources als Pointer-Tabelle anhaengen (keine Expansion).
    subs = await client.get_resource_sub_resources(parsed)
    resource.sub_resources = subs
    # 'inline'-Kinder zusaetzlich als Volldokument mitgeben (eine Ebene). Nur
    # 'resource'-scope kann inline sein; 'lazy' bleibt reiner Pointer.
    inline_ids: list[UUID] = []
    seen: set[UUID] = set()
    for sub in subs:
        if (
            sub.embedding_mode == "inline"
            and sub.link_scope == "resource"
            and sub.id not in seen
        ):
            seen.add(sub.id)
            inline_ids.append(sub.id)
    resource.inline_sub_resources = [
        await client.get_resource(cid, locale) for cid in inline_ids
    ]
    return resource


def main() -> None:
    configure_logging(get_settings().log_format)
    mcp.run()


if __name__ == "__main__":
    main()
