"""Geschaeftslogik fuer Workspace-Invitations (Phase 2.3-B).

Erzeugt Einladungen (Token-Klartext nur einmal im Result, in der DB nur der
Hash), listet offene Einladungen, widerruft sie und akzeptiert sie single-use.
Der Mail-Versand via GoTrue ist best-effort — schlaegt er fehl, bleibt die
Invitation gueltig und der Klartext-Token kann manuell geteilt werden.
"""

import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import asyncpg
from fastapi import status

from who2be_api.core.errors import ApiError
from who2be_api.core.security import WorkspaceContext, hash_token
from who2be_api.integrations.gotrue_mailer import send_invitation_email
from who2be_api.repositories.invitation_repository import (
    AcceptResult,
    InvitationRepository,
    PendingInvitation,
    PendingInvitationRepository,
)
from who2be_api.services.audit_service import AuditService
from who2be_models import InvitationCreate, InvitationCreated, InvitationRead

_EXPIRY = timedelta(days=7)


def _new_invitation_token() -> str:
    """Token-Klartext fuer eine Einladung — bewusst ohne `w2b_`-Praefix,
    damit er nie mit einem API-Token verwechselt wird."""
    return secrets.token_urlsafe(32)


class InvitationService:
    """Adapter um das Invitation-Repository plus Mail-Versand."""

    def __init__(
        self,
        invitation_repo: InvitationRepository,
        audit_service: AuditService | None = None,
        pool: asyncpg.Pool | None = None,
    ) -> None:
        self._repo = invitation_repo
        self._audit = audit_service
        self._pool = pool

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
        if self._audit is not None and self._pool is not None:
            await self._audit.record(
                self._pool,
                action="invitation.issued",
                actor_id=ctx.user_id,
                workspace_id=ctx.workspace_id,
                target=invitation.id,
                detail={"role": data.role.value},
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
            raise ApiError(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Einladung nicht gefunden.",
                reason="invitation_not_found",
            )
        if self._audit is not None and self._pool is not None:
            await self._audit.record(
                self._pool,
                action="invitation.revoked",
                actor_id=ctx.user_id,
                workspace_id=ctx.workspace_id,
                target=invitation_id,
            )

    async def accept(self, token: str, user_id: UUID, jwt_email: str | None) -> UUID:
        """Akzeptiert eine Einladung single-use; gibt die `workspace_id` zurueck.

        404, wenn der Token unbekannt ist; 410 Gone, wenn die Einladung bereits
        akzeptiert, widerrufen oder abgelaufen ist; 403, wenn `jwt_email` fehlt
        (`invitation_email_required`) oder nicht zur Invitation-Email passt
        (`invitation_email_mismatch`). Der Klick muss vom eingeladenen Account
        kommen, und das laesst sich nur mit Email-Claim belegen — deshalb
        fail-closed und ohne Default fuer `jwt_email`.
        """
        result = await self._repo.accept(hash_token(token), user_id, jwt_email)
        return _accepted_workspace(result)


def _accepted_workspace(result: AcceptResult) -> UUID:
    """HTTP-Abbildung eines Accept-Ergebnisses — fuer beide Annahmewege gleich.

    Geteilter Link (Token) und Annahme per Klick (ID) laufen ueber dieselbe
    Repository-Transaktion; dieselbe Abbildung haelt ihre Antworten gleich.
    """
    if result.status == "not_found":
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Einladung nicht gefunden.",
            reason="invitation_not_found",
        )
    if result.status == "gone":
        # Ein Grund fuer alle drei Endzustaende (akzeptiert/widerrufen/
        # abgelaufen) — genau wie `detail`, das sie schon heute nicht
        # unterscheidet: welcher es war, ist fuer den Eingeladenen
        # gleichbedeutend und fuer einen Fremden eine Information zu viel.
        raise ApiError(
            status_code=status.HTTP_410_GONE,
            detail="Einladung ist nicht mehr gueltig.",
            reason="invitation_no_longer_valid",
        )
    if result.status == "email_required":
        raise ApiError(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Diese Einladung laesst sich nur mit einem Konto annehmen, "
                "das eine bestaetigte Email-Adresse traegt."
            ),
            reason="invitation_email_required",
        )
    if result.status == "email_mismatch":
        raise ApiError(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Diese Einladung ist fuer eine andere Email-Adresse.",
            reason="invitation_email_mismatch",
        )
    assert result.workspace_id is not None
    return result.workspace_id


class PendingInvitationService:
    """Offene Einladungen fuer die E-Mail-Adresse des eingeloggten Kontos.

    Kontoweit (ohne Workspace) und deshalb neben `InvitationService` statt
    darin: dessen Repository-Vertrag bleibt workspace-gebunden.
    """

    def __init__(self, repo: PendingInvitationRepository) -> None:
        self._repo = repo

    async def list_for_account(
        self, user_id: UUID, jwt_email: str | None
    ) -> list[PendingInvitation]:
        """Ohne Token gibt es nur noch das Konto als Beleg fuer den Besitz der
        Adresse — deshalb erst nach bestaetigter Adresse: 403
        `invitation_email_required` ohne `email`-Claim, 403
        `invitation_email_unconfirmed`, wenn GoTrue die Adresse des Kontos nicht
        bestaetigt hat oder der Claim nicht die Kontoadresse ist (fail-closed).
        """
        email = await self._confirmed_address(
            user_id,
            jwt_email,
            required=(
                "Offene Einladungen gibt es nur fuer ein Konto, "
                "das eine bestaetigte Email-Adresse traegt."
            ),
            unconfirmed=(
                "Offene Einladungen sind erst sichtbar, wenn die Email-Adresse "
                "des Kontos bestaetigt ist."
            ),
        )
        return await self._repo.list_pending_for_email(email)

    async def accept_for_account(
        self, invitation_id: UUID, user_id: UUID, jwt_email: str | None
    ) -> UUID:
        """Nimmt die Einladung `invitation_id` per Klick an; gibt die
        `workspace_id` zurueck.

        Dieselbe Bestaetigungspruefung wie `list_for_account` (403), dann:
        lautet die Einladung nicht auf die Kontoadresse oder gibt es sie nicht,
        404 `invitation_not_found` — beides gleich, kein Existenz-Orakel.
        Angenommen wird ueber dieselbe Repository-Transaktion wie beim
        geteilten Link, deshalb auch dieselben Antworten (410 fuer
        angenommen/widerrufen/abgelaufen).
        """
        email = await self._confirmed_address(
            user_id,
            jwt_email,
            required=(
                "Diese Einladung laesst sich nur mit einem Konto annehmen, "
                "das eine bestaetigte Email-Adresse traegt."
            ),
            unconfirmed=(
                "Einladungen lassen sich erst annehmen, wenn die Email-Adresse "
                "des Kontos bestaetigt ist."
            ),
        )
        invitation = await self._repo.find_for_account(invitation_id, email)
        if invitation is None:
            raise ApiError(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Einladung nicht gefunden.",
                reason="invitation_not_found",
            )
        result = await self._repo.accept(invitation.token_hash, user_id, email)
        return _accepted_workspace(result)

    async def _confirmed_address(
        self, user_id: UUID, jwt_email: str | None, *, required: str, unconfirmed: str
    ) -> str:
        """Die bestaetigte Adresse des Kontos — oder 403 (fail-closed)."""
        if jwt_email is None:
            raise ApiError(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=required,
                reason="invitation_email_required",
            )
        account = await self._repo.self_account_email(user_id)
        if (
            not account.confirmed
            or account.email is None
            or account.email.lower() != jwt_email.lower()
        ):
            raise ApiError(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=unconfirmed,
                reason="invitation_email_unconfirmed",
            )
        return account.email
