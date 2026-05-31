"""Smoke-Tests fuer die CORS-Middleware (F1 aus dem 2026-05-24-Review).

Sicherstellen, dass der Browser-Preflight von der Web-UI gegen die API
beantwortet wird; ohne ACAO-Header schlagen alle Mutating-Calls im
Browser fehl, auch wenn die ASGI-Tests gruen sind.
"""

from fastapi.testclient import TestClient

from who2be_api.main import app

client = TestClient(app)
_WEB_ORIGIN = "http://localhost:5173"


def test_preflight_allows_configured_origin() -> None:
    response = client.options(
        "/v1/me",
        headers={
            "Origin": _WEB_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == _WEB_ORIGIN
    assert "POST" in response.headers["access-control-allow-methods"]


def test_preflight_allows_patch_method() -> None:
    # PATCH wird vom Auto-Save (Persona/Playbook/Resource-Draft) und vom
    # Members-Role-Update gebraucht; fehlt es in `allow_methods`, blockt der
    # Browser den Preflight und der Client sieht "Who2Be-API nicht erreichbar".
    response = client.options(
        "/v1/me",
        headers={
            "Origin": _WEB_ORIGIN,
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code == 200
    assert "PATCH" in response.headers["access-control-allow-methods"]


def test_simple_request_carries_acao_header() -> None:
    response = client.get("/v1/health", headers={"Origin": _WEB_ORIGIN})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == _WEB_ORIGIN


def test_preflight_rejects_disallowed_custom_header() -> None:
    # `allow_headers` ist eine Whitelist — ein ungelisteter Header darf nicht
    # erlaubt werden, sonst koennen Skripte beliebige Custom-Header an die API
    # senden ohne Browser-Schutz.
    response = client.options(
        "/v1/me",
        headers={
            "Origin": _WEB_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "x-not-allowed",
        },
    )
    allowed = response.headers.get("access-control-allow-headers", "")
    assert "x-not-allowed" not in allowed.lower()


def test_disallowed_origin_is_rejected_by_browser() -> None:
    # Mit `allow_origins=[...]` (kein Wildcard) liefert Starlette fuer eine
    # nicht gelistete Origin gar keinen ACAO-Header — der Browser blockt
    # die Antwort entsprechend.
    response = client.get("/v1/health", headers={"Origin": "https://evil.example.com"})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
