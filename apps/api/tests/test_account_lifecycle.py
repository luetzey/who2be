"""Integrationstests fuer Account-/Org-Lifecycle (Track O, Plan §3.2).

Belegt: `DELETE /v1/me` mottet Account + Personal-Org ein (Soft-Delete);
`DELETE /v1/organizations/{id}` ist owner-only und schuetzt Personal-Orgs;
eingemottete Orgs verschwinden aus den Reads und sperren den Workspace-Zugriff;
der Hard-Purge raeumt faellige Eintraege endgueltig ab.
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
from who2be_api.core.purge import purge_expired
from who2be_api.main import app
from who2be_api.repositories.account_repository import PgAccountPurgeRepository
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


async def _fetchrow(query: str, *args: object) -> asyncpg.Record | None:
    conn = await asyncpg.connect(get_settings().database_url)
    try:
        return await conn.fetchrow(query, *args)
    finally:
        await conn.close()


async def _execute(query: str, *args: object) -> None:
    conn = await asyncpg.connect(get_settings().database_url)
    try:
        await conn.execute(query, *args)
    finally:
        await conn.close()


def _drop_company_org(slug: str) -> None:
    asyncio.run(_execute("DELETE FROM organization WHERE slug = $1", slug))


@pytest.mark.integration
def test_delete_me_soft_deletes_account_and_personal_org(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))

    owner = fresh_user_id()
    setup_workspace(owner)
    try:
        with TestClient(app) as client:
            deleted = client.delete("/v1/me", headers=_auth(owner))
            assert deleted.status_code == 200
            assert "purge_after" in deleted.json()

            # account_deletion-Zeile angelegt, noch nicht gepurged.
            row = asyncio.run(
                _fetchrow("SELECT purged_at FROM account_deletion WHERE user_id = $1", owner)
            )
            assert row is not None
            assert row["purged_at"] is None

            # Personal-Org ist eingemottet (deleted_at gesetzt).
            org = asyncio.run(
                _fetchrow(
                    "SELECT deleted_at FROM organization WHERE kind = 'personal' AND slug = $1",
                    str(owner),
                )
            )
            assert org is not None
            assert org["deleted_at"] is not None

            # /v1/me blendet die eingemottete Org aus.
            me = client.get("/v1/me", headers=_auth(owner)).json()
            assert me["default_workspace_id"] is None
            assert me["organizations"] == []
    finally:
        cleanup_workspaces([owner])
        asyncio.run(_execute("DELETE FROM account_deletion WHERE user_id = $1", owner))


@pytest.mark.integration
def test_delete_organization_owner_only(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))

    owner = fresh_user_id()
    other = fresh_user_id()
    setup_workspace(owner)
    setup_workspace(other)
    slug = f"acme-{secrets.token_hex(4)}"
    try:
        with TestClient(app) as client:
            created = client.post(
                "/v1/organizations",
                json={"name": "Acme", "slug": slug},
                headers=_auth(owner),
            )
            assert created.status_code == 201
            org_id = created.json()["id"]

            # Nicht-Owner darf nicht loeschen.
            forbidden = client.delete(f"/v1/organizations/{org_id}", headers=_auth(other))
            assert forbidden.status_code == 403

            # Personal-Org laeuft ueber Konto-Loeschung → 400.
            personal = asyncio.run(
                _fetchrow(
                    "SELECT id FROM organization WHERE kind = 'personal' AND slug = $1",
                    str(owner),
                )
            )
            assert personal is not None
            bad = client.delete(f"/v1/organizations/{personal['id']}", headers=_auth(owner))
            assert bad.status_code == 400

            # Owner loescht die Company-Org (Soft-Delete).
            ok = client.delete(f"/v1/organizations/{org_id}", headers=_auth(owner))
            assert ok.status_code == 200

            listed = client.get("/v1/organizations", headers=_auth(owner)).json()
            assert org_id not in {o["id"] for o in listed}
    finally:
        _drop_company_org(slug)
        cleanup_workspaces([owner, other])


@pytest.mark.integration
def test_soft_deleted_org_blocks_workspace_access(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))

    owner = fresh_user_id()
    setup_workspace(owner)
    slug = f"acme-{secrets.token_hex(4)}"
    try:
        with TestClient(app) as client:
            created = client.post(
                "/v1/organizations",
                json={"name": "Acme", "slug": slug},
                headers=_auth(owner),
            )
            org_id = created.json()["id"]
            me = client.get("/v1/me", headers=_auth(owner)).json()
            company = next(o for o in me["organizations"] if o["id"] == org_id)
            ws_id = company["workspaces"][0]["id"]

            # Vor dem Loeschen: Zugriff ok.
            before = client.get(f"/v1/workspaces/{ws_id}/personas", headers=_auth(owner))
            assert before.status_code == 200

            client.delete(f"/v1/organizations/{org_id}", headers=_auth(owner))

            # Nach dem Soft-Delete: Workspace-Zugriff gesperrt (403).
            blocked = client.get(f"/v1/workspaces/{ws_id}/personas", headers=_auth(owner))
            assert blocked.status_code == 403
    finally:
        _drop_company_org(slug)
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_purge_removes_expired(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))

    owner = fresh_user_id()
    setup_workspace(owner)
    slug = f"acme-{secrets.token_hex(4)}"
    try:
        with TestClient(app) as client:
            org_id = client.post(
                "/v1/organizations",
                json={"name": "Acme", "slug": slug},
                headers=_auth(owner),
            ).json()["id"]
            client.delete(f"/v1/organizations/{org_id}", headers=_auth(owner))
            client.delete("/v1/me", headers=_auth(owner))

        # Grace kuenstlich in die Vergangenheit ziehen.
        past = datetime.now(UTC) - timedelta(days=1)
        asyncio.run(
            _execute("UPDATE organization SET purge_after = $1 WHERE deleted_at IS NOT NULL", past)
        )
        asyncio.run(_execute("UPDATE account_deletion SET purge_after = $1", past))

        async def _purge() -> None:
            conn = await asyncpg.connect(get_settings().database_url)
            try:
                result = await purge_expired(PgAccountPurgeRepository(conn))
                assert result.organizations >= 1
                assert result.accounts >= 1
            finally:
                await conn.close()

        asyncio.run(_purge())

        # Company-Org + Personal-Org hart geloescht; account_deletion finalisiert.
        assert asyncio.run(_fetchrow("SELECT id FROM organization WHERE id = $1", org_id)) is None
        assert (
            asyncio.run(
                _fetchrow(
                    "SELECT id FROM organization WHERE kind = 'personal' AND slug = $1", str(owner)
                )
            )
            is None
        )
        purged = asyncio.run(
            _fetchrow("SELECT purged_at FROM account_deletion WHERE user_id = $1", owner)
        )
        assert purged is not None
        assert purged["purged_at"] is not None
    finally:
        _drop_company_org(slug)
        cleanup_workspaces([owner])
        asyncio.run(_execute("DELETE FROM account_deletion WHERE user_id = $1", owner))
