"""Pydantic-Modelle fuer Workspace-Invitations (Phase 2.3-0).

Spiegel der `workspace_invitation`-Tabelle aus
`apps/api/src/who2be_api/migrations/0017_workspace_invitation.sql`. Der
Klartext-Token taucht NUR im Accept-Request (`InvitationAccept`) auf; in der
DB liegt ausschliesslich der Hash, und `InvitationRead` gibt ihn nie zurueck
(ADR-0006/0023). Auswertender Code (Invite-/Accept-Endpoints, Mail-Versand)
folgt in einer spaeteren Phase-2.3-PR.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr

from who2be_models.workspace_member import WorkspaceRole


class InvitationCreate(BaseModel):
    """Eingabe fuer `POST /v1/workspaces/{ws}/invitations`."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    role: WorkspaceRole


class InvitationRead(BaseModel):
    """Invitation-Metadaten — ohne token_hash und ohne Klartext-Token."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    role: WorkspaceRole
    expires_at: datetime
    created_at: datetime


class InvitationCreated(InvitationRead):
    """Antwort auf `POST /v1/workspaces/{ws}/invitations`.

    Enthaelt den Klartext-Token genau einmal — der Caller versendet den
    Mail-Link bzw. teilt ihn manuell. Persistiert wird nur der Hash.
    """

    token: str


class InvitationAccept(BaseModel):
    """Eingabe fuer `POST /v1/invitations/{token}/accept`.

    Traegt den Klartext-Token aus der Einladungs-Mail; der Server vergleicht
    dessen Hash gegen `workspace_invitation.token_hash`.
    """

    model_config = ConfigDict(extra="forbid")

    token: str
