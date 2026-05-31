"""Pydantic-Modelle fuer das Agent-Aggregat.

Agent ist die Top-Level-Konfiguration der neuen Domain-Hierarchie (Phase 3
Runde 3 Track 3): genau eine Persona + genau ein SystemPromptTemplate pro
Agent. Keine eigene Versionshistorie — Aenderungen am Agent sind reine
Konfig-Updates. Inhaltliche Versionierung lebt auf Persona/Template/Playbook.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# PersonaRead importiert keine agent-Modelle — kein zirkulaerer Import.
from who2be_models.persona import PersonaRead


class AgentStatus(StrEnum):
    """Konfigurations-Status des Agenten.

    `enabled` = der Agent ist im UI aufrufbar / kopierbar.
    `disabled` = der Agent ist deaktiviert (versteckt sich im List-Filter,
    Render-Endpoint antwortet 409).
    """

    enabled = "enabled"
    disabled = "disabled"


class AgentCreate(BaseModel):
    """Eingabe fuer `POST .../agents` — legt einen Agent an."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2_000)
    persona_id: UUID
    system_prompt_template_id: UUID
    status: AgentStatus = AgentStatus.enabled


class AgentUpdate(BaseModel):
    """Eingabe fuer `PUT .../agents/{id}` — aendert Konfig in-place."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2_000)
    persona_id: UUID | None = None
    system_prompt_template_id: UUID | None = None
    status: AgentStatus | None = None


class AgentRead(BaseModel):
    """Agent im aktuellen Stand."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    owner_id: UUID
    name: str
    description: str
    persona_id: UUID
    system_prompt_template_id: UUID
    status: AgentStatus
    created_at: datetime
    updated_at: datetime


# Output-Formate des Render-Endpoints. `plain` ist der Default (rohe
# Substitution); `markdown` rendert Sections als `##`-Headings; `html` jagt
# das Markdown durch `markdown-it-py` und liefert sicheres HTML.
RenderFormat = Literal["plain", "markdown", "html"]


class AgentRenderResponse(BaseModel):
    """Antwort des `GET .../agents/{id}/render`-Endpoints.

    `unresolved_placeholders` enthaelt jeden im Template gefundenen, vom
    Render-Service nicht aufgeloesten Platzhalter (deduped, in Auftauchreihen-
    folge). Im Output sind diese mit `⚠ {{ … }}` markiert, damit der User
    direkt sieht, was nicht befuellt wurde.
    """

    model_config = ConfigDict(extra="forbid")

    content: str
    unresolved_placeholders: list[str] = Field(default_factory=list)
    format: RenderFormat = "plain"


class AgentWithRenderedPrompt(BaseModel):
    """Antwort des MCP-Tools `fetch_agent` (und des API-Endpoints `GET .../rendered`).

    Liefert den Agent zusammen mit seiner Persona und dem bereits expandierten
    System-Prompt als Plain-Text — alle Placeholder wurden bereits aufgeloest,
    sodass MCP-Konsumenten den fertigen Prompt direkt einsetzen koennen.

    Hinweis: `persona` ist direkt inline (kein Wrapper-Objekt), damit der
    Frontend-Agent und der MCP-Konsument ohne zusaetzlichen Fetch auskommen.
    """

    model_config = ConfigDict(extra="forbid")

    id: UUID
    name: str
    persona: PersonaRead
    system_prompt_rendered: str
    system_prompt_template_id: UUID
