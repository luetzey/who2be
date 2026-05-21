"""asyncpg-Connection-Pool: Lifecycle und FastAPI-Dependency.

Der Pool wird im FastAPI-Lifespan auf- und abgebaut. Ist die Datenbank beim
Start nicht erreichbar, startet die App trotzdem (ohne Pool) — so bleibt der
Liveness-Endpoint bedienbar und der Ausfall sichtbar.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI

from who2be_api.core.config import get_settings

logger = logging.getLogger(__name__)


class Database:
    """Haelt den asyncpg-Pool ueber die Lebensdauer der App."""

    def __init__(self) -> None:
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        settings = get_settings()
        self._pool = await asyncpg.create_pool(settings.database_url)

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
    try:
        await database.connect()
    except (asyncpg.PostgresError, OSError):
        logger.warning("Datenbank beim Start nicht erreichbar — App startet ohne Pool.")
    yield
    await database.disconnect()


def get_pool() -> asyncpg.Pool:
    """FastAPI-Dependency: liefert den aktiven asyncpg-Pool."""
    return database.pool
