"""Pydantic-Modelle fuer `GET /v1/me` (TASK-301).

Liefert dem Frontend/MCP nach Login alle Memberships + einen Default-
Workspace, damit Web auf `/w/{default_workspace_id}/...` redirecten kann.
"""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class MeWorkspace(BaseModel):
    """Workspace + Rolle des aktuellen Users."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    role: Literal["admin", "editor", "viewer"]


class MeOrganization(BaseModel):
    """Organization + die Workspaces, in denen der User Member ist."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    kind: Literal["personal", "company"]
    workspaces: list[MeWorkspace]


class MeRead(BaseModel):
    """Antwort von `GET /v1/me`."""

    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    default_workspace_id: UUID | None
    organizations: list[MeOrganization]
    # `has_password` ist `False`, solange der User nur per Magic-Link
    # eingeloggt ist (GoTrue-`encrypted_password IS NULL`). Frontend leitet
    # ihn dann beim Invitation-Accept auf `/onboarding/set-password`.
    has_password: bool = False
