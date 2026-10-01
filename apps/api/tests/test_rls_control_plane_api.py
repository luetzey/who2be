"""Kernpfade der API unter der Laufzeitrolle `who2be_app` (Migration 0092).

0092 stellt `workspace`, `organization` und `status_history` unter RLS und
macht `mcp_usage` strikt. Die uebrige Suite verbindet als Owner (RLS-Bypass) und
saehe einen Bruch durch die neuen Policies nicht. Diese Tests fahren die Pfade,
die vor oder ausserhalb des Mandanten-Scopes auf die Stammdaten zugreifen,
deshalb ueber einen App-Pool als `who2be_app` — Muster aus
`test_user_profiles_function.py`:

* Login: `/v1/me` samt Lazy-Seed des persoenlichen Workspace.
* Org und Workspace anlegen, Workspace loeschen, Last-Workspace-Schutz.
* Statuswechsel (schreibt `status_history`) und Dashboard (liest ihn).
* Agent-Token anlegen und damit lesen; fremder Workspace bleibt zu.
"""

from __future__ import annotations

import asyncio
import secrets
from collections.abc import Callable, Iterator
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

import asyncpg
import pytest
from fastapi.testclient import TestClient

from who2be_api.core import db
from who2be_api.core.config import Settings, get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.main import app
from who2be_api.testing.api_helpers import agent_token
from who2be_api.testing.workspace_setup import (
    _ensure_auth_users_stub,
    cleanup_workspaces,
    fresh_user_id,
    setup_workspace,
)

# Dieselbe Test-Konstante wie test_rls_isolation (die Rolle ist cluster-global).
_APP_PASSWORD = "rls_test_secret"  # noqa: S105 — Test-Fixture, kein echtes Secret


def _app_role_url() -> str:
    parts = urlsplit(get_settings().database_url)
    host = parts.hostname or "localhost"
    port = f":{parts.port}" if parts.port else ""
    netloc = f"who2be_app:{_APP_PASSWORD}@{host}{port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def _prepare_public_schema() -> None:
    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await apply_migrations(conn, MIGRATIONS_DIR)
            await _ensure_auth_users_stub(conn)
            await conn.execute(f"ALTER ROLE who2be_app WITH PASSWORD '{_APP_PASSWORD}'")
        finally:
            await conn.close()

    asyncio.run(_run())


def _drop_company_org(slug: str) -> None:
    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await conn.execute(
                "DELETE FROM organization WHERE kind = 'company' AND slug = $1", slug
            )
        finally:
            await conn.close()

    asyncio.run(_run())


def _persona_body(text: str) -> dict[str, object]:
    # Promote-Validator: Beschreibung und Profil-Body duerfen nicht leer sein.
    return {
        "name": "RLS-Bot",
        "content": {
            "description": text,
            "system_prompt": "Be precise.",
            "traits": ["thorough"],
            "content": {
                "description": text,
                "blocks": [
                    {
                        "id": "b1",
                        "type": "paragraph",
                        "content": [{"type": "text", "text": text, "styles": {}}],
                    }
                ],
            },
        },
    }


@pytest.fixture
def app_role_client(
    monkeypatch: pytest.MonkeyPatch, patched_jwt_secret: str
) -> Iterator[TestClient]:
    """TestClient, dessen App-Pool als `who2be_app` verbindet."""
    _prepare_public_schema()
    app_url = _app_role_url()
    monkeypatch.setattr(db, "get_settings", lambda: Settings(app_database_url=app_url))
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.mark.integration
def test_login_and_workspace_lifecycle_as_app_role(
    app_role_client: TestClient,
    make_auth_headers: Callable[[UUID], dict[str, str]],
) -> None:
    user = fresh_user_id()
    auth = make_auth_headers(user)
    slug = f"rlscp-{secrets.token_hex(4)}"
    try:
        # Lazy-Seed: Org + Workspace entstehen ohne gesetzten Mandanten.
        me = app_role_client.get("/v1/me", headers=auth)
        assert me.status_code == 200, me.text
        assert me.json()["default_workspace_id"] is not None

        org = app_role_client.post(
            "/v1/organizations", json={"name": "RLS", "slug": slug}, headers=auth
        )
        assert org.status_code == 201, org.text
        org_id = org.json()["id"]

        listed = app_role_client.get("/v1/organizations", headers=auth)
        assert listed.status_code == 200, listed.text
        assert org_id in {o["id"] for o in listed.json()}

        created = app_role_client.post(
            f"/v1/organizations/{org_id}/workspaces",
            json={"name": "Zwei", "slug": "zwei"},
            headers=auth,
        )
        assert created.status_code == 201, created.text
        second = created.json()["id"]

        detail = app_role_client.get(f"/v1/workspaces/{second}", headers=auth)
        assert detail.status_code == 200, detail.text

        # Loeschen braucht die Geschwister der Org (Last-Workspace-Schutz).
        deleted = app_role_client.delete(f"/v1/workspaces/{second}", headers=auth)
        assert deleted.status_code == 204, deleted.text
        remaining = [
            ws["id"]
            for o in app_role_client.get("/v1/me", headers=auth).json()["organizations"]
            if o["id"] == org_id
            for ws in o["workspaces"]
        ]
        assert len(remaining) == 1, remaining
        last = app_role_client.delete(f"/v1/workspaces/{remaining[0]}", headers=auth)
        assert last.status_code == 409, last.text
    finally:
        _drop_company_org(slug)
        cleanup_workspaces([user])


@pytest.mark.integration
def test_status_history_and_tokens_as_app_role(
    app_role_client: TestClient,
    make_auth_headers: Callable[[UUID], dict[str, str]],
) -> None:
    owner = fresh_user_id()
    stranger = fresh_user_id()
    ws = setup_workspace(owner)
    foreign_ws = setup_workspace(stranger)
    auth = make_auth_headers(owner)
    base = f"/v1/workspaces/{ws}"
    try:
        persona = app_role_client.post(f"{base}/personas", json=_persona_body("rls"), headers=auth)
        assert persona.status_code == 201, persona.text
        persona_id = persona.json()["id"]

        # Statuswechsel schreibt status_history unter dem Mandanten.
        moved = app_role_client.post(
            f"{base}/personas/{persona_id}/versions/1/transition",
            json={"to": "review"},
            headers=auth,
        )
        assert moved.status_code == 200, moved.text

        dash = app_role_client.get(f"{base}/dashboard", headers=auth)
        assert dash.status_code == 200, dash.text
        assert dash.json()["activity"], "Statusverlauf fehlt im Dashboard"

        # Agent-Token: anlegen und damit lesen.
        _, token_auth = agent_token(app_role_client, base, "rls-agent", {}, auth)
        read = app_role_client.get(f"{base}/personas", headers=token_auth)
        assert read.status_code == 200, read.text

        # Fremder Workspace bleibt zu — fuer Token und Mensch.
        blocked = app_role_client.get(f"/v1/workspaces/{foreign_ws}/personas", headers=token_auth)
        assert blocked.status_code in (401, 403), blocked.text
        foreign = app_role_client.get(f"/v1/workspaces/{foreign_ws}", headers=auth)
        assert foreign.status_code == 403, foreign.text
    finally:
        cleanup_workspaces([owner, stranger])
