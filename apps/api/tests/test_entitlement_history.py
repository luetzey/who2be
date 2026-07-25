"""Integrationstest fuer das Entitlement-Journal (WP-C, Migration 0045).

Beweist die GoBD-Lueckenlosigkeit: drei aufeinanderfolgende `upsert`-Calls
(free → pro → manual_override) auf `org_entitlement` schreiben genau drei
Zeilen in `entitlement_history` in zeitlicher Reihenfolge — der UPSERT
(aktueller Stand) und der Journal-Insert laufen atomar in derselben
Transaktion (ADR-0031).

Laeuft in einem isolierten Schema (gleiches Muster wie
`test_entitlement_write_sources.py`); ohne DB uebersprungen.
"""

from __future__ import annotations

import asyncio
import secrets
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import TypeVar
from uuid import uuid4

import asyncpg
import pytest

from who2be_api.core.config import get_settings
from who2be_api.core.db import init_connection
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.licensing.entitlement import Entitlement, Feature
from who2be_api.repositories.entitlement_repository import PgEntitlementRepository

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


async def _with_isolated_schema(
    body: Callable[[asyncpg.Pool, asyncpg.Connection], Awaitable[_T]],
) -> _T:
    settings = get_settings()
    schema = f"ent_hist_{secrets.token_hex(6)}"
    owner = await asyncpg.connect(settings.database_url)
    pool: asyncpg.Pool | None = None
    try:
        await owner.execute(f'CREATE SCHEMA "{schema}"')
        await owner.execute(f'SET search_path TO "{schema}"')
        await apply_migrations(owner, MIGRATIONS_DIR)
        pool = await asyncpg.create_pool(
            settings.database_url,
            # Codec wie der Prod-Pool (core/db.init_connection) — sonst kann
            # asyncpg keine `list`-Argumente in `jsonb`-Spalten binden.
            init=init_connection,
            min_size=1,
            max_size=2,
            server_settings={"search_path": schema},
        )
        return await body(pool, owner)
    finally:
        if pool is not None:
            await pool.close()
        try:
            await owner.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        finally:
            await owner.close()


@pytest.mark.integration
def test_upsert_writes_exactly_one_history_row_per_call() -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")

    async def _run(pool: asyncpg.Pool, owner: asyncpg.Connection) -> None:
        org_id = await owner.fetchval(
            "INSERT INTO organization (name, slug, kind) VALUES ('o', $1, 'company') RETURNING id",
            f"o-{secrets.token_hex(4)}",
        )
        repo = PgEntitlementRepository(pool)
        expires = datetime.now(UTC) + timedelta(days=30)

        # 1) free
        free = Entitlement(status="active", features=frozenset({Feature.CORE}))
        await repo.upsert(org_id, free, source="cloud", external_ref=None)

        # 2) pro (Upgrade)
        pro = Entitlement(
            status="active",
            features=frozenset({Feature.CORE, Feature.AGENTS}),
            expires_at=expires,
        )
        await repo.upsert(org_id, pro, source="mollie", external_ref="sub_123")

        # 3) manual_override (Kulanz/Ops)
        override = Entitlement(
            status="active",
            features=frozenset({Feature.CORE, Feature.AGENTS, Feature.SSO}),
            expires_at=expires,
        )
        await repo.upsert(
            org_id,
            override,
            source="manual_override",
            external_ref=None,
            created_by=uuid4(),
            reason="Kulanz Q2",
        )

        rows = await owner.fetch(
            "SELECT source, status, recorded_at FROM entitlement_history "
            "WHERE org_id = $1 ORDER BY recorded_at ASC, source ASC",
            org_id,
        )
        sources = [row["source"] for row in rows]
        assert sources == ["cloud", "mollie", "manual_override"]
        assert all(row["status"] == "active" for row in rows)

        # SSoT zeigt nur den letzten Stand.
        current_source = await owner.fetchval(
            "SELECT source FROM org_entitlement WHERE org_id = $1",
            org_id,
        )
        assert current_source == "manual_override"

    asyncio.run(_with_isolated_schema(_run))


@pytest.mark.integration
def test_history_survives_org_delete() -> None:
    """`entitlement_history.org_id` ist KEINE FK-Referenz — der Org-Hard-Purge
    (CASCADE-Delete der ganzen Hierarchie) loescht das Journal NICHT mit
    (GoBD-Aufbewahrung, ADR-0031)."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")

    async def _run(pool: asyncpg.Pool, owner: asyncpg.Connection) -> None:
        org_id = await owner.fetchval(
            "INSERT INTO organization (name, slug, kind) VALUES ('o', $1, 'company') RETURNING id",
            f"o-{secrets.token_hex(4)}",
        )
        repo = PgEntitlementRepository(pool)
        await repo.upsert(
            org_id,
            Entitlement(status="active", features=frozenset({Feature.CORE})),
            source="cloud",
            external_ref=None,
        )

        # Org-Hard-Purge bleibt moeglich; Journal bleibt erhalten.
        await owner.execute("DELETE FROM organization WHERE id = $1", org_id)
        remaining = await owner.fetchval(
            "SELECT count(*) FROM entitlement_history WHERE org_id = $1",
            org_id,
        )
        assert remaining == 1

    asyncio.run(_with_isolated_schema(_run))
