"""Integrationstest fuer Workspace-Management (Track C).

Deckt die neuen/geschaerften Mgmt-Routen ab:
- `POST /v1/organizations/{org}/workspaces` (Anlage, Fix fuer toten Button)
- `PATCH /v1/workspaces/{id}` (Umbenennen, jetzt admin-only)
- `DELETE /v1/workspaces/{id}` (Danger-Zone, admin-only, Last-Workspace-Guard)
- `GET /v1/workspaces/{id}/members` liefert die Email aus `auth.users`

Skippt ohne erreichbare DB (wie die uebrigen Integrationstests).
"""

import asyncio
import secrets
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


def _drop_company_org(slug: str) -> None:
    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await conn.execute(
                "DELETE FROM organization WHERE kind = 'company' AND slug = $1",
                slug,
            )
        finally:
            await conn.close()

    asyncio.run(_run())


def _add_member(workspace_id: str, user_id: UUID, role: str) -> None:
    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await conn.execute(
                "INSERT INTO workspace_member (workspace_id, user_id, role) "
                "VALUES ($1, $2, $3) ON CONFLICT (workspace_id, user_id) "
                "DO UPDATE SET role = excluded.role",
                UUID(workspace_id),
                user_id,
                role,
            )
        finally:
            await conn.close()

    asyncio.run(_run())


@pytest.mark.integration
def test_workspace_create_rename_delete_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    setup_workspace(owner)
    slug = f"acme-{secrets.token_hex(4)}"

    try:
        with TestClient(app) as client:
            org = client.post(
                "/v1/organizations",
                json={"name": "Acme", "slug": slug},
                headers=_auth(owner),
            ).json()

            # Zweiter Workspace (Fix fuer den toten "Workspace hinzufügen"-Button).
            created = client.post(
                f"/v1/organizations/{org['id']}/workspaces",
                json={"name": "Marketing", "slug": "marketing"},
                headers=_auth(owner),
            )
            assert created.status_code == 201
            ws_id = created.json()["id"]

            # Umbenennen (admin).
            renamed = client.patch(
                f"/v1/workspaces/{ws_id}",
                json={"name": "Marketing & Sales"},
                headers=_auth(owner),
            )
            assert renamed.status_code == 200
            assert renamed.json()["name"] == "Marketing & Sales"

            # Loeschen (admin) — Org hat noch den Default-Workspace, also erlaubt.
            deleted = client.delete(f"/v1/workspaces/{ws_id}", headers=_auth(owner))
            assert deleted.status_code == 204

            # Workspace ist weg.
            gone = client.get(f"/v1/workspaces/{ws_id}", headers=_auth(owner))
            assert gone.status_code == 403
    finally:
        _drop_company_org(slug)
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_workspace_create_content_locale(monkeypatch: pytest.MonkeyPatch) -> None:
    """Workspace-Content-Sprache (ADR-0045, WP8): Create mit `content_locale='en'`
    liefert die Sprache in `WorkspaceRead` zurueck (Create/List/Detail), seedet
    die EN-Standard-Inhalte, defaultet ohne Angabe auf 'de' und lehnt
    unbekannte Sprachen mit 422 ab."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    setup_workspace(owner)
    slug = f"loc-{secrets.token_hex(4)}"

    try:
        with TestClient(app) as client:
            org = client.post(
                "/v1/organizations",
                json={"name": "Locale", "slug": slug},
                headers=_auth(owner),
            ).json()

            # Ohne Angabe: Default 'de'.
            created_de = client.post(
                f"/v1/organizations/{org['id']}/workspaces",
                json={"name": "Deutsch", "slug": "deutsch"},
                headers=_auth(owner),
            )
            assert created_de.status_code == 201, created_de.text
            assert created_de.json()["content_locale"] == "de"

            # Explizit 'en': Read traegt die Sprache, Seeds sind englisch.
            created_en = client.post(
                f"/v1/organizations/{org['id']}/workspaces",
                json={"name": "English", "slug": "english", "content_locale": "en"},
                headers=_auth(owner),
            )
            assert created_en.status_code == 201, created_en.text
            assert created_en.json()["content_locale"] == "en"
            ws_en = created_en.json()["id"]

            # Liste + Detail liefern die Spalte mit (WP8: SELECTs erweitert).
            listed = client.get(
                f"/v1/organizations/{org['id']}/workspaces", headers=_auth(owner)
            ).json()
            by_slug = {w["slug"]: w["content_locale"] for w in listed}
            assert by_slug["english"] == "en"
            assert by_slug["deutsch"] == "de"
            fetched = client.get(f"/v1/workspaces/{ws_en}", headers=_auth(owner))
            assert fetched.status_code == 200, fetched.text
            assert fetched.json()["content_locale"] == "en"

            # Der EN-Workspace wurde mit dem EN-Content-Pack geseedet.
            templates = client.get(
                f"/v1/workspaces/{ws_en}/system-prompts", headers=_auth(owner)
            ).json()
            names = {t["name"] for t in templates}
            assert "Customer Support Agent" in names, names
            assert "Customer-Support-Agent" not in names, names

            # Unbekannte Sprache → 422 an der Modell-Grenze.
            bad = client.post(
                f"/v1/organizations/{org['id']}/workspaces",
                json={"name": "Bad", "slug": "bad", "content_locale": "xx"},
                headers=_auth(owner),
            )
            assert bad.status_code == 422, bad.text
    finally:
        _drop_company_org(slug)
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_delete_last_workspace_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    setup_workspace(owner)
    slug = f"solo-{secrets.token_hex(4)}"

    try:
        with TestClient(app) as client:
            org = client.post(
                "/v1/organizations",
                json={"name": "Solo", "slug": slug},
                headers=_auth(owner),
            ).json()
            # Org hat genau einen (Default-)Workspace.
            workspaces = client.get(
                f"/v1/organizations/{org['id']}/workspaces", headers=_auth(owner)
            ).json()
            assert len(workspaces) == 1
            only_ws = workspaces[0]["id"]

            rejected = client.delete(f"/v1/workspaces/{only_ws}", headers=_auth(owner))
            assert rejected.status_code == 409
    finally:
        _drop_company_org(slug)
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_non_admin_cannot_rename_or_delete(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    editor = fresh_user_id()
    setup_workspace(owner)
    setup_workspace(editor)
    slug = f"team-{secrets.token_hex(4)}"

    try:
        with TestClient(app) as client:
            org = client.post(
                "/v1/organizations",
                json={"name": "Team", "slug": slug},
                headers=_auth(owner),
            ).json()
            ws_id = client.post(
                f"/v1/organizations/{org['id']}/workspaces",
                json={"name": "Shared", "slug": "shared"},
                headers=_auth(owner),
            ).json()["id"]
            _add_member(ws_id, editor, "editor")

            patch_resp = client.patch(
                f"/v1/workspaces/{ws_id}",
                json={"name": "Hijacked"},
                headers=_auth(editor),
            )
            assert patch_resp.status_code == 403

            delete_resp = client.delete(f"/v1/workspaces/{ws_id}", headers=_auth(editor))
            assert delete_resp.status_code == 403
    finally:
        _drop_company_org(slug)
        cleanup_workspaces([owner, editor])


@pytest.mark.integration
def test_members_list_includes_email(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    setup_workspace(owner)
    seed_auth_user(owner, "owner@example.com", None)

    try:
        with TestClient(app) as client:
            me = client.get("/v1/me", headers=_auth(owner)).json()
            ws_id = me["default_workspace_id"]
            members = client.get(f"/v1/workspaces/{ws_id}/members", headers=_auth(owner)).json()
            assert len(members) == 1
            assert members[0]["email"] == "owner@example.com"
    finally:
        cleanup_workspaces([owner])
