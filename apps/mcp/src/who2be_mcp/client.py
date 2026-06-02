"""HTTP-Client des MCP-Servers gegen die Who2Be-REST-API (ADR-0005).

Ein duenner Adapter: keine Geschaeftslogik, keine Owner-Pruefung — die liegt
in der API. Fehler werden in `ToolError` mit fuer Agenten lesbaren Meldungen
uebersetzt.
"""

import logging
from typing import Any
from uuid import UUID

import httpx
from fastmcp.exceptions import ToolError

from who2be_models import (
    AgentWithRenderedPrompt,
    PersonaRead,
    PlaybookRead,
    ResourceLinkRead,
    ResourceRead,
    TriggerOverview,
)

logger = logging.getLogger(__name__)

_TIMEOUT = 10.0


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

    async def _get(self, path: str, params: dict[str, str] | None = None) -> Any:
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                headers=self._headers,
                transport=self._transport,
                timeout=_TIMEOUT,
            ) as client:
                response = await client.get(path, params=params)
        except httpx.HTTPError as exc:
            # Nur den Exception-Typ loggen — die `str(exc)`-Repraesentation kann
            # je nach httpx-Pfad das Request-Objekt mit `Authorization`-Header
            # mitfuehren; den Token-Klartext wollen wir nirgends im Log sehen.
            logger.warning("Who2Be-API nicht erreichbar: %s", type(exc).__name__)
            raise ToolError("Who2Be-API nicht erreichbar.") from exc
        if response.status_code == 404:
            raise ToolError("Angefragte Ressource nicht gefunden.")
        if response.status_code == 401:
            raise ToolError("Nicht autorisiert — WHO2BE_API_TOKEN pruefen.")
        if response.is_error:
            logger.warning("Who2Be-API-Fehler %s fuer %s", response.status_code, path)
            raise ToolError(f"Who2Be-API-Fehler ({response.status_code}).")
        return response.json()

    async def get_persona(self, identifier: str) -> PersonaRead:
        """Laedt eine Persona per UUID oder — sonst — per Name."""
        try:
            persona_id = UUID(identifier)
        except ValueError:
            return await self._resolve_persona_by_name(identifier)
        data = await self._get(f"{self._workspace_prefix}/personas/{persona_id}")
        return PersonaRead.model_validate(data)

    async def _resolve_persona_by_name(self, name: str) -> PersonaRead:
        data = await self._get(f"{self._workspace_prefix}/personas")
        for entry in data:
            persona = PersonaRead.model_validate(entry)
            if persona.name == name:
                return persona
        raise ToolError(f"Keine Persona mit Name '{name}'.")

    async def get_persona_playbooks(self, persona_id: UUID) -> list[PlaybookRead]:
        data = await self._get(f"{self._workspace_prefix}/personas/{persona_id}/playbooks")
        return [PlaybookRead.model_validate(item) for item in data]

    async def get_persona_rendered(self, persona_id: UUID) -> str:
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
        data = await self._get(f"{self._workspace_prefix}/personas/{persona_id}/rendered")
        body = data.get("body_rendered") if isinstance(data, dict) else None
        return body if isinstance(body, str) else ""

    async def list_playbooks(self, tag: str | None, trigger: str | None) -> list[PlaybookRead]:
        params: dict[str, str] = {}
        if tag is not None:
            params["tag"] = tag
        if trigger is not None:
            params["trigger"] = trigger
        data = await self._get(f"{self._workspace_prefix}/playbooks", params=params)
        return [PlaybookRead.model_validate(item) for item in data]

    async def list_triggers(self) -> list[TriggerOverview]:
        data = await self._get(f"{self._workspace_prefix}/playbooks/triggers")
        return [TriggerOverview.model_validate(item) for item in data]

    async def get_playbook(self, playbook_id: UUID) -> PlaybookRead:
        data = await self._get(f"{self._workspace_prefix}/playbooks/{playbook_id}")
        return PlaybookRead.model_validate(data)

    async def list_resources(self, tag: str | None = None) -> list[ResourceRead]:
        params: dict[str, str] = {}
        if tag is not None:
            params["tag"] = tag
        data = await self._get(f"{self._workspace_prefix}/resources", params=params)
        return [ResourceRead.model_validate(item) for item in data]

    async def get_resource(self, resource_id: UUID) -> ResourceRead:
        data = await self._get(f"{self._workspace_prefix}/resources/{resource_id}")
        return ResourceRead.model_validate(data)

    async def get_playbook_resource_links(self, playbook_id: UUID) -> list[ResourceLinkRead]:
        data = await self._get(f"{self._workspace_prefix}/playbooks/{playbook_id}/resource_links")
        return [ResourceLinkRead.model_validate(item) for item in data]

    async def get_playbook_composes(self, playbook_id: UUID) -> list[PlaybookRead]:
        """Laedt die geordneten aktiven Sub-Playbooks eines Composite (eine Ebene).

        Leere Liste wenn das Playbook kein Composite ist oder keine aktiven
        Kinder hat (API-Token-Pfad liefert nur aktive Versionen).
        """
        data = await self._get(f"{self._workspace_prefix}/playbooks/{playbook_id}/composes")
        return [PlaybookRead.model_validate(item) for item in data]

    async def get_agent_rendered(self, agent_id: UUID) -> AgentWithRenderedPrompt:
        """Laedt Agent + Persona + expandierten System-Prompt vom API-Endpoint."""
        data = await self._get(f"{self._workspace_prefix}/agents/{agent_id}/rendered")
        return AgentWithRenderedPrompt.model_validate(data)

    async def get_playbook_rendered(self, playbook_id: UUID) -> str:
        """Laedt den serverseitig expandierten Playbook-Body (B5).

        Der API-Endpoint `GET .../playbooks/{id}/rendered` jagt den Body durch den
        Placeholder-Renderer (Inline-Pills → Plain-Text). Bei `body_format='plain'`
        kommt der rohe Body zurueck. Der MCP-Prozess hat keinen DB-Zugriff — das
        Rendering MUSS daher ueber diesen Endpoint laufen.

        Gibt nur den `body_rendered`-String zurueck; die `unresolved`-Liste ist fuer
        den Agent-Konsum nicht relevant (best-effort Expansion).
        """
        data = await self._get(f"{self._workspace_prefix}/playbooks/{playbook_id}/rendered")
        body = data.get("body_rendered") if isinstance(data, dict) else None
        return body if isinstance(body, str) else ""
