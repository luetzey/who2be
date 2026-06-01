"""Integrationstest fuer den Placeholder-Preview-Endpoint.

`GET /v1/workspaces/{ws}/placeholders/preview` loest eine einzelne Editor-Pill
zu ihrem Output auf (Klick-Overlay). Laeuft nur mit erreichbarer Datenbank —
`get_current_workspace` prueft die Workspace-Mitgliedschaft gegen die DB.
"""

import asyncio
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

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


@pytest.mark.integration
def test_placeholder_preview_resolves_and_misses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    base = f"/v1/workspaces/{ws}/placeholders/preview"

    try:
        with TestClient(app) as client:
            # Unauthentifiziert -> 401
            assert client.get(base, params={"kind": "date"}).status_code == 401

            # date (ISO) -> heutiges Datum, nicht unresolved
            iso = client.get(base, params={"kind": "date", "target_id": ""}, headers=auth)
            assert iso.status_code == 200
            assert iso.json()["text"] == date.today().isoformat()
            assert iso.json()["unresolved"] is False

            # date (human) -> deutscher Monatsname enthalten
            human = client.get(
                base, params={"kind": "date", "target_id": "human"}, headers=auth
            )
            assert human.status_code == 200
            assert str(date.today().year) in human.json()["text"]
            assert human.json()["unresolved"] is False

            # tools-overview -> statische Markdown-Liste, nie unresolved
            tools = client.get(base, params={"kind": "tools-overview"}, headers=auth)
            assert tools.status_code == 200
            assert "Verfuegbare Werkzeuge" in tools.json()["text"]
            assert tools.json()["unresolved"] is False

            # playbook mit unbekannter UUID -> Miss (unresolved True, Fallback-Text)
            miss = client.get(
                base,
                params={"kind": "playbook", "target_id": str(uuid4())},
                headers=auth,
            )
            assert miss.status_code == 200
            assert miss.json()["unresolved"] is True
            assert "nicht verfuegbar" in miss.json()["text"]

            # persona-field ohne Persona-Kontext -> Miss
            pf = client.get(
                base,
                params={"kind": "persona-field", "target_id": "name"},
                headers=auth,
            )
            assert pf.status_code == 200
            assert pf.json()["unresolved"] is True

            # Unbekanntes Kind -> 422
            bad = client.get(base, params={"kind": "bogus"}, headers=auth)
            assert bad.status_code == 422
    finally:
        cleanup_workspaces([owner])
