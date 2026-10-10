"""Integrationstest: der erste Login des Bootstrap-Admins landet in der Bootstrap-Org.

`services/bootstrap_service.py` seedet die Bootstrap-Org mit einer aus der E-Mail
abgeleiteten Platzhalter-User-ID (uuid5). GoTrue vergibt beim ersten Login eine
eigene, zufaellige UUID. Ohne Abbildung landete dieser Login in einer neuen
Personal-Org, und niemand war Admin der Bootstrap-Org.

Die Abbildung (`claim_bootstrap_org`) uebernimmt die Mitgliedschaften des
Platzhalters nur, wenn die E-Mail des Kontos in GoTrue **bestaetigt** ist und
der Bootstrap-Adresse entspricht. Ohne Variable oder in der Cloud passiert nichts.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4

import asyncpg
import jwt
import pytest
from fastapi.testclient import TestClient

from who2be_api.core import security
from who2be_api.core.config import Settings, get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.main import app
from who2be_api.services import bootstrap_service
from who2be_api.services.bootstrap_service import _deterministic_user_id, seed_bootstrap_tenant
from who2be_api.testing.workspace_setup import (
    _connect_with_codec,
    _ensure_auth_users_stub,
    cleanup_workspaces,
    fresh_user_id,
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


def _prepare(email: str, user_id: UUID, *, confirmed: bool) -> UUID:
    """Migriert, seedet die Bootstrap-Org und legt den GoTrue-User an.

    Gibt die ID der Bootstrap-Org zurueck.
    """

    async def _run() -> UUID:
        conn = await _connect_with_codec()
        try:
            await apply_migrations(conn, MIGRATIONS_DIR)
            await _ensure_auth_users_stub(conn)
            await conn.execute(
                "INSERT INTO auth.users (id, email, email_confirmed_at) VALUES ($1, $2, $3)",
                user_id,
                email,
                datetime.now(UTC) if confirmed else None,
            )
            async with conn.transaction():
                org_id = await seed_bootstrap_tenant(conn, email)
            assert org_id is not None
            return org_id
        finally:
            await conn.close()

    return asyncio.run(_run())


def _org_ids_of(user_id: UUID) -> list[UUID]:
    async def _run() -> list[UUID]:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            rows = await conn.fetch(
                "SELECT org_id FROM org_member WHERE user_id = $1 ORDER BY org_id", user_id
            )
        finally:
            await conn.close()
        return [r["org_id"] for r in rows]

    return asyncio.run(_run())


def _workspace_role_in_org(user_id: UUID, org_id: UUID) -> list[str]:
    async def _run() -> list[str]:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            rows = await conn.fetch(
                "SELECT m.role FROM workspace_member m JOIN workspace w ON w.id = m.workspace_id "
                "WHERE m.user_id = $1 AND w.org_id = $2",
                user_id,
                org_id,
            )
        finally:
            await conn.close()
        return [r["role"] for r in rows]

    return asyncio.run(_run())


def _cleanup(org_id: UUID, user_ids: list[UUID]) -> None:
    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            async with conn.transaction():
                await conn.execute(
                    "DELETE FROM agent_access_log WHERE workspace_id IN "
                    "(SELECT id FROM workspace WHERE org_id = $1)",
                    org_id,
                )
                await conn.execute("DELETE FROM organization WHERE id = $1", org_id)
                await conn.execute("DELETE FROM auth.users WHERE id = ANY($1::uuid[])", user_ids)
        finally:
            await conn.close()

    asyncio.run(_run())
    cleanup_workspaces(user_ids)


def _auth(user_id: UUID, email: str) -> dict[str, str]:
    token = jwt.encode(
        {
            "sub": str(user_id),
            "email": email,
            "aud": "authenticated",
            "role": "authenticated",
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        _TEST_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def _login(
    monkeypatch: pytest.MonkeyPatch, user_id: UUID, email: str, *, settings: Settings
) -> dict[str, object]:
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    monkeypatch.setattr(bootstrap_service, "get_settings", lambda: settings)
    with TestClient(app) as client:
        resp = client.get("/v1/me", headers=_auth(user_id, email))
    assert resp.status_code == 200
    body: dict[str, object] = resp.json()
    return body


def _skip_without_db() -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")


@pytest.mark.integration
def test_first_login_of_bootstrap_admin_lands_in_bootstrap_org(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _skip_without_db()
    email = f"boot-{uuid4().hex[:10]}@who2be.dev"
    user = fresh_user_id()
    placeholder = _deterministic_user_id(email)
    org_id = _prepare(email, user, confirmed=True)
    try:
        me = _login(
            monkeypatch,
            user,
            email,
            settings=Settings(edition="onprem", bootstrap_admin_email=email),
        )
        # Der echte Login ist Owner der Bootstrap-Org und Admin ihres Workspaces,
        # es entsteht keine zweite Personal-Org.
        assert _org_ids_of(user) == [org_id]
        assert _workspace_role_in_org(user, org_id) == ["admin"]
        orgs = me["organizations"]
        assert isinstance(orgs, list)
        assert [o["id"] for o in orgs] == [str(org_id)]
        # Der Platzhalter haelt nichts mehr.
        assert _org_ids_of(placeholder) == []
    finally:
        _cleanup(org_id, [user, placeholder])


@pytest.mark.integration
def test_unconfirmed_email_does_not_take_over_bootstrap_org(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _skip_without_db()
    email = f"boot-{uuid4().hex[:10]}@who2be.dev"
    user = fresh_user_id()
    placeholder = _deterministic_user_id(email)
    org_id = _prepare(email, user, confirmed=False)
    try:
        _login(
            monkeypatch,
            user,
            email,
            settings=Settings(edition="onprem", bootstrap_admin_email=email),
        )
        assert org_id not in _org_ids_of(user)
        assert _org_ids_of(placeholder) == [org_id]
    finally:
        _cleanup(org_id, [user, placeholder])


@pytest.mark.integration
def test_other_confirmed_email_does_not_take_over_bootstrap_org(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _skip_without_db()
    email = f"boot-{uuid4().hex[:10]}@who2be.dev"
    other = fresh_user_id()
    placeholder = _deterministic_user_id(email)
    org_id = _prepare(email, other, confirmed=True)
    # Das Konto traegt eine ANDERE bestaetigte Adresse als die Bootstrap-Variable.
    try:
        _login(
            monkeypatch,
            other,
            email,
            settings=Settings(edition="onprem", bootstrap_admin_email=f"x-{email}"),
        )
        assert org_id not in _org_ids_of(other)
        assert _org_ids_of(placeholder) == [org_id]
    finally:
        _cleanup(org_id, [other, placeholder])


@pytest.mark.integration
@pytest.mark.parametrize(
    ("edition", "with_variable"),
    [("onprem", False), ("cloud", True)],
    ids=["onprem-ohne-variable", "cloud-mit-variable"],
)
def test_login_is_unchanged_without_variable_or_in_cloud(
    monkeypatch: pytest.MonkeyPatch, edition: Literal["cloud", "onprem"], with_variable: bool
) -> None:
    _skip_without_db()
    email = f"boot-{uuid4().hex[:10]}@who2be.dev"
    user = fresh_user_id()
    placeholder = _deterministic_user_id(email)
    org_id = _prepare(email, user, confirmed=True)
    settings = Settings(edition=edition, bootstrap_admin_email=email if with_variable else "")
    try:
        _login(monkeypatch, user, email, settings=settings)
        assert org_id not in _org_ids_of(user)
        assert len(_org_ids_of(user)) == 1  # eigene Personal-Org wie bisher
        assert _org_ids_of(placeholder) == [org_id]
    finally:
        _cleanup(org_id, [user, placeholder])
