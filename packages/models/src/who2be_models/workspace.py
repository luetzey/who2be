"""Pydantic-Modelle fuer das Workspace-Aggregat (TASK-301).

Zweite Stufe der Tenant-Hierarchie. Ein Workspace haengt an genau einer
Organization; Personae/Playbooks/Tokens leben innerhalb eines Workspaces.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

WorkspaceNameStr = Annotated[str, StringConstraints(min_length=1, max_length=200)]
WorkspaceSlugStr = Annotated[str, StringConstraints(min_length=1, max_length=64)]


class WorkspaceCreate(BaseModel):
    """Eingabe fuer `POST /v1/organizations/{org_id}/workspaces`."""

    model_config = ConfigDict(extra="forbid")

    name: WorkspaceNameStr
    slug: WorkspaceSlugStr


class WorkspaceUpdate(BaseModel):
    """Eingabe fuer `PATCH /v1/workspaces/{id}` — nur `name` aenderbar."""

    model_config = ConfigDict(extra="forbid")

    name: WorkspaceNameStr | None = Field(default=None)


class WorkspaceRead(BaseModel):
    """Workspace-Metadaten."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID
    name: str
    slug: str
    created_at: datetime
