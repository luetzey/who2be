"""Integrationstest fuer die Append-only-Erzwingung (WP-A, Migrationen 0044/0045).

Beweist:
- Als Laufzeitrolle `who2be_app` (NOBYPASSRLS) sind `status_history`,
  `audit_log` und `entitlement_history` append-only: INSERT geht, UPDATE/DELETE
  schlaegt mit `InsufficientPrivilege` fehl.
- Als Owner sind UPDATE und DELETE weiterhin erlaubt (wird vom DSGVO-Purge in
  WP-D fuer die Anonymisierung gebraucht).

Laeuft in einem isolierten Schema wie `test_rls_isolation.py`. Die Rolle
`who2be_app` ist cluster-global; die Migrationen 0036/0044/0045 legen sie und
ihre Grants idempotent an. Hier wird ihr nur ein Test-Passwort gesetzt.
"""

from __future__ import annotations

import asyncio
import secrets
from uuid import uuid4

import asyncpg
import pytest

from who2be_api.core.config import get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations

# Test-only Passwort fuer die App-Rolle (kein Injection-Vektor; per format()
# in ALTER ROLE eingesetzt).
_APP_PASSWORD = "audit_test_secret"  # noqa: S105 — Test-Fixture, kein echtes Secret


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
def test_append_only_for_app_role_and_owner_full_access() -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")

    settings = get_settings()
    schema = f"audit_{secrets.token_hex(6)}"

    async def _run() -> None:
        owner = await asyncpg.connect(settings.database_url)
        app: asyncpg.Connection | None = None
        try:
            await owner.execute(f'CREATE SCHEMA "{schema}"')
            await owner.execute(f'SET search_path TO "{schema}"')
            await apply_migrations(owner, MIGRATIONS_DIR)

            # Seed: Org + Workspace + eine status_history-Zeile + eine
            # entitlement_history-Zeile (als Owner — RLS-Bypass).
            org_id = await owner.fetchval(
                "INSERT INTO organization (name, slug, kind) "
                "VALUES ('o', $1, 'company') RETURNING id",
                f"o-{secrets.token_hex(4)}",
            )
            ws_id = await owner.fetchval(
                "INSERT INTO workspace (org_id, name, slug) VALUES ($1, 'w', 'w') RETURNING id",
                org_id,
            )
            entity_id = uuid4()
            actor = uuid4()
            sh_id = await owner.fetchval(
                "INSERT INTO status_history "
                "(entity_type, entity_id, from_status, to_status, changed_by) "
                "VALUES ('persona', $1, NULL, 'draft', $2) RETURNING id",
                entity_id,
                actor,
            )
            al_id = await owner.fetchval(
                "INSERT INTO audit_log (org_id, workspace_id, actor_id, action, target) "
                "VALUES ($1, $2, $3, 'member.role_changed', $4) RETURNING id",
                org_id,
                ws_id,
                actor,
                str(uuid4()),
            )
            eh_id = await owner.fetchval(
                "INSERT INTO entitlement_history (org_id, status, source) "
                "VALUES ($1, 'active', 'cloud') RETURNING id",
                org_id,
            )

            # Test-Passwort fuer die App-Rolle.
            await owner.execute(f"ALTER ROLE who2be_app WITH PASSWORD '{_APP_PASSWORD}'")

            app = await asyncpg.connect(
                settings.database_url, user="who2be_app", password=_APP_PASSWORD
            )
            await app.execute(f'SET search_path TO "{schema}"')
            await app.execute("SELECT set_config('app.current_org', $1, false)", str(org_id))
            await app.execute("SELECT set_config('app.current_tenant', $1, false)", str(ws_id))

            # --- Als who2be_app: INSERT erlaubt. ---
            await app.execute(
                "INSERT INTO status_history "
                "(entity_type, entity_id, from_status, to_status, changed_by) "
                "VALUES ('persona', $1, 'draft', 'review', $2)",
                entity_id,
                actor,
            )
            await app.execute(
                "INSERT INTO audit_log (org_id, workspace_id, actor_id, action) "
                "VALUES ($1, $2, $3, 'token.issued')",
                org_id,
                ws_id,
                actor,
            )
            await app.execute(
                "INSERT INTO entitlement_history (org_id, status, source) "
                "VALUES ($1, 'active', 'mollie')",
                org_id,
            )

            # --- Als who2be_app: UPDATE/DELETE auf allen drei Journalen verboten. ---
            for table in ("status_history", "audit_log", "entitlement_history"):
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    await app.execute(f"UPDATE {table} SET id = id")
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    await app.execute(f"DELETE FROM {table}")

            # --- Als Owner: UPDATE/DELETE weiter erlaubt (Erasure-Anonymisierung). ---
            await owner.execute(
                "UPDATE status_history SET changed_by = $1 WHERE id = $2",
                uuid4(),
                sh_id,
            )
            await owner.execute(
                "UPDATE audit_log SET actor_id = $1 WHERE id = $2",
                uuid4(),
                al_id,
            )
            # entitlement_history Owner-DELETE existiert technisch — die
            # GoBD-Aufbewahrung wird nicht via REVOKE, sondern via Policy
            # (Purge fasst die Tabelle nicht an, WP-D) sichergestellt.
            await owner.execute("DELETE FROM entitlement_history WHERE id = $1", eh_id)
        finally:
            if app is not None:
                await app.close()
            await owner.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            await owner.close()

    asyncio.run(_run())
