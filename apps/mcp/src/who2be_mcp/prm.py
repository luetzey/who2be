"""RFC-9728-Protected-Resource-Metadata mit unveraendertem Issuer-Identifier.

Beide PRM-Wege dieses Servers — die kanonische Resource (`auth.py`) und die
agent-spezifische (`agent_path.py`) — rendern ihren Body hier, damit sie
denselben Issuer-String advertisieren.

Warum nicht direkt der SDK-Handler: `ProtectedResourceMetadata.authorization_
servers` ist `list[AnyHttpUrl]`, und Pydantic haengt einer URL OHNE Pfad beim
Validieren ein `/` an. Der Issuer-Identifier wird aber vom LLM-Client per
String-Gleichheit gegen den `issuer` der AS-Metadaten der API gehalten
(RFC 8414 §3.3). Aus `https://api.example.de` wird so `https://api.example.de/`
— und der Connector-Login bricht ab mit:

    Authorization server metadata issuer mismatch:
    https://api.example.de != https://api.example.de/

Das SDK-Modell bleibt trotzdem die Quelle des Bodys (Felder, Defaults und
kuenftige Ergaenzungen kommen von dort); zurechtgerueckt wird danach genau
ein Feld.
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

from who2be_models import canonical_issuer

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
    # Das eine Feld zurechtruecken (s. Modul-Docstring): massgeblich ist die
    # Eingabe, nicht ihre durch `AnyHttpUrl` gelaufene Form.
    body["authorization_servers"] = [
        canonical_issuer(str(server)) for server in authorization_servers
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
