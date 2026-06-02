"""Rate-Limiting fuer schreibende Endpoints (slowapi).

Single-Process / In-Memory: ausreichend fuer den aktuellen Single-Container-Lauf.
Mehrere API-Replicas in MS-2+ erfordern ein Redis-Storage (`storage_uri="redis://..."`).

Key-Funktion: SHA-256-Praefix des Bearer-Tokens (deckt JWT- und `w2b_`-Pfad ohne
DB-Roundtrip ab) und faellt auf Client-IP zurueck, wenn kein Auth-Header anliegt.
"""

import hashlib
import threading
import time
from collections import defaultdict, deque

from fastapi import Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from who2be_api.core.config import get_settings

__all__ = [
    "RateLimitExceeded",
    "TokenRateLimiter",
    "_rate_limit_exceeded_handler",
    "limiter",
    "rate_limit_key",
    "token_rate_limiter",
    "write_limit",
]


def rate_limit_key(request: Request) -> str:
    """Per-Token-Bucket, sonst Per-IP — ohne DB-Lookup."""
    auth = request.headers.get("authorization")
    if auth and auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
        if token:
            return hashlib.sha256(token.encode("utf-8")).hexdigest()[:32]
    return get_remote_address(request)


# Rueckwaerts-kompatibler Alias (frueher privat). Andere Module/Tests nutzen `_rate_limit_key`.
_rate_limit_key = rate_limit_key


def write_limit() -> str:
    """Callable-Form, damit Tests `Settings.rate_limit_write` zur Laufzeit aendern koennen."""
    return get_settings().rate_limit_write


limiter = Limiter(key_func=rate_limit_key)


class TokenRateLimiter:
    """In-Memory Sliding-Window-Limiter fuer das per-Token-Rate-Ceiling (Track D).

    Das MCP-Limit-Gate liest das `mcp_rate_per_min` aus dem Org-Entitlement und
    nutzt diesen Limiter, um agent-facing Reads pro Token (req/min) zu deckeln —
    ergaenzend zum Monats-Kontingent. Single-Process/In-Memory, konsistent mit
    dem slowapi-Hinweis oben; mehrere Replicas erfordern spaeter ein geteiltes
    Backend (Redis). `limit <= 0` bzw. `None` ⇒ unbegrenzt (durchlassen).
    """

    _WINDOW_SECONDS = 60.0

    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, limit_per_min: int | None, now: float | None = None) -> bool:
        """True, wenn der Read im aktuellen 60s-Fenster noch unter dem Limit liegt."""
        if limit_per_min is None or limit_per_min <= 0:
            return True
        reference = now if now is not None else time.monotonic()
        cutoff = reference - self._WINDOW_SECONDS
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit_per_min:
                return False
            events.append(reference)
            return True

    def reset(self) -> None:
        """Leert alle Fenster — fuer Test-Isolation."""
        with self._lock:
            self._events.clear()


token_rate_limiter = TokenRateLimiter()
