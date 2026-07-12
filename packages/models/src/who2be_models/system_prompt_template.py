"""Pydantic-Modelle fuer das SystemPromptTemplate-Aggregat.

Templates traegen den eigentlichen System-Prompt des Agenten — mit Liquid-
Style-Placeholders (`{{ persona.name }}`, `{{ playbooks }}` etc.), die der
Render-Service serverseitig befuellt. Versionierung analog persona/playbook
(ADR-0004, ADR-0020): Identitaets-Zeile `system_prompt_template` + Snapshots
in `system_prompt_template_version`.

Track B (Nur-BlockNote): `body` ist immer ein stringifiziertes BlockNote-JSON-
Dokument mit Custom-Inline-Blocks vom Typ `placeholder`, die der Renderer
expandiert. Der frueher gefuehrte `body_format`-Schalter (Migration 0025/0026)
ist mit Migration `0030_blocknote_only.sql` entfallen.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from who2be_models.locale import DEFAULT_LOCALE, ContentLocale
from who2be_models.status import VersionStatus

# Slug-Form fuer Default-Templates und idempotenten Seed (Migration 0023b).
# Kleinbuchstaben + Bindestriche; max. 100 Zeichen.
SlugStr = Annotated[
    str, StringConstraints(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9-]*$")
]


class SystemPromptTemplateContent(BaseModel):
    """Typisierter Inhalt einer Template-Version.

    `body` ist der eigentliche System-Prompt-Text mit eingebetteten
    Placeholders. Wir limitieren auf 50_000 Zeichen (DoS-Schutz), genug fuer
    sehr ausfuehrliche Prompts inkl. mehrerer Beispiele.
    """

    model_config = ConfigDict(extra="forbid")

    description: str = Field(default="", max_length=2_000)
    body: str = Field(min_length=1, max_length=50_000)


class SystemPromptTemplateCreate(BaseModel):
    """Eingabe fuer `POST .../system-prompts` — legt Version 1 an."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    # `slug` wird beim Create automatisch aus `name` abgeleitet, falls nicht
    # gesetzt. Wir lassen Clients aber auch explizit einen Slug uebergeben
    # (Default-Templates aus dem Seed nutzen feste Slugs).
    slug: SlugStr | None = None
    content: SystemPromptTemplateContent


class SystemPromptTemplateUpdate(BaseModel):
    """Eingabe fuer `PUT .../system-prompts/{id}` — erzeugt eine neue Version."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    content: SystemPromptTemplateContent


class SystemPromptTemplateRead(BaseModel):
    """Template im aktuellen Stand (inkl. Inhalt der aktuellen Version)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    owner_id: UUID
    name: str
    slug: str
    # Vom System verwaltet (Builder-Lock): User-Edits werden serverseitig
    # mit 403 geblockt; nur Duplizieren ist erlaubt.
    is_managed: bool = False

    current_version: int
    current_status: VersionStatus = VersionStatus.inactive
    has_pending_draft: bool = False
    # Content-i18n (ADR-0027): Sprachvariante dieser Antwort. Templates sind
    # heute einsprachig ('de'); das Feld haelt das Read-Modell konsistent mit
    # den uebrigen Aggregaten und deckt den Migration-Default.
    locale: ContentLocale = DEFAULT_LOCALE
    content: SystemPromptTemplateContent
    # List-Enrichment (Card-Pill): NUR der List-Endpoint befuellt diesen
    # Batch-Aggregat-Zaehler (kein N+1) — Anzahl der Agenten mit
    # `agent.system_prompt_template_id = id`. Direkt konstruierte Reads lassen
    # ihn auf 0.
    agent_count: int = 0
    created_at: datetime
    updated_at: datetime


class SystemPromptTemplateVersionRead(BaseModel):
    """Ein unveraenderlicher Versions-Snapshot eines Templates."""

    model_config = ConfigDict(from_attributes=True)

    version: int
    status: VersionStatus = VersionStatus.inactive
    locale: ContentLocale = DEFAULT_LOCALE
    content: SystemPromptTemplateContent
    created_by: UUID
    created_at: datetime
