"""RFC-9728-Protected-Resource-Metadata mit dem kanonischen Issuer-Identifier.

Beide PRM-Wege dieses Servers — die kanonische Resource (`auth.py`) und die
agent-spezifische (`agent_path.py`) — rendern ihren Body hier, damit sie
denselben Issuer-String advertisieren wie die AS-Metadaten der API.

Warum nicht direkt der SDK-Handler: `ProtectedResourceMetadata.authorization_
servers` ist `list[AnyHttpUrl]`, und was Pydantic beim Validieren mit der URL
macht (Trailing Slash bei leerem Pfad, Kleinschreibung, Default-Port), ist
nicht unsere Entscheidung. Massgeblich ist `issuer_identifier()` — der eine
String, den auch die API fuehrt. Ueber die Leitung geht deshalb genau der,
nicht seine durch das SDK-Modell gelaufene Form.

Das SDK-Modell bleibt trotzdem die Quelle des Bodys (Felder, Defaults und
kuenftige Ergaenzungen kommen von dort); zurechtgerueckt wird danach genau
ein Feld.

Warum der Identifier so aussieht, wie er aussieht — und warum eine
slash-freie Variante den Login NICHT rettet — steht in
`who2be_models.oauth_issuer`.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from mcp.server.auth.routes import cors_middleware
from mcp.shared.auth import ProtectedResourceMetadata
from pydantic import AnyHttpUrl
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from who2be_models import issuer_identifier

#: Pfad-Praefix aller PRM-Routen (RFC 9728 §3.1).
PRM_PREFIX = "/.well-known/oauth-protected-resource"

#: Identisch zum SDK-Handler (`ProtectedResourceMetadataHandler`).
_PRM_HEADERS = {"Cache-Control": "public, max-age=3600"}


def prm_body(
    *,
    resource: str,
    authorization_servers: Sequence[AnyHttpUrl | str],
    scopes_supported: list[str] | None = None,
) -> dict[str, Any]:
    """PRM-Body wie das SDK ihn baut — nur mit kanonischem Issuer-Identifier."""
    metadata = ProtectedResourceMetadata(
        resource=AnyHttpUrl(resource),
        authorization_servers=[AnyHttpUrl(str(server)) for server in authorization_servers],
        scopes_supported=scopes_supported,
    )
    # `exclude_none` wie `PydanticJSONResponse` des SDK — sonst saehe der Body
    # anders aus als bisher.
    body: dict[str, Any] = metadata.model_dump(mode="json", exclude_none=True)
    # Das eine Feld zurechtruecken (s. Modul-Docstring): massgeblich ist
    # `issuer_identifier`, nicht die durch `AnyHttpUrl` gelaufene Form. Die
    # Funktion ist idempotent — der Aufrufer darf sie schon angewandt haben.
    body["authorization_servers"] = [
        issuer_identifier(str(server)) for server in authorization_servers
    ]
    return body


def prm_response(
    *,
    resource: str,
    authorization_servers: Sequence[AnyHttpUrl | str],
    scopes_supported: list[str] | None = None,
) -> Response:
    """Fertige PRM-Antwort inkl. der Cache-Header des SDK-Handlers."""
    return JSONResponse(
        prm_body(
            resource=resource,
            authorization_servers=authorization_servers,
            scopes_supported=scopes_supported,
        ),
        headers=_PRM_HEADERS,
    )


def build_prm_route(
    *,
    path: str,
    resource: str,
    authorization_servers: Sequence[AnyHttpUrl | str],
    scopes_supported: list[str] | None = None,
    name: str | None = None,
) -> Route:
    """PRM-Route fuer eine feste Resource — CORS wie beim SDK (GET + OPTIONS)."""

    async def handle(_request: Request) -> Response:
        return prm_response(
            resource=resource,
            authorization_servers=authorization_servers,
            scopes_supported=scopes_supported,
        )

    return Route(
        path,
        endpoint=cors_middleware(handle, ["GET", "OPTIONS"]),
        methods=["GET", "OPTIONS"],
        name=name,
    )
