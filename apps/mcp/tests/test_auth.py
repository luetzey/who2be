"""Tests fuer den OAuth-Resource-Server des MCP-Servers (ADR-0034-Folge).

`Who2BeTokenVerifier` introspectiert den eingehenden Bearer gegen `GET /v1/me`:
200 ⇒ gueltiges `AccessToken`, sonst `None` (FastMCP antwortet 401). Ohne
laufende API simuliert `httpx.MockTransport` die Who2Be-REST-API.
`build_auth_provider` muss die RFC-9728-PRM-Route bereitstellen und auf die
Who2Be-API als Authorization-Server zeigen.
"""

import asyncio
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from who2be_mcp import auth
from who2be_mcp.config import Settings


def _settings() -> Settings:
    return Settings(
        api_base_url="http://api.test",
        transport="http",
        oauth_issuer_url="http://api.test",
        mcp_public_url="http://mcp.test",
    )


def _patch_httpx(
    monkeypatch: pytest.MonkeyPatch,
    handler: Callable[[httpx.Request], httpx.Response],
) -> None:
    real = httpx.AsyncClient

    def factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs.pop("transport", None)
        return real(*args, transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", factory)


def test_verify_token_accepts_valid_bearer(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/me"
        assert request.headers["authorization"] == "Bearer w2b_good"
        return httpx.Response(200, json={"user_id": "u", "default_workspace_id": "w"})

    _patch_httpx(monkeypatch, handler)
    verifier = auth.Who2BeTokenVerifier(_settings())
    token = asyncio.run(verifier.verify_token("w2b_good"))
    assert token is not None
    assert token.token == "w2b_good"


def test_verify_token_rejects_401(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "nope"})

    _patch_httpx(monkeypatch, handler)
    verifier = auth.Who2BeTokenVerifier(_settings())
    assert asyncio.run(verifier.verify_token("w2b_bad")) is None


def test_verify_token_rejects_empty() -> None:
    verifier = auth.Who2BeTokenVerifier(_settings())
    assert asyncio.run(verifier.verify_token("")) is None


def test_verify_token_handles_unreachable_api(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    _patch_httpx(monkeypatch, handler)
    verifier = auth.Who2BeTokenVerifier(_settings())
    assert asyncio.run(verifier.verify_token("w2b_x")) is None


def test_auth_provider_exposes_prm_and_authorization_server() -> None:
    provider = auth.build_auth_provider(_settings())
    assert provider.authorization_servers == ["http://api.test/"]


# ---------------------------------------------------------------------------
# Issuer-Identifier (RFC 8414 §3.3 / RFC 9728 §2)
#
# Der Client liest `authorization_servers` aus der PRM, holt damit die
# AS-Metadaten der API und vergleicht deren `issuer` per STRING-Gleichheit.
# `provider.authorization_servers` oben prueft nur die Eingabe — entscheidend
# ist, was ueber die Leitung geht UND was der Client daraus macht: er legt den
# Wert in einem URL-Typ ab, bevor er vergleicht. Advertisiert wird deshalb die
# URL-Normalform (Begruendung in `who2be_models.oauth_issuer`).
# ---------------------------------------------------------------------------


def _prm_body(issuer: str) -> dict[str, Any]:
    from starlette.applications import Starlette
    from starlette.testclient import TestClient

    settings = Settings(
        api_base_url="https://api.example.de",
        transport="http",
        oauth_issuer_url=issuer,
        mcp_public_url="https://mcp.example.de",
        http_path="/mcp",
    )
    provider = auth.build_auth_provider(settings)
    with TestClient(Starlette(routes=provider.get_routes(mcp_path="/mcp"))) as client:
        response = client.get("/.well-known/oauth-protected-resource/mcp")
    assert response.status_code == 200, response.text
    return dict(response.json())


def test_prm_advertises_the_url_normal_form_of_the_issuer() -> None:
    body = _prm_body("https://api.example.de")
    assert body["authorization_servers"] == ["https://api.example.de/"]
    assert body["resource"] == "https://mcp.example.de/mcp"
    # Die uebrigen SDK-Felder bleiben unangetastet.
    assert body["bearer_methods_supported"] == ["header"]


def test_prm_issuer_is_canonical_even_if_env_has_a_slash() -> None:
    # Ein Betreiber, der die ENV mit Slash setzt, darf den Connector nicht
    # kippen — beide Schreibweisen ergeben denselben Identifier.
    assert _prm_body("https://api.example.de/") == _prm_body("https://api.example.de")


def test_client_reads_the_prm_back_as_the_advertised_string() -> None:
    """Die PRM durch das Modell des ECHTEN Clients gedreht.

    `mcp/client/auth/oauth2.py` macht aus der Antwort
    `str(ProtectedResourceMetadata(...).authorization_servers[0])` und haelt
    das Ergebnis gegen den rohen `issuer` der API. Dieser Test ist die eine
    Gegenprobe, die in #523 gefehlt hat: nicht was wir senden, sondern was der
    Client daraus liest, muss der Identifier sein.
    """
    from mcp.shared.auth import ProtectedResourceMetadata

    body = _prm_body("https://api.example.de")
    parsed = ProtectedResourceMetadata.model_validate(body)
    assert str(parsed.authorization_servers[0]) == body["authorization_servers"][0]
