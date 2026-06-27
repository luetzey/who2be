"""Integrationstest fuer Tag-Praedikat-Write-Scoping (ADR-0039, Track 4-B).

Ein agent-gebundener Token mit `write_tags={"playbook": ["support"]}` darf nur
`support`-getaggte Playbooks anlegen/aendern; `legal` wird mit 403 abgelehnt, und
ein bestehendes `legal`-Playbook kann er nicht uebernehmen (Existing-Tag-Check).
"""

import asyncio
import json
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


def _restrict_builder_to_support(ws: UUID) -> str:
    """Builder-Agent auf 'darf nur support-Playbooks schreiben' setzen; gibt id."""

    async def _run() -> str:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            agent_id = await conn.fetchval(
                "SELECT id FROM agent WHERE workspace_id = $1 LIMIT 1", ws
            )
            policy = {
                "playbook_read": "all",
                "playbook_write": True,
                "write_tags": {"playbook": ["support"]},
            }
            await conn.execute(
                "UPDATE agent SET tool_policy = $2::jsonb WHERE id = $1",
                agent_id,
                json.dumps(policy),
            )
            return str(agent_id)
        finally:
            await conn.close()

    return asyncio.run(_run())


def _playbook(name: str, tags: list[str]) -> dict[str, object]:
    return {
        "name": name,
        "content": {
            "description": "d",
            "body": "1. Step.",
            "type": "workflow",
            "tags": tags,
            "triggers": None,
        },
    }


@pytest.mark.integration
def test_write_tags_scopes_playbook_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    jwt_auth = _auth(owner)
    agent_id = _restrict_builder_to_support(ws)
    pbase = f"/v1/workspaces/{ws}/playbooks"

    try:
        with TestClient(app) as client:
            token = client.post(
                f"/v1/workspaces/{ws}/tokens",
                json={"name": "mcp", "agent_id": agent_id},
                headers=jwt_auth,
            ).json()["token"]
            tok = {"Authorization": f"Bearer {token}"}

            # support-getaggt → erlaubt.
            ok = client.post(pbase, json=_playbook("Support-PB", ["support"]), headers=tok)
            assert ok.status_code == 201, ok.text

            # legal-getaggt → 403 (eingehender Tag-Check).
            blocked = client.post(pbase, json=_playbook("Legal-PB", ["legal"]), headers=tok)
            assert blocked.status_code == 403, blocked.text

            # Owner legt ein legal-Playbook an; der Agent darf es NICHT uebernehmen
            # (Existing-Tag-Check beim Update).
            legal_id = client.post(
                pbase, json=_playbook("Owner-Legal", ["legal"]), headers=jwt_auth
            ).json()["id"]
            takeover = client.put(
                f"{pbase}/{legal_id}",
                json={"name": "Owner-Legal", "content": _playbook("x", ["support"])["content"]},
                headers=tok,
            )
            assert takeover.status_code == 403, takeover.text
    finally:
        cleanup_workspaces([owner])
