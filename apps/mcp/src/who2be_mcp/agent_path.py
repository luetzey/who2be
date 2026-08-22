"""Agent-spezifische Connector-URL im Pfad: `{http_path}/a/{agent_uuid}` (Issue #404).

Warum im Pfad statt als Query (`?agent=...`): Der LLM-Client setzt den
RFC-8707-`resource`-Parameter auf die Resource aus der RFC-9728-Protected-
Resource-Metadata (PRM). Dabei faellt eine Query weg — der Pfad ist Teil der
Resource-Identitaet und ueberlebt. Die API bindet den Agenten beim
OAuth-Consent aus diesem Pfad.

Damit `…/mcp/a/{uuid}` trotzdem vom bereits registrierten, kanonischen
MCP-Route-Handler bedient wird, schreibt `AgentPathMiddleware` den Pfad VOR
dem Routing auf `{http_path}` um und korrigiert auf dem Rueckweg genau einen
Wert: den `resource_metadata`-Parameter im `WWW-Authenticate`-Header einer
401-Antwort (FastMCP setzt dort fest die kanonische PRM-URL). Die
agent-spezifische PRM liefert `build_agent_prm_route`.

Sicherheitsrahmen: Die UUID aus dem Pfad ist ein Hinweis fuer den
OAuth-Consent der API, kein Vertrauensanker. Hier faellt keine
Autorisierungsentscheidung, es wird kein anderer Header angefasst, und die
UUID wird nur nach syntaktischer Validierung in eine URL interpoliert.
"""

from __future__ import annotations

import re
from functools import lru_cache

from mcp.server.auth.handlers.metadata import ProtectedResourceMetadataHandler
from mcp.server.auth.routes import build_resource_metadata_url, cors_middleware
from mcp.shared.auth import ProtectedResourceMetadata
from pydantic import AnyHttpUrl
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from who2be_models.agent_uuid import AGENT_UUID_PATTERN, is_canonical_agent_uuid

#: Pfad-Segment vor der Agent-UUID — kurz gehalten, weil die Connector-URL
#: manuell in Client-UIs eingetragen wird.
AGENT_SEGMENT = "a"

# Kanonische 8-4-4-4-12-Hex-Form, geteilt mit der OAuth-Seite
# (`who2be_models.agent_uuid`) — Begruendung fuer die Striktheit dort. `_UUID_PATTERN`
# bleibt hier als Alias, weil `_agent_path_re` das rohe (unverankerte) Muster
# zum Einbetten in den Pfad-Regex braucht.
_UUID_PATTERN = AGENT_UUID_PATTERN
_RESOURCE_METADATA_RE = re.compile(rb'resource_metadata="[^"]*"')


def is_agent_id(value: str) -> bool:
    """`True`, wenn `value` eine UUID in kanonischer Schreibweise ist."""
    return is_canonical_agent_uuid(value)


@lru_cache(maxsize=8)
def _agent_path_re(http_path: str) -> re.Pattern[str]:
    """Kompiliert `^{http_path}/a/(uuid)$` — pro Prozess gibt es genau einen Pfad."""
    base = http_path.rstrip("/")
    return re.compile(rf"^{re.escape(base)}/{AGENT_SEGMENT}/({_UUID_PATTERN})$")


def parse_agent_id(path: str, http_path: str) -> str | None:
    """Zieht die Agent-UUID aus `{http_path}/a/{uuid}`.

    `None` fuer den kanonischen Pfad, kaputte/fehlende UUIDs, zusaetzliche
    Segmente und Trailing-Slash-Reste — der Anker `$` macht das strikt.
    Die UUID wird nicht normalisiert, damit die advertisierte Resource exakt
    der angefragten URL entspricht (RFC-8707-Vergleich ist String-Vergleich).
    """
    match = _agent_path_re(http_path).match(path)
    return match.group(1) if match else None


def agent_resource_url(mcp_public_url: str, http_path: str, agent_id: str) -> str:
    """Agent-spezifische Resource `{mcp_public_url}{http_path}/a/{agent_id}`."""
    if not is_agent_id(agent_id):
        raise ValueError("agent_id ist keine kanonische UUID")
    return f"{mcp_public_url.rstrip('/')}{http_path.rstrip('/')}/{AGENT_SEGMENT}/{agent_id}"


def agent_prm_url(mcp_public_url: str, http_path: str, agent_id: str) -> str:
    """PRM-URL zur agent-spezifischen Resource (RFC 9728 §3.1, SDK-Helfer)."""
    resource = agent_resource_url(mcp_public_url, http_path, agent_id)
    return str(build_resource_metadata_url(AnyHttpUrl(resource)))


def _with_agent_prm(message: Message, prm_url: str) -> Message:
    """Ersetzt in einer 401-Antwort nur `resource_metadata="…"` im WWW-Authenticate."""
    if message.get("type") != "http.response.start" or message.get("status") != 401:
        return message
    headers: list[tuple[bytes, bytes]] = list(message.get("headers") or [])
    replacement = f'resource_metadata="{prm_url}"'.encode()
    patched: list[tuple[bytes, bytes]] = []
    changed = False
    for name, value in headers:
        if name.lower() == b"www-authenticate":
            # Lambda statt Template-String: kein Backslash-/Gruppen-Escaping im Ersatz.
            new_value, count = _RESOURCE_METADATA_RE.subn(lambda _m: replacement, value, count=1)
            if count:
                patched.append((name, new_value))
                changed = True
                continue
        patched.append((name, value))
    if not changed:
        return message
    return {**message, "headers": patched}


class AgentPathMiddleware:
    """Mappt `{http_path}/a/{uuid}` auf den kanonischen MCP-Endpoint.

    Inbound wird `scope["path"]` (und `raw_path`) auf `{http_path}` umgeschrieben,
    damit das bestehende Routing greift; outbound wird die 401-PRM-URL auf die
    agent-spezifische Variante gezogen. Alle anderen Requests — inklusive
    `lifespan`/`websocket` und dem kanonischen Pfad — gehen unveraendert durch.
    """

    def __init__(self, app: ASGIApp, *, http_path: str, mcp_public_url: str) -> None:
        self.app = app
        self._http_path = http_path
        self._mcp_public_url = mcp_public_url

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        agent_id = parse_agent_id(scope.get("path", ""), self._http_path)
        if agent_id is None:
            await self.app(scope, receive, send)
            return

        # Pro Request kopieren, nie auf der Instanz merken — die Middleware
        # bedient nebenlaeufige Requests mit unterschiedlichen Agenten.
        rewritten: Scope = dict(scope)
        rewritten["path"] = self._http_path
        if rewritten.get("raw_path") is not None:
            rewritten["raw_path"] = self._http_path.encode("ascii")
        prm_url = agent_prm_url(self._mcp_public_url, self._http_path, agent_id)

        async def send_with_agent_prm(message: Message) -> None:
            await send(_with_agent_prm(message, prm_url))

        await self.app(rewritten, receive, send_with_agent_prm)


def build_agent_prm_route(
    *,
    http_path: str,
    mcp_public_url: str,
    authorization_servers: list[AnyHttpUrl],
    scopes_supported: list[str] | None = None,
) -> Route:
    """Agent-spezifische PRM unter `/.well-known/oauth-protected-resource{http_path}/a/{id}`.

    Body und CORS kommen aus dem MCP-SDK (`ProtectedResourceMetadata`,
    `ProtectedResourceMetadataHandler`, `cors_middleware`) — identisch zur
    kanonischen PRM, nur mit agent-spezifischer `resource`. Eine ungueltige
    UUID im Pfad ergibt 404, damit hier keine beliebige Fremdeingabe in eine
    advertisierte Resource-URL wandert.
    """
    path = (
        f"/.well-known/oauth-protected-resource{http_path.rstrip('/')}/{AGENT_SEGMENT}/{{agent_id}}"
    )

    async def handle(request: Request) -> Response:
        agent_id = str(request.path_params.get("agent_id", ""))
        if not is_agent_id(agent_id):
            return JSONResponse({"error": "not_found"}, status_code=404)
        metadata = ProtectedResourceMetadata(
            resource=AnyHttpUrl(agent_resource_url(mcp_public_url, http_path, agent_id)),
            authorization_servers=authorization_servers,
            scopes_supported=scopes_supported,
        )
        return await ProtectedResourceMetadataHandler(metadata).handle(request)

    return Route(
        path,
        endpoint=cors_middleware(handle, ["GET", "OPTIONS"]),
        methods=["GET", "OPTIONS"],
        name="agent_protected_resource_metadata",
    )
