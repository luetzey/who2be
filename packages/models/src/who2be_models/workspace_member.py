"""Pydantic-Modelle fuer Workspace-Mitgliedschaft + Rollen (Phase 2.3-0).

`WorkspaceRole` ist die Single-Source der Rollen-Hierarchie
`admin > editor > viewer` (ADR-0023). Die DB spiegelt sie als CHECK-Constraint
auf `workspace_member.role` (0007) und `workspace_invitation.role` (0017).
Auswertender RBAC-Code (geschaerfte `get_current_workspace`, Member-Endpoints)
folgt in einer spaeteren Phase-2.3-PR.
"""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class WorkspaceRole(StrEnum):
    """Rolle eines Mitglieds in einem Workspace (Hierarchie admin>editor>viewer)."""

    admin = "admin"
    editor = "editor"
    viewer = "viewer"


class WorkspaceMemberRead(BaseModel):
    """Mitgliedschafts-Metadaten (read-only, Spiegel von `workspace_member`)."""

    model_config = ConfigDict(from_attributes=True)

    workspace_id: UUID
    user_id: UUID
    role: WorkspaceRole
    joined_at: datetime


class WorkspaceMemberUpdate(BaseModel):
    """Eingabe fuer `PATCH /v1/workspaces/{ws}/members/{user_id}` — nur `role`."""

    model_config = ConfigDict(extra="forbid")

    role: WorkspaceRole
