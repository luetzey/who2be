"""End-to-End-Smoke für den OAuth-Remote-MCP-Connector gegen einen LIVEN Stack.

Anders als `apps/api/tests/test_oauth.py` (TestClient, monkeypatched, frische
Owner-DB) fährt dieses Skript den vollen Flow — DCR → authorize → consent →
token → Refresh — gegen einen echten, laufenden API-Prozess und prüft danach
den MCP-Resource-Server. Dadurch lässt sich die Edition wählen: läuft die API
als `who2be_app` (Cloud, RLS aktiv), beweist der Lauf den RLS-sicheren
Consent-Pfad; als Owner (On-Prem) den klassischen.

Fixtures (User/Workspace/Agent) werden über die OWNER-Connection geseedet
(RLS-Bypass, deterministisch) — der OAuth-Flow läuft danach über HTTP gegen die
API in der jeweiligen Edition. Der JWT des Consent-Users wird direkt mit dem
JWT-Secret gemintet (kein GoTrue-Roundtrip nötig).

Aufruf via `scripts/oauth_smoke.sh onprem|cloud` (setzt die Env passend).
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import os
import secrets
import sys
from datetime import UTC, datetime, timedelta
from typing import NoReturn
from urllib.parse import parse_qs, urlparse
from uuid import UUID

import asyncpg
import httpx
import jwt

from who2be_api.testing.workspace_setup import (
    cleanup_workspaces,
    fresh_user_id,
    setup_workspace,
)

API = os.environ.get("API_BASE", "http://localhost:8000").rstrip("/")
MCP = os.environ.get("MCP_BASE", "http://localhost:8765").rstrip("/")
RESOURCE = os.environ.get("MCP_RESOURCE", "http://localhost:8765/mcp")
SECRET = os.environ.get("JWT_SECRET", "dev-jwt-secret-change-me-32chars-min")
DB = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/who2be")
REDIRECT = "http://localhost:9999/cb"  # Loopback ⇒ von _is_allowed_redirect erlaubt
EDITION = os.environ.get("EDITION_LABEL", "?")

_OK = "\033[32m✓\033[0m"
_FAIL = "\033[31m✗\033[0m"


def ok(msg: str) -> None:
    print(f"  {_OK} {msg}")


def die(msg: str) -> NoReturn:
    print(f"  {_FAIL} {msg}")
    sys.exit(1)


def pkce() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=")
    return verifier, challenge.decode()


def mint_jwt(user_id: UUID) -> str:
    return jwt.encode(
        {
            "sub": str(user_id),
            "aud": "authenticated",
            "role": "authenticated",
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        SECRET,
        algorithm="HS256",
    )


async def agent_in(ws: UUID) -> UUID:
    conn = await asyncpg.connect(DB)
    try:
        agent_id: UUID | None = await conn.fetchval(
            "SELECT id FROM agent WHERE workspace_id = $1 LIMIT 1", ws
        )
        if agent_id is None:
            die("Kein Seed-Agent im Workspace gefunden.")
        return agent_id
    finally:
        await conn.close()


async def token_row(token_hash: str) -> dict[str, object] | None:
    conn = await asyncpg.connect(DB)
    try:
        row = await conn.fetchrow(
            "SELECT agent_id, role, expires_at, revoked_at FROM api_token WHERE token_hash = $1",
            token_hash,
        )
        return dict(row) if row else None
    finally:
        await conn.close()


def hash_token(plain: str) -> str:
    return hashlib.sha256(plain.encode()).hexdigest()


def main() -> None:
    print(f"\n=== OAuth-Smoke — Edition: {EDITION} ===")
    print(f"    API={API}  MCP={MCP}  RESOURCE={RESOURCE}")

    user_id = fresh_user_id()
    ws = setup_workspace(user_id)
    agent_id = str(asyncio.run(agent_in(ws)))
    jwt_auth = {"Authorization": f"Bearer {mint_jwt(user_id)}"}
    ok(f"Fixtures geseedet: user={user_id} ws={ws} agent={agent_id}")

    try:
        with httpx.Client(base_url=API, timeout=15.0, follow_redirects=False) as c:
            # 1) AS-Metadaten (RFC 8414)
            meta = c.get("/.well-known/oauth-authorization-server").json()
            assert meta["code_challenge_methods_supported"] == ["S256"], meta
            ok("AS-Metadaten: S256 + Endpunkte vorhanden")

            # 2) DCR (RFC 7591)
            reg = c.post(
                "/oauth/register",
                json={"redirect_uris": [REDIRECT], "client_name": "Smoke-Client"},
            )
            assert reg.status_code == 201, reg.text
            client_id = reg.json()["client_id"]
            ok(f"DCR: client_id={client_id}")

            # 3) authorize — Open-Redirect-Choke-Point
            verifier, challenge = pkce()
            bad = c.get(
                "/oauth/authorize",
                params={
                    "response_type": "code",
                    "client_id": client_id,
                    "redirect_uri": "https://evil.example/cb",
                    "code_challenge": challenge,
                    "resource": RESOURCE,
                },
            )
            assert bad.status_code == 400, f"fremde redirect_uri → erwartet 400: {bad.status_code}"
            ok("authorize: fremde redirect_uri → 400 (kein Redirect)")

            # 4) authorize (gültig) → signierter Blob in der Consent-URL
            auth = c.get(
                "/oauth/authorize",
                params={
                    "response_type": "code",
                    "client_id": client_id,
                    "redirect_uri": REDIRECT,
                    "code_challenge": challenge,
                    "code_challenge_method": "S256",
                    "resource": RESOURCE,
                    "state": "smoke-state",
                },
            )
            assert auth.status_code == 302, auth.text
            blob = parse_qs(urlparse(auth.headers["location"]).query)["request"][0]
            ok("authorize: 302 → signierter Consent-Blob")

            # 5) consent (eingeloggter User) → Auth-Code  [RLS-kritischer Pfad]
            con = c.post(
                "/oauth/consent",
                json={"request": blob, "agent_id": agent_id, "approve": True},
                headers=jwt_auth,
            )
            assert con.status_code == 200, f"consent fehlgeschlagen ({con.status_code}): {con.text}"
            redirect = con.json()["redirect"]
            params = parse_qs(urlparse(redirect).query)
            assert params["state"] == ["smoke-state"], params
            code = params["code"][0]
            ok("consent: 200 → Auth-Code (RLS-sicherer Agent-Lookup OK)")

            # 6) token: authorization_code (PKCE)
            tok = c.post(
                "/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": REDIRECT,
                    "client_id": client_id,
                    "code_verifier": verifier,
                },
            )
            assert tok.status_code == 200, tok.text
            assert tok.headers.get("cache-control") == "no-store"
            body = tok.json()
            access, refresh = body["access_token"], body["refresh_token"]
            assert access.startswith("w2b_") and body["expires_in"] == 28800, body
            ok(f"token: Access (w2b_, exp={body['expires_in']}s) + Refresh ausgestellt")

            # DB-Beleg: agent-gebunden + Rolle-Snapshot + expires_at
            row = asyncio.run(token_row(hash_token(access)))
            assert row and str(row["agent_id"]) == agent_id and row["expires_at"] is not None, row
            ok(f"DB: api_token agent-gebunden, role={row['role']}, expires_at gesetzt")

            # 7) Code-Replay → invalid_grant
            replay = c.post(
                "/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": REDIRECT,
                    "client_id": client_id,
                    "code_verifier": verifier,
                },
            )
            assert replay.status_code == 400, replay.text
            assert replay.json()["error"] == "invalid_grant", replay.text
            ok("Code-Replay → invalid_grant")

            # 8) Refresh-Rotation
            r1 = c.post(
                "/oauth/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh,
                    "client_id": client_id,
                },
            )
            assert r1.status_code == 200, r1.text
            new_access = r1.json()["access_token"]
            assert new_access != access
            old = asyncio.run(token_row(hash_token(access)))
            assert old and old["revoked_at"] is not None, "alter Access nicht widerrufen"
            ok("Refresh-Rotation: neuer Access, alter widerrufen")

            # 9) Access-Token wirkt an der API (/v1/me → 200)
            me = c.get("/v1/me", headers={"Authorization": f"Bearer {new_access}"})
            assert me.status_code == 200, me.text
            ok("Access-Token gültig an /v1/me")

        # 10) Resource-Server (MCP) — best effort, falls erreichbar
        smoke_rs(new_access)
    finally:
        cleanup_workspaces([user_id])
        ok("Fixtures aufgeräumt")

    print(f"\n=== {EDITION}: ALLE CHECKS BESTANDEN ===\n")


def smoke_rs(access: str) -> None:
    try:
        with httpx.Client(base_url=MCP, timeout=10.0) as c:
            prm = c.get("/.well-known/oauth-protected-resource/mcp")
            if prm.status_code != 200:
                print(f"  · MCP-RS nicht geprüft (PRM {prm.status_code}) — MCP-Server aus?")
                return
            assert "authorization_servers" in prm.json(), prm.text
            ok("MCP-PRM: authorization_servers vorhanden")

            init = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "smoke", "version": "0"},
                },
            }
            hdr = {
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            }
            no_tok = c.post("/mcp", json=init, headers=hdr)
            assert no_tok.status_code == 401, f"MCP ohne Token → erwartet 401: {no_tok.status_code}"
            assert "www-authenticate" in {k.lower() for k in no_tok.headers}, no_tok.headers
            ok("MCP ohne Token → 401 + WWW-Authenticate")

            with_tok = c.post(
                "/mcp", json=init, headers={**hdr, "Authorization": f"Bearer {access}"}
            )
            assert with_tok.status_code != 401, "MCP mit gültigem Token sollte nicht 401 sein"
            ok(f"MCP mit Token → {with_tok.status_code} (Auth-Gate passiert)")
    except httpx.HTTPError as exc:
        print(f"  · MCP-RS nicht erreichbar ({type(exc).__name__}) — übersprungen.")


if __name__ == "__main__":
    main()
