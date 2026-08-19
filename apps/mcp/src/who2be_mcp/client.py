"""HTTP-Client des MCP-Servers gegen die Who2Be-REST-API (ADR-0005).

Ein duenner Adapter: keine Geschaeftslogik, keine Owner-Pruefung — die liegt
in der API. Fehler werden in `ToolError` mit fuer Agenten lesbaren Meldungen
uebersetzt.
"""

import logging
from typing import Any, Literal
from uuid import UUID

import httpx
from fastmcp.exceptions import ToolError
from pydantic import BaseModel

from who2be_models import (
    AgentCopy,
    AgentCreate,
    AgentFeedbackRead,
    AgentRead,
    AgentUpdate,
    AgentWithRenderedPrompt,
    ChunkType,
    ContentChunkHit,
    ExternalToolCreate,
    ExternalToolRead,
    ExternalToolUpdate,
    ExternalToolVersionRead,
    FeedbackCreate,
    FeedbackResolutionCreate,
    FeedbackSummary,
    MemoryCreate,
    MemoryHit,
    MemoryRead,
    PersonaCreate,
    PersonaPlaybookLinkSet,
    PersonaRead,
    PersonaUpdate,
    PersonaVersionRead,
    PlaceholderCatalog,
    PlaybookCompositionLinkSet,
    PlaybookCreate,
    PlaybookRead,
    PlaybookUpdate,
    PlaybookUsage,
    PlaybookVersionRead,
    ResourceBlockAnchor,
    ResourceCreate,
    ResourceLinkRead,
    ResourceLinkSet,
    ResourceRead,
    ResourceUpdate,
    ResourceUsage,
    ResourceVersionRead,
    SearchHit,
    SearchMode,
    SearchType,
    SubResourceLinkSet,
    SubResourceRead,
    SystemFeedbackCreate,
    SystemPromptTemplateCreate,
    SystemPromptTemplateRead,
    SystemPromptTemplateUpdate,
    SystemPromptTemplateVersionRead,
    TriggerOverview,
    UsageEventCreate,
    UsageEventRead,
    VersionDiff,
    VersionTransitionRequest,
    WhoAmIRead,
    WorkspaceRead,
)

logger = logging.getLogger(__name__)

_TIMEOUT = 10.0


def problem_message(response: httpx.Response, fallback: str) -> str:
    """Fehlerantwort der API → Meldung fuer den Agenten (best-effort).

    Die API antwortet an ihren Gates mit `application/problem+json`
    (`who2be_models.ApiProblem`): `detail` erklaert den Fall in Prosa,
    `reason` ist ein STABILER Schluessel aus einem geschlossenen Vokabular
    (`convention_missing`, `rev_conflict`, `tablestore_unavailable` …), und
    `actionable_by` sagt, ob der Agent selbst nachbessern kann (`agent`), ein
    Mensch ran muss (`human`) oder die Aktion endgueltig nicht erlaubt ist
    (`none`).

    Genau dafuer wurde `reason` gebaut — „ein Agent kann darauf deterministisch
    verzweigen, ohne den `detail`-Freitext zu parsen" (`models/errors.py`).
    Bis 2026-08-17 hat der MCP-Server ihn trotzdem verworfen und nur `detail`
    weitergereicht; bei allen uebrigen Statuses (400/408/413/429/503) sogar nur
    den nackten Code. Ein Agent sah `Who2Be-API-Fehler (503)` und konnte weder
    erkennen, dass ein Retry sinnlos ist, noch warum.

    Die Reihenfolge ist bewusst: erst die Prosa (danach handelt das Modell),
    dann die Schluessel als ``key=value`` — greppbar und ohne den Lesefluss zu
    stoeren. Antworten ohne `reason` (FastAPI-`HTTPException`,
    Validierungsfehler) bleiben unveraendert; es wird nichts erfunden.
    """
    try:
        payload = response.json()
    except ValueError:
        return fallback
    if not isinstance(payload, dict):
        return fallback
    detail = payload.get("detail")
    message = detail if isinstance(detail, str) and detail else fallback
    reason = payload.get("reason")
    if not isinstance(reason, str) or not reason:
        return message
    actionable_by = payload.get("actionable_by")
    if isinstance(actionable_by, str) and actionable_by:
        return f"{message} (reason={reason}, actionable_by={actionable_by})"
    return f"{message} (reason={reason})"


# Read-only Reverse-Lookups + Versions-Historie (Track 1). Die drei Kernelemente
# teilen sich uniforme REST-Pfade (`/{plural}/{id}/versions|usages`), daher
# genuegt ein Entity-Dispatch ueber diese Maps statt 3x near-duplicate Methoden.
# `external_tool` (WP-3) haengt sich an denselben Dispatch fuer list_versions/
# get_version an — nur `diff_versions` lehnt es explizit ab (kein REST-Diff-
# Endpunkt fuer ExternalTool, siehe `diff_version` unten).
EntityType = Literal["persona", "playbook", "resource", "system_prompt", "external_tool"]
UsageEntityType = Literal["playbook", "resource"]
AnyVersionRead = (
    PersonaVersionRead
    | PlaybookVersionRead
    | ResourceVersionRead
    | SystemPromptTemplateVersionRead
    | ExternalToolVersionRead
)
AnyUsage = PlaybookUsage | ResourceUsage

_ENTITY_PLURAL: dict[str, str] = {
    "persona": "personas",
    "playbook": "playbooks",
    "resource": "resources",
    "system_prompt": "system-prompts",
    "external_tool": "external_tools",
}
_VERSION_MODEL: dict[
    str,
    type[PersonaVersionRead]
    | type[PlaybookVersionRead]
    | type[ResourceVersionRead]
    | type[SystemPromptTemplateVersionRead]
    | type[ExternalToolVersionRead],
] = {
    "persona": PersonaVersionRead,
    "playbook": PlaybookVersionRead,
    "resource": ResourceVersionRead,
    "system_prompt": SystemPromptTemplateVersionRead,
    "external_tool": ExternalToolVersionRead,
}

# entity_types ohne REST-Diff-Endpunkt (WP-1 hat fuer external_tools bewusst
# keinen `/versions/{v}/diff`-Pfad implementiert). `diff_version` lehnt diese
# sauber mit `ToolError` ab, statt den generischen 404 der API durchzureichen.
_NO_DIFF_ENDPOINT: frozenset[str] = frozenset({"external_tool"})
_USAGE_MODEL: dict[str, type[PlaybookUsage] | type[ResourceUsage]] = {
    "playbook": PlaybookUsage,
    "resource": ResourceUsage,
}


class ApiClient:
    """Liest Personae und Playbooks ueber die Who2Be-REST-API.

    `transport` ist nur fuer Tests gedacht (`httpx.MockTransport`); im Betrieb
    bleibt er `None`.
    """

    def __init__(
        self,
        base_url: str,
        token: str,
        workspace_id: UUID,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"}
        self._transport = transport
        # Vorgefertigter Pfad-Prefix — sparte uns die String-Konkatenation in
        # jeder Methode und macht Refactors auf weitere Workspace-Endpunkte trivial.
        self._workspace_prefix = f"/v1/workspaces/{workspace_id}"

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: Any = None,
    ) -> httpx.Response:
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                headers=self._headers,
                transport=self._transport,
                timeout=_TIMEOUT,
            ) as client:
                response = await client.request(method, path, params=params, json=json)
        except httpx.HTTPError as exc:
            # Nur den Exception-Typ loggen — die `str(exc)`-Repraesentation kann
            # je nach httpx-Pfad das Request-Objekt mit `Authorization`-Header
            # mitfuehren; den Token-Klartext wollen wir nirgends im Log sehen.
            logger.warning("Who2Be-API nicht erreichbar: %s", type(exc).__name__)
            raise ToolError("Who2Be-API nicht erreichbar.") from exc
        self._raise_for_status(response, path)
        return response

    def _raise_for_status(self, response: httpx.Response, path: str) -> None:
        """Uebersetzt API-Fehlerstatuses in fuer Agenten lesbare `ToolError`s."""
        if response.status_code == 401:
            raise ToolError("Nicht autorisiert — WHO2BE_API_TOKEN pruefen.")
        if response.status_code == 404:
            raise ToolError(problem_message(response, "Angefragte Ressource nicht gefunden."))
        if response.status_code == 403:
            # Das `detail` der API traegt die genaue Ursache — Rollen-Gate ODER
            # die Pro-Agent-Tool-Policy ("Dieser Agent ist nicht berechtigt …").
            # Durchreichen, damit der Agent versteht, warum das Tool gesperrt ist.
            raise ToolError(
                problem_message(
                    response,
                    "Keine Berechtigung — der API-Token braucht mindestens die editor-Rolle "
                    "(Status-Promote/Retire erfordert admin), bzw. dieser Agent darf das "
                    "Tool laut seiner Tool-Policy nicht nutzen.",
                )
            )
        if response.status_code == 409:
            raise ToolError(problem_message(response, "Konflikt mit dem aktuellen Stand."))
        if response.status_code == 422:
            raise ToolError(problem_message(response, "Ungueltige Eingabe."))
        if response.is_error:
            logger.warning("Who2Be-API-Fehler %s fuer %s", response.status_code, path)
            raise ToolError(
                problem_message(response, f"Who2Be-API-Fehler ({response.status_code}).")
            )

    async def _get(self, path: str, params: dict[str, str] | None = None) -> Any:
        response = await self._request("GET", path, params=params)
        return response.json()

    async def _write(
        self,
        method: str,
        path: str,
        body: BaseModel | None,
        params: dict[str, str] | None = None,
    ) -> Any:
        """Sendet einen mutierenden Request und gibt die JSON-Antwort zurueck.

        `body` wird via `model_dump(mode="json")` serialisiert (UUID/datetime →
        JSON-tauglich); `None` sendet einen leeren Body (z.B. Restore-Endpunkte).
        """
        payload = body.model_dump(mode="json") if body is not None else None
        response = await self._request(method, path, params=params, json=payload)
        return response.json()

    async def whoami(self) -> WhoAmIRead:
        """Laedt Identitaet + effektive Berechtigungen des aufrufenden Tokens (#253)."""
        data = await self._get(f"{self._workspace_prefix}/whoami")
        return WhoAmIRead.model_validate(data)

    async def get_workspace(self) -> WorkspaceRead:
        """Laedt die Workspace-Metadaten (u.a. `content_locale`, Plan 2026-07-24).

        Genutzt vom MCP-Write-Pfad, um bei `locale=None` auf einem Create die
        Workspace-Content-Sprache als Default aufzuloesen (`GET /v1/workspaces/
        {ws_id}` — derselbe Pfad wie `self._workspace_prefix`, Membership-Read,
        keine erhoehte Rolle noetig).
        """
        data = await self._get(self._workspace_prefix)
        return WorkspaceRead.model_validate(data)

    async def get_persona(self, identifier: str, locale: str | None = None) -> PersonaRead:
        """Laedt eine Persona per UUID oder — sonst — per Name.

        `locale` ist ein Backward-Compat-Parameter (frueher: Variantenwahl,
        ADR-0027). Bei UUID-Aufloesung wird er seit „Ein Element, eine Sprache"
        (Plan 2026-07-24) IGNORIERT (gar nicht erst mitgesendet) — die Persona
        traegt ihre Sprache selbst als `locale`-Metadatum. Bei Namens-Aufloesung
        wirkt er als optionaler Filter auf gleichnamige Personae in anderen
        Sprachen (`None` = kein Filter, alle Sprachen).
        """
        try:
            persona_id = UUID(identifier)
        except ValueError:
            return await self._resolve_persona_by_name(identifier, locale)
        data = await self._get(f"{self._workspace_prefix}/personas/{persona_id}")
        return PersonaRead.model_validate(data)

    async def _resolve_persona_by_name(self, name: str, locale: str | None = None) -> PersonaRead:
        params = {"locale": locale} if locale is not None else None
        data = await self._get(f"{self._workspace_prefix}/personas", params=params)
        for entry in data:
            persona = PersonaRead.model_validate(entry)
            if persona.name == name:
                return persona
        raise ToolError(f"Keine Persona mit Name '{name}'.")

    async def get_persona_playbooks(
        self, persona_id: UUID, locale: str | None = None
    ) -> list[PlaybookRead]:
        params = {"locale": locale} if locale is not None else None
        data = await self._get(
            f"{self._workspace_prefix}/personas/{persona_id}/playbooks",
            params=params,
        )
        return [PlaybookRead.model_validate(item) for item in data]

    async def get_persona_rendered(
        self, persona_id: UUID, locale: str | None = None, mode: str | None = None
    ) -> tuple[str, str | None]:
        """Laedt den serverseitig expandierten Persona-Profil-Body (Track F).

        Der API-Endpoint `GET .../personas/{id}/rendered` jagt den Profil-Body
        durch den Placeholder-Renderer: Katalog-Pills (`playbooks-catalog`/
        `resources-catalog`) und Slash-Refs werden fetch-time gegen die aktiven
        Playbooks/Resources des Workspace aufgeloest, plus eine Skills-Tabelle.
        Der MCP-Prozess hat keinen DB-Zugriff — das Rendering MUSS daher ueber
        diesen Endpoint laufen.

        `mode` (WP-F) reicht `?mode=` durch: der Server wendet den benannten
        Persona-Modus an (Aktiver-Modus-Sektion im Body); ein unbekannter Modus
        antwortet 422, dessen `detail` (inkl. Liste der verfuegbaren Modi) als
        `ToolError` beim Agenten landet.

        Gibt `(body_rendered, mode)` zurueck — `mode` ist der kanonische Name
        des angewendeten Modus oder `None`. Die `unresolved`-Liste ist fuer den
        Agent-Konsum nicht relevant (best-effort Expansion).
        """
        params: dict[str, str] = {}
        if locale is not None:
            params["locale"] = locale
        if mode is not None:
            params["mode"] = mode
        data = await self._get(
            f"{self._workspace_prefix}/personas/{persona_id}/rendered",
            params=params,
        )
        body = data.get("body_rendered") if isinstance(data, dict) else None
        applied = data.get("mode") if isinstance(data, dict) else None
        return (
            body if isinstance(body, str) else "",
            applied if isinstance(applied, str) else None,
        )

    async def list_playbooks(
        self, tag: str | None, trigger: str | None, locale: str | None = None
    ) -> list[PlaybookRead]:
        """`locale` ist seit „Ein Element, eine Sprache" ein optionaler Sprachfilter
        (`None` = alle Sprachen, Default)."""
        params: dict[str, str] = {}
        if tag is not None:
            params["tag"] = tag
        if trigger is not None:
            params["trigger"] = trigger
        if locale is not None:
            params["locale"] = locale
        data = await self._get(f"{self._workspace_prefix}/playbooks", params=params)
        return [PlaybookRead.model_validate(item) for item in data]

    async def list_triggers(self) -> list[TriggerOverview]:
        data = await self._get(f"{self._workspace_prefix}/playbooks/triggers")
        return [TriggerOverview.model_validate(item) for item in data]

    async def list_placeholders(self) -> PlaceholderCatalog:
        """Laedt den statischen Placeholder-Kind-Katalog (WP-A)."""
        data = await self._get(f"{self._workspace_prefix}/placeholders")
        return PlaceholderCatalog.model_validate(data)

    async def get_playbook(self, playbook_id: UUID, locale: str | None = None) -> PlaybookRead:
        params = {"locale": locale} if locale is not None else None
        data = await self._get(f"{self._workspace_prefix}/playbooks/{playbook_id}", params=params)
        return PlaybookRead.model_validate(data)

    async def list_resources(
        self, tag: str | None = None, locale: str | None = None
    ) -> list[ResourceRead]:
        """`locale` ist seit „Ein Element, eine Sprache" ein optionaler Sprachfilter
        (`None` = alle Sprachen, Default)."""
        params: dict[str, str] = {}
        if tag is not None:
            params["tag"] = tag
        if locale is not None:
            params["locale"] = locale
        data = await self._get(f"{self._workspace_prefix}/resources", params=params)
        return [ResourceRead.model_validate(item) for item in data]

    async def get_resource(self, resource_id: UUID, locale: str | None = None) -> ResourceRead:
        params = {"locale": locale} if locale is not None else None
        data = await self._get(f"{self._workspace_prefix}/resources/{resource_id}", params=params)
        return ResourceRead.model_validate(data)

    async def list_resource_blocks(
        self, resource_id: UUID, locale: str | None = None
    ) -> list[ResourceBlockAnchor]:
        """Laedt die linkbaren Heading-Anker einer Resource (WP-6).

        `locale` ist ein Backward-Compat-Parameter (frueher: Variantenwahl); die
        Resource traegt ihre Sprache seit „Ein Element, eine Sprache" selbst als
        Metadatum. Ein API-Token-Pfad sieht nur aktive Versionen.
        """
        params = {"locale": locale} if locale is not None else None
        data = await self._get(
            f"{self._workspace_prefix}/resources/{resource_id}/blocks",
            params=params,
        )
        return [ResourceBlockAnchor.model_validate(item) for item in data]

    async def get_resource_sub_resources(self, resource_id: UUID) -> list[SubResourceRead]:
        """Laedt die direkten Sub-Resources einer Resource (Track E §3.3).

        Eine Ebene, keine Expansion: jeder Eintrag traegt `fetch_call`, damit der
        Agent das Kind bei Bedarf separat nachladen kann.
        """
        data = await self._get(f"{self._workspace_prefix}/resources/{resource_id}/sub_resources")
        return [SubResourceRead.model_validate(item) for item in data]

    async def get_playbook_resource_links(self, playbook_id: UUID) -> list[ResourceLinkRead]:
        data = await self._get(f"{self._workspace_prefix}/playbooks/{playbook_id}/resource_links")
        return [ResourceLinkRead.model_validate(item) for item in data]

    async def get_playbook_composes(
        self, playbook_id: UUID, locale: str | None = None
    ) -> list[PlaybookRead]:
        """Laedt die geordneten aktiven Sub-Playbooks eines Composite (eine Ebene).

        Leere Liste wenn das Playbook kein Composite ist oder keine aktiven
        Kinder hat (API-Token-Pfad liefert nur aktive Versionen).
        """
        params = {"locale": locale} if locale is not None else None
        data = await self._get(
            f"{self._workspace_prefix}/playbooks/{playbook_id}/composes",
            params=params,
        )
        return [PlaybookRead.model_validate(item) for item in data]

    async def get_agent_rendered(self, agent_id: UUID) -> AgentWithRenderedPrompt:
        """Laedt Agent + Persona + expandierten System-Prompt vom API-Endpoint."""
        data = await self._get(f"{self._workspace_prefix}/agents/{agent_id}/rendered")
        return AgentWithRenderedPrompt.model_validate(data)

    async def list_agents(self) -> list[AgentRead]:
        """Laedt die Agenten-Konfigurationen des Workspace (eine Seite, Metadaten).

        Liefert reine `AgentRead`-Konfig (Name/Status/Persona/Template/Policy),
        keinen gerenderten Prompt. Enthaelt bewusst auch `disabled`-Agenten, damit
        ein verwaltender Agent frisch angelegte Huellen vervollstaendigen kann.
        """
        data = await self._get(f"{self._workspace_prefix}/agents")
        return [AgentRead.model_validate(item) for item in data]

    async def get_agent(self, agent_id: UUID) -> AgentRead:
        """Laedt die Konfig eines einzelnen Agenten (Metadaten, kein Render)."""
        data = await self._get(f"{self._workspace_prefix}/agents/{agent_id}")
        return AgentRead.model_validate(data)

    async def get_playbook_rendered(self, playbook_id: UUID, locale: str | None = None) -> str:
        """Laedt den serverseitig expandierten Playbook-Body (B5).

        Der API-Endpoint `GET .../playbooks/{id}/rendered` jagt den BlockNote-Body
        durch den Placeholder-Renderer (Inline-Pills → Plain-Text). Der MCP-Prozess
        hat keinen DB-Zugriff — das Rendering MUSS daher ueber diesen Endpoint laufen.

        Gibt nur den `body_rendered`-String zurueck; die `unresolved`-Liste ist fuer
        den Agent-Konsum nicht relevant (best-effort Expansion).
        """
        params = {"locale": locale} if locale is not None else None
        data = await self._get(
            f"{self._workspace_prefix}/playbooks/{playbook_id}/rendered",
            params=params,
        )
        body = data.get("body_rendered") if isinstance(data, dict) else None
        return body if isinstance(body, str) else ""

    async def list_system_prompts(
        self, locale: str | None = None
    ) -> list[SystemPromptTemplateRead]:
        """Laedt die System-Prompt-Templates des Workspace (ADR-0040).

        `locale` ist seit „Ein Element, eine Sprache" (Plan 2026-07-24) ein
        optionaler Sprachfilter (`None` = alle Sprachen, Default) — spiegelt
        `list_playbooks`/`list_resources`/`list_external_tools`.
        """
        params = {"locale": locale} if locale is not None else None
        data = await self._get(f"{self._workspace_prefix}/system-prompts", params=params)
        return [SystemPromptTemplateRead.model_validate(item) for item in data]

    async def get_system_prompt(self, template_id: UUID) -> SystemPromptTemplateRead:
        """Laedt ein einzelnes System-Prompt-Template (Konfig + aktueller Body)."""
        data = await self._get(f"{self._workspace_prefix}/system-prompts/{template_id}")
        return SystemPromptTemplateRead.model_validate(data)

    # ------------------------------------------------------------------
    # ExternalTool-Aggregat (WP-3, Blueprint `.claude/plan/2026-07-18-1315_
    # external-tools-tool-ref.md`): Faehigkeits-Bindungen an externe MCP-
    # Server/Tools, referenziert per stabilem Alias (`tool-ref`-Placeholder).
    # ------------------------------------------------------------------

    async def list_external_tools(self, locale: str | None = None) -> list[ExternalToolRead]:
        """Laedt die externen Tool-Bindungen des Workspace.

        `locale` ist seit „Ein Element, eine Sprache" ein optionaler Sprachfilter
        (`None` = alle Sprachen, Default). Kein `tag`-Filter auf REST-Ebene (WP-1
        hat keinen `?tag=`-Query-Param implementiert) — der MCP-Tool-Adapter
        (`server.list_external_tools`) filtert client-seitig nach Tag, spiegelt
        dabei aber `list_playbooks`/`list_resources`.
        """
        params = {"locale": locale} if locale is not None else None
        data = await self._get(f"{self._workspace_prefix}/external_tools", params=params)
        return [ExternalToolRead.model_validate(item) for item in data]

    async def get_external_tool(self, tool_id: UUID, locale: str | None = None) -> ExternalToolRead:
        """Laedt eine externe Tool-Bindung per UUID.

        `locale` ist ein Backward-Compat-Parameter, ohne Wirkung seit „Ein
        Element, eine Sprache" (Plan 2026-07-24) — wird bei UUID-Aufloesung
        gar nicht erst mitgesendet, die Bindung traegt ihre Sprache selbst.
        """
        data = await self._get(f"{self._workspace_prefix}/external_tools/{tool_id}")
        return ExternalToolRead.model_validate(data)

    async def resolve_external_tool(
        self, identifier: str, locale: str | None = None
    ) -> ExternalToolRead:
        """Laedt eine externe Tool-Bindung per UUID ODER — sonst — per Alias.

        Spiegelt `get_persona`s UUID-oder-Name-Aufloesung: der Alias ist die
        stabile, fuer Agenten gedachte Kennung (`external_tool.alias`,
        Migration 0065), die UUID die interne Identitaet.
        """
        try:
            tool_id = UUID(identifier)
        except ValueError:
            return await self._resolve_external_tool_by_alias(identifier, locale)
        return await self.get_external_tool(tool_id, locale)

    async def _resolve_external_tool_by_alias(
        self, alias: str, locale: str | None = None
    ) -> ExternalToolRead:
        for tool in await self.list_external_tools(locale):
            if tool.alias == alias:
                return tool
        raise ToolError(f"Kein externes Tool mit Alias '{alias}'.")

    async def create_external_tool(self, data: ExternalToolCreate) -> ExternalToolRead:
        body = await self._write("POST", f"{self._workspace_prefix}/external_tools", data)
        return ExternalToolRead.model_validate(body)

    async def update_external_tool(
        self, tool_id: UUID, data: ExternalToolUpdate
    ) -> ExternalToolRead:
        """Aktualisiert eine externe Tool-Bindung. Ein Sprachwechsel laeuft ueber
        `data.locale` (Entity-Metadatum) — kein `?locale=`-Variantenselektor mehr
        (Plan „Ein Element, eine Sprache", Status-Invarianten sind per-entity)."""
        body = await self._write(
            "PUT",
            f"{self._workspace_prefix}/external_tools/{tool_id}",
            data,
        )
        return ExternalToolRead.model_validate(body)

    async def transition_external_tool_version(
        self,
        tool_id: UUID,
        version: int,
        data: VersionTransitionRequest,
    ) -> ExternalToolVersionRead:
        body = await self._write(
            "POST",
            f"{self._workspace_prefix}/external_tools/{tool_id}/versions/{version}/transition",
            data,
        )
        return ExternalToolVersionRead.model_validate(body)

    async def restore_external_tool_version(self, tool_id: UUID, version: int) -> ExternalToolRead:
        body = await self._write(
            "POST",
            f"{self._workspace_prefix}/external_tools/{tool_id}/versions/{version}/restore",
            None,
        )
        return ExternalToolRead.model_validate(body)

    # ------------------------------------------------------------------
    # Read-only Reverse-Lookups + Versions-Historie (Track 1, erweitert
    # ADR-0030/0021). Reine Adapter ueber bestehende REST-Endpunkte; der
    # Server erzwingt Read-Scope und `status='active'` wie bei jedem Read.
    # ------------------------------------------------------------------

    async def list_usages(self, entity_type: UsageEntityType, entity_id: UUID) -> list[AnyUsage]:
        """Reverse-Lookup: welche Aggregate referenzieren dieses Element?

        `playbook` → referenzierende Personae, `resource` → referenzierende
        Playbooks. Personae haben bewusst keinen Usage-Endpunkt (Backlink ist
        `agent.persona_id`, nicht ueber MCP-Reads exponiert).
        """
        plural = _ENTITY_PLURAL[entity_type]
        data = await self._get(f"{self._workspace_prefix}/{plural}/{entity_id}/usages")
        model = _USAGE_MODEL[entity_type]
        return [model.model_validate(item) for item in data]

    async def list_versions(
        self, entity_type: EntityType, entity_id: UUID, locale: str | None = None
    ) -> list[AnyVersionRead]:
        """Listet die Versions-Snapshots eines Elements (Historie).

        `locale` ist ein Backward-Compat-Parameter (frueher: Variantenwahl),
        IGNORIERT (gar nicht erst mitgesendet) seit „Ein Element, eine Sprache"
        — die Historie gehoert zu EINEM Element. Jeder Snapshot traegt sein
        eigenes `locale`-Feld (Historienwert).
        """
        plural = _ENTITY_PLURAL[entity_type]
        model = _VERSION_MODEL[entity_type]
        data = await self._get(f"{self._workspace_prefix}/{plural}/{entity_id}/versions")
        return [model.model_validate(item) for item in data]

    async def get_version(
        self, entity_type: EntityType, entity_id: UUID, version: int, locale: str | None = None
    ) -> AnyVersionRead:
        """Laedt einen einzelnen Versions-Snapshot.

        `locale` ist ein Backward-Compat-Parameter, IGNORIERT seit „Ein Element,
        eine Sprache" — der Snapshot traegt sein eigenes `locale`-Feld.
        """
        plural = _ENTITY_PLURAL[entity_type]
        model = _VERSION_MODEL[entity_type]
        data = await self._get(f"{self._workspace_prefix}/{plural}/{entity_id}/versions/{version}")
        return model.model_validate(data)

    async def diff_version(
        self,
        entity_type: EntityType,
        entity_id: UUID,
        version: int,
        against: str = "active",
        locale: str | None = None,
    ) -> VersionDiff:
        """Strukturierter Feld-/Block-Diff von `version` gegen `against`.

        `locale` ist ein Backward-Compat-Parameter, IGNORIERT seit „Ein Element,
        eine Sprache" (beide verglichenen Staende gehoeren zum selben Element).
        """
        if entity_type in _NO_DIFF_ENDPOINT:
            raise ToolError(
                f"Diff ist fuer entity_type='{entity_type}' nicht verfuegbar "
                "(kein REST-Diff-Endpunkt)."
            )
        plural = _ENTITY_PLURAL[entity_type]
        data = await self._get(
            f"{self._workspace_prefix}/{plural}/{entity_id}/versions/{version}/diff",
            params={"against": against},
        )
        return VersionDiff.model_validate(data)

    # ------------------------------------------------------------------
    # Write-Pfad (ADR-0012). Alle Mutationen brauchen einen Token mit
    # editor-Rolle (Status-Promote/Retire: admin) — die API erzwingt das.
    # ------------------------------------------------------------------

    async def create_persona(self, data: PersonaCreate) -> PersonaRead:
        body = await self._write("POST", f"{self._workspace_prefix}/personas", data)
        return PersonaRead.model_validate(body)

    async def update_persona(self, persona_id: UUID, data: PersonaUpdate) -> PersonaRead:
        """Aktualisiert eine Persona. Ein Sprachwechsel laeuft ueber `data.locale`
        (Entity-Metadatum) — kein `?locale=`-Variantenselektor mehr (Plan „Ein
        Element, eine Sprache")."""
        body = await self._write(
            "PUT",
            f"{self._workspace_prefix}/personas/{persona_id}",
            data,
        )
        return PersonaRead.model_validate(body)

    async def transition_persona_version(
        self,
        persona_id: UUID,
        version: int,
        data: VersionTransitionRequest,
    ) -> PersonaVersionRead:
        body = await self._write(
            "POST",
            f"{self._workspace_prefix}/personas/{persona_id}/versions/{version}/transition",
            data,
        )
        return PersonaVersionRead.model_validate(body)

    async def restore_persona_version(self, persona_id: UUID, version: int) -> PersonaRead:
        body = await self._write(
            "POST",
            f"{self._workspace_prefix}/personas/{persona_id}/versions/{version}/restore",
            None,
        )
        return PersonaRead.model_validate(body)

    async def set_persona_playbooks(
        self, persona_id: UUID, data: PersonaPlaybookLinkSet
    ) -> list[PlaybookRead]:
        body = await self._write(
            "PUT", f"{self._workspace_prefix}/personas/{persona_id}/playbooks", data
        )
        return [PlaybookRead.model_validate(item) for item in body]

    async def create_playbook(self, data: PlaybookCreate) -> PlaybookRead:
        body = await self._write("POST", f"{self._workspace_prefix}/playbooks", data)
        return PlaybookRead.model_validate(body)

    async def update_playbook(self, playbook_id: UUID, data: PlaybookUpdate) -> PlaybookRead:
        """Aktualisiert ein Playbook. Ein Sprachwechsel laeuft ueber `data.locale`
        (Entity-Metadatum) — kein `?locale=`-Variantenselektor mehr (Plan „Ein
        Element, eine Sprache")."""
        body = await self._write(
            "PUT",
            f"{self._workspace_prefix}/playbooks/{playbook_id}",
            data,
        )
        return PlaybookRead.model_validate(body)

    async def transition_playbook_version(
        self,
        playbook_id: UUID,
        version: int,
        data: VersionTransitionRequest,
    ) -> PlaybookVersionRead:
        body = await self._write(
            "POST",
            f"{self._workspace_prefix}/playbooks/{playbook_id}/versions/{version}/transition",
            data,
        )
        return PlaybookVersionRead.model_validate(body)

    async def restore_playbook_version(self, playbook_id: UUID, version: int) -> PlaybookRead:
        body = await self._write(
            "POST",
            f"{self._workspace_prefix}/playbooks/{playbook_id}/versions/{version}/restore",
            None,
        )
        return PlaybookRead.model_validate(body)

    async def set_playbook_resource_links(
        self, playbook_id: UUID, data: ResourceLinkSet
    ) -> list[ResourceLinkRead]:
        body = await self._write(
            "PUT", f"{self._workspace_prefix}/playbooks/{playbook_id}/resource_links", data
        )
        return [ResourceLinkRead.model_validate(item) for item in body]

    async def set_playbook_composes(
        self, playbook_id: UUID, data: PlaybookCompositionLinkSet
    ) -> list[PlaybookRead]:
        body = await self._write(
            "PUT", f"{self._workspace_prefix}/playbooks/{playbook_id}/composes", data
        )
        return [PlaybookRead.model_validate(item) for item in body]

    async def create_resource(self, data: ResourceCreate) -> ResourceRead:
        body = await self._write("POST", f"{self._workspace_prefix}/resources", data)
        return ResourceRead.model_validate(body)

    async def update_resource(self, resource_id: UUID, data: ResourceUpdate) -> ResourceRead:
        """Aktualisiert eine Resource. Ein Sprachwechsel laeuft ueber `data.locale`
        (Entity-Metadatum) — kein `?locale=`-Variantenselektor mehr (Plan „Ein
        Element, eine Sprache")."""
        body = await self._write(
            "PUT",
            f"{self._workspace_prefix}/resources/{resource_id}",
            data,
        )
        return ResourceRead.model_validate(body)

    async def transition_resource_version(
        self,
        resource_id: UUID,
        version: int,
        data: VersionTransitionRequest,
    ) -> ResourceVersionRead:
        body = await self._write(
            "POST",
            f"{self._workspace_prefix}/resources/{resource_id}/versions/{version}/transition",
            data,
        )
        return ResourceVersionRead.model_validate(body)

    async def restore_resource_version(self, resource_id: UUID, version: int) -> ResourceRead:
        body = await self._write(
            "POST",
            f"{self._workspace_prefix}/resources/{resource_id}/versions/{version}/restore",
            None,
        )
        return ResourceRead.model_validate(body)

    async def set_resource_sub_resources(
        self, resource_id: UUID, data: SubResourceLinkSet
    ) -> list[SubResourceRead]:
        body = await self._write(
            "PUT", f"{self._workspace_prefix}/resources/{resource_id}/sub_resources", data
        )
        return [SubResourceRead.model_validate(item) for item in body]

    async def create_agent(self, data: AgentCreate) -> AgentRead:
        body = await self._write("POST", f"{self._workspace_prefix}/agents", data)
        return AgentRead.model_validate(body)

    async def update_agent(self, agent_id: UUID, data: AgentUpdate) -> AgentRead:
        body = await self._write("PUT", f"{self._workspace_prefix}/agents/{agent_id}", data)
        return AgentRead.model_validate(body)

    async def copy_agent(self, agent_id: UUID, data: AgentCopy) -> AgentRead:
        body = await self._write("POST", f"{self._workspace_prefix}/agents/{agent_id}/copy", data)
        return AgentRead.model_validate(body)

    # ------------------------------------------------------------------
    # System-Prompt-Template-Writes (ADR-0040). Verfassen + zur Review
    # einreichen braucht `system_prompt_write`; das Aktivieren (→active/
    # →inactive) bleibt fuer agent-gebundene Tokens serverseitig gesperrt.
    # ------------------------------------------------------------------

    async def create_system_prompt(
        self, data: SystemPromptTemplateCreate
    ) -> SystemPromptTemplateRead:
        body = await self._write("POST", f"{self._workspace_prefix}/system-prompts", data)
        return SystemPromptTemplateRead.model_validate(body)

    async def update_system_prompt(
        self, template_id: UUID, data: SystemPromptTemplateUpdate
    ) -> SystemPromptTemplateRead:
        body = await self._write(
            "PUT", f"{self._workspace_prefix}/system-prompts/{template_id}", data
        )
        return SystemPromptTemplateRead.model_validate(body)

    async def restore_system_prompt(
        self, template_id: UUID, version: int
    ) -> SystemPromptTemplateRead:
        body = await self._write(
            "POST",
            f"{self._workspace_prefix}/system-prompts/{template_id}/versions/{version}/restore",
            None,
        )
        return SystemPromptTemplateRead.model_validate(body)

    async def transition_system_prompt_version(
        self, template_id: UUID, version: int, data: VersionTransitionRequest
    ) -> SystemPromptTemplateVersionRead:
        body = await self._write(
            "POST",
            f"{self._workspace_prefix}/system-prompts/{template_id}/versions/{version}/transition",
            data,
        )
        return SystemPromptTemplateVersionRead.model_validate(body)

    # ------------------------------------------------------------------
    # Usage-/Feedback-Flywheel (ADR-0038). Append-only Telemetrie; verlangt
    # `feedback_write` (Default an). `get_feedback` ist editor-gated.
    # ------------------------------------------------------------------

    async def record_usage(self, data: UsageEventCreate) -> UsageEventRead:
        body = await self._write("POST", f"{self._workspace_prefix}/usage-events", data)
        return UsageEventRead.model_validate(body)

    async def submit_feedback(self, data: FeedbackCreate) -> AgentFeedbackRead:
        body = await self._write("POST", f"{self._workspace_prefix}/feedback", data)
        return AgentFeedbackRead.model_validate(body)

    async def submit_system_feedback(self, data: SystemFeedbackCreate) -> AgentFeedbackRead:
        body = await self._write("POST", f"{self._workspace_prefix}/system-feedback", data)
        return AgentFeedbackRead.model_validate(body)

    async def get_feedback(self, entity_type: str, entity_id: UUID) -> FeedbackSummary:
        data = await self._get(f"{self._workspace_prefix}/feedback/{entity_type}/{entity_id}")
        return FeedbackSummary.model_validate(data)

    async def resolve_feedback(
        self, feedback_id: UUID, data: FeedbackResolutionCreate
    ) -> AgentFeedbackRead:
        # Triage eines einzelnen Signals (append-only Resolution-Event) —
        # editor+ und fuer agent-gebundene Tokens `feedback_resolve`-gated.
        body = await self._write(
            "POST", f"{self._workspace_prefix}/feedback/{feedback_id}/resolution", data
        )
        return AgentFeedbackRead.model_validate(body)

    # ------------------------------------------------------------------
    # Agent-Memory (ADR-0044). Nur agent-gebundene Tokens; Gating ueber
    # `tool_policy.memory_mode` (off/read_only/suggest/auto) serverseitig.
    # ------------------------------------------------------------------

    async def save_memory(self, data: MemoryCreate) -> MemoryRead:
        body = await self._write("POST", f"{self._workspace_prefix}/agent-memories", data)
        return MemoryRead.model_validate(body)

    async def search_memory(self, query: str, k: int) -> list[MemoryHit]:
        data = await self._get(
            f"{self._workspace_prefix}/agent-memories/search",
            params={"query": query, "k": str(k)},
        )
        return [MemoryHit.model_validate(item) for item in data]

    async def list_memories(self, limit: int) -> list[MemoryHit]:
        data = await self._get(
            f"{self._workspace_prefix}/agent-memories", params={"limit": str(limit)}
        )
        return [MemoryHit.model_validate(item) for item in data]

    # ------------------------------------------------------------------
    # Discovery/Search (ADR-0037). Volltext ueber die aktive Version.
    # ------------------------------------------------------------------

    async def search(
        self, query: str, types: list[SearchType] | None, limit: int
    ) -> list[SearchHit]:
        params: dict[str, str] = {"q": query, "limit": str(limit)}
        if types:
            params["types"] = ",".join(types)
        data = await self._get(f"{self._workspace_prefix}/search", params=params)
        return [SearchHit.model_validate(item) for item in data]

    async def search_content(
        self, query: str, types: list[ChunkType] | None, limit: int, mode: SearchMode
    ) -> list[ContentChunkHit]:
        params: dict[str, str] = {"q": query, "limit": str(limit), "mode": mode.value}
        if types:
            params["types"] = ",".join(types)
        data = await self._get(f"{self._workspace_prefix}/search/content", params=params)
        return [ContentChunkHit.model_validate(item) for item in data]
