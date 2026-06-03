"""Unit-Tests fuer das Per-Token-Rate-Ceiling (`core/rate_limit.py`).

Deckt den unveraenderten In-Memory-Pfad ab und belegt, dass die Storage-URI
(Plan CL2) korrekt durch die Factory bzw. an slowapi durchgereicht wird.
"""

from __future__ import annotations

from who2be_api.core.config import Settings
from who2be_api.core.rate_limit import (
    RedisTokenRateLimiter,
    TokenRateLimiter,
    build_token_rate_limiter,
    limiter,
)


def test_allows_up_to_limit_then_blocks() -> None:
    limiter = TokenRateLimiter()
    assert limiter.allow("k", 2, now=0.0)
    assert limiter.allow("k", 2, now=0.1)
    # Drittes Event im selben Fenster ⇒ blockiert.
    assert not limiter.allow("k", 2, now=0.2)


def test_window_slides() -> None:
    limiter = TokenRateLimiter()
    assert limiter.allow("k", 1, now=0.0)
    assert not limiter.allow("k", 1, now=30.0)
    # Nach 60s ist das erste Event aus dem Fenster gefallen.
    assert limiter.allow("k", 1, now=61.0)


def test_keys_are_independent() -> None:
    limiter = TokenRateLimiter()
    assert limiter.allow("a", 1, now=0.0)
    assert limiter.allow("b", 1, now=0.0)
    assert not limiter.allow("a", 1, now=0.0)


def test_none_or_zero_limit_is_unlimited() -> None:
    limiter = TokenRateLimiter()
    for i in range(100):
        assert limiter.allow("k", None, now=float(i))
        assert limiter.allow("k", 0, now=float(i))


def test_factory_defaults_to_in_memory() -> None:
    """`memory://` (Default) ⇒ unveraenderter In-Memory-Limiter."""
    built = build_token_rate_limiter(Settings(rate_limit_storage_uri="memory://"))
    assert isinstance(built, TokenRateLimiter)


def test_factory_routes_redis_uri_to_redis_backend() -> None:
    """`redis://...` ⇒ Redis-backed Limiter, URI 1:1 durchgereicht (Plan CL2)."""
    uri = "redis://localhost:6379/3"
    built = build_token_rate_limiter(Settings(rate_limit_storage_uri=uri))
    assert isinstance(built, RedisTokenRateLimiter)
    assert built.storage_uri == uri


def test_redis_backend_construction_is_lazy() -> None:
    """Konstruktion baut weder Storage noch Verbindung — kein Redis noetig."""
    built = RedisTokenRateLimiter("redis://unreachable-host:6379")
    # `limit<=0`/None gehen den Kurzschluss-Pfad und beruehren das Backend nie.
    assert built.allow("k", None) is True
    assert built.allow("k", 0) is True


def test_slowapi_limiter_uses_configured_storage_uri() -> None:
    """Der Modul-Limiter erhaelt die Storage-URI aus den Settings (Default memory)."""
    assert limiter._storage_uri == "memory://"
