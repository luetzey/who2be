"""Integrationstest fuer `GET /v1/workspaces/{ws}/playbooks/triggers` (Welle 5).

Discovery-Aggregat fuer den MCP-Tool `list_triggers`: liefert pro Trigger-
Keyword die zugehoerigen Playbooks. Wir verifizieren Dedup ueber mehrere
Playbooks, Workspace-Isolation und das leere Default-Verhalten.
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


def _playbook_body(name: str, triggers: str | None) -> dict[str, object]:
    return {
        "name": name,
        "content": {
            "description": "d",
            "body": "1.",
            "type": "workflow",
            "tags": [],
            "triggers": triggers,
        },
    }


@pytest.mark.integration
def test_playbook_triggers_aggregates_dedup_and_isolates_per_workspace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    other = fresh_user_id()
    ws = setup_workspace(owner)
    other_ws = setup_workspace(other)
    auth = _auth(owner)
    other_auth = _auth(other)
    base = f"/v1/workspaces/{ws}/playbooks"
    other_base = f"/v1/workspaces/{other_ws}/playbooks"

    try:
        with TestClient(app) as client:
            # Drei Playbooks: zwei teilen sich "reset", "logout" ist exklusiv,
            # eines hat keine Trigger.
            create_resps = [
                client.post(base, json=_playbook_body("Reset-Mail", "reset, logout"), headers=auth),
                client.post(
                    base,
                    json=_playbook_body("Reset-Telefon", " reset , callback"),
                    headers=auth,
                ),
                client.post(base, json=_playbook_body("Smalltalk", None), headers=auth),
            ]
            for resp in create_resps:
                assert resp.status_code == 201, resp.text
            ids = {r.json()["name"]: r.json()["id"] for r in create_resps}

            # Fremd-Workspace mit eigenem Trigger.
            client.post(other_base, json=_playbook_body("Other", "spam"), headers=other_auth)

            resp = client.get(f"{base}/triggers", headers=auth)
            assert resp.status_code == 200, resp.text
            triggers = resp.json()

            # Lexikografisch sortiert (callback, logout, reset).
            assert [item["trigger"] for item in triggers] == ["callback", "logout", "reset"]

            by_trigger = {item["trigger"]: item["playbooks"] for item in triggers}
            assert {pb["name"] for pb in by_trigger["reset"]} == {"Reset-Mail", "Reset-Telefon"}
            assert {pb["id"] for pb in by_trigger["reset"]} == {
                ids["Reset-Mail"],
                ids["Reset-Telefon"],
            }
            assert by_trigger["logout"][0]["name"] == "Reset-Mail"
            assert by_trigger["callback"][0]["name"] == "Reset-Telefon"

            # Fremd-Workspace darf nicht durchschlagen.
            other_resp = client.get(f"{other_base}/triggers", headers=other_auth)
            assert [item["trigger"] for item in other_resp.json()] == ["spam"]

            # Nicht-Mitglied wird vor dem Lookup geblockt (403).
            assert client.get(f"{base}/triggers", headers=other_auth).status_code == 403
    finally:
        cleanup_workspaces([owner, other])


@pytest.mark.integration
def test_playbook_triggers_empty_for_fresh_workspace(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)

    try:
        with TestClient(app) as client:
            resp = client.get(f"/v1/workspaces/{ws}/playbooks/triggers", headers=auth)
            assert resp.status_code == 200
            assert resp.json() == []
    finally:
        cleanup_workspaces([owner])
