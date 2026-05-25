"""Rate-Limiting fuer schreibende Endpoints (slowapi).

Single-Process / In-Memory: ausreichend fuer den aktuellen Single-Container-Lauf.
Mehrere API-Replicas in MS-2+ erfordern ein Redis-Storage (`storage_uri="redis://..."`).

Key-Funktion: SHA-256-Praefix des Bearer-Tokens (deckt JWT- und `w2b_`-Pfad ohne
DB-Roundtrip ab) und faellt auf Client-IP zurueck, wenn kein Auth-Header anliegt.
"""

import hashlib

from fastapi import Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from who2be_api.core.config import get_settings

__all__ = [
    "RateLimitExceeded",
    "_rate_limit_exceeded_handler",
    "limiter",
    "write_limit",
]


def _rate_limit_key(request: Request) -> str:
    """Per-Token-Bucket, sonst Per-IP — ohne DB-Lookup."""
    auth = request.headers.get("authorization")
    if auth and auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
        if token:
            return hashlib.sha256(token.encode("utf-8")).hexdigest()[:32]
    return get_remote_address(request)


def write_limit() -> str:
    """Callable-Form, damit Tests `Settings.rate_limit_write` zur Laufzeit aendern koennen."""
    return get_settings().rate_limit_write


limiter = Limiter(key_func=_rate_limit_key)
