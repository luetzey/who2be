"""Geschaeftslogik fuer Workspace-Invitations (Phase 2.3-B).

Erzeugt Einladungen (Token-Klartext nur einmal im Result, in der DB nur der
Hash), listet offene Einladungen, widerruft sie und akzeptiert sie single-use.
Der Mail-Versand via GoTrue ist best-effort — schlaegt er fehl, bleibt die
Invitation gueltig und der Klartext-Token kann manuell geteilt werden.
"""

import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status

from who2be_api.core.security import WorkspaceContext, hash_token
from who2be_api.integrations.gotrue_mailer import send_invitation_email
from who2be_api.repositories.invitation_repository import InvitationRepository
from who2be_models import InvitationCreate, InvitationCreated, InvitationRead

_EXPIRY = timedelta(days=7)


def _new_invitation_token() -> str:
    """Token-Klartext fuer eine Einladung — bewusst ohne `w2b_`-Praefix,
    damit er nie mit einem API-Token verwechselt wird."""
    return secrets.token_urlsafe(32)


class InvitationService:
    """Adapter um das Invitation-Repository plus Mail-Versand."""

    def __init__(self, invitation_repo: InvitationRepository) -> None:
        self._repo = invitation_repo

    async def create(self, ctx: WorkspaceContext, data: InvitationCreate) -> InvitationCreated:
        plaintext = _new_invitation_token()
        expires_at = datetime.now(UTC) + _EXPIRY
        invitation = await self._repo.create(
            ctx.workspace_id,
            data.email,
            data.role,
            hash_token(plaintext),
            expires_at,
            ctx.user_id,
        )
        # Best-effort: ein Mail-Fehler darf die (persistierte) Invitation nicht
        # kippen — der Klartext-Token kommt ohnehin im Result zurueck.
        await send_invitation_email(data.email, plaintext)
        return InvitationCreated(**invitation.model_dump(), token=plaintext)

    async def list_pending(self, ctx: WorkspaceContext) -> list[InvitationRead]:
        return await self._repo.list_pending_by_workspace(ctx.workspace_id)

    async def revoke(self, ctx: WorkspaceContext, invitation_id: UUID) -> None:
        revoked = await self._repo.revoke(ctx.workspace_id, invitation_id)
        if not revoked:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Einladung nicht gefunden.",
            )

    async def accept(self, token: str, user_id: UUID, jwt_email: str | None = None) -> UUID:
        """Akzeptiert eine Einladung single-use; gibt die `workspace_id` zurueck.

        404, wenn der Token unbekannt ist; 410 Gone, wenn die Einladung bereits
        akzeptiert, widerrufen oder abgelaufen ist; 403, wenn `jwt_email`
        gesetzt ist und nicht zur Invitation-Email passt (Phase 3-D Magic-Link-
        Schutz — der Klick muss vom eingeladenen Account kommen).
        """
        result = await self._repo.accept(hash_token(token), user_id, jwt_email)
        if result.status == "not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Einladung nicht gefunden.",
            )
        if result.status == "gone":
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Einladung ist nicht mehr gueltig.",
            )
        if result.status == "email_mismatch":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Diese Einladung ist fuer eine andere Email-Adresse.",
            )
        assert result.workspace_id is not None
        return result.workspace_id
