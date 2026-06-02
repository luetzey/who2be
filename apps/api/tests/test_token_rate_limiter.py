"""Unit-Tests fuer das In-Memory Per-Token-Rate-Ceiling (`core/rate_limit.py`)."""

from __future__ import annotations

from who2be_api.core.rate_limit import TokenRateLimiter


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
