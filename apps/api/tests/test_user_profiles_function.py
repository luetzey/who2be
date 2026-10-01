"""Nutzerprofile nur ueber `w2b_user_profiles` (Migration 0090, Cloud-Rolle).

Die Cloud-Edition verbindet zur Laufzeit als `who2be_app` (NOSUPERUSER,
NOBYPASSRLS, Migration 0036). Diese Rolle hat bewusst KEINEN Zugriff auf das
GoTrue-Schema `auth`: `auth.users` traegt kein RLS, ein Grant zeigte jedem
Mandanten jede E-Mail. E-Mail und Metadaten liest die App deshalb nur ueber die
SECURITY-DEFINER-Funktion `w2b_user_profiles(uuid[])`, die ausschliesslich
Nutzer des aktuellen Mandanten (und den Aufrufer selbst) zurueckgibt.

Die Tests laufen als `who2be_app` — als Owner/Superuser waeren sie gruen, ohne
etwas zu beweisen (RLS- und Rechte-Bypass).
"""

from __future__ import annotations

import asyncio
import secrets
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

import asyncpg
import pytest
from fastapi.testclient import TestClient

from who2be_api.core import db
from who2be_api.core.config import Settings, get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.core.tenancy import TENANT_SETTING, USER_SETTING
from who2be_api.main import app
from who2be_api.testing.workspace_setup import (
    _ensure_auth_users_stub,
    cleanup_workspaces,
    fresh_user_id,
    seed_auth_user,
    setup_workspace,
)

# Test-only Passwort der App-Rolle — dieselbe Konstante wie test_rls_isolation.
_APP_PASSWORD = "rls_test_secret"  # noqa: S105 — Test-Fixture, kein echtes Secret


def _app_role_url() -> str:
    """`DATABASE_URL` mit `who2be_app` statt der Owner-Rolle."""
    parts = urlsplit(get_settings().database_url)
    host = parts.hostname or "localhost"
    port = f":{parts.port}" if parts.port else ""
    netloc = f"who2be_app:{_APP_PASSWORD}@{host}{port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


async def _owner() -> asyncpg.Connection:
    return await asyncpg.connect(get_settings().database_url)


def _prepare_public_schema() -> None:
    """Migrationen + Auth-Stub im Standard-Schema, Passwort der App-Rolle setzen."""

    async def _run() -> None:
        conn = await _owner()
        try:
            await apply_migrations(conn, MIGRATIONS_DIR)
            await _ensure_auth_users_stub(conn)
            await conn.execute(f"ALTER ROLE who2be_app WITH PASSWORD '{_APP_PASSWORD}'")
        finally:
            await conn.close()

    asyncio.run(_run())


def _add_member(workspace_id: UUID, user_id: UUID) -> None:
    async def _run() -> None:
        conn = await _owner()
        try:
            await conn.execute(
                "INSERT INTO workspace_member (workspace_id, user_id, role) "
                "VALUES ($1, $2, 'editor') ON CONFLICT DO NOTHING",
                workspace_id,
                user_id,
            )
        finally:
            await conn.close()

    asyncio.run(_run())


def _insert_history(entity_id: UUID, changed_by: UUID) -> None:
    async def _run() -> None:
        conn = await _owner()
        try:
            await conn.execute(
                "INSERT INTO status_history "
                "(entity_type, entity_id, from_status, to_status, changed_by) "
                "VALUES ('persona', $1, 'draft', 'review', $2)",
                entity_id,
                changed_by,
            )
        finally:
            await conn.close()

    asyncio.run(_run())


def _seed_persona(workspace_id: UUID) -> UUID:
    async def _run() -> UUID:
        conn = await _owner()
        try:
            persona_id: UUID = await conn.fetchval(
                "SELECT id FROM persona WHERE workspace_id = $1 LIMIT 1", workspace_id
            )
            return persona_id
        finally:
            await conn.close()

    return asyncio.run(_run())


def _set_account_fields(
    user_id: UUID,
    *,
    password_hash: str | None,
    created_at: datetime | None = None,
    last_sign_in_at: datetime | None = None,
) -> None:
    """Setzt die Konto-Spalten im `auth.users`-Stub (als Owner)."""

    async def _run() -> None:
        conn = await _owner()
        try:
            await conn.execute(
                "UPDATE auth.users SET encrypted_password = $2, created_at = $3, "
                "last_sign_in_at = $4 WHERE id = $1",
                user_id,
                password_hash,
                created_at,
                last_sign_in_at,
            )
        finally:
            await conn.close()

    asyncio.run(_run())


@pytest.fixture
def app_role_client(
    monkeypatch: pytest.MonkeyPatch, patched_jwt_secret: str
) -> Iterator[TestClient]:
    """TestClient, dessen App-Pool als `who2be_app` verbindet (Cloud-Modus)."""
    _prepare_public_schema()
    app_url = _app_role_url()
    monkeypatch.setattr(db, "get_settings", lambda: Settings(app_database_url=app_url))
    # Server-Fehler als HTTP-Status sehen (500), nicht als Exception im Test —
    # genau das ist der Befund, den dieser Test festhaelt.
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.mark.integration
def test_app_role_pool_has_no_access_to_auth_users(app_role_client: TestClient) -> None:
    """Vorbedingung, sonst bewiesen die folgenden Tests nichts: der Pool laeuft
    wirklich als `who2be_app`, und diese Rolle kann `auth.users` nicht lesen."""

    async def _run() -> tuple[str, bool, bool]:
        owner = await _owner()
        conn = await asyncpg.connect(_app_role_url())
        try:
            role: str = await conn.fetchval("SELECT current_user")
            # Rechte-Abfrage ueber den Owner: `has_table_privilege` muss den
            # Namen aufloesen und braucht dafuer selbst Schema-Rechte.
            schema_usage: bool = await owner.fetchval(
                "SELECT has_schema_privilege('who2be_app', 'auth', 'USAGE')"
            )
            table_select: bool = await owner.fetchval(
                "SELECT has_table_privilege('who2be_app', 'auth.users', 'SELECT')"
            )
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await conn.fetch("SELECT email FROM auth.users LIMIT 1")
            return role, schema_usage, table_select
        finally:
            await conn.close()
            await owner.close()

    role, schema_usage, table_select = asyncio.run(_run())
    assert role == "who2be_app"
    assert schema_usage is False, "who2be_app darf keinen USAGE auf das Schema auth haben"
    assert table_select is False, "who2be_app darf auth.users nicht direkt lesen"


@pytest.mark.integration
def test_dashboard_members_and_me_show_profiles_as_app_role(
    app_role_client: TestClient,
    make_auth_headers: Callable[[UUID], dict[str, str]],
) -> None:
    owner = fresh_user_id()
    member = fresh_user_id()
    fresh = fresh_user_id()
    ws = setup_workspace(owner)
    _add_member(ws, member)
    seed_auth_user(owner, email="n1a-owner@example.com", name="N1a Owner")
    seed_auth_user(member, email="n1a-member@example.com", name=None)
    seed_auth_user(fresh, email="n1a-fresh@example.com", name=None)
    persona_id = _seed_persona(ws)
    _insert_history(persona_id, owner)
    _insert_history(persona_id, member)

    try:
        dash = app_role_client.get(
            f"/v1/workspaces/{ws}/dashboard", headers=make_auth_headers(owner)
        )
        assert dash.status_code == 200, dash.text
        names = [entry["actor"]["display_name"] for entry in dash.json()["activity"]]
        # Neuester zuerst: Mitglied (E-Mail-Local-Part), dann Owner (Meta-Name).
        assert names == ["n1a-member", "N1a Owner"]

        members = app_role_client.get(
            f"/v1/workspaces/{ws}/members", headers=make_auth_headers(owner)
        )
        assert members.status_code == 200, members.text
        emails = {row["user_id"]: row["email"] for row in members.json()}
        assert emails == {
            str(owner): "n1a-owner@example.com",
            str(member): "n1a-member@example.com",
        }

        # Lazy-Seed: die Personal-Org traegt den Local-Part der eigenen E-Mail.
        me = app_role_client.get("/v1/me", headers=make_auth_headers(fresh))
        assert me.status_code == 200, me.text
        assert [org["name"] for org in me.json()["organizations"]] == ["n1a-fresh"]
    finally:
        cleanup_workspaces([owner, member, fresh])


@pytest.mark.integration
def test_user_profiles_function_is_scoped_to_current_tenant() -> None:
    """Negativtest: die Funktion liefert nur Nutzer des gesetzten Mandanten und
    den Aufrufer selbst — nie einen Nutzer eines fremden Mandanten, und ohne
    Mandanten gar nichts."""
    _prepare_public_schema()
    user_a = fresh_user_id()
    user_b = fresh_user_id()
    ws_a = setup_workspace(user_a)
    setup_workspace(user_b)
    seed_auth_user(user_a, email="n1a-a@example.com", name="A")
    seed_auth_user(user_b, email="n1a-b@example.com", name="B")
    lookup = "SELECT id, email FROM w2b_user_profiles($1::uuid[]) ORDER BY email"

    async def _run() -> None:
        conn = await asyncpg.connect(_app_role_url())
        try:
            both = [user_a, user_b]
            # Ohne Mandant und ohne Self-GUC: nichts.
            assert await conn.fetch(lookup, both) == []

            await conn.execute("SELECT set_config($1, $2, false)", TENANT_SETTING, str(ws_a))
            rows = await conn.fetch(lookup, both)
            assert [(r["id"], r["email"]) for r in rows] == [(user_a, "n1a-a@example.com")]
            # Fremder Nutzer allein: leer, auch wenn die ID exakt bekannt ist.
            assert await conn.fetch(lookup, [user_b]) == []

            # Self-Lookup: nur der Aufrufer, nicht der fremde Mandant.
            await conn.execute("RESET ALL")
            await conn.execute("SELECT set_config($1, $2, false)", USER_SETTING, str(user_b))
            rows = await conn.fetch(lookup, both)
            assert [r["id"] for r in rows] == [user_b]
        finally:
            await conn.close()

    try:
        asyncio.run(_run())
    finally:
        cleanup_workspaces([user_a, user_b])


@pytest.mark.integration
def test_gdpr_export_and_me_read_own_account_as_app_role(
    app_role_client: TestClient,
    make_auth_headers: Callable[[UUID], dict[str, str]],
) -> None:
    """DSGVO-Export und `/v1/me` lesen die eigenen Kontodaten als `who2be_app`
    ueber `w2b_self_account()` (Migration 0093): `account`-Block vollstaendig,
    `has_password` true fuer den Passwortnutzer, false fuer den OAuth-Nutzer."""
    password_user = fresh_user_id()
    oauth_user = fresh_user_id()
    setup_workspace(password_user)
    setup_workspace(oauth_user)
    seed_auth_user(password_user, email="n1b-password@example.com", name=None)
    seed_auth_user(oauth_user, email="n1b-oauth@example.com", name=None)
    created = datetime(2026, 9, 1, 8, 30, tzinfo=UTC)
    last_sign_in = created + timedelta(days=29, hours=2)
    _set_account_fields(
        password_user,
        password_hash="$2a$10$n1btestnotarealhash",  # noqa: S106 — Test-Stub, kein Secret
        created_at=created,
        last_sign_in_at=last_sign_in,
    )
    _set_account_fields(oauth_user, password_hash=None, created_at=created)

    try:
        export = app_role_client.get("/v1/gdpr/export", headers=make_auth_headers(password_user))
        assert export.status_code == 200, export.text
        account = export.json()["account"]
        assert account["id"] == str(password_user)
        assert account["email"] == "n1b-password@example.com"
        assert datetime.fromisoformat(account["created_at"]) == created
        assert datetime.fromisoformat(account["last_sign_in_at"]) == last_sign_in

        me_password = app_role_client.get("/v1/me", headers=make_auth_headers(password_user))
        assert me_password.status_code == 200, me_password.text
        assert me_password.json()["has_password"] is True

        me_oauth = app_role_client.get("/v1/me", headers=make_auth_headers(oauth_user))
        assert me_oauth.status_code == 200, me_oauth.text
        assert me_oauth.json()["has_password"] is False
    finally:
        cleanup_workspaces([password_user, oauth_user])


@pytest.mark.integration
def test_self_account_function_returns_only_current_user() -> None:
    """Negativtest: `w2b_self_account()` liefert ausschliesslich die Zeile von
    `app.current_user_id` — nie die eines anderen Nutzers, und ohne die GUC
    nichts, auch nicht mit gesetztem Workspace-Mandanten."""
    _prepare_public_schema()
    user_a = fresh_user_id()
    user_b = fresh_user_id()
    ws_a = setup_workspace(user_a)
    setup_workspace(user_b)
    seed_auth_user(user_a, email="n1b-a@example.com", name=None)
    seed_auth_user(user_b, email="n1b-b@example.com", name=None)
    _set_account_fields(user_a, password_hash="$2a$10$n1bhash")  # noqa: S106 — Test-Stub
    lookup = "SELECT * FROM w2b_self_account()"

    async def _run() -> None:
        conn = await asyncpg.connect(_app_role_url())
        try:
            # Ohne GUC: nichts.
            assert await conn.fetch(lookup) == []
            # Workspace-Mandant allein oeffnet nichts — die Funktion ist kein
            # Mitglieder-Lookup.
            await conn.execute("SELECT set_config($1, $2, false)", TENANT_SETTING, str(ws_a))
            assert await conn.fetch(lookup) == []

            await conn.execute("RESET ALL")
            await conn.execute("SELECT set_config($1, $2, false)", USER_SETTING, str(user_a))
            rows = await conn.fetch(lookup)
            assert [(r["id"], r["email"], r["has_password"]) for r in rows] == [
                (user_a, "n1b-a@example.com", True)
            ]
            # Nur der Wahrheitswert verlaesst die Funktion, nie der Hash.
            assert set(rows[0].keys()) == {
                "id",
                "email",
                "created_at",
                "last_sign_in_at",
                "has_password",
            }

            # Anderer Aufrufer: nur dessen Zeile, nie die von user_a.
            await conn.execute("SELECT set_config($1, $2, false)", USER_SETTING, str(user_b))
            rows = await conn.fetch(lookup)
            assert [(r["id"], r["has_password"]) for r in rows] == [(user_b, False)]

            # Transaktionslokal gesetzt (wie `scope_to_self`): nach COMMIT leer.
            await conn.execute("RESET ALL")
            async with conn.transaction():
                await conn.execute("SELECT set_config($1, $2, true)", USER_SETTING, str(user_a))
                assert len(await conn.fetch(lookup)) == 1
            assert await conn.fetch(lookup) == []
        finally:
            await conn.close()

    try:
        asyncio.run(_run())
    finally:
        cleanup_workspaces([user_a, user_b])


@pytest.mark.integration
@pytest.mark.parametrize("signature", ["w2b_user_profiles(uuid[])", "w2b_self_account()"])
def test_profile_functions_execute_only_for_owner_and_app_role(signature: str) -> None:
    """EXECUTE haben nur Owner und `who2be_app` — auch wenn Default-Privileges
    (wie in Images mit vordefinierten API-Rollen) EXECUTE an weitere Rollen
    vergeben wuerden. Laeuft im isolierten Schema, damit die Default-Privileges
    nur dort wirken."""
    schema = f"n1a_{secrets.token_hex(6)}"
    probe_role = f"w2b_probe_{secrets.token_hex(4)}"

    async def _run() -> None:
        owner = await _owner()
        try:
            await owner.execute(f'CREATE ROLE "{probe_role}" NOLOGIN')
            await owner.execute(f'CREATE SCHEMA "{schema}"')
            await owner.execute(
                f'ALTER DEFAULT PRIVILEGES IN SCHEMA "{schema}" '
                f'GRANT EXECUTE ON FUNCTIONS TO "{probe_role}"'
            )
            await owner.execute(f'SET search_path TO "{schema}"')
            await apply_migrations(owner, MIGRATIONS_DIR)

            qualified = f'"{schema}".{signature}'
            grantees = await owner.fetch(
                "SELECT CASE WHEN a.grantee = 0 THEN 'PUBLIC' "
                "            ELSE pg_get_userbyid(a.grantee) END AS grantee "
                "FROM pg_proc p, aclexplode(p.proacl) a "
                "WHERE p.oid = $1::regprocedure AND a.privilege_type = 'EXECUTE'",
                qualified,
            )
            fn_owner = await owner.fetchval(
                "SELECT pg_get_userbyid(proowner) FROM pg_proc WHERE oid = $1::regprocedure",
                qualified,
            )
            assert {row["grantee"] for row in grantees} == {fn_owner, "who2be_app"}

            config = await owner.fetchval(
                "SELECT proconfig FROM pg_proc WHERE oid = $1::regprocedure", qualified
            )
            assert config == ["search_path=pg_catalog, pg_temp"]
            definer = await owner.fetchval(
                "SELECT prosecdef FROM pg_proc WHERE oid = $1::regprocedure", qualified
            )
            assert definer is True
        finally:
            await owner.execute("RESET search_path")
            await owner.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            await owner.execute(f'DROP OWNED BY "{probe_role}"')
            await owner.execute(f'DROP ROLE IF EXISTS "{probe_role}"')
            await owner.close()

    asyncio.run(_run())
