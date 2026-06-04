"""Integrationstest fuer die Dev-CLI `who2be-set-entitlement` (`core/set_entitlement.py`).

Belegt: `free` / `pro` schreiben den Plan-Default aus `licensing/plans.py`,
`--quota` / `--rate` ueberschreiben die Defaults, und ein zweiter Lauf mit den
gleichen Argumenten ist idempotent (ON CONFLICT … UPDATE). Laeuft in einem
isolierten Postgres-Schema (wie `test_migrations.py`), damit `public` und
parallele Integrationstests unangetastet bleiben; ohne erreichbare DB wird der
Test uebersprungen.
"""

from __future__ import annotations

import asyncio
import json
import secrets
from collections.abc import Awaitable, Callable
from typing import TypeVar, cast
from uuid import UUID

import asyncpg
import pytest

from who2be_api.core.config import get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.core.set_entitlement import set_entitlement
from who2be_api.licensing.plans import FREE_PLAN, PRO_PLAN
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
    body: Callable[[asyncpg.Connection], Awaitable[_T]],
) -> _T:
    schema = f"setent_{secrets.token_hex(6)}"
    conn = await asyncpg.connect(get_settings().database_url)
    try:
        # jsonb-Codec, damit der Repo `features` als Liste schreiben kann
        # (gleicher Setup wie der Laufzeit-Pool, `core/db.py:_init_connection`).
        await conn.set_type_codec(
            "jsonb",
            encoder=json.dumps,
            decoder=json.loads,
            schema="pg_catalog",
        )
        await conn.execute(f'CREATE SCHEMA "{schema}"')
        await conn.execute(f'SET search_path TO "{schema}"')
        await apply_migrations(conn, MIGRATIONS_DIR)
        return await body(conn)
    finally:
        try:
            await conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        finally:
            await conn.close()


async def _new_org(conn: asyncpg.Connection) -> UUID:
    return cast(
        UUID,
        await conn.fetchval(
            "INSERT INTO organization (name, slug, kind) "
            "VALUES ($1, $1, 'company') RETURNING id",
            f"setent-{secrets.token_hex(4)}",
        ),
    )


@pytest.mark.integration
def test_set_entitlement_free_writes_plan_defaults() -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")

    async def _run(conn: asyncpg.Connection) -> asyncpg.Record:
        org_id = await _new_org(conn)
        await set_entitlement(
            PgEntitlementRepository(conn),
            org_id=org_id,
            plan_code="free",
            quota=None,
            rate=None,
        )
        row = await conn.fetchrow(
            "SELECT status, features, mcp_monthly_quota, mcp_rate_per_min, source, external_ref "
            "FROM org_entitlement WHERE org_id = $1",
            org_id,
        )
        assert row is not None
        return row

    row = asyncio.run(_with_isolated_schema(_run))
    assert row["status"] == "active"
    assert set(row["features"]) == set(FREE_PLAN.features)
    assert row["mcp_monthly_quota"] == FREE_PLAN.mcp_monthly_quota
    assert row["mcp_rate_per_min"] == FREE_PLAN.mcp_rate_per_min
    assert row["source"] == "manual"
    assert row["external_ref"] is None


@pytest.mark.integration
def test_set_entitlement_pro_writes_plan_defaults() -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")

    async def _run(conn: asyncpg.Connection) -> asyncpg.Record:
        org_id = await _new_org(conn)
        await set_entitlement(
            PgEntitlementRepository(conn),
            org_id=org_id,
            plan_code="pro",
            quota=None,
            rate=None,
        )
        row = await conn.fetchrow(
            "SELECT features, mcp_monthly_quota, mcp_rate_per_min, source "
            "FROM org_entitlement WHERE org_id = $1",
            org_id,
        )
        assert row is not None
        return row

    row = asyncio.run(_with_isolated_schema(_run))
    assert set(row["features"]) == set(PRO_PLAN.features)
    assert row["mcp_monthly_quota"] == PRO_PLAN.mcp_monthly_quota
    assert row["mcp_rate_per_min"] == PRO_PLAN.mcp_rate_per_min
    assert row["source"] == "manual"


@pytest.mark.integration
def test_set_entitlement_quota_and_rate_override_plan_defaults() -> None:
    """`--quota 2 --rate 5` haelt den Pro-Featureset, druckt die Limits aber runter.

    Genau das Muster aus `docs/cloud-local-smoke.md`, um den 429 schnell zu
    provozieren, ohne 1.000 Reads zu machen.
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")

    async def _run(conn: asyncpg.Connection) -> asyncpg.Record:
        org_id = await _new_org(conn)
        await set_entitlement(
            PgEntitlementRepository(conn),
            org_id=org_id,
            plan_code="pro",
            quota=2,
            rate=5,
        )
        row = await conn.fetchrow(
            "SELECT features, mcp_monthly_quota, mcp_rate_per_min "
            "FROM org_entitlement WHERE org_id = $1",
            org_id,
        )
        assert row is not None
        return row

    row = asyncio.run(_with_isolated_schema(_run))
    # Features bleiben Pro; nur die Limits sind ueberschrieben.
    assert set(row["features"]) == set(PRO_PLAN.features)
    assert row["mcp_monthly_quota"] == 2
    assert row["mcp_rate_per_min"] == 5


@pytest.mark.integration
def test_set_entitlement_is_idempotent_on_rerun() -> None:
    """Zweimal `pro` setzen ist No-op-aequivalent (ON CONFLICT … UPDATE)."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")

    async def _run(conn: asyncpg.Connection) -> tuple[int, asyncpg.Record]:
        org_id = await _new_org(conn)
        repo = PgEntitlementRepository(conn)
        await set_entitlement(
            repo, org_id=org_id, plan_code="pro", quota=None, rate=None
        )
        await set_entitlement(
            repo, org_id=org_id, plan_code="pro", quota=None, rate=None
        )
        count = await conn.fetchval(
            "SELECT count(*) FROM org_entitlement WHERE org_id = $1", org_id
        )
        row = await conn.fetchrow(
            "SELECT mcp_monthly_quota, mcp_rate_per_min FROM org_entitlement WHERE org_id = $1",
            org_id,
        )
        assert row is not None
        return count, row

    count, row = asyncio.run(_with_isolated_schema(_run))
    # Eine Zeile, Pro-Defaults stehen.
    assert count == 1
    assert row["mcp_monthly_quota"] == PRO_PLAN.mcp_monthly_quota
    assert row["mcp_rate_per_min"] == PRO_PLAN.mcp_rate_per_min


def test_set_entitlement_unknown_plan_raises() -> None:
    """Unbekannter Plan-Code ist ein ValueError — keine DB noetig."""

    class _NoopRepo:
        async def fetch(self, _org_id: UUID):  # type: ignore[no-untyped-def]
            return None

        async def upsert(  # type: ignore[no-untyped-def]
            self, _org_id, _entitlement, *, source, external_ref
        ):
            raise AssertionError("upsert sollte nicht aufgerufen werden")

    with pytest.raises(ValueError, match="Unbekannter Plan-Code"):
        asyncio.run(
            set_entitlement(
                _NoopRepo(),  # type: ignore[arg-type]
                org_id=UUID("11111111-1111-1111-1111-111111111111"),
                plan_code="enterprise",
                quota=None,
                rate=None,
            )
        )
