"""Pydantic-Modelle fuer das ExternalTool-Aggregat (WP-1, Blueprint
`.claude/plan/2026-07-18-1315_external-tools-tool-ref.md`).

Externe MCP-Server/Tool-Bindings (z. B. Todoist, Things 3) als versioniertes
Workspace-Objekt mit stabilem Faehigkeits-**Alias** (z. B. `todo`), ueber den
Playbooks/Personas/Resources/System-Prompt-Vorlagen die Bindung per
`tool-ref`-Placeholder referenzieren (WP-2, Fetch-Time-Expansion). Rein
**instruktive** Bindung — KEINE Server-URLs, KEINE Credentials (Entscheidung
2, Blueprint).

Aufbau spiegelt `resource.py`: ein `…Create`/`…Update`/`…Read`/`…VersionRead`-
Satz, `…Content` typisiert das `jsonb`-Feld. Der `alias` lebt — wie der
Resource-`slug` (Migration 0064) bzw. der Template-Slug (0022) — auf der
AGGREGAT-Zeile (stabile Identitaet ueber Versionen hinweg), NICHT im
Versions-Content: ein Re-Binding (neues Tool-Objekt uebernimmt denselben
Alias) darf bestehende `tool-ref`-Referenzen nicht brechen.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)

from who2be_models.locale import DEFAULT_LOCALE, ContentLocale, normalize_locale
from who2be_models.slug import SlugStr
from who2be_models.status import VersionStatus

# Einzelner Tool-Bezeichner (`add_task`, `list_tasks`, …) — Eingabe-Limit als
# DoS-Schutz fuer in jsonb persistierte Strings (analog `TagStr`, ADR-0009).
ToolNameStr = Annotated[str, StringConstraints(min_length=1, max_length=100)]

# Tag-String — identisch zu `ResourceContent.TagStr`/`PlaybookContent.TagStr`.
TagStr = Annotated[str, StringConstraints(min_length=1, max_length=100)]


class ExternalToolContent(BaseModel):
    """Typisierter Inhalt einer ExternalTool-Version (`external_tool_version.content`).

    Rein beschreibend (Blueprint Entscheidung 2): `display_name` ist der
    Anzeigename des konkreten Tools ("Todoist"), `mcp_server_name` der
    Connector-Name in der Runtime ("Todoist MCP"), `tool_names` die relevanten
    MCP-Tool-Bezeichner. `usage_notes` ist — wie `PlaybookContent.body`/
    `SystemPromptTemplateContent.body` — ein stringifiziertes BlockNote-JSON-
    Dokument (wann/wie nutzen, Do/Don't); `fallback_note` ein optionaler
    Klartext-Hinweis, was der Agent tun soll, wenn der Server in der Runtime
    nicht verbunden ist. `tags` ermoeglicht spaetere Picker-/Filter-UX
    (analog `ResourceContent.tags`, E3).
    """

    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(default="", max_length=200)
    mcp_server_name: str = Field(default="", max_length=200)
    tool_names: list[ToolNameStr] = Field(default_factory=list, max_length=100)
    usage_notes: str = Field(default="", max_length=20_000)
    fallback_note: str | None = Field(default=None, max_length=2_000)
    tags: list[TagStr] = Field(default_factory=list, max_length=50)


class ExternalToolCreate(BaseModel):
    """Eingabe fuer `POST /v1/workspaces/{ws}/external_tools` — legt Version 1 an.

    Nur `name` ist Pflicht (spiegelt `ResourceCreate`/`SystemPromptTemplateCreate`).
    `alias` wird beim Create aus dem Namen abgeleitet, falls nicht gesetzt —
    workspace-eindeutig (409 bei Kollision, partieller UNIQUE-Index Migration 0065).
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    alias: SlugStr | None = None
    content: ExternalToolContent = Field(default_factory=ExternalToolContent)
    # Content-i18n (ADR-0027): Sprachvarianten beim Anlegen. Default `['de']`.
    locales: list[ContentLocale] = Field(default_factory=lambda: [DEFAULT_LOCALE])

    @field_validator("locales")
    @classmethod
    def _dedup_non_empty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("Mindestens eine Sprache ist erforderlich.")
        seen: set[str] = set()
        ordered: list[str] = []
        for loc in value:
            norm = normalize_locale(loc)
            if norm not in seen:
                seen.add(norm)
                ordered.append(norm)
        return ordered


class ExternalToolUpdate(BaseModel):
    """Eingabe fuer `PUT /v1/workspaces/{ws}/external_tools/{id}` — neue Version.

    Kein `alias`-Feld: der Alias ist nach dem Create unveraenderlich (spiegelt
    `ResourceUpdate`, dessen `slug` ebenfalls nur beim Create gesetzt wird).
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    content: ExternalToolContent


class ExternalToolRead(BaseModel):
    """ExternalTool im aktuellen Stand (inkl. Inhalt der aktuellen Version)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    owner_id: UUID
    name: str
    # Workspace-eindeutiger Faehigkeits-Alias (Migration 0065). Ziel der
    # `tool-ref`-Placeholder-Referenz (WP-2).
    alias: str
    current_version: int
    # Vom System verwaltet (Builder-Lock): User-Edits werden serverseitig
    # mit 403 geblockt. Heute seedet der Builder keine ExternalTools — die
    # Spalte existiert, weil der gemeinsame `VersionedAggregateRepository`-
    # SELECT sie immer liest (spiegelt Resource, Migration 0057).
    is_managed: bool = False

    current_status: VersionStatus = VersionStatus.inactive
    has_pending_draft: bool = False
    locale: ContentLocale = DEFAULT_LOCALE
    content: ExternalToolContent
    created_at: datetime
    updated_at: datetime


class ExternalToolVersionRead(BaseModel):
    """Ein unveraenderlicher Versions-Snapshot eines ExternalTools."""

    model_config = ConfigDict(from_attributes=True)

    version: int
    status: VersionStatus = VersionStatus.inactive
    locale: ContentLocale = DEFAULT_LOCALE
    content: ExternalToolContent
    created_by: UUID
    created_at: datetime
