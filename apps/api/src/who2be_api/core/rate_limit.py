"""Rate-Limiting fuer schreibende Endpoints (slowapi).

Storage ist pluggable (Plan CL2 / §3.1): `RATE_LIMIT_STORAGE_URI` steuert sowohl
den slowapi-`Limiter` als auch das Per-Token-Ceiling. Default `memory://` ⇒
Single-Process / In-Memory, ausreichend fuer den Single-Container-Lauf. Ein
`redis://...`-URI aktiviert ein geteiltes Backend, sodass mehrere API-Replicas
dasselbe Fenster sehen — ohne Verhaltensaenderung im Default.

Key-Funktion: SHA-256-Praefix des Bearer-Tokens (deckt JWT- und `w2b_`-Pfad ohne
DB-Roundtrip ab) und faellt auf Client-IP zurueck, wenn kein Auth-Header anliegt.
"""

import hashlib
import threading
import time
from collections import defaultdict, deque
from typing import Protocol

from fastapi import Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from who2be_api.core.config import Settings, get_settings

__all__ = [
    "RateLimitExceeded",
    "RedisTokenRateLimiter",
    "TokenRateLimiter",
    "TokenRateLimiterPort",
    "_rate_limit_exceeded_handler",
    "build_token_rate_limiter",
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


limiter = Limiter(key_func=rate_limit_key, storage_uri=get_settings().rate_limit_storage_uri)


class TokenRateLimiterPort(Protocol):
    """Vertrag des Per-Token-Ceilings — In-Memory und Redis erfuellen ihn gleich."""

    def allow(self, key: str, limit_per_min: int | None, now: float | None = None) -> bool: ...

    def reset(self) -> None: ...


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


class RedisTokenRateLimiter:
    """Redis-backed Per-Token-Ceiling via `limits` (Moving-Window-Strategie).

    Semantik-gleich zum In-Memory `TokenRateLimiter` (60s-Sliding-Window pro Key),
    aber prozessuebergreifend: mehrere API-Replicas teilen sich denselben Bucket
    (Plan CL2). Aktiv, sobald `RATE_LIMIT_STORAGE_URI` auf `redis://...` zeigt.

    Storage/Strategie werden **lazy** beim ersten `allow` gebaut, damit Import und
    Config-Aufloesung ohne erreichbares Redis funktionieren (Tests, Boot-Reihenfolge).
    Der `now`-Parameter existiert nur fuer API-Kompatibilitaet; das Zeitfenster
    verwaltet `limits` selbst.
    """

    _WINDOW_SECONDS = 60

    def __init__(self, storage_uri: str) -> None:
        self.storage_uri = storage_uri
        self._limiter: object | None = None

    def _strategy(self) -> object:
        if self._limiter is None:
            from limits.storage import storage_from_string
            from limits.strategies import MovingWindowRateLimiter

            self._limiter = MovingWindowRateLimiter(storage_from_string(self.storage_uri))
        return self._limiter

    def allow(self, key: str, limit_per_min: int | None, now: float | None = None) -> bool:
        """True, solange der Read im aktuellen 60s-Fenster unter dem Limit liegt."""
        if limit_per_min is None or limit_per_min <= 0:
            return True
        from limits import RateLimitItemPerMinute
        from limits.strategies import MovingWindowRateLimiter

        item = RateLimitItemPerMinute(limit_per_min)
        strategy = self._strategy()
        assert isinstance(strategy, MovingWindowRateLimiter)  # noqa: S101 — Typ-Narrowing
        return strategy.hit(item, key)

    def reset(self) -> None:
        """Verwirft die Strategie — frische Verbindung/Buckets beim naechsten Lauf."""
        self._limiter = None


def build_token_rate_limiter(settings: Settings | None = None) -> TokenRateLimiterPort:
    """Waehlt das Per-Token-Backend anhand der Storage-URI (Default: In-Memory)."""
    resolved = settings or get_settings()
    uri = resolved.rate_limit_storage_uri
    if uri.startswith("redis"):
        return RedisTokenRateLimiter(uri)
    return TokenRateLimiter()


token_rate_limiter: TokenRateLimiterPort = build_token_rate_limiter()
