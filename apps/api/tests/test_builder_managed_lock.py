"""Integrationstest fuer den Builder-Managed-Lock (Migration 0057).

Der geseedete Builder (Persona/Template/Playbooks/Agent) ist `is_managed=true`.
User-Mutationen (update/transition/delete) muessen mit 403 (`managed_aggregate`)
abprallen; das Duplizieren des Agenten bleibt erlaubt und liefert eine
unverwaltete Kopie.
"""

from __future__ import annotations

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


def _builder_ids(ws: UUID) -> dict[str, str]:
    async def _run() -> dict[str, str]:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            persona = await conn.fetchval(
                "SELECT id FROM persona WHERE workspace_id = $1 AND name = 'Builder'", ws
            )
            agent = await conn.fetchval(
                "SELECT id FROM agent WHERE workspace_id = $1 AND name = 'Builder'", ws
            )
            return {"persona": str(persona), "agent": str(agent)}
        finally:
            await conn.close()

    return asyncio.run(_run())


@pytest.mark.integration
def test_builder_is_locked_but_copyable(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    ids = _builder_ids(ws)
    base = f"/v1/workspaces/{ws}"

    try:
        with TestClient(app) as client:
            # Agent ist als verwaltet markiert (Read exponiert is_managed).
            agent = client.get(f"{base}/agents/{ids['agent']}", headers=auth)
            assert agent.status_code == 200, agent.text
            assert agent.json()["is_managed"] is True

            # Delete des Builder-Agenten -> 403 managed_aggregate.
            r = client.delete(f"{base}/agents/{ids['agent']}", headers=auth)
            assert r.status_code == 403, r.text
            assert r.json().get("reason") == "managed_aggregate"

            # Transition der Builder-Persona (aktive v1 -> inactive) -> 403.
            r = client.post(
                f"{base}/personas/{ids['persona']}/versions/1/transition",
                json={"to": "inactive"},
                headers=auth,
            )
            assert r.status_code == 403, r.text
            assert r.json().get("reason") == "managed_aggregate"

            # Update der Builder-Persona -> 403 (Body egal, Gate sitzt vorher).
            current = client.get(f"{base}/personas/{ids['persona']}", headers=auth).json()
            r = client.put(
                f"{base}/personas/{ids['persona']}",
                json={"name": current["name"], "content": current["content"]},
                headers=auth,
            )
            assert r.status_code == 403, r.text
            assert r.json().get("reason") == "managed_aggregate"

            # Duplizieren bleibt erlaubt -> 201, Voll-Klon: Kopie ist unverwaltet
            # und zeigt auf NEUE, unverwaltete Persona + Template (Deep-Copy).
            copy = client.post(
                f"{base}/agents/{ids['agent']}/copy",
                json={"name": "Mein Builder"},
                headers=auth,
            )
            assert copy.status_code == 201, copy.text
            cbody = copy.json()
            assert cbody["is_managed"] is False
            assert cbody["persona_id"] != ids["persona"], "Persona muss geklont sein."
            assert cbody["system_prompt_template_id"] is not None
            assert cbody["activatable"] is True, "Klon muss einsetzbar sein."

            # Die geklonte Persona ist unverwaltet -> editierbar (kein 403).
            new_pid = cbody["persona_id"]
            new_persona = client.get(f"{base}/personas/{new_pid}", headers=auth).json()
            assert new_persona["is_managed"] is False
            upd = client.put(
                f"{base}/personas/{new_pid}",
                json={"name": "Mein Builder-Profil", "content": new_persona["content"]},
                headers=auth,
            )
            assert upd.status_code == 200, upd.text

            # Die vier Builder-Playbooks wurden mitkopiert (an die Klon-Persona).
            links = client.get(f"{base}/personas/{new_pid}/playbooks", headers=auth)
            assert links.status_code == 200, links.text
            assert len(links.json()) == 4, "Alle vier Builder-Playbooks sollten geklont sein."
    finally:
        cleanup_workspaces([owner])
