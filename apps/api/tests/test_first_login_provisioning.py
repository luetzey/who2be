"""Integrationstest fuer First-Login-Provisioning (Track K, Plan §3.3).

Ein frischer Cloud-User (E-Mail ODER Social-Login) ohne Org bekommt beim
ersten `/v1/me`-Aufruf automatisch eine Personal-Org + Default-Workspace +
`org_member(owner)` + `workspace_member(admin)` — analog zum On-Prem-Bootstrap
(`services/bootstrap_service.py`), aber pro neuem User und idempotent.

Der Pfad ist editions-unabhaengig: Social-Login unterscheidet sich nur in der
GoTrue-Identitaet, nicht im API-Provisioning — beide kommen als verifiziertes
JWT mit `sub`/`email` an. Der Test deckt daher beide Faelle mit einem
JWT-Aufruf ab und prueft die Tenancy-Rollen direkt in der DB.
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
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, seed_auth_user

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


def _tenancy_rows(user_id: UUID) -> dict[str, object]:
    """Liest die Tenancy-Rollen des Users direkt aus der DB."""

    async def _run() -> dict[str, object]:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            org_roles = await conn.fetch(
                "SELECT om.role, o.kind FROM org_member om "
                "JOIN organization o ON o.id = om.org_id WHERE om.user_id = $1",
                user_id,
            )
            ws_roles = await conn.fetch(
                "SELECT role FROM workspace_member WHERE user_id = $1",
                user_id,
            )
        finally:
            await conn.close()
        return {
            "org_roles": [(r["role"], r["kind"]) for r in org_roles],
            "ws_roles": [r["role"] for r in ws_roles],
        }

    return asyncio.run(_run())


def _auth(owner_id: UUID, email: str) -> dict[str, str]:
    token = jwt.encode(
        {
            "sub": str(owner_id),
            "email": email,
            "aud": "authenticated",
            "role": "authenticated",
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        _TEST_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.integration
def test_first_login_provisions_owner_and_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    """Frischer User → Personal-Org (owner) + Default-Workspace (admin)."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    # Identitaet in auth.users (wie nach GoTrue-Signup bzw. Social-Login).
    seed_auth_user(owner, email="social-user@who2be.dev", name=None)

    try:
        with TestClient(app) as client:
            resp = client.get("/v1/me", headers=_auth(owner, "social-user@who2be.dev"))
            assert resp.status_code == 200
            assert resp.json()["default_workspace_id"] is not None

        rows = _tenancy_rows(owner)
        # Genau eine Personal-Org mit Owner-Rolle, genau ein Admin-Workspace.
        assert rows["org_roles"] == [("owner", "personal")]
        assert rows["ws_roles"] == ["admin"]
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_first_login_provisioning_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mehrfache /v1/me-Aufrufe ergaenzen nichts doppelt (ERST PRUEFEN)."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    seed_auth_user(owner, email="repeat-user@who2be.dev", name=None)

    try:
        with TestClient(app) as client:
            first = client.get("/v1/me", headers=_auth(owner, "repeat-user@who2be.dev"))
            second = client.get("/v1/me", headers=_auth(owner, "repeat-user@who2be.dev"))
            assert first.status_code == 200
            assert second.status_code == 200
            assert first.json()["default_workspace_id"] == second.json()["default_workspace_id"]

        rows = _tenancy_rows(owner)
        assert rows["org_roles"] == [("owner", "personal")]
        assert rows["ws_roles"] == ["admin"]
    finally:
        cleanup_workspaces([owner])
