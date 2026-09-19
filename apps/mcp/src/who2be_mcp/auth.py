"""OAuth-Resource-Server-Verifikation fuer den Who2Be-MCP-Server (ADR-0034-Folge).

FastMCP agiert als OAuth-Resource-Server: jeder eingehende Bearer wird VOR dem
Tool-Run introspectiert. Da der Access-Token ein gewoehnlicher Who2Be-`w2b_`-
Token ist (kein selbst-signiertes JWT), validiert der Verifier ihn per
`GET /v1/me` gegen die API — 200 ⇒ gueltig, sonst `None` (FastMCP antwortet dann
401 + `WWW-Authenticate`, das den Client zum Authorization-Server schickt).

`RemoteAuthProvider` liefert zusaetzlich automatisch die RFC-9728-Protected-
Resource-Metadata (`/.well-known/oauth-protected-resource`) mit dem
`authorization_servers`-Pointer auf die Who2Be-API. Dieser Pointer IST der
Issuer-Identifier, den der Client anschliessend gegen den `issuer` der
AS-Metadaten haelt — deshalb wird die PRM hier selbst gerendert
(`Who2BeRemoteAuthProvider`, Begruendung in `prm.py`).
"""

from __future__ import annotations

import logging

import httpx
from fastmcp.server.auth import RemoteAuthProvider
from fastmcp.server.auth.auth import AccessToken, TokenVerifier
from starlette.routing import Route

from who2be_mcp.config import Settings
from who2be_mcp.prm import PRM_PREFIX, build_prm_route
from who2be_models import canonical_issuer

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


class Who2BeRemoteAuthProvider(RemoteAuthProvider):
    """`RemoteAuthProvider`, dessen PRM den Issuer-Identifier unveraendert fuehrt.

    `RemoteAuthProvider.get_routes()` liefert ausschliesslich PRM-Routen. Hier
    werden sie durch Routen mit demselben Pfad, demselben Namen und demselben
    Body ersetzt — nur `authorization_servers` bleibt der konfigurierte String,
    statt durch `AnyHttpUrl` einen Trailing Slash zu bekommen (Begruendung und
    Fehlerbild in `prm.py`). `get_well_known_routes()` filtert `get_routes()`
    und ist damit mit abgedeckt.
    """

    def get_routes(self, mcp_path: str | None = None) -> list[Route]:
        routes = super().get_routes(mcp_path)
        resource_url = self._get_resource_url(mcp_path)
        if resource_url is None:
            return routes
        scopes_supported = (
            self._scopes_supported
            if self._scopes_supported is not None
            else self.token_verifier.scopes_supported
        )
        return [
            build_prm_route(
                path=route.path,
                name=route.name,
                resource=str(resource_url),
                authorization_servers=self.authorization_servers,
                scopes_supported=scopes_supported,
            )
            if route.path.startswith(PRM_PREFIX)
            else route
            for route in routes
        ]


def build_auth_provider(settings: Settings) -> Who2BeRemoteAuthProvider:
    """`RemoteAuthProvider` fuer den HTTP-Transport (PRM + 401/WWW-Authenticate)."""
    return Who2BeRemoteAuthProvider(
        token_verifier=Who2BeTokenVerifier(settings),
        # Kanonisch: exakt der String, den die API als `issuer` ihrer
        # AS-Metadaten fuehrt. Beide Seiten ziehen ihn aus `canonical_issuer`,
        # damit der String-Vergleich des Clients nicht an einer Schreibweise
        # scheitert.
        authorization_servers=[canonical_issuer(settings.oauth_issuer_url)],  # type: ignore[list-item]
        base_url=settings.mcp_public_url,
    )
