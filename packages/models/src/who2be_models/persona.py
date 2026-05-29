"""Pydantic-Modelle fuer das Persona-Aggregat."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from who2be_models.resource import ResourceBlock
from who2be_models.status import VersionStatus

# Eingabe-Limits — DoS-Schutz gegen riesige Payloads, da Versions-Inhalte
# unveraenderlich in `persona_version` eingefroren und in jeder
# `list_personas`-Antwort retourniert werden.
TraitStr = Annotated[str, StringConstraints(min_length=1, max_length=200)]
TagStr = Annotated[str, StringConstraints(min_length=1, max_length=100)]


class PersonaContent(BaseModel):
    """BlockNote-strukturierter Persona-Profil-Inhalt (Phase 3-0).

    Wird als optionales Feld an `PersonaVersionContent.content` haengen und
    traegt Rolle, Tonfall, Beispiele als BlockNote-Dokument (ADR-0022). Gleiche
    Obergrenze (`max_length=2000`) wie bei `ResourceContent.blocks` — gross
    genug fuer eine Persona-Karte, klein genug zum Embedden in Listen.
    """

    model_config = ConfigDict(extra="forbid")

    description: str = Field(default="", max_length=2_000)
    blocks: list[ResourceBlock] = Field(default_factory=list, max_length=2_000)


class PersonaVersionContent(BaseModel):
    """Typisierter Inhalt einer Persona-Version (`persona_version.content`).

    Vor Phase 3-0 hiess diese Klasse `PersonaContent`. Der Name ist mit Phase
    3-0 an die neue BlockNote-Profil-Klasse uebergegangen; die per-Version
    persistierten Felder leben hier.

    `traits` ist mit Phase 3-0 als Persona-Strukturfeld deprecated — neue UIs
    liefern den strukturierten Profil-Inhalt ueber `content` (BlockNote). Das
    Feld bleibt mit Default `[]` als Wire-Schema-Backward-Compat (alte Clients
    schicken/erwarten es weiter).
    """

    model_config = ConfigDict(extra="forbid")

    description: str = Field(max_length=2_000)
    system_prompt: str = Field(max_length=20_000)
    traits: list[TraitStr] = Field(default_factory=list, max_length=50)
    tags: list[TagStr] = Field(default_factory=list, max_length=50)
    content: PersonaContent | None = None


class PersonaCreate(BaseModel):
    """Eingabe fuer `POST /v1/personas` — legt Version 1 an."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    content: PersonaVersionContent


class PersonaUpdate(BaseModel):
    """Eingabe fuer `PUT /v1/personas/{id}` — erzeugt eine neue Version."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    content: PersonaVersionContent


class PersonaRead(BaseModel):
    """Persona im aktuellen Stand (inkl. Inhalt der aktuellen Version)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    owner_id: UUID
    name: str
    current_version: int
    current_status: VersionStatus = VersionStatus.inactive
    has_pending_draft: bool = False
    content: PersonaVersionContent
    created_at: datetime
    updated_at: datetime


class PersonaVersionRead(BaseModel):
    """Ein unveraenderlicher Versions-Snapshot einer Persona."""

    model_config = ConfigDict(from_attributes=True)

    version: int
    status: VersionStatus = VersionStatus.inactive
    content: PersonaVersionContent
    created_by: UUID
    created_at: datetime
