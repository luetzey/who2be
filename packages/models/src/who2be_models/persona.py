"""Pydantic-Modelle fuer das Persona-Aggregat."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# Eingabe-Limits — DoS-Schutz gegen riesige Payloads, da Versions-Inhalte unveraenderlich
# in `persona_version` eingefroren und in jeder `list_personas`-Antwort retourniert werden.
TraitStr = Annotated[str, StringConstraints(min_length=1, max_length=200)]


class PersonaContent(BaseModel):
    """Typisierter Inhalt einer Persona-Version (`persona_version.content`)."""

    model_config = ConfigDict(extra="forbid")

    description: str = Field(max_length=2_000)
    system_prompt: str = Field(max_length=20_000)
    traits: list[TraitStr] = Field(default_factory=list, max_length=50)


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
    workspace_id: UUID
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
