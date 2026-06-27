"""FastMCP server for Who2Be.

Stellt Agenten Lese-Zugriff auf Personae und Playbooks bereit. Die Tools
sind duenne Adapter: sie rufen die Who2Be-REST-API (ADR-0005) und reichen
die Modelle durch — keine Geschaeftslogik im MCP-Server.

Phase 2.1a-2: Beim ersten Tool-Call wird die Workspace-ID des Tokens via
`GET /v1/me` resolved und fuer den Server-Lifetime gecached; alternativ ueber
`WHO2BE_WORKSPACE_ID` explizit gesetzt. Pfade folgen
`/v1/workspaces/{workspace_id}/...`.
"""

import hashlib
import logging
import time
from collections import OrderedDict
from uuid import UUID

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_http_headers
from pydantic import BaseModel

from who2be_mcp.client import (
    AnyUsage,
    AnyVersionRead,
    ApiClient,
    EntityType,
    UsageEntityType,
)
from who2be_mcp.config import Settings, get_settings
from who2be_mcp.core_logging import configure_logging, with_tool_log
from who2be_models import (
    TRANSITION_RULE_DOC,
    AgentCopy,
    AgentCreate,
    AgentFeedbackRead,
    AgentRead,
    AgentUpdate,
    AgentWithRenderedPrompt,
    FeedbackCreate,
    FeedbackSummary,
    FeedbackTarget,
    PersonaCreate,
    PersonaPlaybookLinkSet,
    PersonaRead,
    PersonaUpdate,
    PersonaVersionRead,
    PlaybookCompositionLinkSet,
    PlaybookCreate,
    PlaybookRead,
    PlaybookUpdate,
    PlaybookVersionRead,
    ResourceBlockAnchor,
    ResourceCreate,
    ResourceLinkRead,
    ResourceLinkSet,
    ResourceRead,
    ResourceUpdate,
    ResourceVersionRead,
    SubResourceLinkSet,
    SubResourceRead,
    SystemPromptTemplateCreate,
    SystemPromptTemplateRead,
    SystemPromptTemplateUpdate,
    SystemPromptTemplateVersionRead,
    TriggerOverview,
    UsageEventCreate,
    UsageEventRead,
    VersionDiff,
    VersionStatus,
    VersionTransitionRequest,
    WhoAmIRead,
)

logger = logging.getLogger(__name__)

mcp: FastMCP = FastMCP("who2be")

# Workspace-Resolution wird PRO TOKEN gecacht (Streamable-HTTP ist multi-tenant:
# jeder Request traegt seinen eigenen Bearer, ADR-0034). Key ist der sha256-Hash
# des Tokens (defense-in-depth: kein Klartext-Token als Dict-Key), Wert ist
# (workspace_id, Ablauf-Monotonic). LRU-Schranke + TTL halten den Cache in einem
# langlebigen HTTP-Server beschraenkt und vermeiden stale WS-Aufloesung.
_WS_CACHE_MAX = 512
_WS_CACHE_TTL_SECONDS = 300.0
_workspace_cache: OrderedDict[str, tuple[UUID, float]] = OrderedDict()


def _token_key(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _ws_cache_get(token: str) -> UUID | None:
    key = _token_key(token)
    entry = _workspace_cache.get(key)
    if entry is None:
        return None
    workspace_id, expires_at = entry
    if time.monotonic() >= expires_at:
        _workspace_cache.pop(key, None)
        return None
    _workspace_cache.move_to_end(key)
    return workspace_id


def _ws_cache_put(token: str, workspace_id: UUID) -> None:
    key = _token_key(token)
    _workspace_cache[key] = (workspace_id, time.monotonic() + _WS_CACHE_TTL_SECONDS)
    _workspace_cache.move_to_end(key)
    while len(_workspace_cache) > _WS_CACHE_MAX:
        _workspace_cache.popitem(last=False)


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


def _request_token(settings: Settings) -> str:
    """Der fuer DIESEN Aufruf gueltige API-Token.

    HTTP-Transport (ADR-0034): ausschliesslich der vom Client mitgeschickte
    `Authorization: Bearer`-Header — jede MCP-Session ist ihr eigener,
    serverseitig gescopter Token/Agent (Multi-Tenant). Fehlt der Bearer oder ist
    er leer/ungueltig, wird HART abgelehnt — KEIN Rueckfall auf den statischen
    Env-Token, sonst agierte ein Caller mit kaputtem Header als der privilegierte
    Server-Token (Privilege-Konfusion).

    Wichtig: FastMCP filtert `authorization` per Default aus `get_http_headers()`
    heraus — der Header muss explizit via `include` angefordert werden.

    stdio (kein HTTP-Kontext): der statische `WHO2BE_API_TOKEN` aus der Env.
    """
    if settings.transport == "http":
        headers = get_http_headers(include={"authorization"})
        auth = headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[len("bearer ") :].strip()
            if token:
                return token
        raise ToolError("Nicht autorisiert — Authorization: Bearer-Header fehlt oder ist leer.")
    return settings.api_token


async def _resolve_workspace_id(settings: Settings, token: str) -> UUID:
    """Resolved die Default-Workspace-ID eines Tokens ueber `GET /v1/me`.

    Pro Token gecacht (LRU + TTL) — die WS-Mitgliedschaft eines Tokens ist stabil
    (Token sind workspace-gepinnt), die TTL deckt rotierte/revozierte Tokens ab.
    Ein explizit gepinnter `WHO2BE_WORKSPACE_ID` ueberschreibt die Resolution
    (stdio/Single-Tenant). Kein globaler Lock: paralleler Erst-Resolve desselben
    Tokens fuehrt hoechstens zu einem doppelten, idempotenten `/v1/me`-Aufruf.
    """
    if settings.workspace_id:
        try:
            return UUID(settings.workspace_id)
        except ValueError as exc:
            raise ToolError("WHO2BE_WORKSPACE_ID ist keine gueltige UUID.") from exc
    cached = _ws_cache_get(token)
    if cached is not None:
        return cached
    try:
        async with httpx.AsyncClient(
            base_url=settings.api_base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0,
        ) as client:
            response = await client.get("/v1/me")
    except httpx.HTTPError as exc:
        logger.warning("Who2Be-/v1/me nicht erreichbar: %s", type(exc).__name__)
        raise ToolError("Who2Be-API nicht erreichbar.") from exc
    if response.status_code == 401:
        raise ToolError("Nicht autorisiert — API-Token pruefen.")
    if response.is_error:
        raise ToolError(f"Who2Be-API-Fehler ({response.status_code}).")
    data = response.json()
    ws_id = data.get("default_workspace_id")
    if not isinstance(ws_id, str):
        raise ToolError("Token hat keinen Default-Workspace.")
    resolved = UUID(ws_id)
    _ws_cache_put(token, resolved)
    return resolved


async def build_client() -> ApiClient:
    """Baut den API-Client fuer den aktuellen Aufruf (Token + Workspace)."""
    settings = get_settings()
    token = _request_token(settings)
    if not token:
        # Nur erreichbar im stdio-Pfad mit leerem WHO2BE_API_TOKEN.
        raise ToolError("Kein API-Token — WHO2BE_API_TOKEN ist nicht gesetzt.")
    workspace_id = await _resolve_workspace_id(settings, token)
    return ApiClient(settings.api_base_url, token, workspace_id)


def _parse_uuid(value: str, label: str) -> UUID:
    """Parst eine UUID oder wirft einen fuer Agenten lesbaren `ToolError`."""
    try:
        return UUID(value)
    except ValueError as exc:
        raise ToolError(f"Ungueltige {label}-UUID: '{value}'.") from exc


@mcp.tool
@with_tool_log("ping")
def ping() -> str:
    """Liveness-Check fuer den Who2Be-MCP-Server.

    Bewusst auth-frei (kein API-Aufruf): bestaetigt nur, dass der MCP-Server
    erreichbar ist. Fuer *wer bin ich und was darf ich* (Identitaet, Rolle,
    Agent-Bindung, gewaehrte Capabilities, Read-Scopes, Entitlement-Features)
    nutze stattdessen `whoami` — das den Token gegen die API aufloest.
    """
    return "pong"


@mcp.tool
@with_tool_log("whoami")
async def whoami() -> WhoAmIRead:
    """Identitaet + effektive Berechtigungen des aktuellen API-Tokens (#253).

    Loest den Bearer-Token gegen die API auf und liefert, wer du bist und was du
    darfst — ohne Raten: `role`, `is_api_token`, `agent_id` (null wenn der Token
    nicht an einen Agenten gebunden ist), die gewaehrten Write-`capabilities`,
    die `read_scopes` je Domain und die org-weiten `features` (Entitlement).

    Wichtig — `unrestricted`: bei einem Menschen/JWT oder einem ungebundenen
    Token ist `unrestricted=True` und `capabilities`/`read_scopes` sind `null`.
    Das heisst **"keine Pro-Agent-Restriktion"**, NICHT "nichts erlaubt": es
    greift dann allein das Rollen-Gate. Nur ein agent-gebundener Token traegt
    eine konkrete Policy (`unrestricted=False`) mit aufgelisteten Capabilities.

    Wer eine Write-Capability haelt, sieht ueber die Lese-Tools zudem die
    Current-Version inkl. Draft/Review der betreffenden Domain (nicht nur
    `active`) — so erscheint z. B. eine frisch via `create_*` angelegte Draft
    sofort im eigenen `fetch_*`.
    """
    client = await build_client()
    return await client.whoami()


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

    Hinweis: Ein agent-gebundener Token darf ueber dieses Tool nur den EIGENEN
    Agenten rendern (fremde UUID => „nicht gefunden"). Fuer die Konfig anderer
    Agenten — etwa direkt nach `create_agent` — nimm `get_agent`/`list_agents`.
    """
    try:
        parsed = UUID(agent_id)
    except ValueError as exc:
        raise ToolError(f"Ungueltige Agent-UUID: '{agent_id}'.") from exc
    client = await build_client()
    return await client.get_agent_rendered(parsed)


@mcp.tool
@with_tool_log("list_agents")
async def list_agents() -> list[AgentRead]:
    """Listet die Agenten-Konfigurationen des Workspace (Metadaten, kein Prompt).

    Liefert Name, Status, verknuepfte Persona/Template und die Tool-Policy jedes
    Agenten — inklusive `disabled`-Agenten. Damit findest du bestehende Agenten
    und kannst sie per `get_agent`/`update_agent` weiterbearbeiten. Den fertig
    gerenderten Systemprompt liefert nur `fetch_agent` (und nur fuer dich selbst).
    """
    client = await build_client()
    return await client.list_agents()


@mcp.tool
@with_tool_log("get_agent")
async def get_agent(agent_id: str) -> AgentRead:
    """Laedt die Konfig eines Agenten anhand seiner UUID (Metadaten, kein Render).

    Der richtige Read nach `create_agent`/`copy_agent`, um den frisch angelegten
    Agenten zu pruefen und zu vervollstaendigen. Gibt `AgentRead` zurueck
    (Persona/Template/Status/Policy/activatable) — fuer den expandierten
    Systemprompt siehe `fetch_agent` (self-only).
    """
    parsed = _parse_uuid(agent_id, "Agent")
    client = await build_client()
    return await client.get_agent(parsed)


@mcp.tool
@with_tool_log("fetch_resource")
async def fetch_resource(
    resource_id: str, block_ids: list[str] | None = None, locale: str = "de"
) -> ResourceRead:
    """Laedt eine Resource (per UUID) in ihrer fuer dich sichtbaren Version.

    Welche Version du siehst, haengt von deiner Berechtigung ab (`sees_drafts`):
    Wer die `resource_write`-Capability haelt (Mensch/Editor-Agent), bekommt die
    **Current-Version inkl. Draft/Review** — eine frisch via `create_resource`
    angelegte Draft erscheint also sofort hier. Reine Konsum-Tokens (kein
    `resource_write`) sehen weiterhin nur die **aktive** Version; existiert keine
    aktive, antwortet die API mit 404. Pruefe deine Capabilities via `whoami`.

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
        if sub.embedding_mode == "inline" and sub.link_scope == "resource" and sub.id not in seen:
            seen.add(sub.id)
            inline_ids.append(sub.id)
    resource.inline_sub_resources = [await client.get_resource(cid, locale) for cid in inline_ids]
    return resource


@mcp.tool
@with_tool_log("list_resource_blocks")
async def list_resource_blocks(resource_id: str, locale: str = "de") -> list[ResourceBlockAnchor]:
    """Listet die linkbaren Heading-Anker einer Resource (WP-6).

    Jeder Eintrag traegt `block_id` (stabile BlockNote-ID), `level`
    (Heading-Ebene, 1 = h1) und `text` (Heading-Klartext). Nur Heading-Bloecke
    sind verlinkbar (ADR-0021, Heading-Only-Anker). Nutze die `block_id`, um
    beim Setzen von Playbook-Resource-Links (`set_playbook_resource_links`) bzw.
    Sub-Resource-Links einen `link_scope='block'`-Anker zu referenzieren — so
    musst du keine Block-ID aus dem Volldokument raten.

    `locale` waehlt die Sprachvariante (Default `'de'`); es werden nur Anker der
    aktiven Resource-Version geliefert.
    """
    try:
        parsed = UUID(resource_id)
    except ValueError as exc:
        raise ToolError(f"Ungueltige Resource-UUID: '{resource_id}'.") from exc
    client = await build_client()
    return await client.list_resource_blocks(parsed, locale)


@mcp.tool
@with_tool_log("list_system_prompts")
async def list_system_prompts() -> list[SystemPromptTemplateRead]:
    """Listet die System-Prompt-Templates des Workspace (ADR-0040).

    Jedes Template ist das versionierte Aggregat hinter `agent.system_prompt_
    template_id`. Nutze das, um ein bestehendes Template fuer `create_agent`/
    `update_agent` auszuwaehlen oder vor dem Anpassen zu finden. Den vollen Body
    einer Version liefert `get_system_prompt` bzw. `get_version`.
    """
    client = await build_client()
    return await client.list_system_prompts()


@mcp.tool
@with_tool_log("get_system_prompt")
async def get_system_prompt(template_id: str) -> SystemPromptTemplateRead:
    """Laedt ein System-Prompt-Template (Konfig + Body der sichtbaren Version).

    Der richtige Read nach `create_system_prompt`/`update_system_prompt` und vor
    dem Editieren. Versions-Historie + Diff laufen ueber `list_versions`/
    `diff_versions` mit `entity_type='system_prompt'`.
    """
    parsed = _parse_uuid(template_id, "system_prompt")
    client = await build_client()
    return await client.get_system_prompt(parsed)


# ---------------------------------------------------------------------------
# Read-only Reverse-Lookups + Versions-Historie (Track 1, erweitert ADR-0030/
# 0021). Duenne Adapter ueber bestehende REST-Endpunkte — kein neuer
# Backend-Code. Read-Scope und `status='active'`-Sichtbarkeit erzwingt die API.
# ---------------------------------------------------------------------------


@mcp.tool
@with_tool_log("find_usages")
async def find_usages(entity_type: UsageEntityType, entity_id: str) -> list[AnyUsage]:
    """Reverse-Lookup: welche Aggregate referenzieren dieses Element?

    `entity_type='playbook'` listet die Personae, die das Playbook verknuepfen;
    `entity_type='resource'` die Playbooks, die Bloecke der Resource referenzieren
    (je mit `block_count`). Nutze das, um den Impact zu verstehen, BEVOR du ein
    Element aenderst oder retirest — referenzierende Aggregate brechen sonst.

    Personae haben bewusst keinen Usage-Lookup (ihr Backlink ist die
    Agent-Zuordnung, nicht ueber MCP-Reads exponiert).
    """
    parsed = _parse_uuid(entity_id, entity_type)
    client = await build_client()
    return await client.list_usages(entity_type, parsed)


@mcp.tool
@with_tool_log("list_versions")
async def list_versions(
    entity_type: EntityType, entity_id: str, locale: str = "de"
) -> list[AnyVersionRead]:
    """Listet die Versions-Historie eines Persona-/Playbook-/Resource-Elements.

    Jeder Eintrag traegt `version`, `status` (draft/review/active/inactive),
    `content`, `created_by` und `created_at`. Reine Konsum-Tokens sehen nur
    aktive Versionen; ein Token mit der passenden `*_write`-Capability sieht auch
    Draft/Review. `locale` waehlt die Sprachvariante (Default `'de'`).
    """
    parsed = _parse_uuid(entity_id, entity_type)
    client = await build_client()
    return await client.list_versions(entity_type, parsed, locale)


@mcp.tool
@with_tool_log("get_version")
async def get_version(
    entity_type: EntityType, entity_id: str, version: int, locale: str = "de"
) -> AnyVersionRead:
    """Laedt einen einzelnen, unveraenderlichen Versions-Snapshot.

    `entity_type` ∈ {persona, playbook, resource}, `version` ist die
    Versionsnummer (1-basiert). Liefert den vollstaendigen Content-Snapshot
    dieser Version. `locale` waehlt die Sprachvariante (Default `'de'`).
    """
    parsed = _parse_uuid(entity_id, entity_type)
    client = await build_client()
    return await client.get_version(entity_type, parsed, version, locale)


@mcp.tool
@with_tool_log("diff_versions")
async def diff_versions(
    entity_type: EntityType,
    entity_id: str,
    version: int,
    against: str = "active",
    locale: str = "de",
) -> VersionDiff:
    """Strukturierter Feld-/Block-Diff einer Version gegen einen Vergleichsstand.

    `version` ist die betrachtete Version, `against` der Vergleich (Default
    `'active'` = die aktive Version; sonst eine Versionsnummer als String). Die
    `changes`-Liste nennt pro Aenderung `path`, `op` (added/removed/changed) und
    before/after. Nutze das, um einen Draft vor dem Promote selbst zu reviewen.
    `locale` waehlt die Sprachvariante (Default `'de'`).
    """
    parsed = _parse_uuid(entity_id, entity_type)
    client = await build_client()
    return await client.diff_version(entity_type, parsed, version, against, locale)


# ---------------------------------------------------------------------------
# Write-Tools (ADR-0012). Verlangen einen API-Token mit editor-Rolle;
# Status-Promote (draft→active) und Retire (active→inactive) brauchen admin.
# Versionsmodell: PUT auf eine aktive Version legt eine neue Draft an (409,
# falls bereits ein Draft existiert). Reads (MCP get_*/fetch_*) sehen nur
# aktive Versionen — eine neu erstellte/bearbeitete Entitaet wird erst nach
# `transition(..., to='active')` fuer Agenten sichtbar.
# ---------------------------------------------------------------------------


@mcp.tool
@with_tool_log("create_persona")
async def create_persona(data: PersonaCreate) -> PersonaRead:
    """Legt eine neue Persona an (initiale Draft-Version 1).

    `data.content` traegt die strukturierten Felder (Beschreibung, Traits,
    Tags, Modi, Profil-Bloecke). Die Persona ist nach dem Anlegen `draft` und
    fuer MCP-Reads noch unsichtbar — erst `transition_persona(..., to='active')`
    schaltet sie scharf.
    """
    client = await build_client()
    return await client.create_persona(data)


@mcp.tool
@with_tool_log("update_persona")
async def update_persona(persona_id: str, data: PersonaUpdate, locale: str = "de") -> PersonaRead:
    """Aktualisiert eine Persona (versioniert). PUT auf eine aktive Version legt
    eine neue Draft an; 409, falls bereits ein Draft existiert (dann den Draft
    weiterbearbeiten und neu transitionieren). `locale` waehlt die Variante.
    """
    client = await build_client()
    return await client.update_persona(_parse_uuid(persona_id, "Persona"), data, locale)


@mcp.tool(
    description=(
        f"Schaltet eine Persona-Version in einen neuen Status. {TRANSITION_RULE_DOC} "
        "`note` landet in der Status-Historie."
    )
)
@with_tool_log("transition_persona")
async def transition_persona(
    persona_id: str, version: int, to: VersionStatus, note: str | None = None, locale: str = "de"
) -> PersonaVersionRead:
    """Schaltet eine Persona-Version in einen neuen Status.

    Tool-`description` wird via `description=` aus `TRANSITION_RULE_DOC` gesetzt
    (SSoT, WP-5/#257), da f-String-Docstrings nicht in `__doc__` landen.
    """
    client = await build_client()
    return await client.transition_persona_version(
        _parse_uuid(persona_id, "Persona"),
        version,
        VersionTransitionRequest(to=to, note=note),
        locale,
    )


@mcp.tool
@with_tool_log("restore_persona")
async def restore_persona(persona_id: str, version: int, locale: str = "de") -> PersonaRead:
    """Stellt eine aeltere Persona-Version als neue Draft wieder her (non-destruktiv)."""
    client = await build_client()
    return await client.restore_persona_version(_parse_uuid(persona_id, "Persona"), version, locale)


@mcp.tool
@with_tool_log("set_persona_playbooks")
async def set_persona_playbooks(persona_id: str, playbook_ids: list[str]) -> list[PlaybookRead]:
    """Setzt die mit einer Persona verknuepften Playbooks (Set-Replace-Semantik).

    `playbook_ids` ersetzt die bestehende Verknuepfungs-Liste vollstaendig —
    eine leere Liste loest alle Verknuepfungen.
    """
    parsed = [_parse_uuid(pid, "Playbook") for pid in playbook_ids]
    client = await build_client()
    return await client.set_persona_playbooks(
        _parse_uuid(persona_id, "Persona"), PersonaPlaybookLinkSet(playbook_ids=parsed)
    )


@mcp.tool
@with_tool_log("create_playbook")
async def create_playbook(data: PlaybookCreate) -> PlaybookRead:
    """Legt ein neues Playbook an (initiale Draft-Version 1).

    `data.content.body` ist BlockNote-Markup (oder Plain-Text); `type`, `tags`
    und `triggers` steuern Auffindbarkeit. Erst nach `transition_playbook(...,
    to='active')` fuer MCP-Reads sichtbar.
    """
    client = await build_client()
    return await client.create_playbook(data)


@mcp.tool
@with_tool_log("update_playbook")
async def update_playbook(
    playbook_id: str, data: PlaybookUpdate, locale: str = "de"
) -> PlaybookRead:
    """Aktualisiert ein Playbook (versioniert; PUT auf aktiv → neue Draft, 409 bei
    bestehendem Draft)."""
    client = await build_client()
    return await client.update_playbook(_parse_uuid(playbook_id, "Playbook"), data, locale)


@mcp.tool(
    description=(
        f"Schaltet eine Playbook-Version in einen neuen Status. {TRANSITION_RULE_DOC} "
        "`note` landet in der Status-Historie."
    )
)
@with_tool_log("transition_playbook")
async def transition_playbook(
    playbook_id: str, version: int, to: VersionStatus, note: str | None = None, locale: str = "de"
) -> PlaybookVersionRead:
    """Schaltet eine Playbook-Version in einen neuen Status.

    Tool-`description` wird via `description=` aus `TRANSITION_RULE_DOC` gesetzt
    (SSoT, WP-5/#257), da f-String-Docstrings nicht in `__doc__` landen.
    """
    client = await build_client()
    return await client.transition_playbook_version(
        _parse_uuid(playbook_id, "Playbook"),
        version,
        VersionTransitionRequest(to=to, note=note),
        locale,
    )


@mcp.tool
@with_tool_log("restore_playbook")
async def restore_playbook(playbook_id: str, version: int, locale: str = "de") -> PlaybookRead:
    """Stellt eine aeltere Playbook-Version als neue Draft wieder her (non-destruktiv)."""
    client = await build_client()
    return await client.restore_playbook_version(
        _parse_uuid(playbook_id, "Playbook"), version, locale
    )


@mcp.tool
@with_tool_log("set_playbook_resource_links")
async def set_playbook_resource_links(
    playbook_id: str, links: ResourceLinkSet
) -> list[ResourceLinkRead]:
    """Setzt die Resource-Verweise eines Playbooks (Set-Replace-Semantik).

    Jeder Link traegt `resource_id`, optional `block_id` (Block-Anker),
    `position`, `link_scope` ('resource'|'block') und `embedding_mode`
    ('lazy'|'inline'). Die Liste ersetzt die bestehenden Links vollstaendig.
    """
    client = await build_client()
    return await client.set_playbook_resource_links(_parse_uuid(playbook_id, "Playbook"), links)


@mcp.tool
@with_tool_log("set_playbook_composes")
async def set_playbook_composes(playbook_id: str, child_ids: list[str]) -> list[PlaybookRead]:
    """Setzt die geordneten Sub-Playbooks eines Composite (Set-Replace-Semantik).

    `child_ids` ist die geordnete Sequenz der Kind-Playbooks (ADR-0024). Eine
    leere Liste macht das Playbook wieder zu einem Nicht-Composite.

    Die Kinder duerfen hier noch Drafts sein — das Verketten prueft keinen
    Kind-Status. Die Aktiv-Invariante greift erst beim Promote des Eltern-
    Composite: `transition_playbook(parent, ..., to='active')` schlaegt mit 409
    fehl, solange ein referenziertes Sub-Playbook keine aktive Version hat
    (WP-4 / #256). Aktiviere die Kinder also vor dem Promote des Composite.
    """
    parsed = [_parse_uuid(cid, "Playbook") for cid in child_ids]
    client = await build_client()
    return await client.set_playbook_composes(
        _parse_uuid(playbook_id, "Playbook"), PlaybookCompositionLinkSet(child_ids=parsed)
    )


@mcp.tool
@with_tool_log("create_resource")
async def create_resource(data: ResourceCreate) -> ResourceRead:
    """Legt eine neue Resource an (BlockNote-Dokument, initiale Draft-Version 1).

    `data.content.blocks` ist die BlockNote-Block-Liste; `tags` steuert die
    Auffindbarkeit. Erst nach `transition_resource(..., to='active')` sichtbar.
    """
    client = await build_client()
    return await client.create_resource(data)


@mcp.tool
@with_tool_log("update_resource")
async def update_resource(
    resource_id: str, data: ResourceUpdate, locale: str = "de"
) -> ResourceRead:
    """Aktualisiert eine Resource (versioniert; PUT auf aktiv → neue Draft, 409 bei
    bestehendem Draft)."""
    client = await build_client()
    return await client.update_resource(_parse_uuid(resource_id, "Resource"), data, locale)


@mcp.tool(
    description=(
        f"Schaltet eine Resource-Version in einen neuen Status. {TRANSITION_RULE_DOC} "
        "`note` landet in der Status-Historie."
    )
)
@with_tool_log("transition_resource")
async def transition_resource(
    resource_id: str, version: int, to: VersionStatus, note: str | None = None, locale: str = "de"
) -> ResourceVersionRead:
    """Schaltet eine Resource-Version in einen neuen Status.

    Tool-`description` wird via `description=` aus `TRANSITION_RULE_DOC` gesetzt
    (SSoT, WP-5/#257), da f-String-Docstrings nicht in `__doc__` landen.
    """
    client = await build_client()
    return await client.transition_resource_version(
        _parse_uuid(resource_id, "Resource"),
        version,
        VersionTransitionRequest(to=to, note=note),
        locale,
    )


@mcp.tool
@with_tool_log("restore_resource")
async def restore_resource(resource_id: str, version: int, locale: str = "de") -> ResourceRead:
    """Stellt eine aeltere Resource-Version als neue Draft wieder her (non-destruktiv)."""
    client = await build_client()
    return await client.restore_resource_version(
        _parse_uuid(resource_id, "Resource"), version, locale
    )


@mcp.tool
@with_tool_log("set_resource_sub_resources")
async def set_resource_sub_resources(
    resource_id: str, links: SubResourceLinkSet
) -> list[SubResourceRead]:
    """Setzt die geordneten Sub-Resources einer Resource (Set-Replace-Semantik).

    Jeder Link traegt `child_id`, optional `block_id`, `position`, `link_scope`
    ('resource'|'block') und `embedding_mode` ('lazy'|'inline'). Ersetzt die
    bestehenden Sub-Resource-Links vollstaendig.
    """
    client = await build_client()
    return await client.set_resource_sub_resources(_parse_uuid(resource_id, "Resource"), links)


@mcp.tool
@with_tool_log("create_agent")
async def create_agent(data: AgentCreate) -> AgentRead:
    """Legt einen neuen Agent an (Persona + System-Prompt-Template).

    Ein Agent ist erst aktivierbar (`activatable`), wenn Persona und Template
    gesetzt sind UND die Persona eine aktive Version hat. `status` startet auf
    `disabled`, falls nicht gesetzt.
    """
    client = await build_client()
    return await client.create_agent(data)


@mcp.tool
@with_tool_log("update_agent")
async def update_agent(agent_id: str, data: AgentUpdate) -> AgentRead:
    """Aktualisiert einen Agent (Name, Beschreibung, Persona, Template, Status).

    Nur gesetzte Felder werden geaendert; `None`-Felder bleiben unveraendert.
    """
    client = await build_client()
    return await client.update_agent(_parse_uuid(agent_id, "Agent"), data)


@mcp.tool
@with_tool_log("copy_agent")
async def copy_agent(agent_id: str, name: str | None = None) -> AgentRead:
    """Dupliziert einen Agent unter neuem Namen (Default: '<Name> (Kopie)').

    409, falls der Quell-Agent nicht aktivierbar ist (Persona/Template fehlt
    oder Persona ohne aktive Version) — eine solche Kopie waere nicht einsetzbar.
    """
    client = await build_client()
    return await client.copy_agent(_parse_uuid(agent_id, "Agent"), AgentCopy(name=name))


# ---------------------------------------------------------------------------
# System-Prompt-Template-Writes (ADR-0040). Verlangen `system_prompt_write`.
# Verfassen (create/update/restore) + draft→review sind erlaubt; das Aktivieren
# (→active/→inactive) lehnt die API fuer agent-gebundene Tokens hart ab — der
# eigene System-Prompt wird von einem Menschen/Admin scharfgeschaltet.
# ---------------------------------------------------------------------------


@mcp.tool
@with_tool_log("create_system_prompt")
async def create_system_prompt(data: SystemPromptTemplateCreate) -> SystemPromptTemplateRead:
    """Legt ein neues System-Prompt-Template an (initiale Draft-Version).

    Der Body traegt Liquid-Style-Placeholder (z. B. `{{persona:profile}}`,
    `{{playbook:...}}`, `{{tools-overview}}`), die beim Agent-Rendern expandiert
    werden. Setze die neue Template-UUID anschliessend via `update_agent` als
    `system_prompt_template_id`. Das Scharfschalten uebernimmt ein Mensch/Admin.
    """
    client = await build_client()
    return await client.create_system_prompt(data)


@mcp.tool
@with_tool_log("update_system_prompt")
async def update_system_prompt(
    template_id: str, data: SystemPromptTemplateUpdate
) -> SystemPromptTemplateRead:
    """Aendert ein System-Prompt-Template als neuen Draft (Draft-on-Edit bei Active).

    Auf einer aktiven Version legt das einen neuen Draft an (409, falls bereits
    ein Draft offen ist). Die aktive Version bleibt unveraendert, bis ein
    Mensch/Admin den Draft promotet.
    """
    client = await build_client()
    return await client.update_system_prompt(_parse_uuid(template_id, "system_prompt"), data)


@mcp.tool
@with_tool_log("restore_system_prompt")
async def restore_system_prompt(template_id: str, version: int) -> SystemPromptTemplateRead:
    """Stellt eine fruehere Template-Version als neuen Draft wieder her (non-destruktiv)."""
    client = await build_client()
    return await client.restore_system_prompt(_parse_uuid(template_id, "system_prompt"), version)


@mcp.tool
@with_tool_log("transition_system_prompt")
async def transition_system_prompt(
    template_id: str, version: int, data: VersionTransitionRequest
) -> SystemPromptTemplateVersionRead:
    """Schaltet eine Template-Version weiter — fuer Agenten nur draft→review.

    Ein agent-gebundener Token darf einen Draft `to='review'` zur Freigabe
    einreichen; ein Uebergang nach `active`/`inactive` wird serverseitig hart
    abgelehnt (403, ADR-0040) — das Aktivieren bleibt eine menschliche Handlung.
    """
    client = await build_client()
    return await client.transition_system_prompt_version(
        _parse_uuid(template_id, "system_prompt"), version, data
    )


# ---------------------------------------------------------------------------
# Usage-/Feedback-Flywheel (ADR-0038). Append-only Telemetrie, mit der ein Agent
# zurueckmeldet, was er genutzt hat und wie gut es war — macht die AgentDB
# selbst-verbessernd. Verlangt `feedback_write` (Default an); fliesst NIE in
# einen gerenderten System-Prompt (kein Injection-Vektor).
# ---------------------------------------------------------------------------


@mcp.tool
@with_tool_log("record_usage")
async def record_usage(data: UsageEventCreate) -> UsageEventRead:
    """Meldet, dass du ein Element genutzt hast (append-only Telemetrie).

    `entity_type` ∈ {persona, playbook, resource}, `entity_id` das genutzte
    Element, optional `version` und `outcome` ∈ {applied, skipped, error}. Nutze
    das nach jedem Einsatz eines Playbooks/einer Resource — die Aggregate
    speisen die Kurations-Sicht (welche Inhalte wirklich helfen).
    """
    client = await build_client()
    return await client.record_usage(data)


@mcp.tool
@with_tool_log("submit_feedback")
async def submit_feedback(data: FeedbackCreate) -> AgentFeedbackRead:
    """Gibt qualitatives Feedback zu einem Element (Vorschlag, kein Auto-Edit).

    `signal` ∈ {helpful, outdated, incorrect, unclear} + optionale `note`. Melde
    so veraltete/fehlerhafte Inhalte, statt sie selbst umzuschreiben — ein
    Kurator/Mensch entscheidet ueber die Pflege. Feedback aktiviert oder aendert
    nie Inhalte.
    """
    client = await build_client()
    return await client.submit_feedback(data)


@mcp.tool
@with_tool_log("get_feedback")
async def get_feedback(entity_type: FeedbackTarget, entity_id: str) -> FeedbackSummary:
    """Liest das Feedback-Aggregat eines Elements (Kurations-Sicht, editor+).

    Liefert `usage_count`, `by_outcome`/`by_signal`-Zaehler und die juengsten
    Notizen — die Grundlage, um zu entscheiden, was gepflegt, gemerged oder
    retired gehoert.
    """
    parsed = _parse_uuid(entity_id, entity_type)
    client = await build_client()
    return await client.get_feedback(entity_type, parsed)


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_format)
    if settings.transport == "http":
        # Streamable-HTTP (MCP-Spec 2025-03-26). OAuth-Resource-Server (ADR-0034-
        # Folge): FastMCP introspectiert jeden Bearer (`Who2BeTokenVerifier`) vor
        # dem Tool-Run und serviert RFC-9728-PRM + 401/`WWW-Authenticate`, sodass
        # Remote-MCP-Clients (Claude/ChatGPT) sich per OAuth-Login verbinden.
        from who2be_mcp.auth import build_auth_provider

        mcp.auth = build_auth_provider(settings)
        mcp.run(
            transport="http",
            host=settings.http_host,
            port=settings.http_port,
            path=settings.http_path,
        )
        return
    mcp.run()


if __name__ == "__main__":
    main()
