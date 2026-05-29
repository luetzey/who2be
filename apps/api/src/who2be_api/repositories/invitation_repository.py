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

from who2be_models import InvitationRead, WorkspaceRole

_READ_COLUMNS = "id, email, role, expires_at, created_at"


@dataclass(frozen=True)
class AcceptResult:
    """Ergebnis eines Accept-Versuchs.

    `status` unterscheidet die HTTP-Mappings im Service: `not_found` → 404,
    `gone` (akzeptiert/widerrufen/abgelaufen) → 410,
    `email_mismatch` (JWT-Email passt nicht zur Invitation-Email) → 403,
    `accepted` → 200 mit `workspace_id`.
    """

    status: Literal["not_found", "gone", "email_mismatch", "accepted"]
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
            # Phase 3-D: bringt der Aufrufer eine bestaetigte Email mit (JWT-
            # Claim), muss sie zur Invitation-Email passen — sonst koennte ein
            # falsches Konto die Mitgliedschaft uebernehmen. Vergleich
            # case-insensitive; Invitation bleibt offen.
            if expected_email is not None and expected_email.lower() != row["email"].lower():
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
