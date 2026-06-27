"""Integrationstest fuer die inhaltliche Suche (ADR-0037, Track 2).

`GET /v1/workspaces/{ws}/search` findet ueber die AKTIVE Version, rangsortiert,
und respektiert den Typ-Filter. Owner-JWT (unrestricted) ⇒ kein Read-Scoping.
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


def _playbook_body(name: str, description: str) -> dict[str, object]:
    return {
        "name": name,
        "content": {
            "description": description,
            "body": "1. Step.",
            "type": "workflow",
            "tags": [],
            "triggers": None,
        },
    }


def _activate(client: TestClient, base: str, pid: str, auth: dict[str, str]) -> None:
    """Draft v1 → review → active (Owner ist admin)."""
    for to in ("review", "active"):
        r = client.post(f"{base}/{pid}/versions/1/transition", json={"to": to}, headers=auth)
        assert r.status_code in (200, 201), r.text


@pytest.mark.integration
def test_search_finds_active_playbook_by_content(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    pbase = f"/v1/workspaces/{ws}/playbooks"
    sbase = f"/v1/workspaces/{ws}/search"

    try:
        with TestClient(app) as client:
            hit = client.post(
                pbase, json=_playbook_body("Reklamation", "Umgang mit Beschwerden"), headers=auth
            ).json()["id"]
            _activate(client, pbase, hit, auth)
            # Ein zweites, nicht aktiviertes Playbook (bleibt Draft → unsichtbar).
            client.post(
                pbase, json=_playbook_body("Versand", "Reklamation im Titel-Draft"), headers=auth
            )

            # Volltext ueber Name/Inhalt der aktiven Version.
            res = client.get(sbase, params={"q": "beschwerden"}, headers=auth)
            assert res.status_code == 200, res.text
            body = res.json()
            assert [h["id"] for h in body] == [hit]
            assert body[0]["type"] == "playbook"

            # Typ-Filter persona → kein Playbook-Treffer.
            res2 = client.get(sbase, params={"q": "beschwerden", "types": "persona"}, headers=auth)
            assert res2.json() == []
    finally:
        cleanup_workspaces([owner])
