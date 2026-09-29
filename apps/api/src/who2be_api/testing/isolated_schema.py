"""Test-Helper: ein Integrationstest in einem eigenen, frisch migrierten Schema.

Manche Tests muessen das Schema selbst veraendern — etwa die Vektor-Spalte
entfernen, um den On-Prem-Fall ohne pgvector nachzustellen. Taeten sie das im
geteilten `public`-Schema, haenge die Datenbank jedes anderen Laufs an ihrem
Erfolg: ein Abbruch zwischen `DROP` und Wiederherstellen (SIGKILL, Timeout,
Ctrl-C) hinterliesse eine Dev-DB ohne die Spalte, und ein paralleler Lauf aus
einem zweiten Worktree saehe sie mittendrin fehlen.

``isolated_schema`` legt deshalb ein Wegwerf-Schema an, migriert es, und lenkt
fuer die Dauer des Blocks JEDE Verbindung dorthin um: ``DATABASE_URL`` (und
``APP_DATABASE_URL``, falls gesetzt) bekommen einen ``search_path``-Parameter,
der ``get_settings``-Cache wird geleert. App (``TestClient``), Workspace-Seed
und Test-Verbindungen landen so ohne weiteren Umbau im eigenen Schema.
``public`` steht hinten im Pfad, damit Extension-Objekte (``vector``,
``similarity`` aus pg_trgm) wie im Betrieb aufloesbar bleiben — Tabellen
findet der Pfad zuerst im eigenen Schema.

Bricht der Lauf hart ab, bleibt schlimmstenfalls ein verwaistes Schema
``<prefix>_<hex>`` liegen; ``public`` ist nie beruehrt worden.
"""

from __future__ import annotations

import asyncio
import os
import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from urllib.parse import quote

import asyncpg

from who2be_api.core.config import get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations

_URL_VARS = ("DATABASE_URL", "APP_DATABASE_URL")


def with_search_path(url: str, schema: str) -> str:
    """Haengt ``search_path=<schema>, public`` als Verbindungsparameter an.

    asyncpg reicht unbekannte DSN-Parameter als Server-Settings durch; der
    Pfad gilt damit fuer jede Verbindung, die aus dieser URL entsteht —
    auch fuer die Pool-Verbindungen der App.
    """
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}search_path={quote(f'{schema}, public')}"


async def _create_and_migrate(url: str, schema: str) -> None:
    conn = await asyncpg.connect(url)
    try:
        await conn.execute(f'CREATE SCHEMA "{schema}"')
        await conn.execute(f'SET search_path TO "{schema}", public')
        await apply_migrations(conn, MIGRATIONS_DIR)
    finally:
        await conn.close()


async def _drop(url: str, schema: str) -> None:
    conn = await asyncpg.connect(url)
    try:
        await conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
    finally:
        await conn.close()


@contextmanager
def isolated_schema(prefix: str) -> Iterator[str]:
    """Liefert den Namen eines migrierten Wegwerf-Schemas; raeumt es danach ab.

    Waehrend des Blocks zeigen ``get_settings().database_url`` und
    ``effective_app_database_url`` auf das Schema. Danach sind Umgebung und
    Settings-Cache wiederhergestellt.
    """
    base_url = get_settings().database_url
    schema = f"{prefix}_{secrets.token_hex(6)}"
    saved = {name: os.environ.get(name) for name in _URL_VARS}
    asyncio.run(_create_and_migrate(base_url, schema))
    try:
        for name, value in saved.items():
            if name == "DATABASE_URL":
                os.environ[name] = with_search_path(value or base_url, schema)
            elif value:
                os.environ[name] = with_search_path(value, schema)
        get_settings.cache_clear()
        yield schema
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        get_settings.cache_clear()
        asyncio.run(_drop(base_url, schema))
