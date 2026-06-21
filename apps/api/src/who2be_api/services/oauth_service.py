"""Geschaeftslogik des OAuth-2.1-Authorization-Servers (Remote-MCP-Connector).

Flow: DCR (`register`) → `authorize` (PKCE+Resource-Validierung → signierter
Request-Blob → Web-Consent) → `consent` (User-Login + Agent-Wahl → Auth-Code) →
`token` (Code-Exchange mit PKCE → agent-gebundener `w2b_`-Access-Token + Refresh).

Der Access-Token ist ein gewoehnlicher `api_token` mit `expires_at`; der
MCP-Resource-Server validiert ihn wie jeden Bearer (`/v1/me`). Refresh-Tokens
rotieren; ein wiederverwendeter Refresh widerruft die ganze Token-Kette.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode, urlparse, urlunparse
from uuid import UUID

import asyncpg

from who2be_api.core.config import get_settings
from who2be_api.core.security import hash_token, new_token
from who2be_api.core.tenancy import tenant_scope
from who2be_api.repositories.oauth_repository import PgOAuthRepository
from who2be_api.repositories.token_repository import TokenRepository
from who2be_api.services.audit_service import AuditService
from who2be_models import (
    OAuthClientRegistered,
    OAuthClientRegistration,
    OAuthTokenResponse,
    WorkspaceRole,
)

# 8 h: lange genug, dass interaktive Connector-Sessions (Claude/ChatGPT) nicht
# am Refresh-Fenster in transiente 401 laufen; der Refresh-Token rotiert weiter.
_ACCESS_TTL = timedelta(hours=8)
_REFRESH_TTL = timedelta(days=30)
_CODE_TTL = timedelta(seconds=60)
_REQUEST_BLOB_TTL = 600  # s


class OAuthError(Exception):
    """OAuth-Fehler, der als JSON (400/401) zurueckgeht — KEIN Redirect."""

    def __init__(self, error: str, description: str | None = None, status_code: int = 400) -> None:
        super().__init__(error)
        self.error = error
        self.description = description
        self.status_code = status_code


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class OAuthService:
    def __init__(
        self,
        oauth_repo: PgOAuthRepository,
        token_repo: TokenRepository,
        pool: asyncpg.Pool,
        audit: AuditService | None = None,
    ) -> None:
        self._oauth = oauth_repo
        self._tokens = token_repo
        self._pool = pool
        self._audit = audit
        self._settings = get_settings()

    # --- signierter Authorize-Request-Blob (Tamper-Schutz Web↔Backend) ------

    def _sign(self, payload: dict[str, object]) -> str:
        body = _b64url(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
        secret = self._settings.jwt_secret.encode()
        sig = _b64url(hmac.new(secret, body.encode(), hashlib.sha256).digest())
        return f"{body}.{sig}"

    def _verify_blob(self, blob: str) -> dict[str, object]:
        body, _, sig = blob.partition(".")
        expected = _b64url(
            hmac.new(self._settings.jwt_secret.encode(), body.encode(), hashlib.sha256).digest()
        )
        if not sig or not hmac.compare_digest(sig, expected):
            raise OAuthError("invalid_request", "Ungueltige Consent-Signatur.")
        payload: dict[str, object] = json.loads(_b64url_decode(body))
        exp = payload.get("exp", 0)
        if not isinstance(exp, int | float) or exp < time.time():
            raise OAuthError("invalid_request", "Consent-Request abgelaufen.")
        return payload

    # --- DCR (RFC 7591) ----------------------------------------------------

    async def register_client(self, data: OAuthClientRegistration) -> OAuthClientRegistered:
        for uri in data.redirect_uris:
            if not _is_allowed_redirect(uri):
                raise OAuthError("invalid_redirect_uri", f"Unzulaessige redirect_uri: {uri}")
        client_id = "oac_" + secrets.token_urlsafe(24)
        row = await self._oauth.insert_client(client_id, data.client_name, data.redirect_uris)
        return OAuthClientRegistered(
            client_id=row.client_id,
            client_name=row.client_name,
            redirect_uris=row.redirect_uris,
            token_endpoint_auth_method=row.token_endpoint_auth_method,
            grant_types=row.grant_types,
        )

    # --- authorize → Consent-Redirect -------------------------------------

    async def authorize_to_consent_url(
        self,
        client_id: str,
        redirect_uri: str,
        response_type: str,
        code_challenge: str,
        code_challenge_method: str,
        state: str | None,
        resource: str,
        scope: str | None,
    ) -> str:
        """Validiert den Authorize-Request und liefert die Consent-Redirect-URL.

        Open-Redirect-Choke-Point: bei unbekanntem Client / nicht gewhitelisteter
        redirect_uri wird HART abgelehnt (OAuthError → 400), NIE redirected.
        """
        client = await self._oauth.get_client(client_id)
        if client is None:
            raise OAuthError("invalid_client", "Unbekannter client_id.")
        if redirect_uri not in client.redirect_uris:
            raise OAuthError("invalid_request", "redirect_uri nicht registriert.")
        if response_type != "code":
            raise OAuthError("unsupported_response_type", "Nur response_type=code.")
        if code_challenge_method != "S256" or not code_challenge:
            raise OAuthError("invalid_request", "PKCE S256 erforderlich.")
        if resource != self._settings.mcp_resource_url:
            raise OAuthError("invalid_target", "resource passt nicht zum MCP-Server.")
        blob = self._sign(
            {
                "client_id": client_id,
                "client_name": client.client_name,
                "redirect_uri": redirect_uri,
                "code_challenge": code_challenge,
                "state": state,
                "resource": resource,
                "scope": scope,
                "exp": time.time() + _REQUEST_BLOB_TTL,
            }
        )
        return f"{self._settings.oauth_consent_url}?{urlencode({'request': blob})}"

    # --- consent (User eingeloggt) → Auth-Code ----------------------------

    async def consent(self, user_id: UUID, request_blob: str, agent_id: UUID, approve: bool) -> str:
        payload = self._verify_blob(request_blob)
        redirect_uri = str(payload["redirect_uri"])
        state = payload.get("state")
        state_str = str(state) if state is not None else None
        if not approve:
            return _redirect_with(redirect_uri, {"error": "access_denied"}, state_str)

        # Defense-in-depth: die `resource` im (signierten) Blob muss weiterhin zum
        # MCP-Server passen — die RFC-8707-Audience-Kette bleibt geschlossen.
        if str(payload["resource"]) != self._settings.mcp_resource_url:
            raise OAuthError("invalid_target", "resource passt nicht zum MCP-Server.")

        # Agent → Workspace + Rolle, NUR ueber die Memberships des Consent-Users.
        # `agent` ist RLS-isoliert (Migration 0037, strikt auf `app.current_tenant`):
        # ein roher Pool-Read ohne Tenant-Scope liefert in der Cloud 0 Zeilen. Wir
        # pruefen den Agenten je Kandidaten-Workspace UNTER `tenant_scope`
        # (edition-agnostisch, IDOR-fest: nur eigene Workspaces).
        ws_id, role = await self._resolve_agent_membership(user_id, agent_id)
        if ws_id is None or role is None:
            raise OAuthError(
                "access_denied", "Agent nicht in einem deiner Workspaces.", status_code=403
            )

        code = new_token().removeprefix("w2b_")  # eigener Code-Namespace, nicht w2b_
        await self._oauth.insert_code(
            code_hash=hash_token(code),
            client_id=str(payload["client_id"]),
            redirect_uri=redirect_uri,
            code_challenge=str(payload["code_challenge"]),
            user_id=user_id,
            workspace_id=ws_id,
            agent_id=agent_id,
            role=role,
            resource=str(payload["resource"]),
            scope=str(payload["scope"]) if payload.get("scope") is not None else None,
            expires_at=datetime.now(UTC) + _CODE_TTL,
        )
        return _redirect_with(redirect_uri, {"code": code}, state_str)

    async def _resolve_agent_membership(
        self, user_id: UUID, agent_id: UUID
    ) -> tuple[UUID | None, str | None]:
        """`(workspace_id, role)`, falls der Agent in einem Workspace des Users liegt.

        `workspace_member` ist NICHT RLS-isoliert (frei lesbar), `agent` schon —
        daher pro Mitgliedschaft des Users im passenden `tenant_scope` pruefen.
        Liefert `(None, None)`, wenn kein eigener Workspace den Agenten enthaelt.
        """
        memberships = await self._pool.fetch(
            "SELECT workspace_id, role FROM workspace_member WHERE user_id = $1", user_id
        )
        for m in memberships:
            ws_id: UUID = m["workspace_id"]
            async with tenant_scope(ws_id, None):
                found = await self._pool.fetchval(
                    "SELECT 1 FROM agent WHERE id = $1 AND workspace_id = $2", agent_id, ws_id
                )
            if found is not None:
                return ws_id, str(m["role"])
        return None, None

    # --- token: authorization_code ----------------------------------------

    async def exchange_code(
        self, code: str, redirect_uri: str, client_id: str, code_verifier: str
    ) -> OAuthTokenResponse:
        row = await self._oauth.consume_code(hash_token(code))
        if row is None:
            raise OAuthError("invalid_grant", "Code ungueltig, abgelaufen oder verbraucht.")
        if row.client_id != client_id or row.redirect_uri != redirect_uri:
            raise OAuthError("invalid_grant", "Client/redirect_uri stimmen nicht.")
        expected = _b64url(hashlib.sha256(code_verifier.encode()).digest())
        if not hmac.compare_digest(expected, row.code_challenge):
            raise OAuthError("invalid_grant", "PKCE-Verifizierung fehlgeschlagen.")
        return await self._issue(
            workspace_id=row.workspace_id,
            owner_id=row.user_id,
            role=row.role,
            agent_id=row.agent_id,
            client_id=client_id,
            scope=row.scope,
        )

    # --- token: refresh_token (Rotation + Replay-Detection) ---------------

    async def exchange_refresh(self, refresh_token: str, client_id: str) -> OAuthTokenResponse:
        token_hash = hash_token(refresh_token)
        consumed = await self._oauth.consume_refresh(token_hash)
        if consumed is None:
            # Konnte nicht konsumiert werden: bereits verbraucht (Replay),
            # abgelaufen oder unbekannt. Beim Replay haengt am `rotated_from`-
            # Pfad der AKTUELL aktive Access-Token — die ganze Kette killen.
            await self._oauth.revoke_refresh_chain(token_hash)
            raise OAuthError("invalid_grant", "Refresh-Token ungueltig.")
        old_token_id, bound_client = consumed
        if bound_client != client_id:
            raise OAuthError("invalid_grant", "Client stimmt nicht.")
        binding = await self._oauth.token_binding(old_token_id)
        if binding is None:
            raise OAuthError("invalid_grant", "Token-Bindung fehlt.")
        workspace_id, owner_id, _old_role, agent_id = binding
        # Refresh ist ein Re-Authorization-Punkt: aktuelle Membership-Rolle neu
        # aufloesen. Ist der User kein Mitglied mehr (entfernt), verliert der
        # Connector den Zugriff — Kette killen, kein neuer Token. Sonst erbt der
        # neue Access-Token die FRISCHE Rolle (Downgrade wirkt sofort).
        current_role = await self._pool.fetchval(
            "SELECT role FROM workspace_member WHERE workspace_id = $1 AND user_id = $2",
            workspace_id,
            owner_id,
        )
        if current_role is None:
            await self._oauth.revoke_refresh_chain(token_hash)
            await self._oauth.revoke_api_token(old_token_id)
            raise OAuthError("invalid_grant", "Kein Mitglied dieses Workspace mehr.")
        await self._oauth.revoke_api_token(old_token_id)  # Rotation: alten Access widerrufen
        return await self._issue(
            workspace_id=workspace_id,
            owner_id=owner_id,
            role=str(current_role),
            agent_id=agent_id,
            client_id=client_id,
            scope=None,
            rotated_from=token_hash,
        )

    # --- gemeinsamer Mint-Pfad --------------------------------------------

    async def _issue(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        role: str,
        agent_id: UUID,
        client_id: str,
        scope: str | None,
        rotated_from: str | None = None,
    ) -> OAuthTokenResponse:
        client = await self._oauth.get_client(client_id)
        client_name = client.client_name if client else None
        name = f"OAuth: {client_name}" if client_name else "OAuth-Connector"
        access_plain = new_token()
        stored = await self._tokens.insert(
            workspace_id=workspace_id,
            owner_id=owner_id,
            name=name,
            token_hash=hash_token(access_plain),
            role=WorkspaceRole(role),
            agent_id=agent_id,
            expires_at=datetime.now(UTC) + _ACCESS_TTL,
        )
        refresh_plain = secrets.token_urlsafe(32)
        await self._oauth.insert_refresh(
            token_hash=hash_token(refresh_plain),
            api_token_id=stored.id,
            client_id=client_id,
            expires_at=datetime.now(UTC) + _REFRESH_TTL,
            rotated_from=rotated_from,
        )
        if self._audit is not None:
            await self._audit.record(
                self._pool,
                action="token.issued",
                actor_id=owner_id,
                workspace_id=workspace_id,
                target=stored.id,
                detail={"via": "oauth", "client_id": client_id, "agent_id": str(agent_id)},
            )
        return OAuthTokenResponse(
            access_token=access_plain,
            expires_in=int(_ACCESS_TTL.total_seconds()),
            refresh_token=refresh_plain,
            scope=scope,
        )


def _is_allowed_redirect(uri: str) -> bool:
    """https-URL oder localhost/127.0.0.1-Loopback (Claude/ChatGPT-Clients)."""
    try:
        parsed = urlparse(uri)
    except ValueError:
        return False
    if parsed.scheme == "https":
        return bool(parsed.netloc)
    if parsed.scheme == "http":
        return parsed.hostname in ("localhost", "127.0.0.1", "::1")
    return False


def _redirect_with(redirect_uri: str, params: dict[str, str], state: str | None) -> str:
    if state is not None:
        params = {**params, "state": state}
    parsed = urlparse(redirect_uri)
    query = urlencode(params) if not parsed.query else f"{parsed.query}&{urlencode(params)}"
    return urlunparse(parsed._replace(query=query))
