"""Pydantic-Modelle fuer das SystemPromptTemplate-Aggregat.

Templates traegen den eigentlichen System-Prompt des Agenten — mit Liquid-
Style-Placeholders (`{{ persona.name }}`, `{{ playbooks }}` etc.), die der
Render-Service serverseitig befuellt. Versionierung analog persona/playbook
(ADR-0004, ADR-0020): Identitaets-Zeile `system_prompt_template` + Snapshots
in `system_prompt_template_version`.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

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
    current_version: int
    current_status: VersionStatus = VersionStatus.inactive
    has_pending_draft: bool = False
    content: SystemPromptTemplateContent
    created_at: datetime
    updated_at: datetime


class SystemPromptTemplateVersionRead(BaseModel):
    """Ein unveraenderlicher Versions-Snapshot eines Templates."""

    model_config = ConfigDict(from_attributes=True)

    version: int
    status: VersionStatus = VersionStatus.inactive
    content: SystemPromptTemplateContent
    created_by: UUID
    created_at: datetime
