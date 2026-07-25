"""asyncpg-Connection-Pool: Lifecycle und FastAPI-Dependency.

Der Pool wird im FastAPI-Lifespan auf- und abgebaut. Ist die Datenbank beim
Start nicht erreichbar, startet die App trotzdem (ohne Pool) — so bleibt der
Liveness-Endpoint bedienbar und der Ausfall sichtbar.
"""

import json
import logging
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI

from who2be_api.core.config import Settings, get_settings
from who2be_api.core.tenancy import apply_tenant_settings

logger = logging.getLogger(__name__)

_MIN_JWT_SECRET_LEN = 32

# pgvector kann je nach Umgebung in unterschiedlichen Schemata liegen (lokal:
# public; Supabase: extensions; isolierte Test-Schemata: eigenes). Der Codec
# muss deshalb dasselbe dynamisch aufloesen wie die Migrationen — ein
# unqualifiziertes `vector` haengt am search_path.
_VECTOR_TYPE_SCHEMA_SQL = """
SELECT n.nspname
FROM pg_type t
JOIN pg_namespace n ON n.oid = t.typnamespace
WHERE t.typname = 'vector'
LIMIT 1
"""


def encode_vector(value: Sequence[float]) -> str:
    """Python-Liste → pgvector-Textformat (`[1,2,3]`)."""
    return "[" + ",".join(repr(float(v)) for v in value) + "]"


def decode_vector(value: str) -> list[float]:
    """pgvector-Textformat → Python-Liste."""
    inner = value.strip().strip("[]")
    if not inner:
        return []
    return [float(part) for part in inner.split(",")]


async def init_connection(conn: asyncpg.Connection) -> None:
    """Registriert die Typ-Codecs einer frischen Verbindung.

    - `jsonb`, damit `dict` direkt persistiert/gelesen wird.
    - `vector` (ADR-0046), damit Embeddings als `list[float]` uebergeben werden
      koennen. Fehlt die Extension (frische DB vor den Migrationen, On-Prem
      ohne Semantik), wird der Codec still uebersprungen — die Vektor-Spalte
      ist nullable, und ohne sie laeuft alles im Volltext-Modus weiter.

    Oeffentlich, weil auch die CLIs (`who2be-chunk-backfill`) eine eigene
    Verbindung aufbauen und dieselben Codecs brauchen.
    """
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )
    vector_schema = await conn.fetchval(_VECTOR_TYPE_SCHEMA_SQL)
    if vector_schema is None:
        return
    await conn.set_type_codec(
        "vector",
        encoder=encode_vector,
        decoder=decode_vector,
        schema=vector_schema,
        format="text",
    )


class Database:
    """Haelt den asyncpg-Pool ueber die Lebensdauer der App."""

    def __init__(self) -> None:
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        settings = get_settings()
        # `init` (einmalig je physischer Connection): jsonb- + vector-Codec.
        # `setup` (bei jedem Checkout): Tenant-GUCs aus dem Request-ContextVar
        # (RLS-Choke-Point, core/tenancy.py). Die App verbindet ueber
        # `effective_app_database_url` — Cloud: Rolle `who2be_app` (RLS aktiv),
        # On-Prem/Dev: Owner (RLS-Bypass). Migrationen laufen separat ueber
        # `DATABASE_URL` (who2be-migrate).
        self._pool = await asyncpg.create_pool(
            settings.effective_app_database_url,
            init=init_connection,
            setup=apply_tenant_settings,
        )
        await self._assert_rls_enforced(settings)

    async def _assert_rls_enforced(self, settings: Settings) -> None:
        """Cloud-Guard (Security-Review INFO-2): Ist `APP_DATABASE_URL` gesetzt,
        MUSS der App-Pool als nicht-privilegierte Rolle (`who2be_app`,
        NOSUPERUSER/NOBYPASSRLS) verbinden — sonst umginge die App die
        RLS-Mandantenisolation STILL (typische Fehlkonfig: `DATABASE_URL` statt
        `APP_DATABASE_URL` fuer den Pool). Fail loud beim Boot.

        On-Prem/Dev (kein `APP_DATABASE_URL`) ist bewusst ausgenommen: dort
        verbindet die App als Owner mit RLS-Bypass (Plan R2) — das ist gewollt.
        """
        if not settings.app_database_url or self._pool is None:
            return
        bypasses_rls = await self._pool.fetchval(
            "SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user"
        )
        if bypasses_rls:
            await self._pool.close()
            self._pool = None
            raise RuntimeError(
                "Cloud-Fehlkonfiguration: Der App-Pool verbindet als RLS-umgehende "
                "Rolle (superuser oder rolbypassrls=true). APP_DATABASE_URL muss die "
                "Rolle who2be_app (NOSUPERUSER, NOBYPASSRLS) nutzen — sonst ist die "
                "Mandanten-Isolation (Row Level Security) inaktiv."
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
