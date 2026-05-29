"""Integrationstests fuer die Phase-2.3-0-Migrations (0017-0018).

Belegt:
- Idempotenz der gesamten Migration-Kette inkl. 0017/0018 (zweiter Apply
  ueber den Runner ist No-op, manuelles Statement-Replay der neuen Files ist
  ebenfalls ein No-op dank IF NOT EXISTS).
- Anlage von `workspace_invitation` + partial unique Index "max. eine offene
  Invitation je (Workspace, Mail)".
- `api_token.role` existiert mit DEFAULT 'admin' (Bestands-Token bleiben
  funktional admin) und CHECK auf {admin, editor, viewer}.

Pro Test wird ein dediziertes Postgres-Schema angelegt; die `public`-Schema
bleibt unangetastet (siehe test_phase21_migrations.py fuer dasselbe Muster).
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

_ALL_MIGRATIONS = sorted(p.name for p in MIGRATIONS_DIR.glob("[0-9]*.sql"))
_NEW_MIGRATIONS = ["0017_workspace_invitation.sql", "0018_api_token_role_snapshot.sql"]


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
    schema = f"phase23_{secrets.token_hex(6)}"
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
def test_phase23_idempotent(tmp_path: Path) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")

    _copy_migrations(tmp_path, _ALL_MIGRATIONS)

    async def _run(conn: asyncpg.Connection) -> tuple[list[str], list[str]]:
        first = await apply_migrations(conn, tmp_path)
        second = await apply_migrations(conn, tmp_path)
        # Manuelles Statement-Replay der neuen Files muss ebenfalls No-op sein.
        for name in _NEW_MIGRATIONS:
            sql = (MIGRATIONS_DIR / name).read_text(encoding="utf-8")
            await conn.execute(sql)
        return first, second

    first, second = asyncio.run(_with_isolated_schema(_run))
    assert first == _ALL_MIGRATIONS
    assert second == []


@pytest.mark.integration
def test_phase23_invitation_open_uniq(tmp_path: Path) -> None:
    """Max. eine offene Invitation je (Workspace, Mail); akzeptierte/widerrufene
    blockieren eine neue nicht."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")

    _copy_migrations(tmp_path, _ALL_MIGRATIONS)

    async def _run(conn: asyncpg.Connection) -> None:
        await apply_migrations(conn, tmp_path)

        org_id = await conn.fetchval(
            "INSERT INTO organization (name, slug, kind) VALUES ('o', 's', 'company') RETURNING id"
        )
        ws_id = await conn.fetchval(
            "INSERT INTO workspace (org_id, name, slug) VALUES ($1, 'w', 'w') RETURNING id",
            org_id,
        )
        creator = uuid4()

        async def _invite(email: str) -> None:
            await conn.execute(
                "INSERT INTO workspace_invitation "
                "(workspace_id, email, role, token_hash, expires_at, created_by) "
                "VALUES ($1, $2, 'editor', $3, now() + interval '7 days', $4)",
                ws_id,
                email,
                secrets.token_hex(16),
                creator,
            )

        await _invite("a@example.com")
        # Zweite offene Invitation (case-insensitive) muss abgewiesen werden.
        with pytest.raises(asyncpg.UniqueViolationError):
            await _invite("A@example.com")

        # Erste widerrufen -> eine neue offene ist wieder erlaubt.
        await conn.execute(
            "UPDATE workspace_invitation SET revoked_at = now() "
            "WHERE workspace_id = $1 AND lower(email) = 'a@example.com'",
            ws_id,
        )
        await _invite("a@example.com")

    asyncio.run(_with_isolated_schema(_run))


@pytest.mark.integration
def test_phase23_api_token_role_default(tmp_path: Path) -> None:
    """Neue api_token-Rows ohne explizite Rolle landen auf 'admin'; CHECK greift."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")

    _copy_migrations(tmp_path, _ALL_MIGRATIONS)

    async def _run(conn: asyncpg.Connection) -> str:
        await apply_migrations(conn, tmp_path)

        org_id = await conn.fetchval(
            "INSERT INTO organization (name, slug, kind) VALUES ('o', 's', 'company') RETURNING id"
        )
        ws_id = await conn.fetchval(
            "INSERT INTO workspace (org_id, name, slug) VALUES ($1, 'w', 'w') RETURNING id",
            org_id,
        )
        role: str = await conn.fetchval(
            "INSERT INTO api_token (workspace_id, owner_id, name, token_hash) "
            "VALUES ($1, $2, 't', $3) RETURNING role",
            ws_id,
            uuid4(),
            secrets.token_hex(16),
        )
        # Ungueltige Rolle muss vom CHECK abgewiesen werden.
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute(
                "INSERT INTO api_token (workspace_id, owner_id, name, token_hash, role) "
                "VALUES ($1, $2, 't2', $3, 'superuser')",
                ws_id,
                uuid4(),
                secrets.token_hex(16),
            )
        return role

    role = asyncio.run(_with_isolated_schema(_run))
    assert role == "admin"
