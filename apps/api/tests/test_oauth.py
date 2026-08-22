"""Integrationstest fuer den OAuth-2.1-Authorization-Server (Remote-MCP-Connector).

Deckt den vollen Flow ab — DCR → authorize → consent → token (Code + Refresh) —
plus die Sicherheits-Invarianten: Open-Redirect-Choke-Point (unbekannter Client /
Mismatch ⇒ 400 OHNE Redirect), PKCE-S256-Zwang, Code-Single-Use (Replay ⇒
invalid_grant), Refresh-Rotation inkl. Replay-Detection und Access-Token-Expiry.

Laeuft nur mit erreichbarer Datenbank; ohne DB werden die Tests uebersprungen.
"""

import asyncio
import base64
import hashlib
import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from urllib.parse import parse_qs, urlparse
from uuid import UUID, uuid4

import asyncpg
import jwt
import pytest
from fastapi.testclient import TestClient

from who2be_api.core import security
from who2be_api.core.config import Settings, get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.core.tenancy import current_tenant_context
from who2be_api.main import app
from who2be_api.repositories.oauth_repository import PgOAuthRepository
from who2be_api.services import oauth_service
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace

_TEST_SECRET = "integration-test-jwt-secret-padding-0123456789"
_RESOURCE = "http://testserver/mcp"
_REDIRECT = "https://claude.ai/api/mcp/auth_callback"


def _db_reachable() -> bool:
    async def _check() -> bool:
        try:
            conn = await asyncpg.connect(get_settings().database_url)
        except (asyncpg.PostgresError, OSError):
            return False
        await conn.close()
        return True

    return asyncio.run(_check())


def _prepare_db() -> None:
    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await apply_migrations(conn, MIGRATIONS_DIR)
        finally:
            await conn.close()

    asyncio.run(_run())


def _agent_in(ws: UUID) -> UUID:
    async def _run() -> UUID:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            agent_id: UUID | None = await conn.fetchval(
                "SELECT id FROM agent WHERE workspace_id = $1 LIMIT 1", ws
            )
            assert agent_id is not None, "Seed-Agent fehlt"
            return agent_id
        finally:
            await conn.close()

    return asyncio.run(_run())


def _token_agent_id(token_hash: str) -> UUID | None:
    async def _run() -> UUID | None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            value: UUID | None = await conn.fetchval(
                "SELECT agent_id FROM api_token WHERE token_hash = $1", token_hash
            )
            return value
        finally:
            await conn.close()

    return asyncio.run(_run())


def _token_expires_at(token_hash: str) -> datetime | None:
    async def _run() -> datetime | None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            value: datetime | None = await conn.fetchval(
                "SELECT expires_at FROM api_token WHERE token_hash = $1", token_hash
            )
            return value
        finally:
            await conn.close()

    return asyncio.run(_run())


def _expire_token(token_hash: str) -> None:
    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await conn.execute(
                "UPDATE api_token SET expires_at = now() - interval '1 hour' WHERE token_hash = $1",
                token_hash,
            )
        finally:
            await conn.close()

    asyncio.run(_run())


def _backdate_refresh_consumption(refresh_plain: str, seconds: int) -> None:
    """Verschiebt `consumed_at`/`grace_consumed_at` eines Refresh-Tokens in die
    Vergangenheit — simuliert eine Runtime, die eine veraltete Refresh-Kopie
    erst NACH Ablauf des Grace-Fensters wiederverwendet (multi-runtime Claude)."""

    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await conn.execute(
                "UPDATE oauth_refresh_token SET "
                "consumed_at = consumed_at - $2 * interval '1 second', "
                "grace_consumed_at = grace_consumed_at - $2 * interval '1 second' "
                "WHERE token_hash = $1",
                security.hash_token(refresh_plain),
                seconds,
            )
        finally:
            await conn.close()

    asyncio.run(_run())


def _remove_member(ws: UUID, user_id: UUID) -> None:
    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await conn.execute(
                "DELETE FROM workspace_member WHERE workspace_id = $1 AND user_id = $2",
                ws,
                user_id,
            )
        finally:
            await conn.close()

    asyncio.run(_run())


def _jwt(owner_id: UUID) -> str:
    return jwt.encode(
        {
            "sub": str(owner_id),
            "aud": "authenticated",
            "role": "authenticated",
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        _TEST_SECRET,
        algorithm="HS256",
    )


def _pkce() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=")
    return verifier, challenge.decode()


def _settings() -> Settings:
    return Settings(
        jwt_secret=_TEST_SECRET,
        mcp_resource_url=_RESOURCE,
        oauth_consent_url="http://localhost:5173/oauth/consent",
        oauth_issuer_url="http://testserver",
    )


def _register(client: TestClient) -> str:
    # Body wie ihn echte DCR-Clients (Claude/ChatGPT) senden: zusaetzliche
    # RFC-7591-Standardfelder muessen IGNORIERT werden, nicht mit 422 abgelehnt.
    resp = client.post(
        "/oauth/register",
        json={
            "redirect_uris": [_REDIRECT],
            "client_name": "Claude",
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
            "scope": "openid",
        },
    )
    assert resp.status_code == 201, resp.text
    return str(resp.json()["client_id"])


def _authorize_blob(client: TestClient, client_id: str, challenge: str) -> str:
    resp = client.get(
        "/oauth/authorize",
        params={
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": _REDIRECT,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "resource": _RESOURCE,
            "state": "xyz",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302, resp.text
    location: str = resp.headers["location"]
    blob = parse_qs(urlparse(location).query)["request"][0]
    return blob


def _authorize_blob_resource(
    client: TestClient, client_id: str, challenge: str, resource: str
) -> str:
    resp = client.get(
        "/oauth/authorize",
        params={
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": _REDIRECT,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "resource": resource,
            "state": "xyz",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302, resp.text
    return str(parse_qs(urlparse(resp.headers["location"]).query)["request"][0])


def _consent_code(client: TestClient, blob: str, agent_id: str, jwt_auth: dict[str, str]) -> str:
    resp = client.post(
        "/oauth/consent",
        json={"request": blob, "agent_id": agent_id, "approve": True},
        headers=jwt_auth,
    )
    assert resp.status_code == 200, resp.text
    redirect = resp.json()["redirect"]
    params = parse_qs(urlparse(redirect).query)
    assert params["state"] == ["xyz"]
    return str(params["code"][0])


def test_resource_agent_hint_parses_and_validates() -> None:
    """`_resource_agent_hint` akzeptiert die kanonische Resource und genau einen
    optionalen `?agent=<uuid>`; alles andere ist `invalid_target` (DB-frei)."""
    base = "https://mcp.example.com/mcp"
    aid = uuid4()

    # Kanonisch (kein/leerer Query) → kein Hint.
    assert oauth_service._resource_agent_hint(base, base) is None
    assert oauth_service._resource_agent_hint(f"{base}?", base) is None
    # Gueltiger agent-Query → UUID.
    assert oauth_service._resource_agent_hint(f"{base}?agent={aid}", base) == aid

    # Falsche Basis, fremder/zusaetzlicher Key, mehrfacher agent, kaputte UUID,
    # sowie Alias-Schreibweisen derselben UUID (Issue #404 N-1): `UUID(...)`
    # akzeptiert diese, die kanonische Pruefung bewusst nicht.
    for bad_resource in (
        "https://evil.example/mcp",
        f"{base}?foo=bar",
        f"{base}?agent={aid}&x=1",
        f"{base}?agent={aid}&agent={aid}",
        f"{base}?agent=not-a-uuid",
        f"{base}?agent={str(aid).replace('-', '')}",
        f"{base}?agent=urn:uuid:{aid}",
        f"{base}?agent={{{aid}}}",
    ):
        with pytest.raises(oauth_service.OAuthError) as exc:
            oauth_service._resource_agent_hint(bad_resource, base)
        assert exc.value.error == "invalid_target"


def test_resource_agent_hint_parses_path_form() -> None:
    """`_resource_agent_hint` akzeptiert zusaetzlich die RFC-8707-Pfad-Variante
    `{base}/a/<uuid>` (WP2/#404) — sie ueberlebt LLM-Clients, die fuer `resource`
    die kanonische PRM-Resource verwenden und eine Query verwerfen (DB-frei)."""
    base = "https://mcp.example.com/mcp"
    aid = uuid4()

    # Pfad-Form → UUID, optional mit leerem Query.
    assert oauth_service._resource_agent_hint(f"{base}/a/{aid}", base) == aid
    assert oauth_service._resource_agent_hint(f"{base}/a/{aid}?", base) == aid

    # Fremde Basis, kaputte UUID, zusaetzliche Pfadsegmente, fehlende UUID,
    # falsches Segment, widerspruechlicher `?agent=` zusaetzlich zur Pfad-Form,
    # sowie Alias-Schreibweisen derselben UUID im Pfad (Issue #404 N-1).
    for bad_resource in (
        f"{base}/a/not-a-uuid",
        f"{base}/a/{aid}/x",
        f"{base}/a/",
        f"{base}/b/{aid}",
        f"{base}/a/{aid}?agent={aid}",
        f"{base}/a/{aid}?agent={uuid4()}",
        f"{base}/a/{aid}?foo=bar",
        f"{base}/a/{str(aid).replace('-', '')}",
        f"{base}/a/urn:uuid:{aid}",
        f"{base}/a/{{{aid}}}",
    ):
        with pytest.raises(oauth_service.OAuthError) as exc:
            oauth_service._resource_agent_hint(bad_resource, base)
        assert exc.value.error == "invalid_target"


@pytest.mark.integration
def test_oauth_resource_agent_hint_hard_locks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Traegt die Connector-URL `?agent=<uuid>`, bindet der SIGNIERTE Blob-Agent —
    ein abweichender, vom Web gesendeter `agent_id` wird ignoriert (Hard-Lock)."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: _settings())
    monkeypatch.setattr(oauth_service, "get_settings", lambda: _settings())

    owner_id = fresh_user_id()
    ws = setup_workspace(owner_id)
    agent_id = str(_agent_in(ws))
    jwt_auth = {"Authorization": f"Bearer {_jwt(owner_id)}"}

    try:
        with TestClient(app) as client:
            client_id = _register(client)

            # Beide Hint-Formen muessen denselben Hard-Lock liefern: die Legacy-
            # Query-Variante (Rueckwaertskompatibilitaet fuer bereits eingetragene
            # Connectoren) UND die neue RFC-8707-Pfad-Variante `{resource}/a/<uuid>`
            # (WP2/#404 — ueberlebt LLM-Clients, die die Query verwerfen).
            for resource, bad_resource in (
                (f"{_RESOURCE}?agent={agent_id}", f"{_RESOURCE}?agent=not-a-uuid"),
                (f"{_RESOURCE}/a/{agent_id}", f"{_RESOURCE}/a/not-a-uuid"),
            ):
                verifier, challenge = _pkce()
                blob = _authorize_blob_resource(client, client_id, challenge, resource)
                # Web sendet absichtlich einen FREMDEN agent_id — der Seed-Agent aus
                # dem Blob muss gewinnen: Consent gelingt (Seed ist Mitglied), und der
                # ausgegebene Token ist an den Seed-Agenten gebunden.
                code = _consent_code(client, blob, str(uuid4()), jwt_auth)
                access = client.post(
                    "/oauth/token",
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": _REDIRECT,
                        "client_id": client_id,
                        "code_verifier": verifier,
                    },
                ).json()["access_token"]
                assert _token_agent_id(security.hash_token(access)) == UUID(agent_id)

                # Ungueltige UUID in der resource → authorize 400 invalid_target.
                bad = client.get(
                    "/oauth/authorize",
                    params={
                        "response_type": "code",
                        "client_id": client_id,
                        "redirect_uri": _REDIRECT,
                        "code_challenge": challenge,
                        "code_challenge_method": "S256",
                        "resource": bad_resource,
                    },
                    follow_redirects=False,
                )
                assert bad.status_code == 400
                assert bad.json()["error"] == "invalid_target"
    finally:
        cleanup_workspaces([owner_id])


@pytest.mark.integration
def test_oauth_full_flow_and_security(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: _settings())
    monkeypatch.setattr(oauth_service, "get_settings", lambda: _settings())

    owner_id = fresh_user_id()
    ws = setup_workspace(owner_id)
    agent_id = str(_agent_in(ws))
    jwt_auth = {"Authorization": f"Bearer {_jwt(owner_id)}"}

    try:
        with TestClient(app) as client:
            # --- Metadaten (RFC 8414) ---
            meta = client.get("/.well-known/oauth-authorization-server").json()
            assert meta["code_challenge_methods_supported"] == ["S256"]
            assert meta["token_endpoint"].endswith("/oauth/token")

            # --- DCR ---
            client_id = _register(client)

            # --- authorize: Open-Redirect-Choke-Point ---
            verifier, challenge = _pkce()
            # Unbekannter Client → 400 OHNE Redirect.
            bad = client.get(
                "/oauth/authorize",
                params={
                    "response_type": "code",
                    "client_id": "oac_unknown",
                    "redirect_uri": _REDIRECT,
                    "code_challenge": challenge,
                    "resource": _RESOURCE,
                },
                follow_redirects=False,
            )
            assert bad.status_code == 400
            # Nicht registrierte redirect_uri → 400.
            mism = client.get(
                "/oauth/authorize",
                params={
                    "response_type": "code",
                    "client_id": client_id,
                    "redirect_uri": "https://evil.example/cb",
                    "code_challenge": challenge,
                    "resource": _RESOURCE,
                },
                follow_redirects=False,
            )
            assert mism.status_code == 400
            # PKCE plain → 400.
            plain = client.get(
                "/oauth/authorize",
                params={
                    "response_type": "code",
                    "client_id": client_id,
                    "redirect_uri": _REDIRECT,
                    "code_challenge": challenge,
                    "code_challenge_method": "plain",
                    "resource": _RESOURCE,
                },
                follow_redirects=False,
            )
            assert plain.status_code == 400

            # --- authorize (gueltig) → consent → code ---
            blob = _authorize_blob(client, client_id, challenge)
            code = _consent_code(client, blob, agent_id, jwt_auth)

            # --- token: authorization_code (PKCE) ---
            tok = client.post(
                "/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": _REDIRECT,
                    "client_id": client_id,
                    "code_verifier": verifier,
                },
            )
            assert tok.status_code == 200, tok.text
            assert tok.headers["cache-control"] == "no-store"
            payload = tok.json()
            access = payload["access_token"]
            refresh = payload["refresh_token"]
            assert access.startswith("w2b_")
            assert payload["expires_in"] == 28800  # 8 h
            assert payload["token_type"] == "bearer"

            # Access-Token ist agent-gebunden + hat expires_at.
            assert _token_expires_at(security.hash_token(access)) is not None
            api_auth = {"Authorization": f"Bearer {access}"}
            assert client.get("/v1/me", headers=api_auth).status_code == 200

            # --- Code-Replay → invalid_grant ---
            replay = client.post(
                "/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": _REDIRECT,
                    "client_id": client_id,
                    "code_verifier": verifier,
                },
            )
            assert replay.status_code == 400
            assert replay.json()["error"] == "invalid_grant"

            # --- Refresh-Rotation ---
            r1 = client.post(
                "/oauth/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh,
                    "client_id": client_id,
                },
            )
            assert r1.status_code == 200, r1.text
            new_access = r1.json()["access_token"]
            new_refresh = r1.json()["refresh_token"]
            assert new_access != access
            assert new_refresh != refresh
            # Alter Access-Token ist durch Rotation widerrufen.
            assert client.get("/v1/me", headers=api_auth).status_code == 401
            # Neuer Access-Token funktioniert.
            new_api_auth = {"Authorization": f"Bearer {new_access}"}
            assert client.get("/v1/me", headers=new_api_auth).status_code == 200

            # --- Refresh-Replay INNERHALB der Grace (1x) → gutartiger Retry ---
            # Sofortiger Replay des soeben rotierten Refresh (verlorene Antwort /
            # paralleler Refresh): frischer Token, OHNE die Kette zu killen
            # (RFC 9700 Grace-Window).
            grace_replay = client.post(
                "/oauth/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh,
                    "client_id": client_id,
                },
            )
            assert grace_replay.status_code == 200, grace_replay.text
            grace_access = grace_replay.json()["access_token"]
            assert grace_access not in (access, new_access)
            grace_api_auth = {"Authorization": f"Bearer {grace_access}"}
            # Kette lebt: r1-Nachfolger UND Grace-Token funktionieren beide.
            assert client.get("/v1/me", headers=new_api_auth).status_code == 200
            assert client.get("/v1/me", headers=grace_api_auth).status_code == 200

            # --- Zweiter Grace-Replay → single-use erschoepft → NUR abgelehnt ---
            # Der Grace-Retry ist atomar genau-einmal (grace_consumed_at); ein
            # weiterer Einloese-Versuch desselben Tokens wird abgelehnt, killt
            # aber NICHT die Kette: multi-runtime MCP-Clients (mehrere Claude-
            # Agenten teilen sich die Connector-Tokens) retrien tote Refresh-
            # Kopien gutartig — eine Ketten-Revocation wuerde bei jedem Retry
            # die frisch rotierten Access-Tokens der gesunden Runtime mit
            # widerrufen → dauerhafter "verbunden, aber keine Tools"-Lockout.
            replay_refresh = client.post(
                "/oauth/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh,
                    "client_id": client_id,
                },
            )
            assert replay_refresh.status_code == 400
            assert replay_refresh.json()["error"] == "invalid_grant"
            # Beide gesunden Zweige LEBEN weiter — kein Lockout.
            assert client.get("/v1/me", headers=new_api_auth).status_code == 200
            assert client.get("/v1/me", headers=grace_api_auth).status_code == 200

            # --- Stale-Reuse AUSSERHALB der Grace → abgelehnt, Kette lebt ---
            # Runtime B haelt eine veraltete Refresh-Kopie und verwendet sie
            # deutlich nach der Rotation wieder (Backdating simuliert >Grace).
            _backdate_refresh_consumption(refresh, seconds=3600)
            stale = client.post(
                "/oauth/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh,
                    "client_id": client_id,
                },
            )
            assert stale.status_code == 400
            assert stale.json()["error"] == "invalid_grant"
            # Die aktiven Access-Tokens der gesunden Runtimes bleiben gueltig …
            assert client.get("/v1/me", headers=new_api_auth).status_code == 200
            assert client.get("/v1/me", headers=grace_api_auth).status_code == 200
            # … und der nie benutzte Nachfolge-Refresh rotiert weiterhin normal.
            r2 = client.post(
                "/oauth/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": new_refresh,
                    "client_id": client_id,
                },
            )
            assert r2.status_code == 200, r2.text

            # --- Access-Token-Expiry → 401 ---
            verifier2, challenge2 = _pkce()
            blob2 = _authorize_blob(client, client_id, challenge2)
            code2 = _consent_code(client, blob2, agent_id, jwt_auth)
            tok2 = client.post(
                "/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code2,
                    "redirect_uri": _REDIRECT,
                    "client_id": client_id,
                    "code_verifier": verifier2,
                },
            ).json()
            access2 = tok2["access_token"]
            auth2 = {"Authorization": f"Bearer {access2}"}
            assert client.get("/v1/me", headers=auth2).status_code == 200
            _expire_token(security.hash_token(access2))
            assert client.get("/v1/me", headers=auth2).status_code == 401
    finally:
        cleanup_workspaces([owner_id])


@pytest.mark.integration
def test_oauth_refresh_revoked_when_user_deprovisioned(monkeypatch: pytest.MonkeyPatch) -> None:
    """Wird der User aus dem Workspace entfernt, schlaegt der Refresh fehl und die
    ganze Token-Kette wird widerrufen (Refresh = Re-Authorization-Punkt)."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: _settings())
    monkeypatch.setattr(oauth_service, "get_settings", lambda: _settings())

    owner_id = fresh_user_id()
    ws = setup_workspace(owner_id)
    agent_id = str(_agent_in(ws))
    jwt_auth = {"Authorization": f"Bearer {_jwt(owner_id)}"}

    try:
        with TestClient(app) as client:
            client_id = _register(client)
            verifier, challenge = _pkce()
            blob = _authorize_blob(client, client_id, challenge)
            code = _consent_code(client, blob, agent_id, jwt_auth)
            tok = client.post(
                "/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": _REDIRECT,
                    "client_id": client_id,
                    "code_verifier": verifier,
                },
            ).json()
            access, refresh = tok["access_token"], tok["refresh_token"]
            api_auth = {"Authorization": f"Bearer {access}"}
            assert client.get("/v1/me", headers=api_auth).status_code == 200

            # User wird aus dem Workspace entfernt → Refresh muss scheitern.
            _remove_member(ws, owner_id)
            resp = client.post(
                "/oauth/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh,
                    "client_id": client_id,
                },
            )
            assert resp.status_code == 400
            assert resp.json()["error"] == "invalid_grant"
            # Der aktive Access-Token der Kette ist mit-widerrufen.
            assert client.get("/v1/me", headers=api_auth).status_code == 401
    finally:
        cleanup_workspaces([owner_id])


@pytest.mark.integration
def test_oauth_consent_rejects_non_member(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ein Nicht-Mitglied des Agent-Workspace darf keinen Code erhalten (403)."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: _settings())
    monkeypatch.setattr(oauth_service, "get_settings", lambda: _settings())

    owner_id = fresh_user_id()
    stranger_id = fresh_user_id()
    ws = setup_workspace(owner_id)
    stranger_ws = setup_workspace(stranger_id)
    agent_id = str(_agent_in(ws))
    stranger_auth = {"Authorization": f"Bearer {_jwt(stranger_id)}"}

    try:
        with TestClient(app) as client:
            client_id = _register(client)
            _verifier, challenge = _pkce()
            blob = _authorize_blob(client, client_id, challenge)
            # Fremder User versucht, einen Agenten EINES ANDEREN Workspace zu binden.
            resp = client.post(
                "/oauth/consent",
                json={"request": blob, "agent_id": agent_id, "approve": True},
                headers=stranger_auth,
            )
            assert resp.status_code == 403
    finally:
        cleanup_workspaces([owner_id, stranger_id])
        # stranger_ws nur referenziert, Cleanup raeumt via user_ids.
        _ = stranger_ws


# --- consent/preview (WP1, Issue #405) -------------------------------------
#
# Der Preview-Endpunkt weist den per Hard-Lock gebundenen Agenten LESBAR aus.
# Er ist rein lesend und trifft KEINE Autorisierungs-Entscheidung — das 403
# bleibt am `POST /oauth/consent`. Die Aufloesung laeuft ueber exakt dieselbe
# Funktion (`_resolve_agent_membership`), die dort ueber Erfolg/403 entscheidet.


class _FakePool:
    """Minimaler asyncpg-Pool-Ersatz fuer die DB-freien Preview-Unit-Tests.

    Kennt genau die Queries, die der Preview-Pfad absetzt (Memberships des
    Users, Agent-Existenz je Kandidaten-Workspace, Anzeige-Namen) — und prueft
    nebenbei die RLS-Invariante: die `agent`-Reads MUESSEN unter `tenant_scope`
    laufen (Migration 0037).
    """

    def __init__(
        self,
        memberships: list[tuple[UUID, str]],
        agents: dict[UUID, tuple[UUID, str, str]],
    ) -> None:
        self._memberships = memberships
        self._agents = agents

    async def fetch(self, query: str, *args: object) -> list[dict[str, object]]:
        assert "FROM workspace_member" in query
        return [{"workspace_id": ws, "role": role} for ws, role in self._memberships]

    async def fetchval(self, query: str, *args: object) -> int | None:
        assert "FROM agent" in query
        assert current_tenant_context() is not None, "agent-Read ohne tenant_scope"
        found = self._agents.get(cast(UUID, args[0]))
        return 1 if found is not None and found[0] == args[1] else None

    async def fetchrow(self, query: str, *args: object) -> dict[str, object] | None:
        assert "JOIN workspace" in query
        assert current_tenant_context() is not None, "agent-Read ohne tenant_scope"
        found = self._agents.get(cast(UUID, args[0]))
        if found is None or found[0] != args[1]:
            return None
        return {"agent_name": found[1], "workspace_name": found[2]}


def _preview_service(
    pool: _FakePool, monkeypatch: pytest.MonkeyPatch
) -> oauth_service.OAuthService:
    monkeypatch.setattr(oauth_service, "get_settings", lambda: _settings())
    return oauth_service.OAuthService(
        # Echtes Repository ueber den Fake-Pool: es haelt nur `self._pool` und
        # setzt SQL ab — der Fake bildet `fetchrow` ab. So braucht der
        # Produktions-Konstruktor keinen None-Fallback fuer Testzwecke.
        oauth_repo=PgOAuthRepository(cast(Any, pool)),
        token_repo=cast(Any, None),
        pool=cast(Any, pool),
        audit=None,
    )


def _blob(service: oauth_service.OAuthService, agent_id: UUID | None, ttl: float = 600.0) -> str:
    """Signierter Request-Blob wie ihn `authorize` erzeugt (mit/ohne Agent-Hint)."""
    return service._sign(
        {
            "client_id": "oac_test",
            "client_name": "Claude",
            "redirect_uri": _REDIRECT,
            "code_challenge": "chal",
            "state": "xyz",
            "resource": _RESOURCE,
            "agent_id": str(agent_id) if agent_id is not None else None,
            "scope": None,
            "exp": time.time() + ttl,
        }
    )


def test_consent_preview_without_hint_is_unlocked(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ohne Agent-Hint im Blob: `locked=False`, kein Agent (DB-frei)."""
    ws, user = uuid4(), uuid4()
    service = _preview_service(_FakePool([(ws, "admin")], {}), monkeypatch)

    result = asyncio.run(service.consent_preview(user, _blob(service, None)))

    assert result.model_dump() == {"locked": False, "agent": None}


def test_consent_preview_resolves_own_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Agent-Hint + Agent in einem Workspace des Users: lesbarer Agent (DB-frei)."""
    ws, user, agent = uuid4(), uuid4(), uuid4()
    service = _preview_service(
        _FakePool([(ws, "admin")], {agent: (ws, "Coder", "Who2Be")}), monkeypatch
    )

    result = asyncio.run(service.consent_preview(user, _blob(service, agent)))

    assert result.locked is True
    assert result.agent is not None
    assert result.agent.id == agent
    assert result.agent.name == "Coder"
    assert result.agent.workspace_id == ws
    assert result.agent.workspace_name == "Who2Be"


def test_consent_preview_non_default_workspace_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Der gelockte Agent liegt im ZWEITEN Workspace des Users (Kern von #405).

    Genau dieser Fall zeigte im Web bisher nur die rohe UUID — die Consent-Seite
    laedt die Agentenliste nur fuer den Default-Workspace, das serverseitige
    Gate sucht ueber ALLE Memberships. Der Preview folgt dem Gate (DB-frei).
    """
    default_ws, other_ws, user, agent = uuid4(), uuid4(), uuid4(), uuid4()
    service = _preview_service(
        _FakePool(
            [(default_ws, "admin"), (other_ws, "editor")],
            {agent: (other_ws, "Kanal-Mentor", "Team-Workspace")},
        ),
        monkeypatch,
    )

    result = asyncio.run(service.consent_preview(user, _blob(service, agent)))

    assert result.agent is not None
    assert result.agent.workspace_id == other_ws
    assert result.agent.workspace_name == "Team-Workspace"


def test_consent_preview_is_no_existence_oracle(monkeypatch: pytest.MonkeyPatch) -> None:
    """„Agent existiert nicht" und „Agent gehoert mir nicht" sind IDENTISCH.

    Beide liefern `{locked: True, agent: None}` — kein 403, kein abweichender
    Body, keine abweichende Fehlerform. Ein Angreifer kann ueber den Preview
    also nicht herausfinden, ob eine Agent-UUID existiert (DB-frei).
    """
    own_ws, foreign_ws, user = uuid4(), uuid4(), uuid4()
    foreign_agent, missing_agent = uuid4(), uuid4()
    service = _preview_service(
        _FakePool([(own_ws, "admin")], {foreign_agent: (foreign_ws, "Fremd", "Fremde WS")}),
        monkeypatch,
    )

    foreign = asyncio.run(service.consent_preview(user, _blob(service, foreign_agent)))
    missing = asyncio.run(service.consent_preview(user, _blob(service, missing_agent)))

    assert foreign.model_dump() == {"locked": True, "agent": None}
    assert foreign.model_dump() == missing.model_dump()


def test_consent_preview_rejects_tampered_or_expired_blob(monkeypatch: pytest.MonkeyPatch) -> None:
    """Manipulierter oder abgelaufener Blob ⇒ `OAuthError` (400), keine Aufloesung."""
    ws, user, agent = uuid4(), uuid4(), uuid4()
    service = _preview_service(
        _FakePool([(ws, "admin")], {agent: (ws, "Coder", "Who2Be")}), monkeypatch
    )

    valid = _blob(service, agent)
    body, _, sig = valid.partition(".")
    # Payload getauscht (fremder Agent untergeschoben), Signatur unveraendert.
    forged_body = service._sign({"agent_id": str(uuid4()), "exp": time.time() + 600}).partition(
        "."
    )[0]
    for bad in (f"{forged_body}.{sig}", f"{body}.{sig[:-1]}x", body, "", _blob(service, agent, -1)):
        with pytest.raises(oauth_service.OAuthError) as exc:
            asyncio.run(service.consent_preview(user, bad))
        assert exc.value.error == "invalid_request"
        assert exc.value.status_code == 400


@pytest.mark.integration
def test_oauth_consent_preview_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """End-to-End ueber `POST /oauth/consent/preview` (Vertrag fuer das Web-Paket).

    Vier Faelle: kein Hint ⇒ unlocked; eigener Agent ⇒ lesbar; fremder User auf
    demselben Blob ⇒ `{locked: true, agent: null}` (200, KEIN 403); kaputte
    Signatur ⇒ 400 in OAuthError-Form.
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: _settings())
    monkeypatch.setattr(oauth_service, "get_settings", lambda: _settings())

    owner_id = fresh_user_id()
    stranger_id = fresh_user_id()
    ws = setup_workspace(owner_id)
    setup_workspace(stranger_id)
    agent_id = str(_agent_in(ws))
    jwt_auth = {"Authorization": f"Bearer {_jwt(owner_id)}"}
    stranger_auth = {"Authorization": f"Bearer {_jwt(stranger_id)}"}

    try:
        with TestClient(app) as client:
            client_id = _register(client)
            _verifier, challenge = _pkce()

            # (1) Blob ohne Agent-Hint → unlocked.
            plain_blob = _authorize_blob(client, client_id, challenge)
            resp = client.post(
                "/oauth/consent/preview", json={"request": plain_blob}, headers=jwt_auth
            )
            assert resp.status_code == 200, resp.text
            assert resp.headers["cache-control"] == "no-store"
            assert resp.json() == {"locked": False, "agent": None}

            # (2) Hard-Lock-Blob → lesbarer Agent (Name + Workspace-Name).
            locked_blob = _authorize_blob_resource(
                client, client_id, challenge, f"{_RESOURCE}/a/{agent_id}"
            )
            resp = client.post(
                "/oauth/consent/preview", json={"request": locked_blob}, headers=jwt_auth
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["locked"] is True
            assert body["agent"]["id"] == agent_id
            assert body["agent"]["workspace_id"] == str(ws)
            assert body["agent"]["name"]
            assert body["agent"]["workspace_name"]

            # (3) Fremder User auf demselben Blob: 200 + agent=None (KEIN 403,
            #     kein Existenz-Orakel) — identisch zu einer nie existierenden
            #     Agent-UUID.
            foreign = client.post(
                "/oauth/consent/preview", json={"request": locked_blob}, headers=stranger_auth
            )
            assert foreign.status_code == 200, foreign.text
            assert foreign.json() == {"locked": True, "agent": None}
            ghost_blob = _authorize_blob_resource(
                client, client_id, challenge, f"{_RESOURCE}/a/{uuid4()}"
            )
            ghost = client.post(
                "/oauth/consent/preview", json={"request": ghost_blob}, headers=jwt_auth
            )
            assert ghost.status_code == 200, ghost.text
            assert ghost.json() == foreign.json()

            # (4) Manipulierte Signatur → 400 in OAuthError-Form.
            bad = client.post(
                "/oauth/consent/preview",
                json={"request": locked_blob[:-1] + ("x" if locked_blob[-1] != "x" else "y")},
                headers=jwt_auth,
            )
            assert bad.status_code == 400
            assert bad.json()["error"] == "invalid_request"

            # (5) Ohne Login: kein Preview.
            assert client.post(
                "/oauth/consent/preview", json={"request": locked_blob}
            ).status_code in (401, 403)

            # Der autoritative Pfad bleibt unveraendert: derselbe fremde User
            # bekommt am echten Consent weiterhin 403.
            denied = client.post(
                "/oauth/consent",
                json={"request": locked_blob, "agent_id": agent_id, "approve": True},
                headers=stranger_auth,
            )
            assert denied.status_code == 403
    finally:
        cleanup_workspaces([owner_id, stranger_id])


# --- Consent-Zugang: NUR die eingeloggte Web-Session -------------------------
#
# `/oauth/consent` und `/oauth/consent/preview` sind der interaktive
# Entscheidungspunkt eines MENSCHEN. Ein `w2b_`-API-Token darf sie nicht
# passieren: sonst laesst sich ein bereits ausgegebener (womoeglich bewusst auf
# `viewer` herabgestufter) Token dazu benutzen, sich ueber DCR → authorize →
# consent → token einen NEUEN, staerkeren Token ausstellen zu lassen — die
# Rolle des frischen Tokens kommt aus der aktuellen Membership, nicht aus der
# im aufrufenden Token gepinnten Snapshot-Rolle. `/oauth/*` laeuft ausserhalb
# des Workspace-Prefix, es greift also auch kein `get_current_workspace`.


def _issue_api_token(
    workspace_id: UUID, owner_id: UUID, agent_id: UUID, role: str = "viewer"
) -> str:
    """Legt einen echten `w2b_`-API-Token an und liefert ihn im Klartext.

    Agent-gebunden (Migration 0048: `api_token_agent_bound_or_revoked`) — genau
    die Form, die auch ein Connector-Token beim LLM-Client hat.
    """
    plain = security.new_token()

    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await conn.execute(
                "INSERT INTO api_token "
                "(workspace_id, owner_id, name, token_hash, role, agent_id) "
                "VALUES ($1, $2, $3, $4, $5, $6)",
                workspace_id,
                owner_id,
                "consent-escalation-test",
                security.hash_token(plain),
                role,
                agent_id,
            )
        finally:
            await conn.close()

    asyncio.run(_run())
    return plain


@pytest.mark.integration
def test_oauth_consent_rejects_api_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Privilege-Escalation-Regression: ein `w2b_`-Token kommt am Consent NICHT
    durch (401) — weder am Submit noch an der Preview. Der JWT-Pfad des
    gleichen Users bleibt unveraendert erfolgreich."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: _settings())
    monkeypatch.setattr(oauth_service, "get_settings", lambda: _settings())

    owner_id = fresh_user_id()
    ws = setup_workspace(owner_id)
    agent_id = str(_agent_in(ws))
    jwt_auth = {"Authorization": f"Bearer {_jwt(owner_id)}"}
    # Bewusst herabgestufter Token DESSELBEN Owners — genau der Fall, in dem
    # der Consent-Pfad sonst wieder `admin` ausstellen wuerde.
    api_token = _issue_api_token(ws, owner_id, UUID(agent_id), "viewer")
    token_auth = {"Authorization": f"Bearer {api_token}"}

    try:
        with TestClient(app) as client:
            client_id = _register(client)
            _verifier, challenge = _pkce()
            blob = _authorize_blob(client, client_id, challenge)

            # (1) Consent-Submit mit API-Token ⇒ 401, KEIN Auth-Code.
            escalation = client.post(
                "/oauth/consent",
                json={"request": blob, "agent_id": agent_id, "approve": True},
                headers=token_auth,
            )
            assert escalation.status_code == 401, escalation.text
            assert escalation.headers.get("www-authenticate") == "Bearer"
            assert "redirect" not in escalation.json()

            # (2) Preview mit API-Token ⇒ 401 (Workspace-Pin bleibt dicht).
            preview = client.post(
                "/oauth/consent/preview", json={"request": blob}, headers=token_auth
            )
            assert preview.status_code == 401, preview.text

            # (3) Der JWT-Pfad desselben Users: unveraendert.
            ok_preview = client.post(
                "/oauth/consent/preview", json={"request": blob}, headers=jwt_auth
            )
            assert ok_preview.status_code == 200, ok_preview.text
            assert ok_preview.json() == {"locked": False, "agent": None}
            assert _consent_code(client, blob, agent_id, jwt_auth)
    finally:
        cleanup_workspaces([owner_id])


@pytest.mark.integration
def test_oauth_consent_agent_id_is_optional(monkeypatch: pytest.MonkeyPatch) -> None:
    """`agent_id` ist optional: Ablehnen geht immer durch (kein 422), Zustimmen
    ohne Agent faellt als `invalid_request`, und ein Blob-Hard-Lock bindet auch
    dann, wenn der Client gar keinen `agent_id` mitschickt."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: _settings())
    monkeypatch.setattr(oauth_service, "get_settings", lambda: _settings())

    owner_id = fresh_user_id()
    ws = setup_workspace(owner_id)
    agent_id = str(_agent_in(ws))
    jwt_auth = {"Authorization": f"Bearer {_jwt(owner_id)}"}

    try:
        with TestClient(app) as client:
            client_id = _register(client)
            _verifier, challenge = _pkce()
            blob = _authorize_blob(client, client_id, challenge)

            # (1) Ablehnen OHNE agent_id ⇒ access_denied-Redirect. Genau der
            #     Fall "gelockt, aber nicht aufloesbar" im Web: Approve ist
            #     gesperrt, Deny muss trotzdem beim Client ankommen.
            denied = client.post(
                "/oauth/consent", json={"request": blob, "approve": False}, headers=jwt_auth
            )
            assert denied.status_code == 200, denied.text
            denied_params = parse_qs(urlparse(denied.json()["redirect"]).query)
            assert denied_params["error"] == ["access_denied"]
            assert denied_params["state"] == ["xyz"]

            # (2) Zustimmen ohne agent_id und ohne Blob-Hint ⇒ invalid_request.
            incomplete = client.post(
                "/oauth/consent", json={"request": blob, "approve": True}, headers=jwt_auth
            )
            assert incomplete.status_code == 400, incomplete.text
            assert incomplete.json()["detail"] == "invalid_request"

            # (3) Zustimmen ohne agent_id, aber MIT Blob-Hint ⇒ Hard-Lock greift
            #     trotzdem und der Token haengt am Blob-Agenten.
            verifier, locked_challenge = _pkce()
            locked_blob = _authorize_blob_resource(
                client, client_id, locked_challenge, f"{_RESOURCE}/a/{agent_id}"
            )
            approved = client.post(
                "/oauth/consent", json={"request": locked_blob, "approve": True}, headers=jwt_auth
            )
            assert approved.status_code == 200, approved.text
            code = parse_qs(urlparse(approved.json()["redirect"]).query)["code"][0]
            access = client.post(
                "/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": _REDIRECT,
                    "client_id": client_id,
                    "code_verifier": verifier,
                },
            ).json()["access_token"]
            assert _token_agent_id(security.hash_token(access)) == UUID(agent_id)
    finally:
        cleanup_workspaces([owner_id])
