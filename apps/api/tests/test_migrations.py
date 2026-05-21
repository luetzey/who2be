"""Integrationstest fuer den Migrations-Runner.

Belegt die Idempotenz (zweite Anwendung ist ein No-op). Laeuft nur mit
erreichbarer Datenbank; ohne DB wird der Test uebersprungen.
"""

import asyncio
from pathlib import Path

import asyncpg
import pytest

from who2be_api.core.config import get_settings
from who2be_api.core.migrations import apply_migrations

_SELFTEST_TABLE = "_w2b_migration_selftest"
_SELFTEST_FILE = "9001_runner_selftest.sql"


def _db_reachable() -> bool:
    async def _check() -> bool:
        try:
            conn = await asyncpg.connect(get_settings().database_url)
        except (asyncpg.PostgresError, OSError):
            return False
        await conn.close()
        return True

    return asyncio.run(_check())


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
            await conn.execute(
                "DELETE FROM schema_migrations WHERE version = $1", _SELFTEST_FILE
            )
            await conn.close()

    first, second = asyncio.run(_run())
    assert first == [_SELFTEST_FILE]
    assert second == []
