"""ASGI-Middleware fuer Request-Korrelation und Access-Logs (ADR-0007).

Zwei duenne Klassen direkt auf ASGI-Ebene — ohne `BaseHTTPMiddleware`, das
den Request-Body konsumieren und Streaming-Antworten brechen kann.

`RequestIDMiddleware` setzt eine `request_id` (uebernommen aus `X-Request-ID`
oder neu erzeugt), bindet sie an `structlog.contextvars` und propagiert sie
als Response-Header zurueck. `AccessLogMiddleware` misst die Bearbeitungszeit
und emittiert eine strukturierte Log-Zeile pro HTTP-Request.
"""

import re
import time
import uuid
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any, cast

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


def _header_value(headers: list[tuple[bytes, bytes]], name: bytes) -> str | None:
    for key, value in headers:
        if key.lower() == name:
            return value.decode("latin-1")
    return None
