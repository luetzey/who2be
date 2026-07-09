"""Integrationstest fuer Migration 0063 (Trigger-Normalisierung, WP-D1).

Playbook-Trigger sind ein kanonisch kommagetrennter String; Bestand mit ';'
als Separator rendert in der UI als eine Riesen-Pill. Neue Writes normalisiert
der Modell-Validator (`PlaybookContent.triggers`); Migration 0063 zieht den
Bestand nach: die denormalisierte Spalte `playbook.triggers` UND das
`triggers`-Feld in `playbook_version.content` werden IN-PLACE normalisiert
(Split an ','/';', trim, Dedupe case-insensitiv — erste Schreibweise gewinnt,
Join mit ', '). Rein syntaktisch: KEINE neue Version, `updated_at` bleibt
unangetastet, NULL bleibt NULL, Leerstring bleibt Leerstring. Idempotent.

Der Test schreibt den Legacy-Zustand per Raw-SQL an der Pydantic-Schicht
vorbei (das Modell wuerde ihn sonst sofort normalisieren) und fuehrt die
0063-SQL danach zweimal aus.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from uuid import UUID

import asyncpg
import pytest

from who2be_api.core.config import get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace

_MIGRATION_0063 = MIGRATIONS_DIR / "0063_normalize_playbook_triggers.sql"

_MESSY = "Reset; logout;reset , LOGOUT; callback;"
_NORMALIZED = "Reset, logout, callback"


def _db_reachable() -> bool:
    async def _check() -> bool:
        try:
            conn = await asyncpg.connect(get_settings().database_url)
        except (asyncpg.PostgresError, OSError):
            return False
        await conn.close()
        return True

    return asyncio.run(_check())


def _prepare_db() -> None:
    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await apply_migrations(conn, MIGRATIONS_DIR)
        finally:
            await conn.close()

    asyncio.run(_run())


def _content(triggers: str | None) -> str:
    return json.dumps(
        {
            "description": "d",
            "body": "[]",
            "type": "workflow",
            "tags": [],
            "triggers": triggers,
        }
    )


async def _plant_playbook(
    conn: asyncpg.Connection, ws: UUID, owner: UUID, name: str, triggers: str | None
) -> UUID:
    """Legt ein Playbook mit v1 (messy) + v2-Draft (messy) via Raw-SQL an."""
    playbook_id: UUID = await conn.fetchval(
        "INSERT INTO playbook (workspace_id, owner_id, name, type, triggers, current_version) "
        "VALUES ($1, $2, $3, 'workflow', $4, 2) RETURNING id",
        ws,
        owner,
        name,
        triggers,
    )
    for version, status in ((1, "active"), (2, "draft")):
        await conn.execute(
            "INSERT INTO playbook_version "
            "(playbook_id, version, content, status, created_by, locale) "
            "VALUES ($1, $2, $3::jsonb, $4, $5, 'de')",
            playbook_id,
            version,
            _content(triggers),
            status,
            owner,
        )
    return playbook_id


@pytest.mark.integration
def test_migration_0063_normalizes_triggers_in_place_and_is_idempotent() -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    migration_sql = _MIGRATION_0063.read_text()

    async def _run() -> dict[str, Any]:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            messy_id = await _plant_playbook(conn, ws, owner, "Messy", _MESSY)
            null_id = await _plant_playbook(conn, ws, owner, "Null", None)
            empty_id = await _plant_playbook(conn, ws, owner, "Empty", "")
            seps_id = await _plant_playbook(conn, ws, owner, "Seps", " ; , ")
            updated_before = await conn.fetchval(
                "SELECT updated_at FROM playbook WHERE id = $1", messy_id
            )

            await conn.execute(migration_sql)

            async def _snapshot() -> dict[str, Any]:
                rows = await conn.fetch(
                    "SELECT p.id, p.name, p.triggers, p.updated_at, "
                    "       (SELECT count(*) FROM playbook_version v "
                    "          WHERE v.playbook_id = p.id) AS version_count, "
                    "       (SELECT jsonb_agg(v.content ->> 'triggers' ORDER BY v.version) "
                    "          FROM playbook_version v "
                    "         WHERE v.playbook_id = p.id) AS version_triggers "
                    "FROM playbook p WHERE p.workspace_id = $1 AND p.name <> 'Builder' "
                    "ORDER BY p.name",
                    ws,
                )
                return {row["name"]: dict(row) for row in rows}

            first = await _snapshot()
            # Idempotenz: zweiter Lauf aendert nichts (auch updated_at nicht).
            await conn.execute(migration_sql)
            second = await _snapshot()
            return {
                "first": first,
                "second": second,
                "updated_before": updated_before,
                "ids": {"messy": messy_id, "null": null_id, "empty": empty_id, "seps": seps_id},
            }
        finally:
            await conn.close()

    try:
        res = asyncio.run(_run())
    finally:
        cleanup_workspaces([owner])

    first = res["first"]

    # Spalte normalisiert: Split ,/;, trim, Dedupe case-insensitiv (erste
    # Schreibweise gewinnt), Join ', '.
    assert first["Messy"]["triggers"] == _NORMALIZED
    # Beide Versionen in-place normalisiert — KEINE neue Version.
    assert first["Messy"]["version_count"] == 2
    assert json.loads(first["Messy"]["version_triggers"]) == [_NORMALIZED, _NORMALIZED]
    # Rein syntaktisch: updated_at unangetastet.
    assert first["Messy"]["updated_at"] == res["updated_before"]

    # NULL bleibt NULL, Leerstring bleibt Leerstring; nur Separatoren/
    # Whitespace kollabieren zum Leerstring (non-NULL bleibt non-NULL).
    assert first["Null"]["triggers"] is None
    assert json.loads(first["Null"]["version_triggers"]) == [None, None]
    assert first["Empty"]["triggers"] == ""
    assert json.loads(first["Empty"]["version_triggers"]) == ["", ""]
    assert first["Seps"]["triggers"] == ""
    assert json.loads(first["Seps"]["version_triggers"]) == ["", ""]

    # Idempotenz: der zweite Lauf ist ein vollstaendiger No-op.
    assert res["second"] == first
