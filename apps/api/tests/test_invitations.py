"""Integrationstests fuer Members + Invitations (Phase 2.3-B).

Deckt §2.3.C/D ab: Create→Accept-E2E, Single-Use (Double-Accept→410),
Expired→410, Revoked→410, Cross-Workspace-Isolation, admin-only Gate sowie
die Last-admin-Self-demote-Invariante (409). Laeuft nur mit erreichbarer
Datenbank; ohne DB werden die Tests uebersprungen.
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
from who2be_api.testing.workspace_setup import (
    cleanup_workspaces,
    fresh_user_id,
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


def _expire_invitation(invitation_id: str) -> None:
    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await conn.execute(
                "UPDATE workspace_invitation SET expires_at = now() - interval '1 day' "
                "WHERE id = $1",
                UUID(invitation_id),
            )
        finally:
            await conn.close()

    asyncio.run(_run())


def _jwt(user_id: UUID) -> str:
    return jwt.encode(
        {
            "sub": str(user_id),
            "aud": "authenticated",
            "role": "authenticated",
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        _TEST_SECRET,
        algorithm="HS256",
    )


def _auth(user_id: UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {_jwt(user_id)}"}


@pytest.fixture(autouse=True)
def _patch_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    # GoTrue bleibt unkonfiguriert (supabase_url leer) → Mail-Versand ist ein
    # No-op, der Test braucht kein Netzwerk.
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))


@pytest.mark.integration
def test_invitation_create_accept_member_lifecycle() -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    admin_id = fresh_user_id()
    invitee_id = fresh_user_id()
    ws = setup_workspace(admin_id)
    base = f"/v1/workspaces/{ws}"

    try:
        with TestClient(app) as client:
            created = client.post(
                f"{base}/invitations",
                json={"email": "invitee@example.com", "role": "editor"},
                headers=_auth(admin_id),
            )
            assert created.status_code == 201
            body = created.json()
            token = body["token"]
            assert token
            assert "token_hash" not in body
            assert body["role"] == "editor"

            # Pending-Liste zeigt die offene Einladung (admin-only).
            pending = client.get(f"{base}/invitations", headers=_auth(admin_id))
            assert pending.status_code == 200
            assert [i["id"] for i in pending.json()] == [body["id"]]
            assert all("token" not in i for i in pending.json())

            # Zweiter User akzeptiert anonym mit dem Mail-Token.
            accepted = client.post(f"/v1/invitations/{token}/accept", headers=_auth(invitee_id))
            assert accepted.status_code == 200
            assert accepted.json()["workspace_id"] == str(ws)

            # Member-Liste enthaelt nun beide; Invitee hat Rolle editor.
            members = client.get(f"{base}/members", headers=_auth(admin_id)).json()
            by_user = {m["user_id"]: m["role"] for m in members}
            assert by_user[str(admin_id)] == "admin"
            assert by_user[str(invitee_id)] == "editor"

            # Pending-Liste ist nach Accept leer.
            assert client.get(f"{base}/invitations", headers=_auth(admin_id)).json() == []

            # Single-use: zweiter Accept → 410 Gone.
            again = client.post(f"/v1/invitations/{token}/accept", headers=_auth(invitee_id))
            assert again.status_code == 410
    finally:
        cleanup_workspaces([admin_id, invitee_id])


@pytest.mark.integration
def test_invitation_expired_is_gone() -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    admin_id = fresh_user_id()
    invitee_id = fresh_user_id()
    ws = setup_workspace(admin_id)

    try:
        with TestClient(app) as client:
            created = client.post(
                f"/v1/workspaces/{ws}/invitations",
                json={"email": "expired@example.com", "role": "viewer"},
                headers=_auth(admin_id),
            )
            assert created.status_code == 201
            body = created.json()
            _expire_invitation(body["id"])

            resp = client.post(f"/v1/invitations/{body['token']}/accept", headers=_auth(invitee_id))
            assert resp.status_code == 410
    finally:
        cleanup_workspaces([admin_id, invitee_id])


@pytest.mark.integration
def test_invitation_revoked_is_gone() -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    admin_id = fresh_user_id()
    invitee_id = fresh_user_id()
    ws = setup_workspace(admin_id)

    try:
        with TestClient(app) as client:
            created = client.post(
                f"/v1/workspaces/{ws}/invitations",
                json={"email": "revoked@example.com", "role": "editor"},
                headers=_auth(admin_id),
            )
            assert created.status_code == 201
            body = created.json()

            revoke = client.delete(
                f"/v1/workspaces/{ws}/invitations/{body['id']}",
                headers=_auth(admin_id),
            )
            assert revoke.status_code == 204

            resp = client.post(f"/v1/invitations/{body['token']}/accept", headers=_auth(invitee_id))
            assert resp.status_code == 410
    finally:
        cleanup_workspaces([admin_id, invitee_id])


@pytest.mark.integration
def test_invitation_unknown_token_is_not_found() -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    user_id = fresh_user_id()
    try:
        with TestClient(app) as client:
            resp = client.post("/v1/invitations/does-not-exist/accept", headers=_auth(user_id))
            assert resp.status_code == 404
    finally:
        cleanup_workspaces([user_id])


@pytest.mark.integration
def test_invitation_cross_workspace_isolation() -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    admin_a = fresh_user_id()
    admin_b = fresh_user_id()
    ws_a = setup_workspace(admin_a)
    ws_b = setup_workspace(admin_b)

    try:
        with TestClient(app) as client:
            created = client.post(
                f"/v1/workspaces/{ws_a}/invitations",
                json={"email": "x@example.com", "role": "editor"},
                headers=_auth(admin_a),
            )
            assert created.status_code == 201

            # ws_b-Admin sieht die ws_a-Einladung nicht.
            assert (
                client.get(f"/v1/workspaces/{ws_b}/invitations", headers=_auth(admin_b)).json()
                == []
            )
            # Und kein Zugriff auf ws_a (kein Mitglied) → 403.
            assert (
                client.get(f"/v1/workspaces/{ws_a}/invitations", headers=_auth(admin_b)).status_code
                == 403
            )
    finally:
        cleanup_workspaces([admin_a, admin_b])


@pytest.mark.integration
def test_invitation_admin_only_gate() -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    admin_id = fresh_user_id()
    editor_id = fresh_user_id()
    ws = setup_workspace(admin_id)
    base = f"/v1/workspaces/{ws}"

    try:
        with TestClient(app) as client:
            created = client.post(
                f"{base}/invitations",
                json={"email": "editor@example.com", "role": "editor"},
                headers=_auth(admin_id),
            )
            token = created.json()["token"]
            client.post(f"/v1/invitations/{token}/accept", headers=_auth(editor_id))

            # Editor darf nicht einladen / nicht listen / nicht Rollen aendern.
            assert (
                client.post(
                    f"{base}/invitations",
                    json={"email": "next@example.com", "role": "viewer"},
                    headers=_auth(editor_id),
                ).status_code
                == 403
            )
            assert client.get(f"{base}/invitations", headers=_auth(editor_id)).status_code == 403
            assert (
                client.patch(
                    f"{base}/members/{admin_id}",
                    json={"role": "viewer"},
                    headers=_auth(editor_id),
                ).status_code
                == 403
            )
            # Member-Liste darf ein Editor aber lesen.
            assert client.get(f"{base}/members", headers=_auth(editor_id)).status_code == 200
    finally:
        cleanup_workspaces([admin_id, editor_id])


@pytest.mark.integration
def test_member_role_update_and_last_admin_guard() -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    admin_id = fresh_user_id()
    second_id = fresh_user_id()
    ws = setup_workspace(admin_id)
    base = f"/v1/workspaces/{ws}"

    try:
        with TestClient(app) as client:
            # Einziger Admin kann sich nicht selbst herabstufen → 409.
            assert (
                client.patch(
                    f"{base}/members/{admin_id}",
                    json={"role": "editor"},
                    headers=_auth(admin_id),
                ).status_code
                == 409
            )

            # Zweiten Admin einladen + akzeptieren.
            created = client.post(
                f"{base}/invitations",
                json={"email": "admin2@example.com", "role": "admin"},
                headers=_auth(admin_id),
            )
            token = created.json()["token"]
            client.post(f"/v1/invitations/{token}/accept", headers=_auth(second_id))

            # Jetzt zwei Admins → Herabstufung des zweiten ist erlaubt.
            patched = client.patch(
                f"{base}/members/{second_id}",
                json={"role": "viewer"},
                headers=_auth(admin_id),
            )
            assert patched.status_code == 200
            assert patched.json()["role"] == "viewer"

            # Unbekanntes Mitglied → 404.
            ghost = fresh_user_id()
            assert (
                client.patch(
                    f"{base}/members/{ghost}",
                    json={"role": "editor"},
                    headers=_auth(admin_id),
                ).status_code
                == 404
            )

            # Entfernen funktioniert; letzter Admin kann nicht entfernt werden.
            assert (
                client.delete(f"{base}/members/{second_id}", headers=_auth(admin_id)).status_code
                == 204
            )
            assert (
                client.delete(f"{base}/members/{admin_id}", headers=_auth(admin_id)).status_code
                == 409
            )
    finally:
        cleanup_workspaces([admin_id, second_id])
