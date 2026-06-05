"""Integrationstests fuer Migration 0043 — Entitlement-Schreibquellen (ADR-0028).

Belegt die beiden CHECK-Constraints auf `org_entitlement`:
- `source` ist auf die geschlossene Taxonomie begrenzt (fremder String → Fehler);
- `manual_override` ist Pflicht-befristet + auditiert (ohne `expires_at`/
  `created_by` → Fehler).

Laeuft in einem isolierten Schema (gleiches Muster wie `test_migrations.py`),
nur mit erreichbarer DB; sonst uebersprungen.
"""

from __future__ import annotations

import asyncio
import secrets
from collections.abc import Awaitable, Callable
from typing import TypeVar
from uuid import uuid4

import asyncpg
import pytest

from who2be_api.core.config import get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations

_T = TypeVar("_T")

# Migrationen bis einschliesslich 0043 — die Taxonomie-Constraints kommen dort an.
_MIGRATIONS = sorted(p.name for p in MIGRATIONS_DIR.glob("[0-9]*.sql"))


def _db_reachable() -> bool:
    async def _check() -> bool:
        try:
            conn = await asyncpg.connect(get_settings().database_url)
        except (asyncpg.PostgresError, OSError):
            return False
        await conn.close()
        return True

    return asyncio.run(_check())


async def _with_isolated_schema(
    body: Callable[[asyncpg.Connection], Awaitable[_T]],
) -> _T:
    schema = f"ent_src_{secrets.token_hex(6)}"
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


async def _seed_org(conn: asyncpg.Connection) -> object:
    return await conn.fetchval(
        "INSERT INTO organization (name, slug, kind) VALUES ('o', $1, 'company') RETURNING id",
        f"o-{secrets.token_hex(4)}",
    )


@pytest.mark.integration
def test_source_check_rejects_unknown_value() -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")

    async def _run(conn: asyncpg.Connection) -> None:
        await apply_migrations(conn, MIGRATIONS_DIR)
        org_id = await _seed_org(conn)
        with pytest.raises(asyncpg.IntegrityConstraintViolationError):
            await conn.execute(
                "INSERT INTO org_entitlement (org_id, source) VALUES ($1, 'hacked')",
                org_id,
            )

    asyncio.run(_with_isolated_schema(_run))


@pytest.mark.integration
def test_known_sources_accepted() -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")

    async def _run(conn: asyncpg.Connection) -> None:
        await apply_migrations(conn, MIGRATIONS_DIR)
        for source in ("mollie", "cloud", "signed_license"):
            org_id = await _seed_org(conn)
            await conn.execute(
                "INSERT INTO org_entitlement (org_id, source) VALUES ($1, $2)",
                org_id,
                source,
            )

    asyncio.run(_with_isolated_schema(_run))


@pytest.mark.integration
def test_manual_override_requires_expiry_and_author() -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")

    async def _run(conn: asyncpg.Connection) -> None:
        await apply_migrations(conn, MIGRATIONS_DIR)

        # Ohne expires_at/created_by ist manual_override unzulaessig.
        org_a = await _seed_org(conn)
        with pytest.raises(asyncpg.IntegrityConstraintViolationError):
            await conn.execute(
                "INSERT INTO org_entitlement (org_id, source) VALUES ($1, 'manual_override')",
                org_a,
            )

        # Mit beiden Pflichtfeldern ist er gueltig.
        org_b = await _seed_org(conn)
        await conn.execute(
            "INSERT INTO org_entitlement "
            "(org_id, source, expires_at, created_by, reason) "
            "VALUES ($1, 'manual_override', now() + interval '30 days', $2, 'Kulanz')",
            org_b,
            uuid4(),
        )

    asyncio.run(_with_isolated_schema(_run))
