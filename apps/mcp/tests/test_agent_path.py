"""Tests fuer die agent-spezifische Connector-URL im Pfad (Issue #404).

`{http_path}/a/{uuid}` muss auf den kanonischen MCP-Endpoint gemappt werden,
die 401-PRM-URL agent-spezifisch zeigen und eine eigene RFC-9728-PRM-Route
liefern — ohne den kanonischen Pfad zu veraendern. Alles laeuft rein
in-process (direkte ASGI-Aufrufe bzw. `TestClient`), ohne Server oder DB.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from who2be_mcp import agent_path, auth
from who2be_mcp.config import Settings

AGENT_ID = "2f1c4d6e-8a90-4b12-9c34-56789abcdef0"
HTTP_PATH = "/mcp"
PUBLIC_URL = "http://mcp.test"


def _settings() -> Settings:
    return Settings(
        api_base_url="http://api.test",
        transport="http",
        oauth_issuer_url="http://api.test",
        mcp_public_url=PUBLIC_URL,
    )


# --- Parser ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        (f"/mcp/a/{AGENT_ID}", AGENT_ID),
        (f"/mcp/a/{AGENT_ID.upper()}", AGENT_ID.upper()),
        ("/mcp", None),
        ("/mcp/", None),
        ("/mcp/a", None),
        ("/mcp/a/", None),
        ("/mcp/a/not-a-uuid", None),
        ("/mcp/a/2f1c4d6e8a904b129c3456789abcdef0", None),
        (f"/mcp/a/{AGENT_ID}/", None),
        (f"/mcp/a/{AGENT_ID}/tools", None),
        (f"/mcp/b/{AGENT_ID}", None),
        (f"/other/a/{AGENT_ID}", None),
        ("/.well-known/oauth-protected-resource/mcp", None),
    ],
)
def test_parse_agent_id(path: str, expected: str | None) -> None:
    assert agent_path.parse_agent_id(path, HTTP_PATH) == expected


def test_agent_resource_url_rejects_invalid_uuid() -> None:
    """Ungeprueft interpolierte Fremdeingabe waere eine gefaelschte Resource-URL."""
    with pytest.raises(ValueError):
        agent_path.agent_resource_url(PUBLIC_URL, HTTP_PATH, "../evil")


def test_prm_url_inserts_well_known_segment() -> None:
    assert agent_path.agent_prm_url(PUBLIC_URL, HTTP_PATH, AGENT_ID) == (
        f"{PUBLIC_URL}/.well-known/oauth-protected-resource/mcp/a/{AGENT_ID}"
    )


# --- Middleware --------------------------------------------------------------


class _Downstream:
    """Minimale ASGI-App: merkt sich das Scope und antwortet konfigurierbar."""

    def __init__(self, status: int = 200, www_authenticate: bytes | None = None) -> None:
        self.status = status
        self.www_authenticate = www_authenticate
        self.scopes: list[dict[str, Any]] = []

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        self.scopes.append(scope)
        if scope["type"] != "http":
            return
        headers: list[tuple[bytes, bytes]] = [(b"content-type", b"application/json")]
        if self.www_authenticate is not None:
            headers.append((b"WWW-Authenticate", self.www_authenticate))
        await send({"type": "http.response.start", "status": self.status, "headers": headers})
        await send({"type": "http.response.body", "body": b"{}"})


def _call(app: Any, scope: dict[str, Any]) -> list[dict[str, Any]]:
    sent: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:  # pragma: no cover - nie abgerufen
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    asyncio.run(app(scope, receive, send))
    return sent


def _http_scope(path: str) -> dict[str, Any]:
    return {
        "type": "http",
        "method": "POST",
        "path": path,
        "raw_path": path.encode(),
        "headers": [],
    }


def _middleware(downstream: _Downstream) -> agent_path.AgentPathMiddleware:
    return agent_path.AgentPathMiddleware(
        downstream, http_path=HTTP_PATH, mcp_public_url=PUBLIC_URL
    )


def test_middleware_rewrites_agent_path_to_canonical() -> None:
    downstream = _Downstream()
    _call(_middleware(downstream), _http_scope(f"/mcp/a/{AGENT_ID}"))

    assert downstream.scopes[0]["path"] == HTTP_PATH
    assert downstream.scopes[0]["raw_path"] == b"/mcp"


def test_middleware_leaves_canonical_path_untouched() -> None:
    downstream = _Downstream()
    scope = _http_scope(HTTP_PATH)
    _call(_middleware(downstream), scope)

    assert downstream.scopes[0] is scope


def test_middleware_leaves_unknown_path_untouched() -> None:
    downstream = _Downstream()
    scope = _http_scope("/mcp/a/kaputt")
    _call(_middleware(downstream), scope)

    assert downstream.scopes[0] is scope


def test_middleware_passes_non_http_scopes_through() -> None:
    downstream = _Downstream()
    scope = {"type": "lifespan"}
    _call(_middleware(downstream), scope)

    assert downstream.scopes == [scope]


def test_middleware_rewrites_resource_metadata_on_401() -> None:
    canonical = (
        b'Bearer error="invalid_token", error_description="Authentication required", '
        b'resource_metadata="http://mcp.test/.well-known/oauth-protected-resource/mcp"'
    )
    downstream = _Downstream(status=401, www_authenticate=canonical)
    sent = _call(_middleware(downstream), _http_scope(f"/mcp/a/{AGENT_ID}"))

    headers = dict(sent[0]["headers"])
    value = headers[b"WWW-Authenticate"].decode()
    assert (
        f'resource_metadata="http://mcp.test/.well-known/oauth-protected-resource'
        f'/mcp/a/{AGENT_ID}"' in value
    )
    # Nur der eine Parameter wird ersetzt, der Rest bleibt woertlich stehen.
    assert 'error="invalid_token"' in value
    assert 'error_description="Authentication required"' in value


def test_middleware_leaves_401_without_resource_metadata_untouched() -> None:
    downstream = _Downstream(status=401, www_authenticate=b'Bearer error="invalid_token"')
    sent = _call(_middleware(downstream), _http_scope(f"/mcp/a/{AGENT_ID}"))

    assert dict(sent[0]["headers"])[b"WWW-Authenticate"] == b'Bearer error="invalid_token"'


def test_middleware_leaves_success_response_untouched() -> None:
    canonical = b'Bearer resource_metadata="http://mcp.test/.well-known/x"'
    downstream = _Downstream(status=200, www_authenticate=canonical)
    sent = _call(_middleware(downstream), _http_scope(f"/mcp/a/{AGENT_ID}"))

    assert dict(sent[0]["headers"])[b"WWW-Authenticate"] == canonical


# --- PRM-Route ---------------------------------------------------------------


def _prm_client() -> TestClient:
    """App aus kanonischer PRM (FastMCP/SDK) + agent-spezifischer PRM-Route."""
    provider = auth.build_auth_provider(_settings())
    routes = list(provider.get_routes(mcp_path=HTTP_PATH))
    routes.append(
        agent_path.build_agent_prm_route(
            http_path=HTTP_PATH,
            mcp_public_url=PUBLIC_URL,
            authorization_servers=provider.authorization_servers,
            scopes_supported=provider.token_verifier.scopes_supported,
        )
    )
    return TestClient(Starlette(routes=routes))


def test_agent_prm_matches_canonical_but_for_resource() -> None:
    client = _prm_client()
    canonical = client.get("/.well-known/oauth-protected-resource/mcp")
    agent = client.get(f"/.well-known/oauth-protected-resource/mcp/a/{AGENT_ID}")

    assert canonical.status_code == 200
    assert agent.status_code == 200
    canonical_body = json.loads(canonical.text)
    agent_body = json.loads(agent.text)
    assert canonical_body["resource"] == "http://mcp.test/mcp"
    assert agent_body["resource"] == f"http://mcp.test/mcp/a/{AGENT_ID}"
    assert agent_body["authorization_servers"] == canonical_body["authorization_servers"]
    assert agent_body["bearer_methods_supported"] == canonical_body["bearer_methods_supported"]


def test_agent_prm_rejects_invalid_uuid() -> None:
    response = _prm_client().get("/.well-known/oauth-protected-resource/mcp/a/kaputt")
    assert response.status_code == 404


def test_agent_prm_allows_cors_preflight() -> None:
    response = _prm_client().options(
        f"/.well-known/oauth-protected-resource/mcp/a/{AGENT_ID}",
        headers={"Origin": "http://client.test", "Access-Control-Request-Method": "GET"},
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"


# --- Zusammenspiel in einer echten FastMCP-HTTP-App ---------------------------


def test_agent_path_reaches_mcp_endpoint_and_advertises_agent_prm() -> None:
    """Verdrahtung wie in `server.main()`: eigene FastMCP-Instanz, damit der
    Modul-Server unberuehrt bleibt.

    `/mcp/a/{uuid}` muss denselben (auth-geschuetzten) Endpoint treffen wie
    `/mcp` — nur mit agent-spezifischer PRM-URL im 401-`WWW-Authenticate`.
    """
    from fastmcp import FastMCP
    from starlette.middleware import Middleware

    settings = _settings()
    provider = auth.build_auth_provider(settings)
    mcp: FastMCP[Any] = FastMCP("test")
    mcp.auth = provider
    mcp._additional_http_routes.append(
        agent_path.build_agent_prm_route(
            http_path=HTTP_PATH,
            mcp_public_url=PUBLIC_URL,
            authorization_servers=provider.authorization_servers,
            scopes_supported=provider.token_verifier.scopes_supported,
        )
    )
    app = mcp.http_app(
        path=HTTP_PATH,
        middleware=[
            Middleware(
                agent_path.AgentPathMiddleware,
                http_path=HTTP_PATH,
                mcp_public_url=PUBLIC_URL,
            )
        ],
    )

    with TestClient(app) as client:
        agent = client.post(f"/mcp/a/{AGENT_ID}", json={})
        canonical = client.post("/mcp", json={})
        unknown = client.post("/mcp/a/kaputt", json={})

    # Ohne Bearer 401 statt 404 ⇒ der Request ist am MCP-Endpoint angekommen.
    assert agent.status_code == 401
    assert f"/oauth-protected-resource/mcp/a/{AGENT_ID}" in agent.headers["www-authenticate"]
    assert canonical.status_code == 401
    assert canonical.headers["www-authenticate"].endswith('/oauth-protected-resource/mcp"')
    assert unknown.status_code == 404
