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

from who2be_models import PersonaRead, PlaybookRead, ResourceLinkRead, ResourceRead

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
        data = await self._get(
            f"{self._workspace_prefix}/personas/{persona_id}/playbooks"
        )
        return [PlaybookRead.model_validate(item) for item in data]

    async def list_playbooks(self, tag: str | None, trigger: str | None) -> list[PlaybookRead]:
        params: dict[str, str] = {}
        if tag is not None:
            params["tag"] = tag
        if trigger is not None:
            params["trigger"] = trigger
        data = await self._get(f"{self._workspace_prefix}/playbooks", params=params)
        return [PlaybookRead.model_validate(item) for item in data]

    async def get_playbook(self, playbook_id: UUID) -> PlaybookRead:
        data = await self._get(f"{self._workspace_prefix}/playbooks/{playbook_id}")
        return PlaybookRead.model_validate(data)

    async def list_resources(self) -> list[ResourceRead]:
        data = await self._get(f"{self._workspace_prefix}/resources")
        return [ResourceRead.model_validate(item) for item in data]

    async def get_resource(self, resource_id: UUID) -> ResourceRead:
        data = await self._get(f"{self._workspace_prefix}/resources/{resource_id}")
        return ResourceRead.model_validate(data)

    async def get_playbook_resource_links(
        self, playbook_id: UUID
    ) -> list[ResourceLinkRead]:
        data = await self._get(
            f"{self._workspace_prefix}/playbooks/{playbook_id}/resource_links"
        )
        return [ResourceLinkRead.model_validate(item) for item in data]
