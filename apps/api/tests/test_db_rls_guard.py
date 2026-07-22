"""Integrationstest fuer den Cloud-RLS-Guard beim Pool-Aufbau (Security-Review
INFO-2, core/db.py `_assert_rls_enforced`).

Beweist: Ist `APP_DATABASE_URL` gesetzt (Cloud), MUSS der App-Pool als
nicht-privilegierte Rolle verbinden — verbindet er als RLS-umgehende Rolle
(Superuser/rolbypassrls), schlaegt der Boot fail-loud fehl. On-Prem (kein
`APP_DATABASE_URL`, Owner-Verbindung mit RLS-Bypass) ist bewusst ausgenommen.

Laeuft nur mit erreichbarer DB; die Owner-URL (`DATABASE_URL`) ist im Testlauf
eine Superuser-Verbindung und dient hier als „RLS-umgehende Rolle".
"""

import asyncio

import asyncpg
import pytest

from who2be_api.core import db
from who2be_api.core.config import Settings, get_settings


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
def test_rls_guard_rejects_bypass_role_in_cloud(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")

    # APP_DATABASE_URL gesetzt (= Cloud-Signal), zeigt aber auf die Owner-/
    # Superuser-Verbindung → der Guard muss den Boot abbrechen.
    owner_url = get_settings().database_url
    monkeypatch.setattr(db, "get_settings", lambda: Settings(app_database_url=owner_url))

    database = db.Database()
    with pytest.raises(RuntimeError, match="Row Level Security"):
        asyncio.run(database.connect())


@pytest.mark.integration
def test_rls_guard_skipped_on_prem(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")

    # Kein APP_DATABASE_URL (On-Prem/Dev): die App verbindet als Owner mit
    # RLS-Bypass — das ist gewollt, der Guard darf NICHT feuern.
    monkeypatch.setattr(db, "get_settings", lambda: Settings(app_database_url=""))

    database = db.Database()

    async def _run() -> None:
        # connect + disconnect im SELBEN Event-Loop: der Pool ist an den Loop
        # gebunden, in dem er erzeugt wurde.
        await database.connect()
        assert database.pool is not None
        await database.disconnect()

    asyncio.run(_run())
