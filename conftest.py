"""Geteiltes Pytest-Setup (ADR-0041 — Test-Pyramide).

Zentralisiert, was bisher in ~40 Integrationstest-Dateien dupliziert lag:

- **DB-Erreichbarkeit** wird einmal pro Session geprueft (gecacht).
- **Zentraler Skip** fuer ``@pytest.mark.integration``: ohne erreichbare DB
  werden diese Tests an *einer* Stelle uebersprungen — die alten Inline-
  ``if not _db_reachable(): pytest.skip(...)``-Zeilen werden damit redundant
  (bleiben aber unschaedlich).
- **CI-Skip-Guard:** ist ``WHO2BE_REQUIRE_DB`` gesetzt (CI), fuehrt eine
  fehlende DB zum *harten Fehlschlag* statt zum stillen Skip. So kann der in
  Phase 0 diagnostizierte "gruen-durch-Skip"-Effekt in CI nie wieder auftreten.
- **Geteilte Fixtures** (JWT-Secret/Header-Factory, Migrationen, Workspace-Seed)
  fuer neue Tests, damit kuenftiger Integrations-Code das Boilerplate nicht
  erneut kopiert. **Review-Regel: kein neues Inline-``_db_reachable`` in
  Testdateien — die zentralen Fixtures/den zentralen Skip hier nutzen (Audit
  TST-10); der Bestand wird inkrementell abgebaut, nicht vermehrt.**

Schwere Importe (``who2be_api``, ``asyncpg``, ``jwt``) bleiben *lazy* in den
Funktionen, damit das Sammeln der reinen Unit-Suites (models/billing) nicht an
API-Imports gekoppelt ist.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest

# Gleiches Secret wie bisher in den Integrationstests — bewusst stabil, damit
# migrierte Tests denselben Token-Pfad nehmen.
TEST_JWT_SECRET = "integration-test-jwt-secret-padding-0123456789"

_DB_REACHABLE_CACHE: bool | None = None
_PG_CONTAINER: Any = None


def pytest_configure(config: pytest.Config) -> None:
    """Opt-in: ephemere Postgres via Testcontainers (ADR-0041, Phase 2).

    Mit ``WHO2BE_TEST_TESTCONTAINERS=1`` (und laufendem Docker) wird vor der
    Collection ein Postgres-Container gestartet, ``DATABASE_URL`` darauf gesetzt
    und der ``get_settings``-Cache geleert — so laufen die Integrationstests
    auch *lokal* wirklich, ohne manuelles ``docker compose``. Default ist aus:
    CI nutzt bewusst den vorhandenen Postgres-Service (eine DB-Quelle, ADR-0041),
    normale lokale Laeufe bleiben unveraendert.
    """
    global _PG_CONTAINER
    if not _truthy(os.environ.get("WHO2BE_TEST_TESTCONTAINERS")):
        return
    from testcontainers.postgres import PostgresContainer

    container = PostgresContainer("pgvector/pgvector:pg16")
    container.start()
    # Testcontainers liefert eine SQLAlchemy-URL (…+psycopg2://); asyncpg will
    # das nackte ``postgresql://``-Schema.
    url = container.get_connection_url().replace("+psycopg2", "")
    os.environ["DATABASE_URL"] = url
    from who2be_api.core.config import get_settings

    get_settings.cache_clear()
    _PG_CONTAINER = container


def pytest_unconfigure(config: pytest.Config) -> None:
    global _PG_CONTAINER
    if _PG_CONTAINER is not None:
        _PG_CONTAINER.stop()
        _PG_CONTAINER = None


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _db_reachable() -> bool:
    """Einmaliger, gecachter Connect-Versuch gegen ``database_url``."""
    global _DB_REACHABLE_CACHE
    if _DB_REACHABLE_CACHE is not None:
        return _DB_REACHABLE_CACHE

    async def _check() -> bool:
        import asyncpg

        from who2be_api.core.config import get_settings

        try:
            conn = await asyncpg.connect(get_settings().database_url)
        except (asyncpg.PostgresError, OSError):
            return False
        await conn.close()
        return True

    _DB_REACHABLE_CACHE = asyncio.run(_check())
    return _DB_REACHABLE_CACHE


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Zentraler Integration-Skip + CI-Skip-Guard.

    Ohne erreichbare DB werden ``integration``-Tests einmalig markiert
    (Skip), bzw. — mit ``WHO2BE_REQUIRE_DB`` — wird hart abgebrochen.
    """
    integration_items = [it for it in items if it.get_closest_marker("integration")]
    if not integration_items:
        return
    if _db_reachable():
        return
    if _truthy(os.environ.get("WHO2BE_REQUIRE_DB")):
        raise pytest.UsageError(
            f"WHO2BE_REQUIRE_DB gesetzt, aber keine DB erreichbar — "
            f"{len(integration_items)} Integrationstests koennen nicht laufen. "
            "Skip-Guard (ADR-0041): in CI muss die DB stehen, sonst ist 'gruen' "
            "eine Luege."
        )
    skip = pytest.mark.skip(
        reason="Keine erreichbare DB — Integrationstest zentral uebersprungen (conftest)."
    )
    for item in integration_items:
        item.add_marker(skip)


# --- Geteilte Fixtures fuer (neue) Integrationstests -------------------------


@pytest.fixture
def patched_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> str:
    """Patcht ``security.get_settings`` auf das Test-JWT-Secret und gibt es zurueck."""
    from who2be_api.core import security
    from who2be_api.core.config import Settings

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=TEST_JWT_SECRET))
    return TEST_JWT_SECRET


@pytest.fixture(scope="session")
def migrated_db() -> None:
    """Wendet alle Migrationen einmal pro Session auf die Test-DB an."""

    async def _run() -> None:
        import asyncpg

        from who2be_api.core.config import get_settings
        from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations

        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await apply_migrations(conn, MIGRATIONS_DIR)
        finally:
            await conn.close()

    asyncio.run(_run())


@pytest.fixture
def make_auth_headers() -> Callable[[UUID], dict[str, str]]:
    """Factory fuer ``Authorization``-Header eines Test-Users (HS256-JWT)."""
    import jwt

    def _factory(user_id: UUID) -> dict[str, str]:
        token = jwt.encode(
            {
                "sub": str(user_id),
                "aud": "authenticated",
                "role": "authenticated",
                "exp": datetime.now(UTC) + timedelta(hours=1),
            },
            TEST_JWT_SECRET,
            algorithm="HS256",
        )
        return {"Authorization": f"Bearer {token}"}

    return _factory
