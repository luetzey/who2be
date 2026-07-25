"""Integrationstest fuer `GET /v1/me` (TASK-301)."""

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
from who2be_api.testing.workspace_setup import (
    cleanup_workspaces,
    fresh_user_id,
    seed_auth_user,
    setup_workspace,
)

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


def _ensure_auth_users_shim() -> None:
    """Stellt `auth.users(id, encrypted_password)` bereit fuer den
    `has_password`-Test. In Docker-Compose legt GoTrue die Tabelle an;
    in der reinen API-Test-DB faellt sie weg — das Shim deckt beide Faelle."""

    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await conn.execute("CREATE SCHEMA IF NOT EXISTS auth")
            await conn.execute(
                "CREATE TABLE IF NOT EXISTS auth.users ("
                "id uuid PRIMARY KEY, "
                "encrypted_password text"
                ")"
            )
            # Defensive: ein vorheriger Test (workspace_setup-Stub) kann die
            # Tabelle ohne encrypted_password angelegt haben; CREATE IF NOT
            # EXISTS oben waere dann no-op. ALTER … ADD COLUMN IF NOT EXISTS
            # schliesst die Luecke.
            await conn.execute(
                "ALTER TABLE auth.users ADD COLUMN IF NOT EXISTS encrypted_password text"
            )
        finally:
            await conn.close()

    asyncio.run(_run())


def _set_auth_user(user_id: UUID, has_password: bool) -> None:
    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await conn.execute(
                "INSERT INTO auth.users (id, encrypted_password) VALUES ($1, $2) "
                "ON CONFLICT (id) DO UPDATE SET encrypted_password = excluded.encrypted_password",
                user_id,
                "$2a$10$dummyhashfortest" if has_password else None,
            )
        finally:
            await conn.close()

    asyncio.run(_run())


def _delete_auth_user(user_id: UUID) -> None:
    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await conn.execute("DELETE FROM auth.users WHERE id = $1", user_id)
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
def test_me_returns_default_workspace_and_memberships(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)

    try:
        with TestClient(app) as client:
            resp = client.get("/v1/me", headers=_auth(owner))
            assert resp.status_code == 200
            body = resp.json()
            assert body["user_id"] == str(owner)
            assert body["default_workspace_id"] == str(ws)
            assert len(body["organizations"]) == 1
            org = body["organizations"][0]
            assert org["kind"] == "personal"
            assert [w["id"] for w in org["workspaces"]] == [str(ws)]
            assert org["workspaces"][0]["role"] == "admin"
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_me_has_password_true_when_encrypted_password_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    _ensure_auth_users_shim()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    setup_workspace(owner)
    _set_auth_user(owner, has_password=True)

    try:
        with TestClient(app) as client:
            resp = client.get("/v1/me", headers=_auth(owner))
            assert resp.status_code == 200
            assert resp.json()["has_password"] is True
    finally:
        _delete_auth_user(owner)
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_me_has_password_false_when_only_magic_link(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    _ensure_auth_users_shim()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    setup_workspace(owner)
    _set_auth_user(owner, has_password=False)

    try:
        with TestClient(app) as client:
            resp = client.get("/v1/me", headers=_auth(owner))
            assert resp.status_code == 200
            assert resp.json()["has_password"] is False
    finally:
        _delete_auth_user(owner)
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_me_lazy_seeds_personal_workspace_for_fresh_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Frischer User ohne Workspace bekommt beim ersten /v1/me-Aufruf automatisch
    eine Personal-Org + Admin-Workspace. Zweiter Aufruf ist idempotent."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    _ensure_auth_users_shim()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    # Kein setup_workspace — User existiert nur in auth.users, nicht in org_member.
    _set_auth_user(owner, has_password=False)

    try:
        with TestClient(app) as client:
            # Erster Aufruf: lazy-seed muss greifen.
            resp = client.get("/v1/me", headers=_auth(owner))
            assert resp.status_code == 200
            body = resp.json()
            assert body["user_id"] == str(owner)
            assert body["default_workspace_id"] is not None
            assert len(body["organizations"]) == 1
            org = body["organizations"][0]
            assert org["kind"] == "personal"
            assert len(org["workspaces"]) == 1
            assert org["workspaces"][0]["role"] == "admin"
            ws_id = body["default_workspace_id"]

            # Zweiter Aufruf: idempotent — gleiche workspace_id, immer noch 1 Org.
            resp2 = client.get("/v1/me", headers=_auth(owner))
            assert resp2.status_code == 200
            body2 = resp2.json()
            assert body2["default_workspace_id"] == ws_id
            assert len(body2["organizations"]) == 1
    finally:
        _delete_auth_user(owner)
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_me_lazy_seed_derives_content_locale_from_preferred_locale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lazy-Seed (ADR-0045, WP8): traegt der User `preferred_locale='en'` in
    `auth.users.raw_user_meta_data`, bekommt der Personal-Workspace
    `content_locale='en'` und die geseedeten Standard-Inhalte sind englisch."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    # Kein setup_workspace — der Lazy-Seed im /v1/me-Flow muss die Sprache
    # selbst aus dem Profil ableiten. `seed_auth_user` stellt den vollen
    # auth.users-Stub (inkl. raw_user_meta_data) bereit.
    seed_auth_user(owner, "en-user@example.com", None, preferred_locale="en")

    async def _seeded_state(workspace_id: UUID) -> dict[str, object]:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            content_locale = await conn.fetchval(
                "SELECT content_locale FROM workspace WHERE id = $1", workspace_id
            )
            template_names = {
                row["name"]
                for row in await conn.fetch(
                    "SELECT name FROM system_prompt_template WHERE workspace_id = $1",
                    workspace_id,
                )
            }
            persona_locale = await conn.fetchval(
                "SELECT locale FROM persona WHERE workspace_id = $1 AND name = 'Builder'",
                workspace_id,
            )
            return {
                "content_locale": content_locale,
                "template_names": template_names,
                "persona_locale": persona_locale,
            }
        finally:
            await conn.close()

    try:
        with TestClient(app) as client:
            resp = client.get("/v1/me", headers=_auth(owner))
            assert resp.status_code == 200
            ws_id = resp.json()["default_workspace_id"]
            assert ws_id is not None

        state = asyncio.run(_seeded_state(UUID(ws_id)))
        assert state["content_locale"] == "en"
        template_names = state["template_names"]
        assert isinstance(template_names, set)
        assert "Customer Support Agent" in template_names, template_names
        assert "Customer-Support-Agent" not in template_names, template_names
        assert state["persona_locale"] == "en"
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_me_rejects_unauthenticated() -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    with TestClient(app) as client:
        assert client.get("/v1/me").status_code == 401
