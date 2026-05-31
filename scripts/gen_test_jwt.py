#!/usr/bin/env python3
"""Erzeugt ein HS256-Supabase-kompatibles JWT.

Stdlib-only, damit das Skript auch auf dem CI-Runner ohne uv/pip laeuft.
CLI-Args haben Vorrang vor Env-Vars (rueckwaerts-kompatibel zu vorherigem
Env-only-Verhalten):
    JWT_SECRET           --secret
    TEST_USER_ID         --sub
    TOKEN_TTL_SECONDS    --ttl

Default-Rolle ist `authenticated` (passt zum bisherigen Smoke). Fuer den
Supabase-Stack (MS-2 C2) werden `anon` und `service_role` Tokens via
`--role` erzeugt.

Beispiele:
    JWT_SECRET=... python scripts/gen_test_jwt.py
    python scripts/gen_test_jwt.py --secret "$JWT_SECRET" \\
        --role anon --ttl 315360000
"""

from __future__ import annotations

import argparse
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


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Erzeugt ein HS256-Supabase-JWT.")
    parser.add_argument(
        "--secret",
        default=os.environ.get("JWT_SECRET", ""),
        help="JWT-Signing-Secret (Default: $JWT_SECRET).",
    )
    parser.add_argument(
        "--role",
        default="authenticated",
        choices=("authenticated", "anon", "service_role"),
        help="Supabase-Rolle (Default: authenticated).",
    )
    parser.add_argument(
        "--ttl",
        type=int,
        default=int(os.environ.get("TOKEN_TTL_SECONDS", "3600")),
        help="Token-Lebensdauer in Sekunden (Default: 3600).",
    )
    parser.add_argument(
        "--sub",
        default=os.environ.get("TEST_USER_ID"),
        help="`sub`-Claim. Default: zufaellige UUID4 (bei service_role/anon "
        "irrelevant — wird trotzdem gesetzt).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    if not args.secret:
        print("JWT-Secret fehlt (--secret oder $JWT_SECRET).", file=sys.stderr)
        return 1

    sub = args.sub or str(uuid.uuid4())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": sub,
        "aud": "authenticated",
        "role": args.role,
        "exp": int(time.time()) + args.ttl,
        "iat": int(time.time()),
    }

    header_b64 = _b64url(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = hmac.new(args.secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    sig_b64 = _b64url(signature)

    print(f"{header_b64}.{payload_b64}.{sig_b64}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
