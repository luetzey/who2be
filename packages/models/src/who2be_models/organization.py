"""Pydantic-Modelle fuer das Organization-Aggregat (TASK-301).

Eine Organization ist die erste Stufe der Tenant-Hierarchie
(User -> org_member -> organization -> workspace). `kind` unterscheidet
auto-angelegte Personal-Orgs vom expliziten Company-Mandant.
"""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

OrgNameStr = Annotated[str, StringConstraints(min_length=1, max_length=200)]
OrgSlugStr = Annotated[str, StringConstraints(min_length=1, max_length=64)]


class OrganizationCreate(BaseModel):
    """Eingabe fuer `POST /v1/organizations` (immer `kind='company'`)."""

    model_config = ConfigDict(extra="forbid")

    name: OrgNameStr
    slug: OrgSlugStr


class OrganizationRead(BaseModel):
    """Organization-Metadaten."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    kind: Literal["personal", "company"]
    created_at: datetime
