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
    assert provider.authorization_servers == ["http://api.test"]
