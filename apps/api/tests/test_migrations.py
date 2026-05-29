"""Integrationstest fuer den Migrations-Runner.

Belegt die Idempotenz (zweite Anwendung ist ein No-op). Laeuft nur mit
erreichbarer Datenbank; ohne DB wird der Test uebersprungen.

Phase 3-0 ergaenzt drei integration-markierte Tests fuer die Migrations
`0019_status_default_draft.sql` (Default + Backfill) und
`0020_playbook_type_check.sql` (CHECK + Backfill). Sie laufen in isolierten
Postgres-Schemas, damit die `public`-Schema und parallele Integration-Tests
unangetastet bleiben (gleiches Muster wie `test_phase21_migrations.py` /
`test_phase23_migrations.py`).
"""

import asyncio
import secrets
import shutil
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TypeVar
from uuid import uuid4

import asyncpg
import pytest

from who2be_api.core.config import get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations

_T = TypeVar("_T")

_SELFTEST_TABLE = "_w2b_migration_selftest"
_SELFTEST_FILE = "9001_runner_selftest.sql"

_CORE_TABLES = (
    "api_token",
    "persona",
    "persona_version",
    "playbook",
    "playbook_version",
    "persona_playbook",
)

_ALL_MIGRATIONS = sorted(p.name for p in MIGRATIONS_DIR.glob("[0-9]*.sql"))
_PHASE3_MIGRATIONS = [
    "0019_status_default_draft.sql",
    "0020_playbook_type_check.sql",
]
_PRE_PHASE3_MIGRATIONS = [m for m in _ALL_MIGRATIONS if m not in _PHASE3_MIGRATIONS]


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


async def _with_isolated_schema(
    body: Callable[[asyncpg.Connection], Awaitable[_T]],
) -> _T:
    """Fuehrt `body(conn)` in einem temporaeren Schema aus und raeumt auf."""
    schema = f"phase3_{secrets.token_hex(6)}"
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
def test_migrations_apply_is_idempotent(tmp_path: Path) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")

    (tmp_path / _SELFTEST_FILE).write_text(
        f"CREATE TABLE IF NOT EXISTS {_SELFTEST_TABLE} (id int);",
        encoding="utf-8",
    )

    async def _run() -> tuple[list[str], list[str]]:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            first = await apply_migrations(conn, tmp_path)
            second = await apply_migrations(conn, tmp_path)
            return first, second
        finally:
            await conn.execute(f"DROP TABLE IF EXISTS {_SELFTEST_TABLE};")
            await conn.execute("DELETE FROM schema_migrations WHERE version = $1", _SELFTEST_FILE)
            await conn.close()

    first, second = asyncio.run(_run())
    assert first == [_SELFTEST_FILE]
    assert second == []


@pytest.mark.integration
def test_core_migrations_create_all_tables() -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")

    async def _run() -> set[str]:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await apply_migrations(conn, MIGRATIONS_DIR)
            rows = await conn.fetch(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
            )
        finally:
            await conn.close()
        return {row["table_name"] for row in rows}

    tables = asyncio.run(_run())
    missing = set(_CORE_TABLES) - tables
    assert not missing, f"Fehlende Tabellen nach Migration: {sorted(missing)}"


# --- Phase 3-0 --------------------------------------------------------------


@pytest.mark.integration
def test_phase30_idempotent(tmp_path: Path) -> None:
    """Alle Migrations + Statement-Replay der Phase-3-0-Files ist No-op."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")

    _copy_migrations(tmp_path, _ALL_MIGRATIONS)

    async def _run(conn: asyncpg.Connection) -> tuple[list[str], list[str]]:
        first = await apply_migrations(conn, tmp_path)
        second = await apply_migrations(conn, tmp_path)
        # Manuelles Statement-Replay der neuen Files muss ebenfalls No-op sein.
        for name in _PHASE3_MIGRATIONS:
            sql = (MIGRATIONS_DIR / name).read_text(encoding="utf-8")
            await conn.execute(sql)
        return first, second

    first, second = asyncio.run(_with_isolated_schema(_run))
    assert first == _ALL_MIGRATIONS
    assert second == []


@pytest.mark.integration
def test_phase30_status_default_and_backfill(tmp_path: Path) -> None:
    """Backfill hebt current_version-Rows ohne Active-Schwester auf 'draft';
    Neu-Insert ohne explizites status faellt auf den neuen Default 'draft'."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")

    async def _run(conn: asyncpg.Connection) -> dict[str, str]:
        # 1) Pre-Phase-3-Stand herstellen: bis einschliesslich 0018 anwenden.
        _copy_migrations(tmp_path, _PRE_PHASE3_MIGRATIONS)
        await apply_migrations(conn, tmp_path)

        # Personal-Tenant fuer FK-Pflicht.
        org_id = await conn.fetchval(
            "INSERT INTO organization (name, slug, kind) VALUES ('o', 'o', 'company') RETURNING id"
        )
        ws_id = await conn.fetchval(
            "INSERT INTO workspace (org_id, name, slug) VALUES ($1, 'w', 'w') RETURNING id",
            org_id,
        )
        owner = uuid4()

        # Persona mit stuck-inactive current_version (kein Active-, kein
        # Draft-Geschwister) — Ziel des Backfills.
        stuck_id = uuid4()
        await conn.execute(
            "INSERT INTO persona (id, workspace_id, owner_id, name, current_version) "
            "VALUES ($1, $2, $3, 'stuck', 1)",
            stuck_id,
            ws_id,
            owner,
        )
        await conn.execute(
            "INSERT INTO persona_version "
            "(persona_id, version, content, status, created_by) "
            "VALUES ($1, 1, '{}'::jsonb, 'inactive', $2)",
            stuck_id,
            owner,
        )

        # Persona mit Active-Schwester — Backfill darf hier NICHT eingreifen.
        skip_id = uuid4()
        await conn.execute(
            "INSERT INTO persona (id, workspace_id, owner_id, name, current_version) "
            "VALUES ($1, $2, $3, 'skip', 2)",
            skip_id,
            ws_id,
            owner,
        )
        await conn.execute(
            "INSERT INTO persona_version "
            "(persona_id, version, content, status, created_by) "
            "VALUES ($1, 1, '{}'::jsonb, 'active', $2)",
            skip_id,
            owner,
        )
        await conn.execute(
            "INSERT INTO persona_version "
            "(persona_id, version, content, status, created_by) "
            "VALUES ($1, 2, '{}'::jsonb, 'inactive', $2)",
            skip_id,
            owner,
        )

        # 2) Phase-3-Migration anwenden.
        _copy_migrations(tmp_path, _PHASE3_MIGRATIONS)
        await apply_migrations(conn, tmp_path)

        # Status nach Backfill.
        stuck_status = await conn.fetchval(
            "SELECT status FROM persona_version WHERE persona_id = $1",
            stuck_id,
        )
        skip_current_status = await conn.fetchval(
            "SELECT status FROM persona_version WHERE persona_id = $1 AND version = 2",
            skip_id,
        )

        # 3) Neu-Insert ohne status nutzt den neuen Default 'draft'.
        fresh_id = uuid4()
        await conn.execute(
            "INSERT INTO persona (id, workspace_id, owner_id, name) VALUES ($1, $2, $3, 'fresh')",
            fresh_id,
            ws_id,
            owner,
        )
        fresh_status = await conn.fetchval(
            "INSERT INTO persona_version "
            "(persona_id, version, content, created_by) "
            "VALUES ($1, 1, '{}'::jsonb, $2) RETURNING status",
            fresh_id,
            owner,
        )

        return {
            "stuck": stuck_status,
            "skip_current": skip_current_status,
            "fresh": fresh_status,
        }

    statuses = asyncio.run(_with_isolated_schema(_run))
    assert statuses["stuck"] == "draft"
    # Active-Schwester war vorhanden -> Backfill ueberspringt diese Persona.
    assert statuses["skip_current"] == "inactive"
    assert statuses["fresh"] == "draft"


@pytest.mark.integration
def test_phase30_playbook_type_check(tmp_path: Path) -> None:
    """Backfill mapped unbekannte Typen auf 'prompt'; CHECK weist neue
    ungueltige Werte ab; gueltige Werte gehen durch."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")

    async def _run(conn: asyncpg.Connection) -> dict[str, str]:
        _copy_migrations(tmp_path, _PRE_PHASE3_MIGRATIONS)
        await apply_migrations(conn, tmp_path)

        org_id = await conn.fetchval(
            "INSERT INTO organization (name, slug, kind) VALUES ('o', 'o', 'company') RETURNING id"
        )
        ws_id = await conn.fetchval(
            "INSERT INTO workspace (org_id, name, slug) VALUES ($1, 'w', 'w') RETURNING id",
            org_id,
        )
        owner = uuid4()

        legacy_id = uuid4()
        await conn.execute(
            "INSERT INTO playbook (id, workspace_id, owner_id, name, type) "
            "VALUES ($1, $2, $3, 'legacy', 'core')",
            legacy_id,
            ws_id,
            owner,
        )

        _copy_migrations(tmp_path, _PHASE3_MIGRATIONS)
        await apply_migrations(conn, tmp_path)

        legacy_type = await conn.fetchval("SELECT type FROM playbook WHERE id = $1", legacy_id)

        # Gueltiger Wert geht durch.
        await conn.execute(
            "INSERT INTO playbook (workspace_id, owner_id, name, type) "
            "VALUES ($1, $2, 'ok', 'workflow')",
            ws_id,
            owner,
        )

        # Ungueltiger Wert wird abgewiesen.
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute(
                "INSERT INTO playbook (workspace_id, owner_id, name, type) "
                "VALUES ($1, $2, 'bad', 'banana')",
                ws_id,
                owner,
            )

        return {"legacy": legacy_type}

    types = asyncio.run(_with_isolated_schema(_run))
    assert types["legacy"] == "prompt"
