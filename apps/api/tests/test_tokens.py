"""Integrationstest fuer `/v1/workspaces/{ws_id}/tokens` und `get_current_workspace`.

Deckt AC1 (API-Token erstellen/listen/widerrufen) ab und belegt beide
Auth-Wege (JWT + w2b_-Token). Laeuft nur mit erreichbarer Datenbank; ohne DB
wird der Test uebersprungen.
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


def _agent_in(ws: UUID) -> UUID:
    """Liefert eine Agent-ID des Workspaces (der Seed legt den „Builder" an).

    Tokens sind ab Migration 0048 zwingend agent-gebunden — die Create-Payloads
    brauchen also eine echte Agent-ID aus demselben Workspace.
    """

    async def _run() -> UUID:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            agent_id: UUID | None = await conn.fetchval(
                "SELECT id FROM agent WHERE workspace_id = $1 LIMIT 1", ws
            )
            assert agent_id is not None, "Seed-Agent fehlt"
            return agent_id
        finally:
            await conn.close()

    return asyncio.run(_run())


def _delete_agent(agent_id: UUID) -> None:
    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await conn.execute("DELETE FROM agent WHERE id = $1", agent_id)
        finally:
            await conn.close()

    asyncio.run(_run())


def _jwt(owner_id: UUID, *, aal: str | None = None) -> str:
    # `aal` (Authenticator Assurance Level, #469): unset by default, wie ein
    # aelteres/handsigniertes Test-JWT ohne den GoTrue-Claim. Explizit gesetzt
    # simuliert es eine aal1- bzw. aal2-Session fuer das Admin-MFA-Gate.
    payload: dict[str, object] = {
        "sub": str(owner_id),
        "aud": "authenticated",
        "role": "authenticated",
        "exp": datetime.now(UTC) + timedelta(hours=1),
    }
    if aal is not None:
        payload["aal"] = aal
    return jwt.encode(payload, _TEST_SECRET, algorithm="HS256")


def _add_member(ws: UUID, user_id: UUID, role: str) -> None:
    """Fuegt ein weiteres Mitglied direkt in workspace_member ein.

    Damit das Entfernen/Herabstufen im Test nicht am Last-admin-Guard scheitert,
    braucht der Workspace neben dem Owner ein zweites (Admin-)Mitglied.
    """

    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await conn.execute(
                "INSERT INTO workspace_member (workspace_id, user_id, role) VALUES ($1, $2, $3)",
                ws,
                user_id,
                role,
            )
        finally:
            await conn.close()

    asyncio.run(_run())


@pytest.mark.integration
def test_token_lifecycle_and_both_auth_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner_id = fresh_user_id()
    ws = setup_workspace(owner_id)
    agent_id = str(_agent_in(ws))
    jwt_auth = {"Authorization": f"Bearer {_jwt(owner_id)}"}
    base = f"/v1/workspaces/{ws}/tokens"

    try:
        with TestClient(app) as client:
            assert client.get(base).status_code == 401

            # Ohne agent_id ist ein Token nicht mehr erstellbar (422).
            assert client.post(base, json={"name": "agent"}, headers=jwt_auth).status_code == 422

            created = client.post(
                base, json={"name": "agent", "agent_id": agent_id}, headers=jwt_auth
            )
            assert created.status_code == 201
            body = created.json()
            plaintext = body["token"]
            token_id = body["id"]
            assert plaintext.startswith("w2b_")
            assert body["workspace_id"] == str(ws)
            assert body["agent_id"] == agent_id

            # Filter nach agent_id listet genau diesen Token.
            listed = client.get(f"{base}?agent_id={agent_id}", headers=jwt_auth).json()
            assert [t["id"] for t in listed] == [token_id]
            assert "token" not in listed[0]
            assert "token_hash" not in listed[0]

            api_auth = {"Authorization": f"Bearer {plaintext}"}
            # Der w2b_-Token authentifiziert (Auth-Weg #2) — belegt an /v1/me ...
            assert client.get("/v1/me", headers=api_auth).status_code == 200
            # ... darf als AGENT-GEBUNDENER Token aber keine Tokens verwalten
            # (Privilege-Escalation-Schutz, ADR-0023): 403 auf die Token-Liste.
            assert client.get(base, headers=api_auth).status_code == 403

            # Umbenennen ändert nur den Namen.
            renamed = client.patch(f"{base}/{token_id}", json={"name": "neu"}, headers=jwt_auth)
            assert renamed.status_code == 200
            assert renamed.json()["name"] == "neu"
            assert renamed.json()["agent_id"] == agent_id

            # Rotieren: neues Secret gültig, altes sofort ungültig.
            rotated = client.post(f"{base}/{token_id}/rotate", headers=jwt_auth)
            assert rotated.status_code == 200
            new_plaintext = rotated.json()["token"]
            assert new_plaintext != plaintext
            new_auth = {"Authorization": f"Bearer {new_plaintext}"}
            # Liveness an /v1/me (GET /tokens waere fuer beide agent-gebundenen
            # Tokens 403): alter Token tot, rotierter gueltig.
            assert client.get("/v1/me", headers=api_auth).status_code == 401
            assert client.get("/v1/me", headers=new_auth).status_code == 200

            revoke = client.delete(f"{base}/{token_id}", headers=jwt_auth)
            assert revoke.status_code == 204

            # Nach Revoke sind sowohl Auth als auch rename/rotate tot.
            assert client.get("/v1/me", headers=new_auth).status_code == 401
            assert client.delete(f"{base}/{token_id}", headers=jwt_auth).status_code == 404
            assert client.post(f"{base}/{token_id}/rotate", headers=jwt_auth).status_code == 404
    finally:
        cleanup_workspaces([owner_id])


@pytest.mark.integration
def test_agent_delete_cascades_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    """Agent-Delete entfernt dessen Tokens (FK ON DELETE CASCADE, Migration 0048)."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner_id = fresh_user_id()
    ws = setup_workspace(owner_id)
    agent_id = str(_agent_in(ws))
    jwt_auth = {"Authorization": f"Bearer {_jwt(owner_id)}"}
    base = f"/v1/workspaces/{ws}/tokens"

    try:
        with TestClient(app) as client:
            created = client.post(
                base, json={"name": "bound", "agent_id": agent_id}, headers=jwt_auth
            )
            assert created.status_code == 201
            plaintext = created.json()["token"]
            api_auth = {"Authorization": f"Bearer {plaintext}"}
            # Token authentifiziert (an /v1/me — GET /tokens waere als agent-
            # gebundener Token 403, irrelevant fuer den Cascade-Beleg).
            assert client.get("/v1/me", headers=api_auth).status_code == 200

            _delete_agent(UUID(agent_id))

            # Token ist mit dem Agenten verschwunden → Auth schlägt fehl.
            assert client.get("/v1/me", headers=api_auth).status_code == 401
    finally:
        cleanup_workspaces([owner_id])


@pytest.mark.integration
def test_member_removal_revokes_their_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deprovisioning: Wird ein Mitglied entfernt, werden dessen aktive Tokens
    in diesem Workspace mit-widerrufen (sonst ueberlebte ein Ex-Admin mit
    lebenden Credentials — der Token-Pfad prueft die Membership nicht live)."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner_id = fresh_user_id()
    ws = setup_workspace(owner_id)
    agent_id = str(_agent_in(ws))
    # Zweites Admin-Mitglied B, damit das Entfernen nicht am Last-admin-Guard scheitert.
    member_id = fresh_user_id()
    _add_member(ws, member_id, "admin")
    base = f"/v1/workspaces/{ws}/tokens"

    try:
        with TestClient(app) as client:
            # B erstellt sich einen (agent-gebundenen) Token.
            created = client.post(
                base,
                json={"name": "b-token", "agent_id": agent_id},
                headers={"Authorization": f"Bearer {_jwt(member_id)}"},
            )
            assert created.status_code == 201
            b_auth = {"Authorization": f"Bearer {created.json()['token']}"}
            assert client.get("/v1/me", headers=b_auth).status_code == 200

            # Owner (Admin) entfernt B → B's Token muss sofort ungueltig sein.
            removed = client.delete(
                f"/v1/workspaces/{ws}/members/{member_id}",
                headers={"Authorization": f"Bearer {_jwt(owner_id)}"},
            )
            assert removed.status_code == 204
            assert client.get("/v1/me", headers=b_auth).status_code == 401
    finally:
        cleanup_workspaces([owner_id])


@pytest.mark.integration
def test_member_downgrade_revokes_their_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deprovisioning: Ein Rollenwechsel invalidiert die gepinnte Snapshot-Rolle
    bestehender Tokens des Mitglieds — sie werden mit-widerrufen."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner_id = fresh_user_id()
    ws = setup_workspace(owner_id)
    agent_id = str(_agent_in(ws))
    member_id = fresh_user_id()
    _add_member(ws, member_id, "admin")
    base = f"/v1/workspaces/{ws}/tokens"

    try:
        with TestClient(app) as client:
            created = client.post(
                base,
                json={"name": "b-token", "agent_id": agent_id},
                headers={"Authorization": f"Bearer {_jwt(member_id)}"},
            )
            assert created.status_code == 201
            b_auth = {"Authorization": f"Bearer {created.json()['token']}"}
            assert client.get("/v1/me", headers=b_auth).status_code == 200

            # Owner stuft B admin→editor herab → B's Token wird mit-widerrufen.
            patched = client.patch(
                f"/v1/workspaces/{ws}/members/{member_id}",
                json={"role": "editor"},
                headers={"Authorization": f"Bearer {_jwt(owner_id)}"},
            )
            assert patched.status_code == 200
            assert client.get("/v1/me", headers=b_auth).status_code == 401
    finally:
        cleanup_workspaces([owner_id])


@pytest.mark.integration
def test_api_token_rejected_for_other_workspace(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner_id = fresh_user_id()
    other_id = fresh_user_id()
    ws_a = setup_workspace(owner_id)
    ws_b = setup_workspace(other_id)
    agent_a = str(_agent_in(ws_a))
    jwt_auth = {"Authorization": f"Bearer {_jwt(owner_id)}"}

    try:
        with TestClient(app) as client:
            created = client.post(
                f"/v1/workspaces/{ws_a}/tokens",
                json={"name": "agent", "agent_id": agent_a},
                headers=jwt_auth,
            )
            assert created.status_code == 201
            plaintext = created.json()["token"]
            api_auth = {"Authorization": f"Bearer {plaintext}"}

            # Token gepinnt auf ws_a: Aufruf auf ws_b -> 403 (Snapshot-Mismatch).
            assert client.get(f"/v1/workspaces/{ws_b}/tokens", headers=api_auth).status_code == 403
    finally:
        cleanup_workspaces([owner_id, other_id])


@pytest.mark.integration
def test_token_listing_pagination_and_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner_id = fresh_user_id()
    ws = setup_workspace(owner_id)
    agent_id = str(_agent_in(ws))
    jwt_auth = {"Authorization": f"Bearer {_jwt(owner_id)}"}
    base = f"/v1/workspaces/{ws}/tokens"

    try:
        with TestClient(app) as client:
            created_ids: list[str] = []
            for i in range(3):
                resp = client.post(
                    base, json={"name": f"t{i}", "agent_id": agent_id}, headers=jwt_auth
                )
                assert resp.status_code == 201
                created_ids.append(resp.json()["id"])

            page1 = client.get(f"{base}?limit=2", headers=jwt_auth)
            assert page1.status_code == 200
            assert len(page1.json()) == 2
            cursor = page1.headers.get("X-Next-Cursor")
            assert cursor is not None

            page2 = client.get(f"{base}?limit=2&cursor={cursor}", headers=jwt_auth)
            assert page2.status_code == 200
            assert len(page2.json()) == 1
            assert "X-Next-Cursor" not in page2.headers

            seen = {t["id"] for t in page1.json()} | {t["id"] for t in page2.json()}
            assert seen == set(created_ids)

            assert client.get(f"{base}?limit=0", headers=jwt_auth).status_code == 422
            assert client.get(f"{base}?limit=201", headers=jwt_auth).status_code == 422
            assert client.get(f"{base}?cursor=!!!", headers=jwt_auth).status_code == 422
    finally:
        cleanup_workspaces([owner_id])


@pytest.mark.integration
def test_admin_token_create_requires_aal2(monkeypatch: pytest.MonkeyPatch) -> None:
    """#469 AC1: ein `admin`-Token laesst sich nur aus einer aal2-Session anlegen.

    Der Owner ist Workspace-`admin` (Seed) — ohne explizite `role` erbt der
    Token also `admin` (Snapshot-Regel) und faellt unter das Admin-MFA-Gate.
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner_id = fresh_user_id()
    ws = setup_workspace(owner_id)
    agent_id = str(_agent_in(ws))
    base = f"/v1/workspaces/{ws}/tokens"

    try:
        with TestClient(app) as client:
            aal1_auth = {"Authorization": f"Bearer {_jwt(owner_id, aal='aal1')}"}
            blocked = client.post(
                base, json={"name": "admin-token", "agent_id": agent_id}, headers=aal1_auth
            )
            assert blocked.status_code == 403
            assert blocked.json()["reason"] == "mfa_required"

            aal2_auth = {"Authorization": f"Bearer {_jwt(owner_id, aal='aal2')}"}
            created = client.post(
                base, json={"name": "admin-token", "agent_id": agent_id}, headers=aal2_auth
            )
            assert created.status_code == 201
            assert created.json()["role"] == "admin"
    finally:
        cleanup_workspaces([owner_id])


@pytest.mark.integration
def test_admin_token_rotate_requires_aal2(monkeypatch: pytest.MonkeyPatch) -> None:
    """#469 AC2: das Rotieren eines bestehenden `admin`-Tokens verlangt aal2.

    Ohne das Gate koennte eine aal1-Session die Ausstellungs-Schwelle aus
    `create` umgehen, indem sie einfach ein neues Secret fuer ein bestehendes
    admin-Token anfordert.
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner_id = fresh_user_id()
    ws = setup_workspace(owner_id)
    agent_id = str(_agent_in(ws))
    base = f"/v1/workspaces/{ws}/tokens"

    try:
        with TestClient(app) as client:
            aal2_auth = {"Authorization": f"Bearer {_jwt(owner_id, aal='aal2')}"}
            created = client.post(
                base, json={"name": "admin-token", "agent_id": agent_id}, headers=aal2_auth
            )
            assert created.status_code == 201
            token_id = created.json()["id"]
            old_plaintext = created.json()["token"]

            aal1_auth = {"Authorization": f"Bearer {_jwt(owner_id, aal='aal1')}"}
            blocked = client.post(f"{base}/{token_id}/rotate", headers=aal1_auth)
            assert blocked.status_code == 403
            assert blocked.json()["reason"] == "mfa_required"

            # Das alte Secret ist durch den Block-Versuch nicht mutiert worden
            # (Gate greift VOR dem Rotate) — es authentifiziert weiterhin.
            assert (
                client.get(
                    "/v1/me", headers={"Authorization": f"Bearer {old_plaintext}"}
                ).status_code
                == 200
            )

            rotated = client.post(f"{base}/{token_id}/rotate", headers=aal2_auth)
            assert rotated.status_code == 200
    finally:
        cleanup_workspaces([owner_id])


@pytest.mark.integration
def test_editor_token_create_and_rotate_unaffected_by_admin_mfa_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#469 AC3: `editor`-Tokens sind vom Admin-MFA-Gate nicht betroffen."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner_id = fresh_user_id()
    ws = setup_workspace(owner_id)
    agent_id = str(_agent_in(ws))
    base = f"/v1/workspaces/{ws}/tokens"
    aal1_auth = {"Authorization": f"Bearer {_jwt(owner_id, aal='aal1')}"}

    try:
        with TestClient(app) as client:
            created = client.post(
                base,
                json={"name": "editor-token", "role": "editor", "agent_id": agent_id},
                headers=aal1_auth,
            )
            assert created.status_code == 201
            assert created.json()["role"] == "editor"
            token_id = created.json()["id"]

            rotated = client.post(f"{base}/{token_id}/rotate", headers=aal1_auth)
            assert rotated.status_code == 200
    finally:
        cleanup_workspaces([owner_id])
