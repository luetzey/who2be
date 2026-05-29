"""Pydantic-Modelle fuer das Resource-Aggregat (Phase 2.2).

Resources sind eine zweite, versionierte Wissensebene mit Block-Editor-Inhalt
(BlockNote-Dokument, ADR-0022). `resource_version.content` haelt das
Block-Array; jeder Block traegt eine stabile `id`, auf die Playbooks per
`playbook_resource_link` zeigen koennen (Block-Refs, ADR-0021).

Versionierung + Status spiegeln Persona/Playbook (ADR-0004 / ADR-0020):
ein `…Create`/`…Update`/`…Read`/`…VersionRead`-Satz, `…Content` typisiert das
`jsonb`-Feld.
"""

import json
from datetime import datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from who2be_models.status import VersionStatus

# Stabile BlockNote-Block-ID bzw. Block-Typ — die ID ist der Anker fuer
# Playbook-Block-Refs.
BlockId = Annotated[str, StringConstraints(min_length=1, max_length=100)]
BlockType = Annotated[str, StringConstraints(min_length=1, max_length=50)]

# DoS-Obergrenze fuer den serialisierten Block-Inhalt. Bloecke sind
# `extra="allow"` (BlockNote-Schema ist offen), darum greift hier ein
# Gesamt-Byte-Limit statt feldweiser `max_length` (F-01-Linie).
_MAX_CONTENT_BYTES = 1_000_000


class ResourceBlock(BaseModel):
    """Ein Top-Level-Block eines BlockNote-Dokuments.

    `extra="allow"`, weil das BlockNote-Schema (`props`, `content`, `children`,
    …) offen und versionsabhaengig ist. Verbindlich sind nur `id` (Anker fuer
    Block-Refs) und `type`.
    """

    model_config = ConfigDict(extra="allow")

    id: BlockId
    type: BlockType


class ResourceContent(BaseModel):
    """Typisierter Inhalt einer Resource-Version (`resource_version.content`)."""

    model_config = ConfigDict(extra="forbid")

    description: str = Field(default="", max_length=2_000)
    blocks: list[ResourceBlock] = Field(default_factory=list, max_length=2_000)

    @model_validator(mode="after")
    def _check_total_size(self) -> Self:
        size = len(json.dumps(self.model_dump(mode="json")))
        if size > _MAX_CONTENT_BYTES:
            raise ValueError(
                f"Resource-Inhalt zu gross ({size} > {_MAX_CONTENT_BYTES} Bytes)."
            )
        return self


class ResourceCreate(BaseModel):
    """Eingabe fuer `POST /v1/workspaces/{ws}/resources` — legt Version 1 an."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    content: ResourceContent


class ResourceUpdate(BaseModel):
    """Eingabe fuer `PUT /v1/workspaces/{ws}/resources/{id}` — neue Version."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    content: ResourceContent


class ResourceRead(BaseModel):
    """Resource im aktuellen Stand (inkl. Inhalt der aktuellen Version)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    owner_id: UUID
    name: str
    current_version: int
    current_status: VersionStatus = VersionStatus.inactive
    has_pending_draft: bool = False
    content: ResourceContent
    created_at: datetime
    updated_at: datetime


class ResourceVersionRead(BaseModel):
    """Ein unveraenderlicher Versions-Snapshot einer Resource."""

    model_config = ConfigDict(from_attributes=True)

    version: int
    status: VersionStatus = VersionStatus.inactive
    content: ResourceContent
    created_by: UUID
    created_at: datetime


class ResourceLinkItem(BaseModel):
    """Ein einzelner Playbook→Resource-Block-Verweis (Eingabe)."""

    model_config = ConfigDict(extra="forbid")

    resource_id: UUID
    block_id: BlockId
    position: int = Field(ge=0)


class ResourceLinkSet(BaseModel):
    """Eingabe fuer `PUT .../playbooks/{id}/resource_links`.

    Set-Replace-Semantik: die Liste ersetzt den bisherigen Stand vollstaendig
    (leere Liste loest alle Links). Obergrenze schuetzt vor Riesen-Arrays.
    """

    model_config = ConfigDict(extra="forbid")

    links: list[ResourceLinkItem] = Field(default_factory=list, max_length=200)


class ResourceLinkRead(BaseModel):
    """Ein aufgeloester Block-Ref inkl. Verfuegbarkeit + Vorschau (Ausgabe)."""

    model_config = ConfigDict(from_attributes=True)

    resource_id: UUID
    resource_name: str
    block_id: str
    position: int
    available: bool
    preview: str | None = None
