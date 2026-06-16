"""OAuth-Resource-Server-Verifikation fuer den Who2Be-MCP-Server (ADR-0034-Folge).

FastMCP agiert als OAuth-Resource-Server: jeder eingehende Bearer wird VOR dem
Tool-Run introspectiert. Da der Access-Token ein gewoehnlicher Who2Be-`w2b_`-
Token ist (kein selbst-signiertes JWT), validiert der Verifier ihn per
`GET /v1/me` gegen die API — 200 ⇒ gueltig, sonst `None` (FastMCP antwortet dann
401 + `WWW-Authenticate`, das den Client zum Authorization-Server schickt).

`RemoteAuthProvider` liefert zusaetzlich automatisch die RFC-9728-Protected-
Resource-Metadata (`/.well-known/oauth-protected-resource`) mit dem
`authorization_servers`-Pointer auf die Who2Be-API.
"""

from __future__ import annotations

import logging

import httpx
from fastmcp.server.auth import RemoteAuthProvider
from fastmcp.server.auth.auth import AccessToken, TokenVerifier

from who2be_mcp.config import Settings

logger = logging.getLogger(__name__)


class Who2BeTokenVerifier(TokenVerifier):
    """Introspectiert den Bearer gegen `GET /v1/me` der Who2Be-API."""

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self._settings = settings

    async def verify_token(self, token: str) -> AccessToken | None:
        if not token:
            return None
        try:
            async with httpx.AsyncClient(
                base_url=self._settings.api_base_url.rstrip("/"),
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            ) as client:
                response = await client.get("/v1/me")
        except httpx.HTTPError as exc:
            logger.warning("Token-Introspektion fehlgeschlagen: %s", type(exc).__name__)
            return None
        if response.is_error:
            return None
        # Der `w2b_`-Token traegt keine OAuth-Scopes; der serverseitige
        # Agent-Tool-Policy-/Read-Scope ist die eigentliche Autorisierung.
        return AccessToken(token=token, client_id="who2be-connector", scopes=[])


def build_auth_provider(settings: Settings) -> RemoteAuthProvider:
    """`RemoteAuthProvider` fuer den HTTP-Transport (PRM + 401/WWW-Authenticate)."""
    return RemoteAuthProvider(
        token_verifier=Who2BeTokenVerifier(settings),
        authorization_servers=[settings.oauth_issuer_url],  # type: ignore[list-item]
        base_url=settings.mcp_public_url,
    )
