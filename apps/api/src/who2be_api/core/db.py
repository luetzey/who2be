"""asyncpg-Connection-Pool: Lifecycle und FastAPI-Dependency.

Der Pool wird im FastAPI-Lifespan auf- und abgebaut. Ist die Datenbank beim
Start nicht erreichbar, startet die App trotzdem (ohne Pool) — so bleibt der
Liveness-Endpoint bedienbar und der Ausfall sichtbar.
"""

import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI

from who2be_api.core.config import get_settings
from who2be_api.core.tenancy import apply_tenant_settings

logger = logging.getLogger(__name__)

_MIN_JWT_SECRET_LEN = 32


async def _init_connection(conn: asyncpg.Connection) -> None:
    """Registriert den jsonb-Codec, damit `dict` direkt persistiert/gelesen wird."""
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )


class Database:
    """Haelt den asyncpg-Pool ueber die Lebensdauer der App."""

    def __init__(self) -> None:
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        settings = get_settings()
        # `init` (einmalig je physischer Connection): jsonb-Codec.
        # `setup` (bei jedem Checkout): Tenant-GUCs aus dem Request-ContextVar
        # (RLS-Choke-Point, core/tenancy.py). Die App verbindet ueber
        # `effective_app_database_url` — Cloud: Rolle `who2be_app` (RLS aktiv),
        # On-Prem/Dev: Owner (RLS-Bypass). Migrationen laufen separat ueber
        # `DATABASE_URL` (who2be-migrate).
        self._pool = await asyncpg.create_pool(
            settings.effective_app_database_url,
            init=_init_connection,
            setup=apply_tenant_settings,
        )

    async def disconnect(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("Datenbank-Pool ist nicht initialisiert.")
        return self._pool

    async def ping(self) -> bool:
        """True, wenn der Pool existiert und eine Test-Query gelingt."""
        if self._pool is None:
            return False
        try:
            async with self._pool.acquire() as conn:
                await conn.execute("SELECT 1")
        except (asyncpg.PostgresError, OSError):
            return False
        return True


database = Database()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    secret = get_settings().jwt_secret
    if 0 < len(secret) < _MIN_JWT_SECRET_LEN:
        # Ein gesetzter, aber zu kurzer JWT_SECRET ist immer ein Konfig-Fehler:
        # `verify_supabase_jwt` wuerde stillschweigend jedes JWT ablehnen — die
        # API liefe scheinbar normal, akzeptiert aber keinen Login. Fail loud.
        raise RuntimeError(
            f"JWT_SECRET ist {len(secret)} Zeichen lang, mindestens "
            f"{_MIN_JWT_SECRET_LEN} sind erforderlich."
        )
    if not secret:
        logger.warning(
            "JWT_SECRET ist leer — JWT-Auth ist deaktiviert (nur API-Tokens). "
            "Fuer Produktion ein starkes Secret konfigurieren."
        )
    try:
        await database.connect()
    except (asyncpg.PostgresError, OSError):
        logger.warning("Datenbank beim Start nicht erreichbar — App startet ohne Pool.")
    yield
    await database.disconnect()


def get_pool() -> asyncpg.Pool:
    """FastAPI-Dependency: liefert den aktiven asyncpg-Pool."""
    return database.pool
