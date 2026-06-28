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
    DEFAULT_LOCALE,
    AgentCopy,
    AgentCreate,
    AgentFeedbackRead,
    AgentRead,
    AgentUpdate,
    AgentWithRenderedPrompt,
    FeedbackCreate,
    FeedbackSummary,
    PersonaCreate,
    PersonaPlaybookLinkSet,
    PersonaRead,
    PersonaUpdate,
    PersonaVersionRead,
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
)

logger = logging.getLogger(__name__)

_TIMEOUT = 10.0

# Read-only Reverse-Lookups + Versions-Historie (Track 1). Die drei Kernelemente
# teilen sich uniforme REST-Pfade (`/{plural}/{id}/versions|usages`), daher
# genuegt ein Entity-Dispatch ueber diese Maps statt 3x near-duplicate Methoden.
EntityType = Literal["persona", "playbook", "resource", "system_prompt"]
UsageEntityType = Literal["playbook", "resource"]
AnyVersionRead = (
    PersonaVersionRead | PlaybookVersionRead | ResourceVersionRead | SystemPromptTemplateVersionRead
)
AnyUsage = PlaybookUsage | ResourceUsage

_ENTITY_PLURAL: dict[str, str] = {
    "persona": "personas",
    "playbook": "playbooks",
    "resource": "resources",
    "system_prompt": "system-prompts",
}
_VERSION_MODEL: dict[
    str,
    type[PersonaVersionRead]
    | type[PlaybookVersionRead]
    | type[ResourceVersionRead]
    | type[SystemPromptTemplateVersionRead],
] = {
    "persona": PersonaVersionRead,
    "playbook": PlaybookVersionRead,
    "resource": ResourceVersionRead,
    "system_prompt": SystemPromptTemplateVersionRead,
}
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
        if response.status_code == 404:
            raise ToolError("Angefragte Ressource nicht gefunden.")
        if response.status_code == 401:
            raise ToolError("Nicht autorisiert — WHO2BE_API_TOKEN pruefen.")
        if response.status_code == 403:
            # Das `detail` der API traegt die genaue Ursache — Rollen-Gate ODER
            # die Pro-Agent-Tool-Policy ("Dieser Agent ist nicht berechtigt …").
            # Durchreichen, damit der Agent versteht, warum das Tool gesperrt ist.
            raise ToolError(
                self._detail(
                    response,
                    "Keine Berechtigung — der API-Token braucht mindestens die editor-Rolle "
                    "(Status-Promote/Retire erfordert admin), bzw. dieser Agent darf das "
                    "Tool laut seiner Tool-Policy nicht nutzen.",
                )
            )
        if response.status_code == 409:
            raise ToolError(self._detail(response, "Konflikt mit dem aktuellen Stand."))
        if response.status_code == 422:
            raise ToolError(self._detail(response, "Ungueltige Eingabe."))
        if response.is_error:
            logger.warning("Who2Be-API-Fehler %s fuer %s", response.status_code, path)
            raise ToolError(f"Who2Be-API-Fehler ({response.status_code}).")

    @staticmethod
    def _detail(response: httpx.Response, fallback: str) -> str:
        """Extrahiert das `detail`-Feld der API-Fehlerantwort (best-effort).

        409/422 tragen oft eine sprechende `detail`-Meldung (z.B. "Es existiert
        bereits ein Draft") — die reichen wir an den Agenten durch. Listen-Details
        (422-Validation) bleiben generisch.
        """
        try:
            payload = response.json()
        except ValueError:
            return fallback
        detail = payload.get("detail") if isinstance(payload, dict) else None
        return detail if isinstance(detail, str) and detail else fallback

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

    async def get_persona(self, identifier: str, locale: str = DEFAULT_LOCALE) -> PersonaRead:
        """Laedt eine Persona per UUID oder — sonst — per Name (in `locale`)."""
        try:
            persona_id = UUID(identifier)
        except ValueError:
            return await self._resolve_persona_by_name(identifier, locale)
        data = await self._get(
            f"{self._workspace_prefix}/personas/{persona_id}", params={"locale": locale}
        )
        return PersonaRead.model_validate(data)

    async def _resolve_persona_by_name(
        self, name: str, locale: str = DEFAULT_LOCALE
    ) -> PersonaRead:
        data = await self._get(f"{self._workspace_prefix}/personas", params={"locale": locale})
        for entry in data:
            persona = PersonaRead.model_validate(entry)
            if persona.name == name:
                return persona
        raise ToolError(f"Keine Persona mit Name '{name}'.")

    async def get_persona_playbooks(
        self, persona_id: UUID, locale: str = DEFAULT_LOCALE
    ) -> list[PlaybookRead]:
        data = await self._get(
            f"{self._workspace_prefix}/personas/{persona_id}/playbooks",
            params={"locale": locale},
        )
        return [PlaybookRead.model_validate(item) for item in data]

    async def get_persona_rendered(self, persona_id: UUID, locale: str = DEFAULT_LOCALE) -> str:
        """Laedt den serverseitig expandierten Persona-Profil-Body (Track F).

        Der API-Endpoint `GET .../personas/{id}/rendered` jagt den Profil-Body
        durch den Placeholder-Renderer: Katalog-Pills (`playbooks-catalog`/
        `resources-catalog`) und Slash-Refs werden fetch-time gegen die aktiven
        Playbooks/Resources des Workspace aufgeloest, plus eine Skills-Tabelle.
        Der MCP-Prozess hat keinen DB-Zugriff — das Rendering MUSS daher ueber
        diesen Endpoint laufen.

        Gibt nur den `body_rendered`-String zurueck; die `unresolved`-Liste ist
        fuer den Agent-Konsum nicht relevant (best-effort Expansion).
        """
        data = await self._get(
            f"{self._workspace_prefix}/personas/{persona_id}/rendered",
            params={"locale": locale},
        )
        body = data.get("body_rendered") if isinstance(data, dict) else None
        return body if isinstance(body, str) else ""

    async def list_playbooks(
        self, tag: str | None, trigger: str | None, locale: str = DEFAULT_LOCALE
    ) -> list[PlaybookRead]:
        params: dict[str, str] = {"locale": locale}
        if tag is not None:
            params["tag"] = tag
        if trigger is not None:
            params["trigger"] = trigger
        data = await self._get(f"{self._workspace_prefix}/playbooks", params=params)
        return [PlaybookRead.model_validate(item) for item in data]

    async def list_triggers(self) -> list[TriggerOverview]:
        data = await self._get(f"{self._workspace_prefix}/playbooks/triggers")
        return [TriggerOverview.model_validate(item) for item in data]

    async def get_playbook(self, playbook_id: UUID, locale: str = DEFAULT_LOCALE) -> PlaybookRead:
        data = await self._get(
            f"{self._workspace_prefix}/playbooks/{playbook_id}", params={"locale": locale}
        )
        return PlaybookRead.model_validate(data)

    async def list_resources(
        self, tag: str | None = None, locale: str = DEFAULT_LOCALE
    ) -> list[ResourceRead]:
        params: dict[str, str] = {"locale": locale}
        if tag is not None:
            params["tag"] = tag
        data = await self._get(f"{self._workspace_prefix}/resources", params=params)
        return [ResourceRead.model_validate(item) for item in data]

    async def get_resource(self, resource_id: UUID, locale: str = DEFAULT_LOCALE) -> ResourceRead:
        data = await self._get(
            f"{self._workspace_prefix}/resources/{resource_id}", params={"locale": locale}
        )
        return ResourceRead.model_validate(data)

    async def list_resource_blocks(
        self, resource_id: UUID, locale: str = DEFAULT_LOCALE
    ) -> list[ResourceBlockAnchor]:
        """Laedt die linkbaren Heading-Anker einer Resource (WP-6).

        `locale` waehlt die Sprachvariante (Default `'de'`); ein API-Token-Pfad
        sieht nur aktive Versionen.
        """
        data = await self._get(
            f"{self._workspace_prefix}/resources/{resource_id}/blocks",
            params={"locale": locale},
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
        self, playbook_id: UUID, locale: str = DEFAULT_LOCALE
    ) -> list[PlaybookRead]:
        """Laedt die geordneten aktiven Sub-Playbooks eines Composite (eine Ebene).

        Leere Liste wenn das Playbook kein Composite ist oder keine aktiven
        Kinder hat (API-Token-Pfad liefert nur aktive Versionen).
        """
        data = await self._get(
            f"{self._workspace_prefix}/playbooks/{playbook_id}/composes",
            params={"locale": locale},
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

    async def get_playbook_rendered(self, playbook_id: UUID, locale: str = DEFAULT_LOCALE) -> str:
        """Laedt den serverseitig expandierten Playbook-Body (B5).

        Der API-Endpoint `GET .../playbooks/{id}/rendered` jagt den BlockNote-Body
        durch den Placeholder-Renderer (Inline-Pills → Plain-Text). Der MCP-Prozess
        hat keinen DB-Zugriff — das Rendering MUSS daher ueber diesen Endpoint laufen.

        Gibt nur den `body_rendered`-String zurueck; die `unresolved`-Liste ist fuer
        den Agent-Konsum nicht relevant (best-effort Expansion).
        """
        data = await self._get(
            f"{self._workspace_prefix}/playbooks/{playbook_id}/rendered",
            params={"locale": locale},
        )
        body = data.get("body_rendered") if isinstance(data, dict) else None
        return body if isinstance(body, str) else ""

    async def list_system_prompts(self) -> list[SystemPromptTemplateRead]:
        """Laedt die System-Prompt-Templates des Workspace (ADR-0040)."""
        data = await self._get(f"{self._workspace_prefix}/system-prompts")
        return [SystemPromptTemplateRead.model_validate(item) for item in data]

    async def get_system_prompt(self, template_id: UUID) -> SystemPromptTemplateRead:
        """Laedt ein einzelnes System-Prompt-Template (Konfig + aktueller Body)."""
        data = await self._get(f"{self._workspace_prefix}/system-prompts/{template_id}")
        return SystemPromptTemplateRead.model_validate(data)

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
        self, entity_type: EntityType, entity_id: UUID, locale: str = DEFAULT_LOCALE
    ) -> list[AnyVersionRead]:
        """Listet die Versions-Snapshots eines Elements (Historie)."""
        plural = _ENTITY_PLURAL[entity_type]
        model = _VERSION_MODEL[entity_type]
        data = await self._get(
            f"{self._workspace_prefix}/{plural}/{entity_id}/versions",
            params={"locale": locale},
        )
        return [model.model_validate(item) for item in data]

    async def get_version(
        self, entity_type: EntityType, entity_id: UUID, version: int, locale: str = DEFAULT_LOCALE
    ) -> AnyVersionRead:
        """Laedt einen einzelnen Versions-Snapshot."""
        plural = _ENTITY_PLURAL[entity_type]
        model = _VERSION_MODEL[entity_type]
        data = await self._get(
            f"{self._workspace_prefix}/{plural}/{entity_id}/versions/{version}",
            params={"locale": locale},
        )
        return model.model_validate(data)

    async def diff_version(
        self,
        entity_type: EntityType,
        entity_id: UUID,
        version: int,
        against: str = "active",
        locale: str = DEFAULT_LOCALE,
    ) -> VersionDiff:
        """Strukturierter Feld-/Block-Diff von `version` gegen `against`."""
        plural = _ENTITY_PLURAL[entity_type]
        data = await self._get(
            f"{self._workspace_prefix}/{plural}/{entity_id}/versions/{version}/diff",
            params={"locale": locale, "against": against},
        )
        return VersionDiff.model_validate(data)

    # ------------------------------------------------------------------
    # Write-Pfad (ADR-0012). Alle Mutationen brauchen einen Token mit
    # editor-Rolle (Status-Promote/Retire: admin) — die API erzwingt das.
    # ------------------------------------------------------------------

    async def create_persona(self, data: PersonaCreate) -> PersonaRead:
        body = await self._write("POST", f"{self._workspace_prefix}/personas", data)
        return PersonaRead.model_validate(body)

    async def update_persona(
        self, persona_id: UUID, data: PersonaUpdate, locale: str = DEFAULT_LOCALE
    ) -> PersonaRead:
        body = await self._write(
            "PUT",
            f"{self._workspace_prefix}/personas/{persona_id}",
            data,
            params={"locale": locale},
        )
        return PersonaRead.model_validate(body)

    async def transition_persona_version(
        self,
        persona_id: UUID,
        version: int,
        data: VersionTransitionRequest,
        locale: str = DEFAULT_LOCALE,
    ) -> PersonaVersionRead:
        body = await self._write(
            "POST",
            f"{self._workspace_prefix}/personas/{persona_id}/versions/{version}/transition",
            data,
            params={"locale": locale},
        )
        return PersonaVersionRead.model_validate(body)

    async def restore_persona_version(
        self, persona_id: UUID, version: int, locale: str = DEFAULT_LOCALE
    ) -> PersonaRead:
        body = await self._write(
            "POST",
            f"{self._workspace_prefix}/personas/{persona_id}/versions/{version}/restore",
            None,
            params={"locale": locale},
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

    async def update_playbook(
        self, playbook_id: UUID, data: PlaybookUpdate, locale: str = DEFAULT_LOCALE
    ) -> PlaybookRead:
        body = await self._write(
            "PUT",
            f"{self._workspace_prefix}/playbooks/{playbook_id}",
            data,
            params={"locale": locale},
        )
        return PlaybookRead.model_validate(body)

    async def transition_playbook_version(
        self,
        playbook_id: UUID,
        version: int,
        data: VersionTransitionRequest,
        locale: str = DEFAULT_LOCALE,
    ) -> PlaybookVersionRead:
        body = await self._write(
            "POST",
            f"{self._workspace_prefix}/playbooks/{playbook_id}/versions/{version}/transition",
            data,
            params={"locale": locale},
        )
        return PlaybookVersionRead.model_validate(body)

    async def restore_playbook_version(
        self, playbook_id: UUID, version: int, locale: str = DEFAULT_LOCALE
    ) -> PlaybookRead:
        body = await self._write(
            "POST",
            f"{self._workspace_prefix}/playbooks/{playbook_id}/versions/{version}/restore",
            None,
            params={"locale": locale},
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

    async def update_resource(
        self, resource_id: UUID, data: ResourceUpdate, locale: str = DEFAULT_LOCALE
    ) -> ResourceRead:
        body = await self._write(
            "PUT",
            f"{self._workspace_prefix}/resources/{resource_id}",
            data,
            params={"locale": locale},
        )
        return ResourceRead.model_validate(body)

    async def transition_resource_version(
        self,
        resource_id: UUID,
        version: int,
        data: VersionTransitionRequest,
        locale: str = DEFAULT_LOCALE,
    ) -> ResourceVersionRead:
        body = await self._write(
            "POST",
            f"{self._workspace_prefix}/resources/{resource_id}/versions/{version}/transition",
            data,
            params={"locale": locale},
        )
        return ResourceVersionRead.model_validate(body)

    async def restore_resource_version(
        self, resource_id: UUID, version: int, locale: str = DEFAULT_LOCALE
    ) -> ResourceRead:
        body = await self._write(
            "POST",
            f"{self._workspace_prefix}/resources/{resource_id}/versions/{version}/restore",
            None,
            params={"locale": locale},
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
