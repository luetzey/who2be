"""Datenzugriff fuer den Tabellen-Katalog (`wa_table`, ADR-0049 / WP13).

Der Katalog ist die Postgres-Seite des Tabellen-Stores: `schema_json` traegt
das validierte `TableSchema` (Spalten/Typen-Allowlist, dedupe_columns,
match_column, category_column), die DATEN liegen in der Area-SQLite
(`tablestore/engine.py`). Tabellen werden pro Area ueber den Namen adressiert
— `UNIQUE (area_id, name)` (0078); der Insert nutzt `ON CONFLICT DO NOTHING
RETURNING` und liefert bei Namens-Kollision `None` (Service → 409, Muster
`work_area_repository.create_shared`).

`insert` nimmt bewusst eine `Connection` (conn-faehig, Muster
`wa_blob_repository`): der Service haelt Katalog-Insert und SQLite-DDL in
EINER Postgres-Transaktion zusammen — scheitert die DDL, rollt die
Katalog-Zeile mit zurueck (kein Katalog-Eintrag ohne SQLite-Tabelle).

Zusaetzlich lebt hier der Konventionen-Read (`wa_source_convention`, M2) fuer
den describe-Pfad. Jede Query filtert auf `workspace_id` (Defense-in-Depth
zusaetzlich zur RLS).
"""

from __future__ import annotations

from typing import Any, Protocol, TypeAlias
from uuid import UUID

import asyncpg

from who2be_models import SourceConventionRead, TableSchema, WaTableRead

_Fetcher: TypeAlias = asyncpg.Pool | asyncpg.Connection

_TABLE_COLUMNS = "id, workspace_id, area_id, name, schema_json, created_at, updated_at"

# UNIQUE (area_id, name) aus 0078 als Conflict-Target: Namens-Kollision liefert
# KEINE Zeile zurueck (Service → 409 `concurrent_conflict`).
_INSERT_SQL = (
    "INSERT INTO wa_table (workspace_id, area_id, name, schema_json) "
    "VALUES ($1, $2, $3, $4::jsonb) "
    "ON CONFLICT (area_id, name) DO NOTHING "
    f"RETURNING {_TABLE_COLUMNS}"
)

_GET_SQL = f"SELECT {_TABLE_COLUMNS} FROM wa_table WHERE workspace_id = $1 AND id = $2"

_LIST_SQL = (
    f"SELECT {_TABLE_COLUMNS} FROM wa_table "
    "WHERE workspace_id = $1 AND area_id = $2 ORDER BY name, id"
)

_CONVENTIONS_SQL = (
    "SELECT id, area_id, source_name, convention, created_by, created_at, updated_at "
    "FROM wa_source_convention WHERE workspace_id = $1 AND area_id = $2 ORDER BY source_name"
)


def _to_read(row: asyncpg.Record) -> WaTableRead:
    """Katalog-Zeile → `WaTableRead`; `schema_json` kommt via jsonb-Codec als dict."""
    return WaTableRead(
        id=row["id"],
        workspace_id=row["workspace_id"],
        area_id=row["area_id"],
        name=row["name"],
        schema=TableSchema.model_validate(row["schema_json"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _to_convention(row: asyncpg.Record) -> SourceConventionRead:
    convention: dict[str, Any] = row["convention"]
    return SourceConventionRead(
        id=row["id"],
        area_id=row["area_id"],
        source_name=row["source_name"],
        convention=convention,
        created_by=row["created_by"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class WaTableRepository(Protocol):
    """Vertrag des Katalog-Datenzugriffs (Service-Sicht)."""

    async def insert(
        self,
        conn: asyncpg.Connection,
        workspace_id: UUID,
        area_id: UUID,
        *,
        name: str,
        schema: TableSchema,
    ) -> WaTableRead | None: ...

    async def get(
        self, fetcher: _Fetcher, workspace_id: UUID, table_id: UUID
    ) -> WaTableRead | None: ...

    async def list_for_area(
        self, fetcher: _Fetcher, workspace_id: UUID, area_id: UUID
    ) -> list[WaTableRead]: ...

    async def list_conventions(
        self, fetcher: _Fetcher, workspace_id: UUID, area_id: UUID
    ) -> list[SourceConventionRead]: ...


class PgWaTableRepository:
    """asyncpg-Implementierung von `WaTableRepository`.

    Bewusst ohne Pool im Konstruktor: `insert` laeuft auf der Transaktions-
    Connection des Services (DDL VOR Commit, s. Modul-Kopf); die Read-Pfade
    nehmen Pool ODER Connection (Muster `wa_blob_repository`).
    """

    async def insert(
        self,
        conn: asyncpg.Connection,
        workspace_id: UUID,
        area_id: UUID,
        *,
        name: str,
        schema: TableSchema,
    ) -> WaTableRead | None:
        """Katalog-Zeile anlegen; `None` = Name in der Area bereits vergeben."""
        row = await conn.fetchrow(
            _INSERT_SQL, workspace_id, area_id, name, schema.model_dump(mode="json")
        )
        return _to_read(row) if row is not None else None

    async def get(
        self, fetcher: _Fetcher, workspace_id: UUID, table_id: UUID
    ) -> WaTableRead | None:
        row = await fetcher.fetchrow(_GET_SQL, workspace_id, table_id)
        return _to_read(row) if row is not None else None

    async def list_for_area(
        self, fetcher: _Fetcher, workspace_id: UUID, area_id: UUID
    ) -> list[WaTableRead]:
        rows = await fetcher.fetch(_LIST_SQL, workspace_id, area_id)
        return [_to_read(row) for row in rows]

    async def list_conventions(
        self, fetcher: _Fetcher, workspace_id: UUID, area_id: UUID
    ) -> list[SourceConventionRead]:
        """Quell-Konventionen der Area (M2) — Kontextteil des describe-Pfads."""
        rows = await fetcher.fetch(_CONVENTIONS_SQL, workspace_id, area_id)
        return [_to_convention(row) for row in rows]
