"""Integrationstests fuer Members + Invitations (Phase 2.3-B).

Deckt §2.3.C/D ab: Create→Accept-E2E, Single-Use (Double-Accept→410),
Expired→410, Revoked→410, Cross-Workspace-Isolation, admin-only Gate sowie
die Last-admin-Self-demote-Invariante (409). Dazu die Annahme per Token im
Body (`POST /v1/invitations/accept`), den befristeten Legacy-Pfad mit Token im
Pfad und den fail-closed Email-Abgleich: ohne Email-Claim keine Annahme.
Laeuft nur mit erreichbarer Datenbank; ohne DB werden die Tests uebersprungen.
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
from who2be_api.integrations import gotrue_mailer
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


def _jwt(user_id: UUID, email: str | None = None) -> str:
    payload: dict[str, object] = {
        "sub": str(user_id),
        "aud": "authenticated",
        "role": "authenticated",
        "exp": datetime.now(UTC) + timedelta(hours=1),
    }
    if email is not None:
        payload["email"] = email
    return jwt.encode(payload, _TEST_SECRET, algorithm="HS256")


def _auth(user_id: UUID, email: str | None = None) -> dict[str, str]:
    return {"Authorization": f"Bearer {_jwt(user_id, email)}"}


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
            accepted = client.post(
                f"/v1/invitations/{token}/accept",
                headers=_auth(invitee_id, email="invitee@example.com"),
            )
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
            again = client.post(
                f"/v1/invitations/{token}/accept",
                headers=_auth(invitee_id, email="invitee@example.com"),
            )
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

            resp = client.post(
                f"/v1/invitations/{body['token']}/accept",
                headers=_auth(invitee_id, email="expired@example.com"),
            )
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

            resp = client.post(
                f"/v1/invitations/{body['token']}/accept",
                headers=_auth(invitee_id, email="revoked@example.com"),
            )
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
            joined = client.post(
                f"/v1/invitations/{token}/accept",
                headers=_auth(editor_id, email="editor@example.com"),
            )
            assert joined.status_code == 200, joined.text

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
            joined = client.post(
                f"/v1/invitations/{token}/accept",
                headers=_auth(second_id, email="admin2@example.com"),
            )
            assert joined.status_code == 200, joined.text

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


def test_build_accept_url_carries_magic_marker(monkeypatch: pytest.MonkeyPatch) -> None:
    """Phase 3-D: der Magic-Link traegt `?via=magic`, damit das Frontend
    weiss, dass es Auto-Accept ohne Klick fahren darf."""
    monkeypatch.setattr(
        gotrue_mailer,
        "get_settings",
        lambda: Settings(web_base_url="https://app.who2be.dev"),
    )
    url = gotrue_mailer.build_accept_url("tkn-abc")
    assert url == "https://app.who2be.dev/invitations/tkn-abc/accept?via=magic"


@pytest.mark.integration
def test_invitation_email_mismatch_is_forbidden() -> None:
    """Phase 3-D: JWT-Email != Invitation-Email → 403, Invitation bleibt offen.

    Schuetzt davor, dass ein anderer User den Magic-Link abfaengt und mit dem
    eigenen Account einen fremden Workspace betritt.
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    admin_id = fresh_user_id()
    intended_id = fresh_user_id()
    attacker_id = fresh_user_id()
    ws = setup_workspace(admin_id)

    try:
        with TestClient(app) as client:
            created = client.post(
                f"/v1/workspaces/{ws}/invitations",
                json={"email": "intended@example.com", "role": "editor"},
                headers=_auth(admin_id),
            )
            assert created.status_code == 201
            token = created.json()["token"]

            # Angreifer mit falscher Email-Claim → 403, Microcopy.
            wrong = client.post(
                f"/v1/invitations/{token}/accept",
                headers=_auth(attacker_id, email="attacker@example.com"),
            )
            assert wrong.status_code == 403
            assert "andere Email" in wrong.json()["detail"]

            # Invitation ist nach 403 weiterhin offen — der eingeladene Account
            # kann sie immer noch akzeptieren (case-insensitive Match).
            ok = client.post(
                f"/v1/invitations/{token}/accept",
                headers=_auth(intended_id, email="Intended@Example.com"),
            )
            assert ok.status_code == 200
            assert ok.json()["workspace_id"] == str(ws)
    finally:
        cleanup_workspaces([admin_id, intended_id, attacker_id])


def _create_invitation(client: TestClient, admin_id: UUID, ws: UUID, email: str) -> str:
    created = client.post(
        f"/v1/workspaces/{ws}/invitations",
        json={"email": email, "role": "editor"},
        headers=_auth(admin_id),
    )
    assert created.status_code == 201, created.text
    token: str = created.json()["token"]
    return token


def _member_ids(client: TestClient, admin_id: UUID, ws: UUID) -> set[str]:
    members = client.get(f"/v1/workspaces/{ws}/members", headers=_auth(admin_id))
    assert members.status_code == 200, members.text
    return {m["user_id"] for m in members.json()}


@pytest.mark.integration
@pytest.mark.parametrize("via", ["body", "legacy_path"])
def test_invitation_accept_without_email_claim_is_rejected(via: str) -> None:
    """Fail-closed: ohne Email-Claim im Login wird keine Einladung angenommen.

    Beide Annahmewege, weil sie denselben Service teilen und der Legacy-Pfad
    sonst unbemerkt der weichere bleiben koennte. Belegt wird die ausgebliebene
    Wirkung (kein Mitglied, Einladung weiter offen), nicht nur der Statuscode.
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    admin_id = fresh_user_id()
    invitee_id = fresh_user_id()
    ws = setup_workspace(admin_id)

    try:
        with TestClient(app) as client:
            token = _create_invitation(client, admin_id, ws, "noclaim@example.com")

            if via == "body":
                resp = client.post(
                    "/v1/invitations/accept", json={"token": token}, headers=_auth(invitee_id)
                )
            else:
                resp = client.post(f"/v1/invitations/{token}/accept", headers=_auth(invitee_id))
            assert resp.status_code == 403, resp.text
            assert resp.json() == {
                "detail": (
                    "Diese Einladung laesst sich nur mit einem Konto annehmen, "
                    "das eine bestaetigte Email-Adresse traegt."
                ),
                "reason": "invitation_email_required",
            }

            assert str(invitee_id) not in _member_ids(client, admin_id, ws)
            pending = client.get(f"/v1/workspaces/{ws}/invitations", headers=_auth(admin_id))
            assert [i["email"] for i in pending.json()] == ["noclaim@example.com"]

            # Dasselbe Konto mit passendem Claim kommt danach regulaer hinein.
            ok = client.post(
                "/v1/invitations/accept",
                json={"token": token},
                headers=_auth(invitee_id, email="noclaim@example.com"),
            )
            assert ok.status_code == 200, ok.text
            assert str(invitee_id) in _member_ids(client, admin_id, ws)
    finally:
        cleanup_workspaces([admin_id, invitee_id])


@pytest.mark.integration
def test_invitation_accept_by_body_lifecycle() -> None:
    """Body-Endpunkt: gueltiger Token → 200, falsche Email → 403, zweiter Accept → 410."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    admin_id = fresh_user_id()
    invitee_id = fresh_user_id()
    stranger_id = fresh_user_id()
    ws = setup_workspace(admin_id)

    try:
        with TestClient(app) as client:
            token = _create_invitation(client, admin_id, ws, "body@example.com")

            wrong = client.post(
                "/v1/invitations/accept",
                json={"token": token},
                headers=_auth(stranger_id, email="stranger@example.com"),
            )
            assert wrong.status_code == 403, wrong.text
            assert wrong.json()["reason"] == "invitation_email_mismatch"
            assert str(stranger_id) not in _member_ids(client, admin_id, ws)

            accepted = client.post(
                "/v1/invitations/accept",
                json={"token": token},
                headers=_auth(invitee_id, email="body@example.com"),
            )
            assert accepted.status_code == 200, accepted.text
            assert accepted.json() == {"workspace_id": str(ws)}
            assert "Sunset" not in accepted.headers
            assert str(invitee_id) in _member_ids(client, admin_id, ws)

            again = client.post(
                "/v1/invitations/accept",
                json={"token": token},
                headers=_auth(invitee_id, email="body@example.com"),
            )
            assert again.status_code == 410, again.text
            assert again.json()["reason"] == "invitation_no_longer_valid"

            unknown = client.post(
                "/v1/invitations/accept",
                json={"token": "gibt-es-nicht"},
                headers=_auth(invitee_id, email="body@example.com"),
            )
            assert unknown.status_code == 404, unknown.text
    finally:
        cleanup_workspaces([admin_id, invitee_id, stranger_id])


@pytest.mark.integration
def test_invitation_accept_by_body_rejects_malformed_body() -> None:
    """Der Body traegt genau `token` — fehlend oder mit Zusatzfeld → 422."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    user_id = fresh_user_id()
    try:
        with TestClient(app) as client:
            headers = _auth(user_id, email="x@example.com")
            assert client.post("/v1/invitations/accept", json={}, headers=headers).status_code == (
                422
            )
            extra = client.post(
                "/v1/invitations/accept",
                json={"token": "t", "workspace_id": "x"},
                headers=headers,
            )
            assert extra.status_code == 422
    finally:
        cleanup_workspaces([user_id])


@pytest.mark.integration
def test_invitation_legacy_path_still_accepts_with_sunset_notice() -> None:
    """Uebergang: alte Links mit Token im Pfad funktionieren weiter.

    Die Antwort kuendigt das Ende an (`Sunset`, RFC 8594) und nennt den
    Nachfolger; die OpenAPI-Spec fuehrt die Route als `deprecated`.
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    admin_id = fresh_user_id()
    invitee_id = fresh_user_id()
    ws = setup_workspace(admin_id)

    try:
        with TestClient(app) as client:
            token = _create_invitation(client, admin_id, ws, "legacy@example.com")
            resp = client.post(
                f"/v1/invitations/{token}/accept",
                headers=_auth(invitee_id, email="legacy@example.com"),
            )
            assert resp.status_code == 200, resp.text
            assert resp.json() == {"workspace_id": str(ws)}
            assert resp.headers["Sunset"] == "Thu, 31 Dec 2026 23:59:59 GMT"
            assert resp.headers["Link"] == '</v1/invitations/accept>; rel="successor-version"'
            assert str(invitee_id) in _member_ids(client, admin_id, ws)

            spec = app.openapi()
            assert spec["paths"]["/v1/invitations/{token}/accept"]["post"]["deprecated"] is True
            assert "deprecated" not in spec["paths"]["/v1/invitations/accept"]["post"]
    finally:
        cleanup_workspaces([admin_id, invitee_id])
