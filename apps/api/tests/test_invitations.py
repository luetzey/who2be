"""Integrationstests fuer Members + Invitations (Phase 2.3-B).

Deckt §2.3.C/D ab: Create→Accept-E2E, Single-Use (Double-Accept→410),
Expired→410, Revoked→410, Cross-Workspace-Isolation, admin-only Gate sowie
die Last-admin-Self-demote-Invariante (409). Dazu die Annahme per Token im
Body (`POST /v1/invitations/accept`), den befristeten Legacy-Pfad mit Token im
Pfad und den fail-closed Email-Abgleich: ohne Email-Claim keine Annahme.
Ausserdem die offenen Einladungen des eigenen Kontos
(`GET /v1/invitations/pending`) und ihre Annahme per Klick
(`POST /v1/invitations/pending/{id}/accept`), nur mit bestaetigter Email-Adresse.
Laeuft nur mit erreichbarer Datenbank; ohne DB werden die Tests uebersprungen.
"""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import httpx
import jwt
import pytest
from fastapi.testclient import TestClient

from who2be_api.core import security
from who2be_api.core.config import Settings, get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.core.security import WorkspaceContext
from who2be_api.integrations import gotrue_mailer
from who2be_api.main import app
from who2be_api.repositories.invitation_repository import AcceptResult
from who2be_api.services.invitation_service import InvitationService
from who2be_api.testing.api_helpers import agent_token, db_execute, db_fetchval
from who2be_api.testing.workspace_setup import (
    cleanup_workspaces,
    fresh_user_id,
    seed_auth_user,
    setup_workspace,
)
from who2be_models import InvitationCreate, InvitationRead, WorkspaceRole

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


class _MailOnlyInvitationRepo:
    """Repo-Stub fuer den Mail-Test: legt nur an, alles andere wird nicht gebraucht."""

    async def create(
        self,
        workspace_id: UUID,
        email: str,
        role: WorkspaceRole,
        token_hash: str,
        expires_at: datetime,
        created_by: UUID,
    ) -> InvitationRead:
        return InvitationRead(
            id=uuid4(), email=email, role=role, expires_at=expires_at, created_at=datetime.now(UTC)
        )

    async def list_pending_by_workspace(
        self, workspace_id: UUID
    ) -> list[InvitationRead]:  # pragma: no cover
        raise NotImplementedError

    async def accept(
        self, token_hash: str, user_id: UUID, expected_email: str | None = None
    ) -> AcceptResult:  # pragma: no cover
        raise NotImplementedError

    async def revoke(self, workspace_id: UUID, invitation_id: UUID) -> bool:  # pragma: no cover
        raise NotImplementedError


def test_invitation_mail_links_to_pending_page_without_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """S2b: die Einladungsmail traegt keinen Einladungs-Token.

    GoTrue uebernimmt `redirect_to` als Query in den Mail-Link, und `data` wird
    zu `user_metadata` im Access-Token. Beides darf den Token nicht enthalten:
    `redirect_to` zeigt auf die Pending-Seite, `data` wird gar nicht gesendet.
    Gemessen wird am echten Request, den der Service beim Anlegen ausloest.
    """
    monkeypatch.setattr(
        gotrue_mailer,
        "get_settings",
        lambda: Settings(
            web_base_url="https://app.who2be.dev/",
            supabase_url="https://supabase.who2be.dev",
            supabase_service_key="service-key",
        ),
    )
    sent: list[httpx.Request] = []

    def _gotrue(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json={})

    real_client = httpx.AsyncClient

    def _client(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        return real_client(*args, transport=httpx.MockTransport(_gotrue), **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", _client)

    service = InvitationService(_MailOnlyInvitationRepo())
    ctx = WorkspaceContext(workspace_id=uuid4(), user_id=uuid4(), role=WorkspaceRole.admin)
    created = asyncio.run(
        service.create(ctx, InvitationCreate(email="neu@example.com", role=WorkspaceRole.editor))
    )

    assert len(sent) == 1
    request = sent[0]
    assert request.url.path == "/auth/v1/invite"
    assert request.url.params["redirect_to"] == "https://app.who2be.dev/invitations"
    assert json.loads(request.content) == {"email": "neu@example.com"}
    # Der Token existiert (Antwort fuer den geteilten Link), steht aber nirgends
    # im Request an GoTrue — weder in der URL noch im Body.
    assert created.token
    assert created.token not in str(request.url)
    assert created.token not in request.content.decode()


def test_invitation_mail_is_skipped_without_gotrue_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ohne GoTrue-Konfiguration kein Versand — die Einladung selbst bleibt gueltig."""
    monkeypatch.setattr(gotrue_mailer, "get_settings", lambda: Settings(supabase_url=""))
    assert asyncio.run(gotrue_mailer.send_invitation_email("neu@example.com")) is False


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


# --------------------------------------------------------------------------
# GET /v1/invitations/pending — offene Einladungen des eigenen Kontos
# --------------------------------------------------------------------------

_PENDING = "/v1/invitations/pending"


def _account(user_id: UUID, email: str, *, confirmed: bool) -> None:
    """Konto im `auth.users`-Stub, bestaetigt oder nicht (wie GoTrue)."""
    seed_auth_user(user_id, email, None)
    db_execute(
        "UPDATE auth.users SET email_confirmed_at = CASE WHEN $2 THEN now() END WHERE id = $1",
        user_id,
        confirmed,
    )


def _invite(
    client: TestClient, admin_id: UUID, ws: UUID, email: str, role: str = "editor"
) -> dict[str, str]:
    created = client.post(
        f"/v1/workspaces/{ws}/invitations",
        json={"email": email, "role": role},
        headers=_auth(admin_id),
    )
    assert created.status_code == 201, created.text
    body: dict[str, str] = created.json()
    return body


def _rename(client: TestClient, admin_id: UUID, ws: UUID, name: str) -> None:
    res = client.patch(f"/v1/workspaces/{ws}", json={"name": name}, headers=_auth(admin_id))
    assert res.status_code == 200, res.text


@pytest.mark.integration
def test_pending_lists_only_open_invitations_for_the_confirmed_account() -> None:
    """Bestaetigt: eigene offene Einladungen aus allen Workspaces, mit Name und
    Rolle, ohne Token. Abgelaufen, widerrufen, angenommen und fremde Adressen
    erscheinen nicht; Gross-/Kleinschreibung zaehlt nicht."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    admin_a = fresh_user_id()
    admin_b = fresh_user_id()
    admin_c = fresh_user_id()
    invitee = fresh_user_id()
    stranger = fresh_user_id()
    ws_a = setup_workspace(admin_a)
    ws_b = setup_workspace(admin_b)
    ws_c = setup_workspace(admin_c)
    # Adresse im Konto anders geschrieben als in den Einladungen und im Claim.
    _account(invitee, "Pending.Invitee@Example.com", confirmed=True)
    _account(stranger, "pending.stranger@example.com", confirmed=True)

    try:
        with TestClient(app) as client:
            _rename(client, admin_a, ws_a, "Pending Probe A")
            _rename(client, admin_b, ws_b, "Pending Probe B")
            # Je Workspace und Adresse gibt es hoechstens eine offene Einladung
            # (workspace_invitation_open_uniq): erst die erledigten anlegen.
            revoked = _invite(client, admin_a, ws_a, "pending.invitee@example.com")
            gone = client.delete(
                f"/v1/workspaces/{ws_a}/invitations/{revoked['id']}", headers=_auth(admin_a)
            )
            assert gone.status_code == 204, gone.text
            accepted = _invite(client, admin_b, ws_b, "pending.invitee@example.com")
            took = client.post(
                "/v1/invitations/accept",
                json={"token": accepted["token"]},
                headers=_auth(invitee, email="pending.invitee@example.com"),
            )
            assert took.status_code == 200, took.text
            expired = _invite(client, admin_c, ws_c, "pending.invitee@example.com")
            _expire_invitation(expired["id"])
            open_a = _invite(client, admin_a, ws_a, "pending.invitee@example.com", "editor")
            open_b = _invite(client, admin_b, ws_b, "PENDING.INVITEE@example.com", "viewer")
            foreign = _invite(client, admin_a, ws_a, "pending.stranger@example.com", "admin")

            res = client.get(_PENDING, headers=_auth(invitee, email="pending.INVITEE@example.com"))
            assert res.status_code == 200, res.text
            rows = res.json()
            by_id = {r["id"]: r for r in rows}
            assert set(by_id) == {open_a["id"], open_b["id"]}
            assert by_id[open_a["id"]] == {
                "id": open_a["id"],
                "workspace_id": str(ws_a),
                "workspace_name": "Pending Probe A",
                "role": "editor",
                "expires_at": by_id[open_a["id"]]["expires_at"],
                "created_at": by_id[open_a["id"]]["created_at"],
            }
            assert by_id[open_b["id"]]["workspace_id"] == str(ws_b)
            assert by_id[open_b["id"]]["workspace_name"] == "Pending Probe B"
            assert by_id[open_b["id"]]["role"] == "viewer"
            # Kein Token, kein Hash — weder als Feld noch irgendwo im Text.
            assert all(set(r) == set(by_id[open_a["id"]]) for r in rows)
            assert "token" not in res.text
            for invitation in (open_a, open_b, expired, revoked, accepted, foreign):
                assert invitation["token"] not in res.text

            # Der Fremde sieht nur seine eigene Einladung, nichts vom Eingeladenen.
            other = client.get(
                _PENDING, headers=_auth(stranger, email="pending.stranger@example.com")
            )
            assert other.status_code == 200, other.text
            assert [r["id"] for r in other.json()] == [foreign["id"]]
            assert open_a["id"] not in other.text
            assert open_b["id"] not in other.text
    finally:
        cleanup_workspaces([admin_a, admin_b, admin_c, invitee, stranger])


@pytest.mark.integration
def test_pending_without_matching_invitations_is_empty() -> None:
    """Fremde Adresse: die eigene Liste ist leer, fremde Einladungen tauchen nicht auf."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    admin = fresh_user_id()
    nobody = fresh_user_id()
    ws = setup_workspace(admin)
    _account(nobody, "pending.nobody@example.com", confirmed=True)

    try:
        with TestClient(app) as client:
            theirs = _invite(client, admin, ws, "pending.someone-else@example.com")
            res = client.get(_PENDING, headers=_auth(nobody, email="pending.nobody@example.com"))
            assert res.status_code == 200, res.text
            assert res.json() == []
            assert theirs["id"] not in res.text
    finally:
        cleanup_workspaces([admin, nobody])


@pytest.mark.integration
@pytest.mark.parametrize("account", ["unconfirmed", "missing", "other_address"])
def test_pending_requires_a_confirmed_account_address(account: str) -> None:
    """Ohne bestaetigte Kontoadresse 403 `invitation_email_unconfirmed` — auch
    wenn der Claim zur Einladung passt. Fail-closed, wenn GoTrue das Konto
    nicht kennt oder der Claim eine andere als die Kontoadresse nennt."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    admin = fresh_user_id()
    invitee = fresh_user_id()
    ws = setup_workspace(admin)
    if account == "unconfirmed":
        _account(invitee, "pending.unconfirmed@example.com", confirmed=False)
    elif account == "other_address":
        _account(invitee, "pending.real-owner@example.com", confirmed=True)

    try:
        with TestClient(app) as client:
            invitation = _invite(client, admin, ws, "pending.unconfirmed@example.com")
            res = client.get(
                _PENDING, headers=_auth(invitee, email="pending.unconfirmed@example.com")
            )
            assert res.status_code == 403, res.text
            assert res.json()["reason"] == "invitation_email_unconfirmed"
            assert invitation["id"] not in res.text
    finally:
        cleanup_workspaces([admin, invitee])


@pytest.mark.integration
def test_pending_without_email_claim_is_rejected() -> None:
    """Ohne `email`-Claim im Login: 403 `invitation_email_required`."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    user = fresh_user_id()
    _account(user, "pending.noclaim@example.com", confirmed=True)
    try:
        with TestClient(app) as client:
            res = client.get(_PENDING, headers=_auth(user))
            assert res.status_code == 403, res.text
            assert res.json()["reason"] == "invitation_email_required"
    finally:
        cleanup_workspaces([user])


@pytest.mark.integration
def test_pending_rejects_agent_tokens() -> None:
    """Nur Menschen: ein agent-gebundener `w2b_`-Token bekommt 403."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    owner = fresh_user_id()
    ws = setup_workspace(owner)
    try:
        with TestClient(app) as client:
            _agent_id, token_auth = agent_token(
                client, f"/v1/workspaces/{ws}", "[Pending] Agent", {}, _auth(owner)
            )
            res = client.get(_PENDING, headers=token_auth)
            assert res.status_code == 403, res.text
            assert res.json()["reason"] == "account_route_requires_human"
    finally:
        cleanup_workspaces([owner])


# --------------------------------------------------------------------------
# POST /v1/invitations/pending/{id}/accept — Annahme per Klick, ohne Token
# --------------------------------------------------------------------------


def _accept_pending(invitation_id: str) -> str:
    return f"{_PENDING}/{invitation_id}/accept"


def _role_of(ws: UUID, user_id: UUID) -> str | None:
    role: str | None = db_fetchval(
        "SELECT role FROM workspace_member WHERE workspace_id = $1 AND user_id = $2",
        ws,
        user_id,
    )
    return role


def _accepted_at(invitation_id: str) -> object:
    return db_fetchval(
        "SELECT accepted_at FROM workspace_invitation WHERE id = $1", UUID(invitation_id)
    )


@pytest.mark.integration
def test_accept_pending_joins_with_the_role_and_is_single_use() -> None:
    """Bestaetigt: Annahme per ID, Mitglied mit der Rolle der Einladung, danach
    nicht mehr offen; der zweite Klick ist 410 wie beim geteilten Link."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    admin = fresh_user_id()
    invitee = fresh_user_id()
    ws = setup_workspace(admin)
    _account(invitee, "Click.Invitee@Example.com", confirmed=True)
    auth = _auth(invitee, email="click.invitee@example.com")

    try:
        with TestClient(app) as client:
            invitation = _invite(client, admin, ws, "CLICK.invitee@example.com", "viewer")
            listed = client.get(_PENDING, headers=auth)
            assert [r["id"] for r in listed.json()] == [invitation["id"]]

            res = client.post(_accept_pending(invitation["id"]), headers=auth)
            assert res.status_code == 200, res.text
            assert res.json() == {"workspace_id": str(ws)}
            assert _role_of(ws, invitee) == "viewer"
            assert _accepted_at(invitation["id"]) is not None
            assert client.get(_PENDING, headers=auth).json() == []

            again = client.post(_accept_pending(invitation["id"]), headers=auth)
            assert again.status_code == 410, again.text
            assert again.json()["reason"] == "invitation_no_longer_valid"
            assert _role_of(ws, invitee) == "viewer"
    finally:
        cleanup_workspaces([admin, invitee])


@pytest.mark.integration
@pytest.mark.parametrize("state", ["revoked", "expired"])
def test_accept_pending_on_a_closed_invitation_is_gone(state: str) -> None:
    """Widerrufen oder abgelaufen, aber an die eigene Adresse: 410, kein Beitritt."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    admin = fresh_user_id()
    invitee = fresh_user_id()
    ws = setup_workspace(admin)
    _account(invitee, "click.closed@example.com", confirmed=True)

    try:
        with TestClient(app) as client:
            invitation = _invite(client, admin, ws, "click.closed@example.com")
            if state == "revoked":
                gone = client.delete(
                    f"/v1/workspaces/{ws}/invitations/{invitation['id']}", headers=_auth(admin)
                )
                assert gone.status_code == 204, gone.text
            else:
                _expire_invitation(invitation["id"])
            res = client.post(
                _accept_pending(invitation["id"]),
                headers=_auth(invitee, email="click.closed@example.com"),
            )
            assert res.status_code == 410, res.text
            assert res.json()["reason"] == "invitation_no_longer_valid"
            assert _role_of(ws, invitee) is None
    finally:
        cleanup_workspaces([admin, invitee])


@pytest.mark.integration
def test_accept_pending_unconfirmed_account_is_rejected_and_stays_open() -> None:
    """Unbestaetigt: 403 `invitation_email_unconfirmed`, die Einladung bleibt
    offen — und der geteilte Link nimmt sie weiterhin an (Owner-Entscheidung)."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    admin = fresh_user_id()
    invitee = fresh_user_id()
    ws = setup_workspace(admin)
    _account(invitee, "click.unconfirmed@example.com", confirmed=False)
    auth = _auth(invitee, email="click.unconfirmed@example.com")

    try:
        with TestClient(app) as client:
            invitation = _invite(client, admin, ws, "click.unconfirmed@example.com")
            res = client.post(_accept_pending(invitation["id"]), headers=auth)
            assert res.status_code == 403, res.text
            assert res.json()["reason"] == "invitation_email_unconfirmed"
            assert _role_of(ws, invitee) is None
            assert _accepted_at(invitation["id"]) is None

            shared = client.post(
                "/v1/invitations/accept", json={"token": invitation["token"]}, headers=auth
            )
            assert shared.status_code == 200, shared.text
            assert _role_of(ws, invitee) == "editor"
    finally:
        cleanup_workspaces([admin, invitee])


@pytest.mark.integration
def test_accept_pending_without_email_claim_is_rejected() -> None:
    """Ohne `email`-Claim: 403 `invitation_email_required`, kein Beitritt."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    admin = fresh_user_id()
    invitee = fresh_user_id()
    ws = setup_workspace(admin)
    _account(invitee, "click.noclaim@example.com", confirmed=True)

    try:
        with TestClient(app) as client:
            invitation = _invite(client, admin, ws, "click.noclaim@example.com")
            res = client.post(_accept_pending(invitation["id"]), headers=_auth(invitee))
            assert res.status_code == 403, res.text
            assert res.json()["reason"] == "invitation_email_required"
            assert _role_of(ws, invitee) is None
            assert _accepted_at(invitation["id"]) is None
    finally:
        cleanup_workspaces([admin, invitee])


@pytest.mark.integration
def test_accept_pending_foreign_and_unknown_ids_are_indistinguishable() -> None:
    """Die ID einer Einladung an eine fremde Adresse endet wie eine unbekannte
    ID: 404 `invitation_not_found`, gleiche Antwort, keine Mitgliedschaft, die
    fremde Einladung bleibt offen (kein Existenz-Orakel, ADR-0036)."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    admin = fresh_user_id()
    clicker = fresh_user_id()
    ws = setup_workspace(admin)
    _account(clicker, "click.clicker@example.com", confirmed=True)
    auth = _auth(clicker, email="click.clicker@example.com")

    try:
        with TestClient(app) as client:
            foreign = _invite(client, admin, ws, "click.someone-else@example.com", "admin")
            res = client.post(_accept_pending(foreign["id"]), headers=auth)
            assert res.status_code == 404, res.text
            unknown = client.post(_accept_pending(str(uuid4())), headers=auth)
            assert unknown.status_code == 404, unknown.text
            assert res.json() == unknown.json()
            assert res.json()["reason"] == "invitation_not_found"
            assert _role_of(ws, clicker) is None
            assert _accepted_at(foreign["id"]) is None
    finally:
        cleanup_workspaces([admin, clicker])


@pytest.mark.integration
def test_accept_pending_rejects_agent_tokens() -> None:
    """Nur Menschen: ein agent-gebundener `w2b_`-Token bekommt 403."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    owner = fresh_user_id()
    ws = setup_workspace(owner)
    try:
        with TestClient(app) as client:
            invitation = _invite(client, owner, ws, "click.agent@example.com")
            _agent_id, token_auth = agent_token(
                client, f"/v1/workspaces/{ws}", "[Click] Agent", {}, _auth(owner)
            )
            res = client.post(_accept_pending(invitation["id"]), headers=token_auth)
            assert res.status_code == 403, res.text
            assert res.json()["reason"] == "account_route_requires_human"
            assert _accepted_at(invitation["id"]) is None
    finally:
        cleanup_workspaces([owner])
