"""Persistenz fuer `workspace_invitation` (Phase 2.3-B).

Einladungen tragen in der DB **nur** den SHA-256-Hash des Tokens (ADR-0006/
0023); der Klartext geht ausschliesslich per Mail bzw. einmalig im 201-Body
raus. `accept` ist single-use und laeuft in einer Transaktion: Zustand pruefen,
`workspace_member` setzen, `accepted_at` stempeln — alles oder nichts.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

import asyncpg

from who2be_api.core.tenancy import scope_to_self
from who2be_models import InvitationRead, WorkspaceRole

_READ_COLUMNS = "id, email, role, expires_at, created_at"


@dataclass(frozen=True)
class SelfAccountEmail:
    """E-Mail-Adresse des eigenen Kontos und ob GoTrue sie bestaetigt hat."""

    email: str | None
    confirmed: bool


@dataclass(frozen=True)
class PendingInvitation:
    """Offene Einladung fuer die E-Mail-Adresse eines Kontos.

    Traegt `token_hash` nur intern: die Annahme per Klick (S2b A2) nimmt die
    Einladung ueber denselben Weg an wie der geteilte Link. Nach aussen geht
    der Datensatz nur ueber ein Antwortmodell ohne dieses Feld.
    """

    id: UUID
    workspace_id: UUID
    workspace_name: str
    role: WorkspaceRole
    expires_at: datetime
    created_at: datetime
    token_hash: str


@dataclass(frozen=True)
class AcceptResult:
    """Ergebnis eines Accept-Versuchs.

    `status` unterscheidet die HTTP-Mappings im Service: `not_found` → 404,
    `gone` (akzeptiert/widerrufen/abgelaufen) → 410,
    `email_required` (Aufrufer bringt keine Email mit) → 403,
    `email_mismatch` (JWT-Email passt nicht zur Invitation-Email) → 403,
    `accepted` → 200 mit `workspace_id`.
    """

    status: Literal["not_found", "gone", "email_required", "email_mismatch", "accepted"]
    workspace_id: UUID | None = None


class InvitationRepository(Protocol):
    """Service-seitige Abstraktion fuer den Invitation-Zugriff."""

    async def create(
        self,
        workspace_id: UUID,
        email: str,
        role: WorkspaceRole,
        token_hash: str,
        expires_at: datetime,
        created_by: UUID,
    ) -> InvitationRead: ...

    async def list_pending_by_workspace(self, workspace_id: UUID) -> list[InvitationRead]: ...

    async def self_account_email(self, user_id: UUID) -> SelfAccountEmail: ...

    async def list_pending_for_email(self, email: str) -> list[PendingInvitation]: ...

    async def accept(
        self, token_hash: str, user_id: UUID, expected_email: str | None = None
    ) -> AcceptResult: ...

    async def revoke(self, workspace_id: UUID, invitation_id: UUID) -> bool: ...


class PgInvitationRepository:
    """asyncpg-Implementierung von `InvitationRepository`."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create(
        self,
        workspace_id: UUID,
        email: str,
        role: WorkspaceRole,
        token_hash: str,
        expires_at: datetime,
        created_by: UUID,
    ) -> InvitationRead:
        row = await self._pool.fetchrow(
            "INSERT INTO workspace_invitation "
            "(workspace_id, email, role, token_hash, expires_at, created_by) "
            "VALUES ($1, $2, $3, $4, $5, $6) "
            f"RETURNING {_READ_COLUMNS}",
            workspace_id,
            email,
            role.value,
            token_hash,
            expires_at,
            created_by,
        )
        return InvitationRead.model_validate(dict(row))

    async def list_pending_by_workspace(self, workspace_id: UUID) -> list[InvitationRead]:
        rows = await self._pool.fetch(
            f"SELECT {_READ_COLUMNS} FROM workspace_invitation "
            "WHERE workspace_id = $1 AND accepted_at IS NULL "
            "AND revoked_at IS NULL AND expires_at > now() "
            "ORDER BY created_at DESC, id DESC",
            workspace_id,
        )
        return [InvitationRead.model_validate(dict(row)) for row in rows]

    async def self_account_email(self, user_id: UUID) -> SelfAccountEmail:
        """Liest Adresse und Bestaetigung des eigenen Kontos.

        Ueber `w2b_self_account()` (Migrationen 0093/0094): die Laufzeitrolle
        liest `auth.users` nicht direkt, die Funktion liefert nur die Zeile von
        `app.current_user_id` — `scope_to_self` setzt die GUC
        transaktionslokal. Keine Zeile gilt als unbestaetigt (fail-closed).
        """
        async with self._pool.acquire() as conn, conn.transaction():
            await scope_to_self(conn, user_id)
            row = await conn.fetchrow("SELECT email, email_confirmed FROM w2b_self_account()")
        if row is None:
            return SelfAccountEmail(email=None, confirmed=False)
        return SelfAccountEmail(email=row["email"], confirmed=bool(row["email_confirmed"]))

    async def list_pending_for_email(self, email: str) -> list[PendingInvitation]:
        """Offene Einladungen fuer `email` ueber alle Workspaces.

        Gross-/Kleinschreibung zaehlt nicht, wie beim Abgleich in `accept`.
        Offen heisst: nicht angenommen, nicht widerrufen, nicht abgelaufen.
        """
        rows = await self._pool.fetch(
            "SELECT i.id, i.workspace_id, w.name AS workspace_name, i.role, "
            "i.expires_at, i.created_at, i.token_hash "
            "FROM workspace_invitation i JOIN workspace w ON w.id = i.workspace_id "
            "WHERE lower(i.email) = lower($1) AND i.accepted_at IS NULL "
            "AND i.revoked_at IS NULL AND i.expires_at > now() "
            "ORDER BY i.created_at DESC, i.id DESC",
            email,
        )
        return [
            PendingInvitation(
                id=row["id"],
                workspace_id=row["workspace_id"],
                workspace_name=row["workspace_name"],
                role=WorkspaceRole(row["role"]),
                expires_at=row["expires_at"],
                created_at=row["created_at"],
                token_hash=row["token_hash"],
            )
            for row in rows
        ]

    async def accept(
        self, token_hash: str, user_id: UUID, expected_email: str | None = None
    ) -> AcceptResult:
        async with self._pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                "SELECT workspace_id, role, email, accepted_at, revoked_at, expires_at "
                "FROM workspace_invitation WHERE token_hash = $1 FOR UPDATE",
                token_hash,
            )
            if row is None:
                return AcceptResult(status="not_found")
            if (
                row["accepted_at"] is not None
                or row["revoked_at"] is not None
                or row["expires_at"] <= datetime.now(row["expires_at"].tzinfo)
            ):
                return AcceptResult(status="gone")
            # Die Einladung gilt einer Email-Adresse; angenommen wird sie nur
            # von einem Konto, das genau diese Adresse belegt (JWT-Claim).
            # Fail-closed: ohne Email kein Abgleich, also keine Annahme — sonst
            # entschiede allein der Besitz des Tokens. Vergleich
            # case-insensitive; die Invitation bleibt in beiden Faellen offen.
            if expected_email is None:
                return AcceptResult(status="email_required")
            if expected_email.lower() != row["email"].lower():
                return AcceptResult(status="email_mismatch")
            # Mitgliedschaft setzen; ein bereits bestehender Member behaelt
            # seine Rolle (DO NOTHING) — der Accept bleibt dennoch single-use.
            await conn.execute(
                "INSERT INTO workspace_member (workspace_id, user_id, role) "
                "VALUES ($1, $2, $3) "
                "ON CONFLICT (workspace_id, user_id) DO NOTHING",
                row["workspace_id"],
                user_id,
                row["role"],
            )
            await conn.execute(
                "UPDATE workspace_invitation SET accepted_at = now() WHERE token_hash = $1",
                token_hash,
            )
        return AcceptResult(status="accepted", workspace_id=row["workspace_id"])

    async def revoke(self, workspace_id: UUID, invitation_id: UUID) -> bool:
        result = await self._pool.execute(
            "UPDATE workspace_invitation SET revoked_at = now() "
            "WHERE id = $1 AND workspace_id = $2 "
            "AND accepted_at IS NULL AND revoked_at IS NULL",
            invitation_id,
            workspace_id,
        )
        return bool(result == "UPDATE 1")
