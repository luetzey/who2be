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

from pydantic import BaseModel, ConfigDict, Field, computed_field

# PersonaRead importiert keine agent-Modelle — kein zirkulaerer Import.
from who2be_models.persona import PersonaRead
from who2be_models.tool_policy import AgentToolPolicy


class AgentStatus(StrEnum):
    """Konfigurations-Status des Agenten.

    `enabled` = der Agent ist im UI aufrufbar / kopierbar.
    `disabled` = der Agent ist deaktiviert (versteckt sich im List-Filter,
    Render-Endpoint antwortet 409).
    """

    enabled = "enabled"
    disabled = "disabled"


class AgentCreate(BaseModel):
    """Eingabe fuer `POST .../agents` — legt einen Agent an.

    `persona_id` und `system_prompt_template_id` sind optional: ein Agent darf
    als leere Huelle (ohne Persona und/oder Template) angelegt werden, die
    spaeter per `PUT` vervollstaendigt wird. Eine unvollstaendige (oder noch
    nicht aktivierbare) Huelle ist nicht render- und nicht kopierbar (siehe
    `POST .../agents/{id}/copy`).

    Default-Status ist `disabled`: ein frisch angelegter Agent ist erst dann
    aktivierbar (`enabled`), wenn er vollstaendig ist (Persona + Template gesetzt
    UND die Persona hat eine aktive Version). Wer beim Anlegen explizit
    `status=enabled` sendet, ohne diese Bedingung zu erfuellen, bekommt 409.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2_000)
    persona_id: UUID | None = None
    system_prompt_template_id: UUID | None = None
    status: AgentStatus = AgentStatus.disabled
    # Welche MCP-Tools der Agent nutzen darf. Default = Read-All / keine Writes.
    tool_policy: AgentToolPolicy = Field(default_factory=AgentToolPolicy)


class AgentUpdate(BaseModel):
    """Eingabe fuer `PUT .../agents/{id}` — aendert Konfig in-place.

    `tool_policy` ist optional: `None` laesst die bestehende Policy unangetastet
    (analog zu name/description). Ein gesetztes Objekt ersetzt die Policy ganz.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2_000)
    persona_id: UUID | None = None
    system_prompt_template_id: UUID | None = None
    status: AgentStatus | None = None
    tool_policy: AgentToolPolicy | None = None


class AgentCopy(BaseModel):
    """Eingabe fuer `POST .../agents/{id}/copy` — dupliziert einen Agent.

    `name` ist optional; ohne Angabe leitet der Service einen Default aus dem
    Quell-Namen ab (``"<Name> (Kopie)"``). Die Kopie uebernimmt Persona,
    Template, Beschreibung und Status der Quelle.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)


class AgentRead(BaseModel):
    """Agent im aktuellen Stand.

    `persona_active` spiegelt, ob die verknuepfte Persona eine aktive Version
    hat (serverseitig aus `persona_version.status='active'` gelesen). Das Feld
    ist die Grundlage fuer `activatable`/`missing` — ohne aktive Persona darf
    der Agent nicht aktiviert oder kopiert werden.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    owner_id: UUID
    name: str
    description: str
    persona_id: UUID | None
    system_prompt_template_id: UUID | None
    status: AgentStatus
    # Vom System verwaltet (Builder-Lock): User-Edits/Delete werden serverseitig
    # mit 403 geblockt; nur Duplizieren ist erlaubt.
    is_managed: bool = False
    # Ob die verknuepfte Persona eine aktive Version hat. Default False, damit
    # direkt konstruierte Reads (ohne DB-Join) konservativ als "nicht aktivierbar"
    # gelten; die Repository-SELECTs befuellen es per EXISTS-Subquery.
    persona_active: bool = False
    # MCP-Tool-Policy des Agenten. Default-Instanz (Read-All/keine Writes) deckt
    # direkt konstruierte Reads und Bestands-Agenten mit leerem `{}`-JSON ab.
    tool_policy: AgentToolPolicy = Field(default_factory=AgentToolPolicy)
    created_at: datetime
    updated_at: datetime

    @property
    def is_shell(self) -> bool:
        """True, solange Persona ODER Template fehlt (unvollstaendige Huelle).

        Eine Huelle ist nicht render- und nicht kopierbar. Schaerfer als das
        reine Vorhandensein ist `activatable` (verlangt zusaetzlich eine aktive
        Persona) — `is_shell` bleibt der Render-Guard (kein Template = nichts
        zu rendern), `activatable` der Enable-/Copy-Guard.
        """
        return self.persona_id is None or self.system_prompt_template_id is None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def missing(self) -> list[str]:
        """Was dem Agenten zur Aktivierbarkeit fehlt — in stabiler Reihenfolge.

        Moegliche Eintraege: ``"persona"`` (keine Persona verknuepft),
        ``"template"`` (kein Template verknuepft), ``"persona_active"`` (Persona
        verknuepft/fehlend, aber ohne aktive Version). Eine leere Liste heisst
        aktivierbar.
        """
        gaps: list[str] = []
        if self.persona_id is None:
            gaps.append("persona")
        if self.system_prompt_template_id is None:
            gaps.append("template")
        if not self.persona_active:
            gaps.append("persona_active")
        return gaps

    @computed_field  # type: ignore[prop-decorator]
    @property
    def activatable(self) -> bool:
        """True, wenn der Agent aktiviert (enabled) und kopiert werden darf.

        Bedingung: Persona UND Template gesetzt UND die Persona hat eine aktive
        Version. Spiegelt `not self.missing`.
        """
        return not self.missing


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

    `unresolved_placeholders` enthaelt jeden Placeholder-Key, der beim Render
    nicht aufgeloest werden konnte (z. B. `"playbook:abc-uuid"` bei fehlender
    aktiver Version). Default leere Liste fuer Backward-Compat.
    """

    model_config = ConfigDict(extra="forbid")

    id: UUID
    name: str
    persona: PersonaRead
    system_prompt_rendered: str
    system_prompt_template_id: UUID
    unresolved_placeholders: list[str] = Field(default_factory=list)
