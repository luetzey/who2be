"""Sperre des internen API-Bereichs ``/v1/internal`` in der App (ADR-0010).

Im Hetzner-Stack weist Caddy ``/v1/internal/*`` ab, bevor die Anfrage die API
erreicht. Vor dem Dokploy-Stack steht Traefik ohne diese Regel; eine Probe von
aussen (2026-10-21) bekam von dort ``404`` von **uvicorn** — die Anfrage kam
also bis in die App, und ein spaeter gebauter Metrik-Endpunkt waere oeffentlich
gewesen. ``InternalAreaGuard`` schliesst das in der App selbst.

Die Tests laufen gegen die echte, mit ``create_app`` gebaute App (ohne
Lifespan, also ohne DB): durchgelassene Anfragen enden im Router mit 404, weil
es unter ``/v1/internal`` heute keine Route gibt. 403 heisst also „die Sperre
hat gegriffen“, 404 heisst „bis zum Router durchgelassen“.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from who2be_api.core.config import Settings
from who2be_api.core.middleware import InternalAreaGuard
from who2be_api.main import create_app

_PUBLIC_PEER = ("203.0.113.7", 40000)  # TEST-NET-3 (RFC 5737), oeffentlich
_DOCKER_PEER = ("172.18.0.5", 40000)  # Docker-Bridge, privat
_LOOPBACK_PEER = ("127.0.0.1", 40000)


@pytest.fixture(scope="module")
def app() -> FastAPI:
    return create_app(settings=Settings(_env_file=None))  # type: ignore[call-arg]


def _client(app: FastAPI, peer: tuple[str, int]) -> TestClient:
    # Ohne `with` laeuft kein Lifespan: die Tests brauchen weder DB noch Pool.
    return TestClient(app, client=peer, raise_server_exceptions=False)


@pytest.mark.parametrize(
    "path",
    [
        "/v1/internal/metrics",
        "/v1/internal/health",
        "/v1/internal",
        "/v1/internal/",
        "/V1/INTERNAL/metrics",
        "/v1//internal/metrics",
        "/v1/%69nternal/metrics",
        "/v1/internal%2Fmetrics",
        "/v1;/internal/metrics",
    ],
)
def test_external_request_to_internal_area_is_forbidden(app: FastAPI, path: str) -> None:
    """Von einer oeffentlichen Adresse: jede Schreibweise bekommt 403."""
    response = _client(app, _PUBLIC_PEER).get(path)
    assert response.status_code == 403, (path, response.status_code, response.text)
    assert response.json() == {"detail": "Forbidden"}
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "header",
    ["X-Forwarded-For", "X-Real-IP", "Forwarded", "X-Forwarded-Host"],
)
def test_proxied_request_from_private_peer_is_forbidden(app: FastAPI, header: str) -> None:
    """Ueber einen Proxy im Docker-Netz (Traefik, web-nginx) bleibt es 403.

    Genau das ist der Dokploy-Weg: Traefik und der nginx im Web-Container
    sitzen im privaten Netz und haengen ``X-Forwarded-For`` an. Die private
    Gegenstelle allein darf deshalb NICHT reichen.
    """
    response = _client(app, _DOCKER_PEER).get(
        "/v1/internal/metrics", headers={header: "198.51.100.9"}
    )
    assert response.status_code == 403


@pytest.mark.parametrize("peer", [_DOCKER_PEER, _LOOPBACK_PEER])
def test_direct_request_from_container_network_passes(app: FastAPI, peer: tuple[str, int]) -> None:
    """Direkt aus dem Container-Netz (z. B. ein Metrik-Agent) kommt durch.

    404 statt 403: die Anfrage hat den Router erreicht, es gibt dort nur
    (noch) keine Route.
    """
    response = _client(app, peer).get("/v1/internal/metrics")
    assert response.status_code == 404


def test_non_ip_peer_is_not_treated_as_internal(app: FastAPI) -> None:
    """Ohne IP-Literal als Gegenstelle gibt es keinen Nachweis interner Herkunft."""
    response = _client(app, ("testclient", 50000)).get("/v1/internal/metrics")
    assert response.status_code == 403


@pytest.mark.parametrize(
    "path",
    ["/v1/internals", "/v1/internalize/x", "/v1/nonexistent", "/v1/workspaces/internal"],
)
def test_other_paths_are_untouched(app: FastAPI, path: str) -> None:
    """Pfade ausserhalb des Bereichs laufen unveraendert bis zum Router.

    Woerter, die nur mit ``internal`` beginnen, gehoeren nicht zum Bereich —
    gleiche Abgrenzung wie ``@internal_alt`` im Hetzner-Caddyfile.
    """
    response = _client(app, _PUBLIC_PEER).get(path, headers={"X-Forwarded-For": "198.51.100.9"})
    assert response.status_code != 403, (path, response.status_code)


def test_guard_passes_non_http_scopes_through() -> None:
    """Lifespan- und andere Nicht-HTTP-Scopes laufen ohne Pruefung durch."""
    seen: list[str] = []

    async def inner(scope, receive, send):  # type: ignore[no-untyped-def]
        seen.append(scope["type"])

    import asyncio

    asyncio.run(InternalAreaGuard(inner)({"type": "lifespan"}, None, None))  # type: ignore[arg-type]
    assert seen == ["lifespan"]
