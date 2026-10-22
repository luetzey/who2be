"""Integrationstests Werkzeug-Profile: Migration 0111 und Repository (ADR-0059 Q2a).

Laeuft in einem isolierten Schema, die Repository-Proben auf der Laufzeitrolle
`who2be_app` (NOBYPASSRLS). Belegt:

- **Bestand (0111 auf Altdaten):** Jeder Bestands-Workspace bekommt die vier
  mitgelieferten Profile, benannt nach `content_locale`. Verwaltete Builder
  stehen danach auf „Builder“ (W59-3 = A), alle anderen Agenten bleiben auf
  „Alle“ ohne Ausnahmen (Owner d).
- **Seed-Paritaet:** Migration und `seed_builtin_profiles` liefern dieselben
  Zeilen, und beide entsprechen `BUILTIN_PROFILES`, der einzigen Quelle. Ein
  neuer Workspace (`ensure_personal_workspace`) ordnet beide Builder zu.
- **RLS, Cascade, RESTRICT:** Profile sind workspace-getrennt, fallen mit
  Workspace und Org, und ein zugeordnetes Profil laesst sich nicht loeschen.
  Der zusammengesetzte FK verhindert ein Profil aus einem fremden Workspace.
- **Repository:** CRUD, Namenskonflikt ohne Gross/Klein, Lieferstand,
  Zuordnung (auch „Alle“ mit Ausnahmen), `fetch_grant`, und `insert` bzw.
  `deep_copy` des Agent-Repository uebernehmen Profil und Ausnahmen.
- **Org-Transfer:** `tool_profile` kommt in der Import-Reihenfolge vor `agent`.
"""

from __future__ import annotations

import asyncio
import secrets
import shutil
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

import asyncpg
import pytest

from who2be_api.core.config import get_settings
from who2be_api.core.db import init_connection
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.core.org_transfer import load_schema
from who2be_api.core.tenancy import apply_tenant_settings, tenant_scope
from who2be_api.repositories.agent_repository import (
    AgentToolProfileColumns,
    PgAgentRepository,
)
from who2be_api.repositories.tool_profile_repository import (
    PgToolProfileRepository,
    ToolProfileBuiltinError,
    ToolProfileInUseError,
    ToolProfileNameTakenError,
    builtin_profile_name,
    seed_builtin_profiles,
)
from who2be_api.repositories.workspace_repository import ensure_personal_workspace
from who2be_models import AgentStatus, AgentToolPolicy
from who2be_models.tool_profiles import (
    BUILTIN_PROFILES,
    BuiltinProfileKey,
    ToolProfileGrant,
    effective_tool_set,
)

pytestmark = pytest.mark.integration

# Test-only Passwort fuer die App-Rolle (per format() in ALTER ROLE eingesetzt).
_APP_PASSWORD = "tool_profile_secret"  # noqa: S105 — Test-Fixture, kein echtes Secret

_MIGRATION = "0111_tool_profile.sql"
_BEFORE = sorted(p.name for p in MIGRATIONS_DIR.glob("[0-9]*.sql") if p.name < _MIGRATION)


def _db_reachable() -> bool:
    async def _check() -> bool:
        try:
            conn = await asyncpg.connect(get_settings().database_url)
        except (asyncpg.PostgresError, OSError):
            return False
        await conn.close()
        return True

    return asyncio.run(_check())


def _require_db() -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")


def _expected(locale: str) -> dict[str, tuple[str, list[str], list[str]]]:
    """Lieferstand aus der einzigen Quelle: key -> (Name, Gruppen, Werkzeuge)."""
    return {
        key.value: (
            builtin_profile_name(key, locale),
            [group.value for group in profile.groups],
            list(profile.tools),
        )
        for key, profile in BUILTIN_PROFILES.items()
    }


async def _profiles(
    conn: asyncpg.Connection, workspace_id: UUID
) -> dict[str, tuple[str, list[str], list[str]]]:
    rows = await conn.fetch(
        "SELECT builtin_key, name, groups, tools FROM tool_profile "
        "WHERE workspace_id = $1 AND builtin_key IS NOT NULL",
        workspace_id,
    )
    return {r["builtin_key"]: (r["name"], list(r["groups"]), list(r["tools"])) for r in rows}


async def _org_ws(conn: asyncpg.Connection, locale: str = "de") -> tuple[UUID, UUID]:
    tag = secrets.token_hex(4)
    org_id = await conn.fetchval(
        "INSERT INTO organization (name, slug, kind) VALUES ($1, $1, 'company') RETURNING id",
        f"org-{tag}",
    )
    ws_id = await conn.fetchval(
        "INSERT INTO workspace (org_id, name, slug, content_locale) "
        "VALUES ($1, $2, $2, $3) RETURNING id",
        org_id,
        f"ws-{tag}",
        locale,
    )
    return org_id, ws_id


async def _agent(
    conn: asyncpg.Connection, workspace_id: UUID, name: str, *, managed: bool = False
) -> UUID:
    agent_id: UUID = await conn.fetchval(
        "INSERT INTO agent (workspace_id, owner_id, name, is_managed) "
        "VALUES ($1, $2, $3, $4) RETURNING id",
        workspace_id,
        uuid4(),
        name,
        managed,
    )
    return agent_id


async def _agent_columns(
    conn: asyncpg.Connection, agent_id: UUID
) -> tuple[str | None, list[str], list[str]]:
    row = await conn.fetchrow(
        "SELECT a.tool_profile_id, a.tools_added, a.tools_removed, p.builtin_key "
        "FROM agent a LEFT JOIN tool_profile p ON p.id = a.tool_profile_id "
        "WHERE a.id = $1",
        agent_id,
    )
    assert row is not None
    return row["builtin_key"], list(row["tools_added"]), list(row["tools_removed"])


def _in_schema(body: Callable[[asyncpg.Connection, str], Awaitable[None]], prefix: str) -> None:
    """Owner-Verbindung in einem frischen Schema; Aufraeumen garantiert."""
    _require_db()
    schema = f"{prefix}_{secrets.token_hex(6)}"

    async def _run() -> None:
        owner = await asyncpg.connect(get_settings().database_url)
        try:
            await owner.execute(f'CREATE SCHEMA "{schema}"')
            await owner.execute(f'SET search_path TO "{schema}"')
            await init_connection(owner)
            await body(owner, schema)
        finally:
            await owner.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            await owner.close()

    asyncio.run(_run())


# --- Migration 0111 auf Bestandsdaten --------------------------------------------


def test_backfill_seeds_profiles_and_assigns_only_managed_builders(tmp_path: Path) -> None:
    """Bestand vor 0111 anlegen, dann 0111 anwenden: Seed, W59-3 = A, Rest „Alle“."""
    for name in _BEFORE:
        shutil.copy(MIGRATIONS_DIR / name, tmp_path / name)

    async def body(owner: asyncpg.Connection, _schema: str) -> None:
        await apply_migrations(owner, tmp_path)
        _, ws_de = await _org_ws(owner, "de")
        _, ws_en = await _org_ws(owner, "en")
        builder_de = await _agent(owner, ws_de, "Builder", managed=True)
        lite_de = await _agent(owner, ws_de, "Builder-Lite", managed=True)
        builder_en = await _agent(owner, ws_en, "Builder", managed=True)
        own_de = await _agent(owner, ws_de, "Eigener Agent")

        shutil.copy(MIGRATIONS_DIR / _MIGRATION, tmp_path / _MIGRATION)
        assert await apply_migrations(owner, tmp_path) == [_MIGRATION]

        # Seed-Paritaet Migration <-> Quelle, je Sprache.
        assert await _profiles(owner, ws_de) == _expected("de")
        assert await _profiles(owner, ws_en) == _expected("en")
        assert (await _profiles(owner, ws_de))["read"][0] == "Lesen"
        assert (await _profiles(owner, ws_en))["read"][0] == "Read"

        # W59-3 = A: beide verwalteten Builder auf „Builder“ des eigenen Workspace.
        for agent_id in (builder_de, lite_de, builder_en):
            assert await _agent_columns(owner, agent_id) == ("builder", [], [])
        same_ws: bool = await owner.fetchval(
            "SELECT bool_and(p.workspace_id = a.workspace_id) FROM agent a "
            "JOIN tool_profile p ON p.id = a.tool_profile_id"
        )
        assert same_ws

        # Owner d: der unverwaltete Agent bleibt „Alle“ ohne Ausnahmen.
        assert await _agent_columns(owner, own_de) == (None, [], [])

        # Zweiter Runner-Lauf ist ein No-op.
        assert await apply_migrations(owner, tmp_path) == []

    _in_schema(body, "tp_backfill")


def test_code_seed_matches_migration_seed() -> None:
    """`seed_builtin_profiles` legt exakt dieselben Zeilen an wie 0111 (beide Sprachen)."""

    async def body(owner: asyncpg.Connection, _schema: str) -> None:
        await apply_migrations(owner, MIGRATIONS_DIR)
        for locale in ("de", "en"):
            _, ws = await _org_ws(owner, locale)
            # Frischer Workspace nach 0111: noch keine Profile (der Migrations-
            # Seed lief vor seiner Anlage), also nur der Code-Weg.
            assert await _profiles(owner, ws) == {}
            await seed_builtin_profiles(owner, ws, locale)
            assert await _profiles(owner, ws) == _expected(locale)
            # Idempotent, und ein angepasstes Profil bleibt angepasst.
            await owner.execute(
                "UPDATE tool_profile SET groups = '{core}' "
                "WHERE workspace_id = $1 AND builtin_key = 'read'",
                ws,
            )
            await seed_builtin_profiles(owner, ws, locale)
            assert (await _profiles(owner, ws))["read"][1] == ["core"]

    _in_schema(body, "tp_parity")


def test_builder_profile_carries_workarea_read() -> None:
    """W59-4: der gespeicherte Lieferstand „Builder“ enthaelt `workarea_read`."""
    expected = _expected("de")["builder"][1]
    assert "workarea_read" in expected
    assert "workarea_write" not in expected


# --- Neuer Workspace unter erzwungener RLS ---------------------------------------


def test_new_workspace_seeds_profiles_and_builders_under_rls() -> None:
    """`ensure_personal_workspace` als `who2be_app`: vier Profile, beide Builder zugeordnet."""

    async def body(owner: asyncpg.Connection, schema: str) -> None:
        await apply_migrations(owner, MIGRATIONS_DIR)
        await owner.execute(f"ALTER ROLE who2be_app WITH PASSWORD '{_APP_PASSWORD}'")
        app = await asyncpg.connect(
            get_settings().database_url, user="who2be_app", password=_APP_PASSWORD
        )
        try:
            await app.execute(f'SET search_path TO "{schema}"')
            await init_connection(app)
            async with app.transaction():
                ws = await ensure_personal_workspace(
                    app, uuid4(), user_email="tp@example.com", content_locale="en"
                )
        finally:
            await app.close()

        assert await _profiles(owner, ws) == _expected("en")
        managed = await owner.fetch(
            "SELECT id FROM agent WHERE workspace_id = $1 AND is_managed = true", ws
        )
        assert len(managed) == 2, "Builder und Builder-Lite erwartet"
        for row in managed:
            assert await _agent_columns(owner, row["id"]) == ("builder", [], [])

    _in_schema(body, "tp_newws")


# --- Schema: RLS, Cascade, RESTRICT, FK ------------------------------------------


@dataclass
class _Env:
    owner: asyncpg.Connection
    schema: str
    org_a: UUID
    ws_a: UUID
    org_b: UUID
    ws_b: UUID


def _with_env(body: Callable[[_Env], Awaitable[None]], prefix: str) -> None:
    async def outer(owner: asyncpg.Connection, schema: str) -> None:
        await apply_migrations(owner, MIGRATIONS_DIR)
        org_a, ws_a = await _org_ws(owner, "de")
        org_b, ws_b = await _org_ws(owner, "de")
        await seed_builtin_profiles(owner, ws_a, "de")
        await seed_builtin_profiles(owner, ws_b, "de")
        await owner.execute(f"ALTER ROLE who2be_app WITH PASSWORD '{_APP_PASSWORD}'")
        await body(_Env(owner, schema, org_a, ws_a, org_b, ws_b))

    _in_schema(outer, prefix)


async def _app_pool(schema: str) -> asyncpg.Pool:
    pool = await asyncpg.create_pool(
        get_settings().database_url,
        user="who2be_app",
        password=_APP_PASSWORD,
        min_size=1,
        max_size=2,
        init=init_connection,
        setup=apply_tenant_settings,
        server_settings={"search_path": schema},
    )
    assert pool is not None
    return pool


def test_rls_separates_workspaces() -> None:
    async def body(env: _Env) -> None:
        pool = await _app_pool(env.schema)
        try:
            async with tenant_scope(env.ws_a, env.org_a):
                own = await PgToolProfileRepository(pool).list_by_workspace(env.ws_a)
                foreign = await PgToolProfileRepository(pool).list_by_workspace(env.ws_b)
                assert len(own) == 4
                assert foreign == [], "RLS muss fremde Profile verbergen"
                visible = await pool.fetchval("SELECT count(*) FROM tool_profile")
                assert visible == 4
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    await pool.execute(
                        "INSERT INTO tool_profile (workspace_id, name) VALUES ($1, 'x')",
                        env.ws_b,
                    )
        finally:
            await pool.close()

    _with_env(body, "tp_rls")


def test_profile_falls_with_workspace_and_org() -> None:
    """Workspace- und Org-Loeschen raeumen Profile mit, auch mit zugeordnetem Agenten."""

    async def body(env: _Env) -> None:
        o = env.owner
        builder_a = await o.fetchval(
            "SELECT id FROM tool_profile WHERE workspace_id = $1 AND builtin_key = 'builder'",
            env.ws_a,
        )
        builder_b = await o.fetchval(
            "SELECT id FROM tool_profile WHERE workspace_id = $1 AND builtin_key = 'builder'",
            env.ws_b,
        )
        agent_a = await _agent(o, env.ws_a, "A")
        agent_b = await _agent(o, env.ws_b, "B")
        await o.execute("UPDATE agent SET tool_profile_id = $2 WHERE id = $1", agent_a, builder_a)
        await o.execute("UPDATE agent SET tool_profile_id = $2 WHERE id = $1", agent_b, builder_b)

        await o.execute("DELETE FROM workspace WHERE id = $1", env.ws_a)
        assert (
            await o.fetchval("SELECT count(*) FROM tool_profile WHERE workspace_id = $1", env.ws_a)
            == 0
        )

        await o.execute("DELETE FROM organization WHERE id = $1", env.org_b)
        assert (
            await o.fetchval("SELECT count(*) FROM tool_profile WHERE workspace_id = $1", env.ws_b)
            == 0
        )
        assert (
            await o.fetchval(
                "SELECT count(*) FROM agent WHERE id = ANY($1::uuid[])", [agent_a, agent_b]
            )
            == 0
        )

    _with_env(body, "tp_cascade")


def test_fk_restricts_delete_and_pins_workspace() -> None:
    async def body(env: _Env) -> None:
        o = env.owner
        custom = await o.fetchval(
            "INSERT INTO tool_profile (workspace_id, name) VALUES ($1, 'Eigen') RETURNING id",
            env.ws_a,
        )
        agent = await _agent(o, env.ws_a, "A")
        await o.execute("UPDATE agent SET tool_profile_id = $2 WHERE id = $1", agent, custom)
        with pytest.raises(asyncpg.ForeignKeyViolationError):
            await o.execute("DELETE FROM tool_profile WHERE id = $1", custom)

        foreign = await o.fetchval(
            "SELECT id FROM tool_profile WHERE workspace_id = $1 AND builtin_key = 'read'",
            env.ws_b,
        )
        with pytest.raises(asyncpg.ForeignKeyViolationError):
            await o.execute("UPDATE agent SET tool_profile_id = $2 WHERE id = $1", agent, foreign)

        # Zweites mitgeliefertes Profil gleichen Schluessels: abgewiesen.
        with pytest.raises(asyncpg.UniqueViolationError):
            await o.execute(
                "INSERT INTO tool_profile (workspace_id, builtin_key, name) "
                "VALUES ($1, 'read', 'Noch eins')",
                env.ws_a,
            )
        with pytest.raises(asyncpg.CheckViolationError):
            await o.execute(
                "INSERT INTO tool_profile (workspace_id, builtin_key, name) "
                "VALUES ($1, 'admin', 'X')",
                env.ws_a,
            )

    _with_env(body, "tp_fk")


def test_org_transfer_imports_profiles_before_agents() -> None:
    async def body(env: _Env) -> None:
        order = (await load_schema(env.owner)).import_order()
        assert order.index("tool_profile") < order.index("agent")

    _with_env(body, "tp_transfer")


# --- Repository auf der App-Rolle ------------------------------------------------


def _with_repo(
    body: Callable[[PgToolProfileRepository, PgAgentRepository, _Env], Awaitable[None]],
    prefix: str,
) -> None:
    async def outer(env: _Env) -> None:
        pool = await _app_pool(env.schema)
        try:
            async with tenant_scope(env.ws_a, env.org_a):
                await body(PgToolProfileRepository(pool), PgAgentRepository(pool), env)
        finally:
            await pool.close()

    _with_env(outer, prefix)


def test_repository_crud_and_errors() -> None:
    async def body(repo: PgToolProfileRepository, _agents: PgAgentRepository, env: _Env) -> None:
        listed = await repo.list_by_workspace(env.ws_a)
        assert [p.builtin_key for p in listed] == list(BUILTIN_PROFILES)

        custom = await repo.insert(env.ws_a, "Recherche", "", ["read"], ["read_artifact"])
        assert custom.builtin_key is None and custom.agent_count == 0
        assert (await repo.list_by_workspace(env.ws_a))[-1].id == custom.id

        with pytest.raises(ToolProfileNameTakenError):
            await repo.insert(env.ws_a, "recherche", "", [], [])
        with pytest.raises(ToolProfileNameTakenError):
            await repo.update(env.ws_a, custom.id, "LESEN", "", [], [])

        updated = await repo.update(env.ws_a, custom.id, "Recherche 2", "d", ["core"], [])
        assert updated is not None and updated.groups == ["core"] and updated.tools == []
        assert await repo.update(env.ws_b, custom.id, "x", "", [], []) is None

        # Lieferstand: mitgeliefertes Profil anpassen und zuruecksetzen.
        read = listed[0]
        await repo.update(env.ws_a, read.id, "Nur lesen", "eigen", ["core"], ["search"])
        reset = await repo.reset_builtin(env.ws_a, read.id, "de")
        assert reset is not None
        assert (reset.name, reset.description, reset.groups, reset.tools) == (
            "Lesen",
            "",
            _expected("de")["read"][1],
            [],
        )
        assert await repo.reset_builtin(env.ws_a, custom.id, "de") is None

        with pytest.raises(ToolProfileBuiltinError):
            await repo.delete(env.ws_a, read.id)
        assert await repo.delete(env.ws_a, custom.id) is True
        assert await repo.delete(env.ws_a, custom.id) is False

    _with_repo(body, "tp_crud")


def test_repository_assign_count_grant_and_in_use() -> None:
    async def body(repo: PgToolProfileRepository, agents: PgAgentRepository, env: _Env) -> None:
        agent = await agents.insert(
            env.ws_a, uuid4(), "A", "", None, None, AgentStatus.disabled, AgentToolPolicy()
        )
        assert agent is not None
        assert (agent.tool_profile_id, agent.tools_added, agent.tools_removed) == (None, [], [])
        assert await repo.fetch_grant(env.ws_a, agent.id) is None

        # „Alle“ mit Ausnahme: Grant ohne id.
        assert await repo.assign_agent(env.ws_a, agent.id, None, [], ["query_table"])
        grant = await repo.fetch_grant(env.ws_a, agent.id)
        assert grant == ToolProfileGrant(id=None, name="", tools_removed=["query_table"])
        assert "query_table" not in effective_tool_set(grant)

        custom = await repo.insert(env.ws_a, "Schmal", "", ["core", "read"], ["search_kb"])
        assert await repo.assign_agent(env.ws_a, agent.id, custom.id, ["list_tables"], [])
        grant = await repo.fetch_grant(env.ws_a, agent.id)
        assert grant is not None
        assert (grant.id, grant.name, grant.groups, grant.tools, grant.tools_added) == (
            custom.id,
            "Schmal",
            ["core", "read"],
            ["search_kb"],
            ["list_tables"],
        )
        fetched = await agents.fetch(env.ws_a, agent.id)
        assert fetched is not None and fetched.tool_profile_id == custom.id
        assert fetched.tools_added == ["list_tables"]

        counted = await repo.fetch(env.ws_a, custom.id)
        assert counted is not None and counted.agent_count == 1
        with pytest.raises(ToolProfileInUseError) as err:
            await repo.delete(env.ws_a, custom.id)
        assert err.value.agent_count == 1

        # Profil eines fremden Workspace und fremder Agent: abgelehnt.
        foreign_id = uuid4()
        assert await repo.assign_agent(env.ws_a, agent.id, foreign_id, [], []) is False
        assert await repo.assign_agent(env.ws_b, agent.id, None, [], []) is False

        # Zurueck auf „Alle“: Grant None, Profil wieder loeschbar.
        assert await repo.assign_agent(env.ws_a, agent.id, None, [], [])
        assert await repo.fetch_grant(env.ws_a, agent.id) is None
        assert await repo.delete(env.ws_a, custom.id) is True

    _with_repo(body, "tp_assign")


def test_agent_insert_and_deep_copy_carry_profile() -> None:
    """`copy_agent`-Wege uebernehmen Profil und Ausnahmen der Quelle (ADR-0059 §4.2)."""

    async def body(repo: PgToolProfileRepository, agents: PgAgentRepository, env: _Env) -> None:
        builder = next(
            p
            for p in await repo.list_by_workspace(env.ws_a)
            if p.builtin_key == BuiltinProfileKey.builder
        )
        columns = AgentToolProfileColumns(builder.id, ("query_table",), ("search_kb",))

        copy = await agents.insert(
            env.ws_a,
            uuid4(),
            "Kopie",
            "",
            None,
            None,
            AgentStatus.disabled,
            AgentToolPolicy(),
            columns,
        )
        assert copy is not None
        assert AgentToolProfileColumns.from_agent(copy) == columns

        # deep_copy braucht eine Quell-Persona und ein Quell-Template.
        owner_id = uuid4()
        persona = await env.owner.fetchval(
            "INSERT INTO persona (workspace_id, owner_id, name) VALUES ($1, $2, 'P') RETURNING id",
            env.ws_a,
            owner_id,
        )
        template = await env.owner.fetchval(
            "INSERT INTO system_prompt_template (workspace_id, owner_id, name, slug) "
            "VALUES ($1, $2, 'T', 't') RETURNING id",
            env.ws_a,
            owner_id,
        )
        deep = await agents.deep_copy(
            env.ws_a,
            owner_id,
            persona,
            template,
            "t-copy",
            "Tiefe Kopie",
            "",
            AgentStatus.disabled,
            AgentToolPolicy(),
            columns,
        )
        assert deep is not None
        assert AgentToolProfileColumns.from_agent(deep) == columns

        # Ohne Angabe: „Alle“ (create_agent-Weg).
        plain = await agents.insert(
            env.ws_a, uuid4(), "Neu", "", None, None, AgentStatus.disabled, AgentToolPolicy()
        )
        assert plain is not None
        assert AgentToolProfileColumns.from_agent(plain) == AgentToolProfileColumns()

    _with_repo(body, "tp_copy")
