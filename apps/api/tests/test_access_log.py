"""Integrationstests fuer das Auto-Zugriffslog (ADR-0047, WP14 — Spec F).

Spec-Akzeptanzen (User-Entscheidung 6):
- Jeder Agent-Zugriff wird serverseitig geloggt, dedupliziert pro
  Element + Operation + Tag (append-only `agent_access_log`, 0079).
- Menschen-Tokens erzeugen KEINE Eintraege.
- `sensitivity_at_access` ist der SERVER-Stand des Objekts.
- Die Agent-Modell-Config (`model_provider`/`model_name`) laeuft ueber den
  Agent-Update-Pfad und wird im `audit_log` protokolliert.
"""

import asyncio
from collections.abc import Callable
from typing import Any
from uuid import UUID

import asyncpg
import pytest
from fastapi.testclient import TestClient

from who2be_api.core.config import get_settings
from who2be_api.main import app
from who2be_api.testing.workspace_setup import (
    cleanup_workspaces,
    fresh_user_id,
    setup_workspace,
)

AuthFactory = Callable[[UUID], dict[str, str]]


def _db_fetch(sql: str, *args: object) -> list[Any]:
    async def _run() -> list[Any]:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            return list(await conn.fetch(sql, *args))
        finally:
            await conn.close()

    return asyncio.run(_run())


def _agent_token(
    client: TestClient, prefix: str, name: str, policy: dict[str, object], auth: dict[str, str]
) -> tuple[str, dict[str, str]]:
    agent = client.post(
        f"{prefix}/agents", json={"name": name, "tool_policy": policy}, headers=auth
    )
    assert agent.status_code == 201, agent.text
    agent_id = agent.json()["id"]
    token = client.post(f"{prefix}/tokens", json={"name": name, "agent_id": agent_id}, headers=auth)
    assert token.status_code == 201, token.text
    return agent_id, {"Authorization": f"Bearer {token.json()['token']}"}


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_agent_access_is_logged_and_deduped(make_auth_headers: AuthFactory) -> None:
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            agent_id, agent_headers = _agent_token(
                client, prefix, "analyst", {"workarea_write": True}, auth
            )
            created = client.post(
                f"{prefix}/artifacts",
                json={
                    "title": "Sensible Notiz",
                    "content_md": "Kontostand Details",
                    "occurred_at": "2026-08-01T00:00:00Z",
                    "sensitivity": "sensitive",
                },
                headers=agent_headers,
            )
            assert created.status_code == 201, created.text
            artifact_id = created.json()["id"]
            # Zwei Reads am selben Tag → EINE read-Row (Dedupe pro Tag).
            for _ in range(2):
                assert (
                    client.get(
                        f"{prefix}/wa-artifacts/{artifact_id}", headers=agent_headers
                    ).status_code
                    == 200
                )
            rows = _db_fetch(
                "SELECT operation, sensitivity_at_access FROM agent_access_log "
                "WHERE agent_id = $1 AND ref_id = $2 ORDER BY operation",
                UUID(agent_id),
                artifact_id,
            )
            operations = [r["operation"] for r in rows]
            assert operations == ["read", "write"]  # je genau EINE Row
            # Server-Snapshot: das Artifact ist 'sensitive' — der Log-Eintrag auch.
            assert all(r["sensitivity_at_access"] == "sensitive" for r in rows)
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_human_access_is_not_logged(make_auth_headers: AuthFactory) -> None:
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area = client.post(f"{prefix}/work-areas", json={"name": "Team"}, headers=auth)
            created = client.post(
                f"{prefix}/work-areas/{area.json()['id']}/artifacts",
                json={
                    "title": "Notiz",
                    "content_md": "Inhalt",
                    "occurred_at": "2026-08-01T00:00:00Z",
                },
                headers=auth,
            )
            assert created.status_code == 201
            client.get(f"{prefix}/wa-artifacts/{created.json()['id']}", headers=auth)
            rows = _db_fetch("SELECT 1 FROM agent_access_log WHERE workspace_id = $1", ws)
            assert rows == []
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_model_config_change_is_audited(make_auth_headers: AuthFactory) -> None:
    """Agent-Modell-Config (User-Entscheidung 6) → audit_log-Eintrag."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            agent = client.post(f"{prefix}/agents", json={"name": "analyst"}, headers=auth)
            agent_id = agent.json()["id"]
            updated = client.put(
                f"{prefix}/agents/{agent_id}",
                json={"model_provider": "anthropic", "model_name": "claude-sonnet-5"},
                headers=auth,
            )
            assert updated.status_code == 200, updated.text
            assert updated.json()["model_provider"] == "anthropic"
            assert updated.json()["model_name"] == "claude-sonnet-5"
            entries = _db_fetch(
                "SELECT action, detail FROM audit_log WHERE workspace_id = $1 "
                "AND action = 'agent.model_config_changed'",
                ws,
            )
            assert len(entries) == 1
            assert "claude-sonnet-5" in str(entries[0]["detail"])
    finally:
        cleanup_workspaces([owner])
