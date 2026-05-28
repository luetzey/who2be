"""Integrationstest fuer `/v1/organizations` + `/v1/workspaces/{id}` (TASK-301)."""

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


@pytest.mark.integration
def test_create_organization_seeds_default_workspace_and_membership(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    setup_workspace(owner)
    slug = f"acme-{secrets.token_hex(4)}"

    try:
        with TestClient(app) as client:
            # POST legt Company-Org + Default-Workspace + Admin-Membership atomar an.
            created = client.post(
                "/v1/organizations",
                json={"name": "Acme", "slug": slug},
                headers=_auth(owner),
            )
            assert created.status_code == 201
            org = created.json()
            assert org["kind"] == "company"

            # /v1/me sieht die neue Org mit dem Default-Workspace
            me = client.get("/v1/me", headers=_auth(owner)).json()
            org_ids = {o["id"] for o in me["organizations"]}
            assert org["id"] in org_ids
            company = next(o for o in me["organizations"] if o["id"] == org["id"])
            assert len(company["workspaces"]) == 1
            assert company["workspaces"][0]["role"] == "admin"

            # Duplikat-Slug -> 409.
            duplicate = client.post(
                "/v1/organizations",
                json={"name": "Acme2", "slug": slug},
                headers=_auth(owner),
            )
            assert duplicate.status_code == 409
    finally:
        _drop_company_org(slug)
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_list_organizations_only_returns_memberships(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    other = fresh_user_id()
    setup_workspace(owner)
    setup_workspace(other)
    slug = f"foo-{secrets.token_hex(4)}"

    try:
        with TestClient(app) as client:
            client.post(
                "/v1/organizations",
                json={"name": "Foo", "slug": slug},
                headers=_auth(owner),
            )

            owner_orgs = client.get("/v1/organizations", headers=_auth(owner)).json()
            owner_slugs = {o["slug"] for o in owner_orgs}
            assert slug in owner_slugs

            other_orgs = client.get("/v1/organizations", headers=_auth(other)).json()
            assert slug not in {o["slug"] for o in other_orgs}
    finally:
        _drop_company_org(slug)
        cleanup_workspaces([owner, other])
