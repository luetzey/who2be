"""Integrationstest fuer `GET /v1/workspaces/{ws_id}/whoami` (#253).

Deckt die drei Identitaets-Pfade ab:
- **JWT/Mensch:** kein Pro-Agent-Limit → `unrestricted=True`, `capabilities`
  und `read_scopes` sind `null`, Rolle aus der Membership.
- **Agent-gebundener Token:** konkrete Tool-Policy → `unrestricted=False`,
  gewaehrte Write-Capabilities + Read-Scopes ausgegeben, `agent_id` gesetzt.
- **Ungueltiger Token:** 401.

Plus: org-weite Entitlement-`features` werden in allen Faellen geliefert.
Laeuft nur mit erreichbarer Datenbank; ohne DB wird der Test uebersprungen.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

import asyncpg
import jwt
import pytest
from fastapi.testclient import TestClient

from who2be_api.core import security
from who2be_api.core.config import Settings, get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.main import app
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace

_TEST_SECRET = "integration-test-jwt-secret-padding-0123456789"


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


def _auth(owner_id: UUID) -> dict[str, str]:
    token = jwt.encode(
        {
            "sub": str(owner_id),
            "aud": "authenticated",
            "role": "authenticated",
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        _TEST_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def _builder_agent_id(ws: UUID) -> str:
    """ID des Seed-„Builder"-Agenten (write-faehige Policy, Reads = `all`)."""

    async def _run() -> str:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            agent_id = await conn.fetchval(
                "SELECT id FROM agent WHERE workspace_id = $1 LIMIT 1", ws
            )
            assert agent_id is not None, "Seed-Agent fehlt"
            return str(agent_id)
        finally:
            await conn.close()

    return asyncio.run(_run())


@pytest.mark.integration
def test_whoami_jwt_is_unrestricted(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mensch/JWT: kein Pro-Agent-Limit → unrestricted, capabilities/read_scopes null."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)

    try:
        with TestClient(app) as client:
            resp = client.get(f"/v1/workspaces/{ws}/whoami", headers=_auth(owner))
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["user_id"] == str(owner)
            assert body["workspace_id"] == str(ws)
            assert body["role"] == "admin"  # Personal-Workspace-Owner
            assert body["is_api_token"] is False
            assert body["agent_id"] is None
            # KRITISCH: kein Pro-Agent-Limit ≠ "nichts erlaubt".
            assert body["unrestricted"] is True
            assert body["capabilities"] is None
            assert body["read_scopes"] is None
            # On-Prem-Default: alle Features (OSS_ENTITLEMENT) — orthogonal zur Policy.
            assert "core" in body["features"]
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_whoami_agent_token_lists_capabilities(monkeypatch: pytest.MonkeyPatch) -> None:
    """Agent-gebundener Token: konkrete Policy → Identitaet + Capabilities + Scopes."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    agent_id = _builder_agent_id(ws)
    jwt_auth = _auth(owner)

    try:
        with TestClient(app) as client:
            token = client.post(
                f"/v1/workspaces/{ws}/tokens",
                json={"name": "mcp", "agent_id": agent_id},
                headers=jwt_auth,
            ).json()["token"]
            token_auth = {"Authorization": f"Bearer {token}"}

            resp = client.get(f"/v1/workspaces/{ws}/whoami", headers=token_auth)
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["user_id"] == str(owner)
            assert body["is_api_token"] is True
            assert body["agent_id"] == agent_id
            # Builder traegt eine echte Tool-Policy → nicht unrestricted.
            assert body["unrestricted"] is False
            # Builder gewaehrt alle Writes + system_prompt_write (ADR-0040) +
            # feedback_write (ADR-0038, default an) + feedback_resolve
            # (Kurations-Handlung des Meta-Agenten, Content-Stand 6) +
            # promote_retire.
            assert set(body["capabilities"]) == {
                "persona_write",
                "playbook_write",
                "resource_write",
                "agent_write",
                "system_prompt_write",
                "feedback_write",
                "feedback_resolve",
                "promote_retire",
            }
            # Builder-Reads = `all` (persona ist An/Aus → 'all').
            assert body["read_scopes"] == {
                "persona": "all",
                "playbook": "all",
                "resource": "all",
                "agent": "all",
            }
            assert "core" in body["features"]
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_whoami_rejects_invalid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ungueltiger Bearer-Token → 401."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)

    try:
        with TestClient(app) as client:
            resp = client.get(
                f"/v1/workspaces/{ws}/whoami",
                headers={"Authorization": "Bearer w2b_definitely-not-a-real-token"},
            )
            assert resp.status_code == 401
    finally:
        cleanup_workspaces([owner])
