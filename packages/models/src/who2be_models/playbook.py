"""Pydantic-Modelle fuer das Playbook-Aggregat.

`type`, `tags` und `triggers` sind Teil des Versions-Inhalts und werden vom
Service auf die `playbook`-Zeile denormalisiert, damit `list_playbooks` ohne
Join filtern kann (siehe architecture.md §3).
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# Eingabe-Limits — DoS-Schutz fuer in jsonb persistierte und unveraendert
# wiedergegebene Versions-Inhalte (siehe Persona-Pendant).
TagStr = Annotated[str, StringConstraints(min_length=1, max_length=100)]


class PlaybookContent(BaseModel):
    """Typisierter Inhalt einer Playbook-Version (`playbook_version.content`)."""

    model_config = ConfigDict(extra="forbid")

    description: str = Field(max_length=2_000)
    body: str = Field(max_length=50_000)
    type: str = Field(min_length=1, max_length=100)
    tags: list[TagStr] = Field(default_factory=list, max_length=50)
    triggers: str | None = Field(default=None, max_length=2_000)


class PlaybookCreate(BaseModel):
    """Eingabe fuer `POST /v1/playbooks` — legt Version 1 an."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    content: PlaybookContent


class PlaybookUpdate(BaseModel):
    """Eingabe fuer `PUT /v1/playbooks/{id}` — erzeugt eine neue Version."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    content: PlaybookContent


class PlaybookRead(BaseModel):
    """Playbook im aktuellen Stand inkl. denormalisierter Filterfelder."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    name: str
    current_version: int
    type: str
    tags: list[str]
    triggers: str | None
    content: PlaybookContent
    created_at: datetime
    updated_at: datetime


class PlaybookVersionRead(BaseModel):
    """Ein unveraenderlicher Versions-Snapshot eines Playbooks."""

    model_config = ConfigDict(from_attributes=True)

    version: int
    content: PlaybookContent
    created_by: UUID
    created_at: datetime
