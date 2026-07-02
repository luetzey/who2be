"""Persistenz fuer den OAuth-Authorization-Server (Clients, Codes, Refresh).

SQL + Row-Mapping, keine Geschaeftsregeln. Alle Werte ueber asyncpg-Binding.
Codes und Refresh-Tokens werden nur als sha256-Hash persistiert; die
single-use-Konsumption ist atomar (`UPDATE … WHERE consumed_at IS NULL`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

import asyncpg


@dataclass(frozen=True)
class OAuthClientRow:
    client_id: str
    client_name: str | None
    redirect_uris: list[str]
    token_endpoint_auth_method: str
    grant_types: list[str]


@dataclass(frozen=True)
class AuthorizationCodeRow:
    client_id: str
    redirect_uri: str
    code_challenge: str
    user_id: UUID
    workspace_id: UUID
    agent_id: UUID
    role: str
    resource: str
    scope: str | None


class PgOAuthRepository:
    """asyncpg-Implementierung der OAuth-Persistenz."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # --- Clients (DCR) -----------------------------------------------------

    async def insert_client(
        self, client_id: str, client_name: str | None, redirect_uris: list[str]
    ) -> OAuthClientRow:
        row = await self._pool.fetchrow(
            "INSERT INTO oauth_client (client_id, client_name, redirect_uris) "
            "VALUES ($1, $2, $3) "
            "RETURNING client_id, client_name, redirect_uris, "
            "token_endpoint_auth_method, grant_types",
            client_id,
            client_name,
            redirect_uris,
        )
        return self._client_row(row)

    async def get_client(self, client_id: str) -> OAuthClientRow | None:
        row = await self._pool.fetchrow(
            "SELECT client_id, client_name, redirect_uris, "
            "token_endpoint_auth_method, grant_types "
            "FROM oauth_client WHERE client_id = $1",
            client_id,
        )
        return self._client_row(row) if row is not None else None

    @staticmethod
    def _client_row(row: asyncpg.Record) -> OAuthClientRow:
        return OAuthClientRow(
            client_id=row["client_id"],
            client_name=row["client_name"],
            redirect_uris=list(row["redirect_uris"]),
            token_endpoint_auth_method=row["token_endpoint_auth_method"],
            grant_types=list(row["grant_types"]),
        )

    # --- Authorization Codes ----------------------------------------------

    async def insert_code(
        self,
        code_hash: str,
        client_id: str,
        redirect_uri: str,
        code_challenge: str,
        user_id: UUID,
        workspace_id: UUID,
        agent_id: UUID,
        role: str,
        resource: str,
        scope: str | None,
        expires_at: datetime,
    ) -> None:
        await self._pool.execute(
            "INSERT INTO oauth_authorization_code "
            "(code_hash, client_id, redirect_uri, code_challenge, user_id, "
            " workspace_id, agent_id, role, resource, scope, expires_at) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)",
            code_hash,
            client_id,
            redirect_uri,
            code_challenge,
            user_id,
            workspace_id,
            agent_id,
            role,
            resource,
            scope,
            expires_at,
        )

    async def consume_code(self, code_hash: str) -> AuthorizationCodeRow | None:
        """Atomar konsumieren: nur unverbrauchte, nicht-abgelaufene Codes.

        `None` bei nicht gefunden / abgelaufen / bereits verbraucht (Replay).
        """
        row = await self._pool.fetchrow(
            "UPDATE oauth_authorization_code SET consumed_at = now() "
            "WHERE code_hash = $1 AND consumed_at IS NULL AND expires_at > now() "
            "RETURNING client_id, redirect_uri, code_challenge, user_id, "
            "workspace_id, agent_id, role, resource, scope",
            code_hash,
        )
        if row is None:
            return None
        return AuthorizationCodeRow(
            client_id=row["client_id"],
            redirect_uri=row["redirect_uri"],
            code_challenge=row["code_challenge"],
            user_id=row["user_id"],
            workspace_id=row["workspace_id"],
            agent_id=row["agent_id"],
            role=row["role"],
            resource=row["resource"],
            scope=row["scope"],
        )

    # --- Refresh Tokens ----------------------------------------------------

    async def insert_refresh(
        self,
        token_hash: str,
        api_token_id: UUID,
        client_id: str,
        expires_at: datetime,
        rotated_from: str | None = None,
    ) -> None:
        await self._pool.execute(
            "INSERT INTO oauth_refresh_token "
            "(token_hash, api_token_id, client_id, rotated_from, expires_at) "
            "VALUES ($1, $2, $3, $4, $5)",
            token_hash,
            api_token_id,
            client_id,
            rotated_from,
            expires_at,
        )

    async def consume_refresh(self, token_hash: str) -> tuple[UUID, str] | None:
        """Atomar konsumieren; `(api_token_id, client_id)` oder `None`."""
        row = await self._pool.fetchrow(
            "UPDATE oauth_refresh_token SET consumed_at = now() "
            "WHERE token_hash = $1 AND consumed_at IS NULL AND expires_at > now() "
            "RETURNING api_token_id, client_id",
            token_hash,
        )
        return (row["api_token_id"], row["client_id"]) if row is not None else None

    async def consume_refresh_grace(
        self, token_hash: str, grace: timedelta
    ) -> tuple[UUID, str] | None:
        """Atomar-single-use Grace-Einloesung eines KUERZLICH rotierten Tokens.

        Setzt `grace_consumed_at` GENAU EINMAL und liefert `(api_token_id,
        client_id)`, wenn der Token bereits konsumiert wurde, aber vor <= `grace`,
        noch nicht abgelaufen ist UND der Grace-Retry noch nicht bedient wurde —
        das Signal fuer einen GUTARTIGEN Retry (verlorene Token-Antwort /
        paralleler Refresh), KEIN Replay/Diebstahl.

        `None` sonst (nie konsumiert, ausserhalb Grace, abgelaufen, unbekannt
        ODER Grace bereits eingeloest) — dann greift die Ketten-Revocation. Wie
        `consume_refresh` genau-einmal: der zweite Grace-Versuch fuer denselben
        Token faellt durch, sodass aus einem Race keine unbegrenzte Zahl
        unabhaengiger Ketten-Zweige entstehen kann.
        """
        row = await self._pool.fetchrow(
            "UPDATE oauth_refresh_token SET grace_consumed_at = now() "
            "WHERE token_hash = $1 AND consumed_at IS NOT NULL "
            "AND consumed_at > now() - $2::interval AND expires_at > now() "
            "AND grace_consumed_at IS NULL "
            "RETURNING api_token_id, client_id",
            token_hash,
            grace,
        )
        return (row["api_token_id"], row["client_id"]) if row is not None else None

    async def revoke_api_token(self, api_token_id: UUID) -> None:
        """Widerruft einen einzelnen Access-Token per ID (Rotation)."""
        await self._pool.execute(
            "UPDATE api_token SET revoked_at = now() WHERE id = $1 AND revoked_at IS NULL",
            api_token_id,
        )

    async def revoke_refresh_chain(self, token_hash: str) -> int:
        """Widerruft die GANZE Rotationskette ab `token_hash` (Replay-Mitigation).

        Folgt `rotated_from` vorwaerts (rekursiv) und widerruft die `api_token`-
        Rows aller Glieder — der wiederverwendete Refresh und jeder daraus
        rotierte Nachfolger (= der aktuell aktive Access-Token). Liefert die
        Zahl der betroffenen Rows (0 ⇒ Hash unbekannt, kein echter Replay).
        """
        revoked = await self._pool.fetchval(
            "WITH RECURSIVE chain AS ("
            "  SELECT token_hash, api_token_id FROM oauth_refresh_token"
            "    WHERE token_hash = $1"
            "  UNION ALL"
            "  SELECT r.token_hash, r.api_token_id FROM oauth_refresh_token r"
            "    JOIN chain c ON r.rotated_from = c.token_hash"
            "), revoked AS ("
            "  UPDATE api_token SET revoked_at = now()"
            "    WHERE id IN (SELECT api_token_id FROM chain) AND revoked_at IS NULL"
            "    RETURNING id"
            ") SELECT count(*) FROM revoked",
            token_hash,
        )
        return int(revoked or 0)

    async def token_binding(self, api_token_id: UUID) -> tuple[UUID, UUID, str, UUID] | None:
        """`(workspace_id, owner_id, role, agent_id)` des Access-Tokens.

        Quelle der Bindung fuer den rotierten Nachfolge-Token (Refresh-Grant).
        """
        row = await self._pool.fetchrow(
            "SELECT workspace_id, owner_id, role, agent_id FROM api_token WHERE id = $1",
            api_token_id,
        )
        if row is None or row["agent_id"] is None:
            return None
        return (row["workspace_id"], row["owner_id"], row["role"], row["agent_id"])
