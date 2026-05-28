"""Integrationstests fuer die Phase-2.1a-1-Migrations (0005-0013).

Belegt:
- Idempotenz der gesamten Migration-Kette (zweiter Apply ist No-op).
- Anlage der neuen Tabellen (organization, org_member, workspace,
  workspace_member, status_history).
- DB-Invariante "max. 1 Draft/Review/Active je Entity" via partial unique
  index auf persona_version / playbook_version.
- Status-Backfill in 0011: current_version -> 'active', alle anderen
  Versionen -> 'inactive'.
- Backfill-Cardinality 0013: pro distinct owner_id genau eine Personal-Org,
  ein Personal-Workspace und ein workspace_member-Eintrag.

Pro Test wird ein dediziertes Postgres-Schema angelegt, in das die Migrations
laufen (search_path lokal gesetzt). Die `public`-Schema und damit der CI-DB-
Zustand bleiben unangetastet — der test_core_migrations_create_all_tables aus
test_migrations.py funktioniert weiter, und parallele Integration-Tests
sehen ihre echten Tabellen.
"""

import asyncio
import secrets
import shutil
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TypeVar
from uuid import UUID, uuid4

import asyncpg
import pytest

from who2be_api.core.config import get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations

_T = TypeVar("_T")


def _db_reachable() -> bool:
    async def _check() -> bool:
        try:
            conn = await asyncpg.connect(get_settings().database_url)
        except (asyncpg.PostgresError, OSError):
            return False
        await conn.close()
        return True

    return asyncio.run(_check())


def _copy_migrations(dst: Path, names: list[str]) -> None:
    for name in names:
        shutil.copy(MIGRATIONS_DIR / name, dst / name)


_ALL_MIGRATIONS = [
    "0001_api_token.sql",
    "0002_persona.sql",
    "0003_playbook.sql",
    "0004_persona_playbook.sql",
    "0005_organization.sql",
    "0006_workspace.sql",
    "0007_workspace_member.sql",
    "0008_persona_workspace.sql",
    "0009_playbook_workspace.sql",
    "0010_api_token_workspace.sql",
    "0011_status_on_versions.sql",
    "0012_status_history.sql",
    "0013_backfill_tenants.sql",
]
_PRE_TENANT_MIGRATIONS = _ALL_MIGRATIONS[:4]
_TENANT_MIGRATIONS = _ALL_MIGRATIONS[4:]


async def _with_isolated_schema(
    body: Callable[[asyncpg.Connection], Awaitable[_T]],
) -> _T:
    """Fuehrt `body(conn)` in einem temporaeren Schema aus und raeumt auf."""
    schema = f"phase21_{secrets.token_hex(6)}"
    conn = await asyncpg.connect(get_settings().database_url)
    try:
        await conn.execute(f'CREATE SCHEMA "{schema}"')
        await conn.execute(f'SET search_path TO "{schema}"')
        return await body(conn)
    finally:
        try:
            await conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        finally:
            await conn.close()


@pytest.mark.integration
def test_phase21_idempotent(tmp_path: Path) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")

    _copy_migrations(tmp_path, _ALL_MIGRATIONS)

    async def _run(conn: asyncpg.Connection) -> tuple[list[str], list[str]]:
        first = await apply_migrations(conn, tmp_path)
        second = await apply_migrations(conn, tmp_path)
        return first, second

    first, second = asyncio.run(_with_isolated_schema(_run))
    assert first == _ALL_MIGRATIONS
    assert second == []


@pytest.mark.integration
def test_phase21_tables_created(tmp_path: Path) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")

    _copy_migrations(tmp_path, _ALL_MIGRATIONS)

    async def _run(conn: asyncpg.Connection) -> set[str]:
        await apply_migrations(conn, tmp_path)
        rows = await conn.fetch(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = current_schema()"
        )
        return {row["table_name"] for row in rows}

    tables = asyncio.run(_with_isolated_schema(_run))
    expected = {
        "organization",
        "org_member",
        "workspace",
        "workspace_member",
        "status_history",
    }
    missing = expected - tables
    assert not missing, f"Fehlende Tabellen nach Migration: {sorted(missing)}"


@pytest.mark.integration
def test_phase21_status_invariant(tmp_path: Path) -> None:
    """Partial unique indices erzwingen max. 1 Active/Draft/Review pro Entity."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")

    _copy_migrations(tmp_path, _ALL_MIGRATIONS)

    async def _run(conn: asyncpg.Connection) -> None:
        await apply_migrations(conn, tmp_path)
        owner = uuid4()
        persona_id = uuid4()
        await conn.execute(
            "INSERT INTO persona (id, owner_id, name, current_version) "
            "VALUES ($1, $2, $3, 1)",
            persona_id,
            owner,
            "p",
        )
        # Erste aktive Version geht durch.
        await conn.execute(
            "INSERT INTO persona_version "
            "(persona_id, version, content, created_by, status) "
            "VALUES ($1, 1, '{}'::jsonb, $2, 'active')",
            persona_id,
            owner,
        )
        # Zweite aktive Version fuer dieselbe persona_id muss durch den
        # partial unique index abgewiesen werden.
        with pytest.raises(asyncpg.UniqueViolationError):
            await conn.execute(
                "INSERT INTO persona_version "
                "(persona_id, version, content, created_by, status) "
                "VALUES ($1, 2, '{}'::jsonb, $2, 'active')",
                persona_id,
                owner,
            )
        # Draft + Review sind separate Slots — ein Draft daneben geht.
        await conn.execute(
            "INSERT INTO persona_version "
            "(persona_id, version, content, created_by, status) "
            "VALUES ($1, 2, '{}'::jsonb, $2, 'draft')",
            persona_id,
            owner,
        )
        # Zweiter Draft jedoch nicht.
        with pytest.raises(asyncpg.UniqueViolationError):
            await conn.execute(
                "INSERT INTO persona_version "
                "(persona_id, version, content, created_by, status) "
                "VALUES ($1, 3, '{}'::jsonb, $2, 'draft')",
                persona_id,
                owner,
            )

    asyncio.run(_with_isolated_schema(_run))


@pytest.mark.integration
def test_phase21_status_backfill(tmp_path: Path) -> None:
    """0011 hebt current_version auf 'active', andere Versionen bleiben 'inactive'."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")

    async def _run(conn: asyncpg.Connection) -> dict[int, str]:
        _copy_migrations(tmp_path, _PRE_TENANT_MIGRATIONS)
        await apply_migrations(conn, tmp_path)

        owner = uuid4()
        persona_id = uuid4()
        await conn.execute(
            "INSERT INTO persona (id, owner_id, name, current_version) "
            "VALUES ($1, $2, 'p', 3)",
            persona_id,
            owner,
        )
        for version in (1, 2, 3):
            await conn.execute(
                "INSERT INTO persona_version "
                "(persona_id, version, content, created_by) "
                "VALUES ($1, $2, '{}'::jsonb, $3)",
                persona_id,
                version,
                owner,
            )

        _copy_migrations(tmp_path, _TENANT_MIGRATIONS)
        await apply_migrations(conn, tmp_path)

        rows = await conn.fetch(
            "SELECT version, status FROM persona_version "
            "WHERE persona_id = $1 ORDER BY version",
            persona_id,
        )
        return {row["version"]: row["status"] for row in rows}

    status_by_version = asyncio.run(_with_isolated_schema(_run))
    assert status_by_version == {1: "inactive", 2: "inactive", 3: "active"}


@pytest.mark.integration
def test_phase21_backfill_cardinality(tmp_path: Path) -> None:
    """Pro distinct owner_id genau eine Personal-Org/Workspace/Member-Triade."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")

    owners = [uuid4() for _ in range(3)]

    async def _run(conn: asyncpg.Connection) -> tuple[int, int, int, list[UUID | None]]:
        _copy_migrations(tmp_path, _PRE_TENANT_MIGRATIONS)
        await apply_migrations(conn, tmp_path)

        # Pre-Seed: drei distinct Owner ueber alle drei Quell-Tabellen verteilen.
        # Owner 0: persona + playbook + api_token.
        # Owner 1: nur persona.
        # Owner 2: nur api_token (kein persona/playbook).
        persona_ids = [uuid4(), uuid4()]
        await conn.execute(
            "INSERT INTO persona (id, owner_id, name) VALUES ($1, $2, 'p0')",
            persona_ids[0],
            owners[0],
        )
        await conn.execute(
            "INSERT INTO persona (id, owner_id, name) VALUES ($1, $2, 'p1')",
            persona_ids[1],
            owners[1],
        )
        await conn.execute(
            "INSERT INTO persona_version "
            "(persona_id, version, content, created_by) "
            "VALUES ($1, 1, '{}'::jsonb, $2)",
            persona_ids[0],
            owners[0],
        )
        await conn.execute(
            "INSERT INTO persona_version "
            "(persona_id, version, content, created_by) "
            "VALUES ($1, 1, '{}'::jsonb, $2)",
            persona_ids[1],
            owners[1],
        )
        await conn.execute(
            "INSERT INTO playbook (id, owner_id, name, type) "
            "VALUES ($1, $2, 'pb0', 'core')",
            uuid4(),
            owners[0],
        )
        await conn.execute(
            "INSERT INTO api_token (owner_id, name, token_hash) "
            "VALUES ($1, 't0', $2)",
            owners[0],
            secrets.token_hex(16),
        )
        await conn.execute(
            "INSERT INTO api_token (owner_id, name, token_hash) "
            "VALUES ($1, 't2', $2)",
            owners[2],
            secrets.token_hex(16),
        )

        _copy_migrations(tmp_path, _TENANT_MIGRATIONS)
        await apply_migrations(conn, tmp_path)

        org_count = await conn.fetchval(
            "SELECT count(*) FROM organization WHERE kind = 'personal'"
        )
        workspace_count = await conn.fetchval("SELECT count(*) FROM workspace")
        admin_count = await conn.fetchval(
            "SELECT count(*) FROM workspace_member WHERE role = 'admin'"
        )

        persona_workspace_ids = await conn.fetch(
            "SELECT workspace_id FROM persona ORDER BY name"
        )
        return (
            org_count,
            workspace_count,
            admin_count,
            [row["workspace_id"] for row in persona_workspace_ids],
        )

    org_count, ws_count, admin_count, persona_workspaces = asyncio.run(
        _with_isolated_schema(_run)
    )
    assert org_count == 3
    assert ws_count == 3
    assert admin_count == 3
    assert all(ws_id is not None for ws_id in persona_workspaces), (
        f"workspace_id darf nach Backfill nicht NULL sein, war: {persona_workspaces}"
    )


@pytest.mark.integration
def test_phase21_backfill_idempotent(tmp_path: Path) -> None:
    """0013 darf bei manuellem Re-Apply keine Duplikate erzeugen."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")

    _copy_migrations(tmp_path, _ALL_MIGRATIONS)

    async def _run(conn: asyncpg.Connection) -> tuple[int, int, int]:
        await apply_migrations(conn, tmp_path)
        owner = uuid4()
        await conn.execute(
            "INSERT INTO persona (id, owner_id, name) VALUES ($1, $2, 'p')",
            uuid4(),
            owner,
        )
        # 0013-Body manuell zweimal ausfuehren — schema_migrations ueberspringt
        # den File-Lauf, daher Re-Apply per Statement-Replay.
        sql = (MIGRATIONS_DIR / "0013_backfill_tenants.sql").read_text(
            encoding="utf-8"
        )
        await conn.execute(sql)
        await conn.execute(sql)
        org_count = await conn.fetchval(
            "SELECT count(*) FROM organization WHERE kind = 'personal'"
        )
        ws_count = await conn.fetchval("SELECT count(*) FROM workspace")
        member_count = await conn.fetchval(
            "SELECT count(*) FROM workspace_member WHERE user_id = $1",
            owner,
        )
        return org_count, ws_count, member_count

    org_count, ws_count, member_count = asyncio.run(_with_isolated_schema(_run))
    assert org_count == 1
    assert ws_count == 1
    assert member_count == 1
