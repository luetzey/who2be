"""Idempotenter SQL-Migrations-Runner.

Wendet nummerierte `*.sql`-Dateien aus `who2be_api/migrations/` in Reihenfolge
an und haelt den Stand in der Tabelle `schema_migrations` fest. Bereits
angewandte Migrationen werden uebersprungen.

CLI: `uv run who2be-migrate`.
"""

import asyncio
from pathlib import Path

import asyncpg

from who2be_api.core.config import get_settings

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"

_SCHEMA_MIGRATIONS_DDL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
);
"""


async def apply_migrations(
    conn: asyncpg.Connection, migrations_dir: Path = MIGRATIONS_DIR
) -> list[str]:
    """Wendet ausstehende Migrationen an und liefert deren Dateinamen.

    Idempotent: ein zweiter Lauf ohne neue Dateien liefert eine leere Liste.
    """
    await conn.execute(_SCHEMA_MIGRATIONS_DDL)
    rows = await conn.fetch("SELECT version FROM schema_migrations")
    applied = {row["version"] for row in rows}

    pending = sorted(
        (path for path in migrations_dir.glob("*.sql") if path.name not in applied),
        key=lambda path: path.name,
    )

    newly_applied: list[str] = []
    for path in pending:
        sql = path.read_text(encoding="utf-8")
        async with conn.transaction():
            await conn.execute(sql)
            await conn.execute(
                "INSERT INTO schema_migrations (version) VALUES ($1)", path.name
            )
        newly_applied.append(path.name)
    return newly_applied


async def _run() -> None:
    try:
        conn = await asyncpg.connect(get_settings().database_url)
    except (asyncpg.PostgresError, OSError) as exc:
        raise SystemExit(f"Datenbank nicht erreichbar: {exc}") from exc
    try:
        applied = await apply_migrations(conn)
    finally:
        await conn.close()
    if applied:
        print(f"Angewandt: {', '.join(applied)}")
    else:
        print("Keine ausstehenden Migrationen.")


def cli() -> None:
    """Console-Entrypoint fuer `who2be-migrate`."""
    asyncio.run(_run())


if __name__ == "__main__":
    cli()
