"""ASGI-Middleware fuer Request-Korrelation, Access-Logs (ADR-0007) und die
Sperre des internen Bereichs ``/v1/internal`` (ADR-0010).

Duenne Klassen direkt auf ASGI-Ebene — ohne `BaseHTTPMiddleware`, das
den Request-Body konsumieren und Streaming-Antworten brechen kann.

`RequestIDMiddleware` setzt eine `request_id` (uebernommen aus `X-Request-ID`
oder neu erzeugt), bindet sie an `structlog.contextvars` und propagiert sie
als Response-Header zurueck. `AccessLogMiddleware` misst die Bearbeitungszeit
und emittiert eine strukturierte Log-Zeile pro HTTP-Request.
"""

import ipaddress
import re
import time
import uuid
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any, cast
from urllib.parse import unquote

import structlog

ASGIScope = MutableMapping[str, Any]
ASGIMessage = MutableMapping[str, Any]
ASGIReceive = Callable[[], Awaitable[ASGIMessage]]
ASGISend = Callable[[ASGIMessage], Awaitable[None]]
ASGIApp = Callable[[ASGIScope, ASGIReceive, ASGISend], Awaitable[None]]

_REQUEST_ID_HEADER = b"x-request-id"
# Akzeptierte Zeichen + Laenge fuer eingehende X-Request-ID. Verhindert
# Log-Injection (CR/LF) und unbeschraenkte Header-Werte (Speicher in jedem
# Log-Record). Werte ausserhalb dieser Form werden verworfen und durch eine
# generierte UUID ersetzt.
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class RequestIDMiddleware:
    """Bindet `request_id` an structlog-Contextvars und propagiert den Response-Header."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: ASGIScope, receive: ASGIReceive, send: ASGISend) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = _header_value(scope.get("headers") or [], _REQUEST_ID_HEADER)
        request_id = (
            incoming
            if incoming is not None and _REQUEST_ID_PATTERN.match(incoming)
            else uuid.uuid4().hex
        )
        structlog.contextvars.bind_contextvars(request_id=request_id)

        async def send_with_header(message: ASGIMessage) -> None:
            if message["type"] == "http.response.start":
                headers = list(cast(list[tuple[bytes, bytes]], message.get("headers") or []))
                headers.append((_REQUEST_ID_HEADER, request_id.encode("ascii")))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_header)
        finally:
            structlog.contextvars.clear_contextvars()


class AccessLogMiddleware:
    """Emittiert pro HTTP-Request eine strukturierte Log-Zeile (`event="http_request"`)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self._logger = structlog.get_logger("who2be_api.access")

    async def __call__(self, scope: ASGIScope, receive: ASGIReceive, send: ASGISend) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        status_holder: dict[str, int] = {"status": 500}
        start = time.perf_counter()

        async def send_capture(message: ASGIMessage) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = int(message.get("status", 500))
            await send(message)

        try:
            await self.app(scope, receive, send_capture)
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            self._logger.info(
                "http_request",
                path=scope.get("path", ""),
                method=scope.get("method", ""),
                status=status_holder["status"],
                duration_ms=duration_ms,
            )


#: Der interne Bereich in jeder Schreibweise: Trennzeichen, Gross/Klein und
#: (von uvicorn bereits dekodierte) Prozent-Kodierung aendern nichts an der
#: Zuordnung. Gleiche Regel wie ``@internal_alt`` im Hetzner-Caddyfile;
#: Woerter, die nur mit ``internal`` BEGINNEN, gehoeren nicht dazu.
_INTERNAL_AREA = re.compile(r"(?i)^/v1[^a-z0-9]+internal([^a-z0-9]|$)")

#: Header, die ein Reverse-Proxy (Traefik, Caddy, der nginx im Web-Container)
#: an jede weitergereichte Anfrage haengt. Ihre blosse Anwesenheit heisst: die
#: Anfrage kam von aussen herein. Geprueft wird die Anwesenheit, nicht der
#: Wert — den Wert kann ein Client vorgeben, das Weglassen kann er nicht, weil
#: der Proxy den Header selbst ergaenzt.
_PROXY_HEADERS = (b"x-forwarded-for", b"x-forwarded-host", b"x-real-ip", b"forwarded")


#: Adressbereiche, aus denen ein Container-Netz kommt: Loopback, RFC 1918
#: (Docker-Bridges liegen in 172.16/12, Podman/Swarm-Overlays in 10/8) und die
#: IPv6-Gegenstuecke. Bewusst eine eigene Liste statt ``is_private``: Python
#: zaehlt dort auch Dokumentations- und Sonderbereiche (TEST-NET u. a.) mit.
_CONTAINER_NETWORKS = tuple(
    ipaddress.ip_network(net)
    for net in (
        "127.0.0.0/8",
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "::1/128",
        "fc00::/7",
    )
)


def _is_internal_area(path: str) -> bool:
    return _INTERNAL_AREA.match(path) is not None


def _is_private_peer(host: str | None) -> bool:
    if not host:
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        # Kein IP-Literal (z. B. "testclient" der Starlette-Testsuite oder ein
        # Unix-Socket-Pfad): kein Nachweis einer internen Herkunft.
        return False
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    return any(address in net for net in _CONTAINER_NETWORKS)


class InternalAreaGuard:
    """Sperrt ``/v1/internal/*`` fuer alles, was nicht aus dem Container-Netz kommt.

    ADR-0010 legt Betriebs-Endpunkte (``/metrics``) unter ``/v1/internal``.
    Im Hetzner-Stack weist Caddy den Bereich ab, bevor er die App erreicht;
    vor dem Dokploy-Stack steht Traefik ohne diese Regel. Deshalb sperrt die
    App den Bereich selbst — unabhaengig davon, welcher Proxy davor steht.

    Erlaubt ist eine Anfrage nur, wenn BEIDES gilt:

    1. kein Proxy-Header ist gesetzt (``X-Forwarded-For`` u. a.) — jede
       Anfrage ueber Traefik, Caddy oder den nginx im Web-Container traegt
       einen, und
    2. die Gegenstelle hat eine Loopback- oder private Adresse (Docker-Netz).

    Alles andere bekommt 403, auch fuer Pfade, die es (noch) nicht gibt: die
    Antwort verraet damit nicht, welche internen Endpunkte existieren.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: ASGIScope, receive: ASGIReceive, send: ASGISend) -> None:
        if scope["type"] != "http" or not self._targets_internal_area(scope):
            await self.app(scope, receive, send)
            return

        headers = cast(list[tuple[bytes, bytes]], scope.get("headers") or [])
        proxied = any(key.lower() in _PROXY_HEADERS for key, _ in headers)
        client = scope.get("client")
        peer = client[0] if client else None
        if not proxied and _is_private_peer(peer):
            await self.app(scope, receive, send)
            return

        body = b'{"detail":"Forbidden"}'
        await send(
            {
                "type": "http.response.start",
                "status": 403,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                    (b"cache-control", b"no-store"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})

    @staticmethod
    def _targets_internal_area(scope: ASGIScope) -> bool:
        path = str(scope.get("path", ""))
        if _is_internal_area(path):
            return True
        # `raw_path` ist die undekodierte Form. Uvicorn dekodiert `path`
        # bereits; ein anderer Server muss das nicht tun, also beide pruefen.
        raw = scope.get("raw_path")
        if isinstance(raw, bytes | bytearray):
            decoded = unquote(bytes(raw).decode("latin-1").split("?", 1)[0])
            return _is_internal_area(decoded)
        return False


def _header_value(headers: list[tuple[bytes, bytes]], name: bytes) -> str | None:
    for key, value in headers:
        if key.lower() == name:
            return value.decode("latin-1")
    return None
