#!/usr/bin/env python3
"""Erzeugt ein HS256-Supabase-kompatibles JWT fuer den lokalen Smoke.

Stdlib-only, damit das Skript auch auf dem CI-Runner ohne uv/pip laeuft.
Liest `JWT_SECRET` aus der Umgebung, druckt das fertige Token auf stdout.

Beispiel:
    JWT_SECRET=$(grep JWT_SECRET .env | cut -d= -f2-) python scripts/gen_test_jwt.py
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sys
import time
import uuid


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def main() -> int:
    secret = os.environ.get("JWT_SECRET", "")
    if not secret:
        print("JWT_SECRET ist nicht gesetzt.", file=sys.stderr)
        return 1

    sub = os.environ.get("TEST_USER_ID") or str(uuid.uuid4())
    ttl = int(os.environ.get("TOKEN_TTL_SECONDS", "3600"))

    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": sub,
        "aud": "authenticated",
        "role": "authenticated",
        "exp": int(time.time()) + ttl,
        "iat": int(time.time()),
    }

    header_b64 = _b64url(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    sig_b64 = _b64url(signature)

    print(f"{header_b64}.{payload_b64}.{sig_b64}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
