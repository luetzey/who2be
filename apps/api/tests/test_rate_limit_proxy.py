"""Beweist die F-02-Mitigation (docs/security-findings.md):

`_rate_limit_key` faellt korrekt auf `request.client.host` zurueck,
sobald kein Bearer-Token vorliegt. Hinter dem Caddy-Reverse-Proxy
schreibt uvicorns `ProxyHeadersMiddleware` (aktiviert durch
`--proxy-headers --forwarded-allow-ips *` in `apps/api/Dockerfile`)
die echte Client-IP in dieses Feld, sodass anonyme Calls *pro Client-IP*
gebucketed werden statt pro Proxy-IP.
"""

from pathlib import Path

from starlette.requests import Request

from who2be_api.core.rate_limit import _rate_limit_key

_DOCKERFILE = Path(__file__).resolve().parents[1] / "Dockerfile"


def _request(client_host: str, headers: dict[str, str] | None = None) -> Request:
    raw_headers = [
        (k.lower().encode("ascii"), v.encode("ascii")) for k, v in (headers or {}).items()
    ]
    return Request(
        scope={
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": raw_headers,
            "client": (client_host, 12345),
        }
    )


def test_anonymous_key_uses_client_host() -> None:
    assert _rate_limit_key(_request("1.2.3.4")) == "1.2.3.4"
    assert _rate_limit_key(_request("9.9.9.9")) == "9.9.9.9"


def test_anonymous_keys_differ_per_client_host() -> None:
    a = _rate_limit_key(_request("1.2.3.4"))
    b = _rate_limit_key(_request("5.6.7.8"))
    assert a != b


def test_bearer_token_overrides_client_host() -> None:
    headers = {"authorization": "Bearer same-token"}
    a = _rate_limit_key(_request("1.2.3.4", headers))
    b = _rate_limit_key(_request("5.6.7.8", headers))
    assert a == b
    # Token-Hash ist 32-Zeichen-Hex-Praefix, nicht eine IP.
    assert len(a) == 32
    assert all(c in "0123456789abcdef" for c in a)


def test_dockerfile_cmd_enables_proxy_headers() -> None:
    """Anti-Regression: F-02-Mitigation darf nicht stillschweigend kippen."""
    content = _DOCKERFILE.read_text(encoding="utf-8")
    assert "--proxy-headers" in content
    assert "--forwarded-allow-ips" in content
