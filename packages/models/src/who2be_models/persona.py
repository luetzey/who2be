"""Pydantic-Modelle fuer das Persona-Aggregat."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PersonaContent(BaseModel):
    """Typisierter Inhalt einer Persona-Version (`persona_version.content`)."""

    model_config = ConfigDict(extra="forbid")

    description: str
    system_prompt: str
    traits: list[str] = Field(default_factory=list)


class PersonaCreate(BaseModel):
    """Eingabe fuer `POST /v1/personas` — legt Version 1 an."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    content: PersonaContent


class PersonaUpdate(BaseModel):
    """Eingabe fuer `PUT /v1/personas/{id}` — erzeugt eine neue Version."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    content: PersonaContent


class PersonaRead(BaseModel):
    """Persona im aktuellen Stand (inkl. Inhalt der aktuellen Version)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    name: str
    current_version: int
    content: PersonaContent
    created_at: datetime
    updated_at: datetime


class PersonaVersionRead(BaseModel):
    """Ein unveraenderlicher Versions-Snapshot einer Persona."""

    model_config = ConfigDict(from_attributes=True)

    version: int
    content: PersonaContent
    created_by: UUID
    created_at: datetime
