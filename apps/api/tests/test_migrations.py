"""Integrationstest fuer den Migrations-Runner.

Belegt die Idempotenz (zweite Anwendung ist ein No-op). Laeuft nur mit
erreichbarer Datenbank; ohne DB wird der Test uebersprungen.

Phase 3-0 ergaenzt drei integration-markierte Tests fuer die Migrations
`0019_status_default_draft.sql` (Default + Backfill) und
`0020_playbook_type_check.sql` (CHECK + Backfill). Sie laufen in isolierten
Postgres-Schemas, damit die `public`-Schema und parallele Integration-Tests
unangetastet bleiben (gleiches Muster wie `test_phase21_migrations.py` /
`test_phase23_migrations.py`).
"""

import asyncio
import json
import secrets
import shutil
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeVar
from uuid import UUID, uuid4

import asyncpg
import pytest

from who2be_api.core.config import get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations

_T = TypeVar("_T")

_SELFTEST_TABLE = "_w2b_migration_selftest"
_SELFTEST_FILE = "9001_runner_selftest.sql"

_CORE_TABLES = (
    "api_token",
    "persona",
    "persona_version",
    "playbook",
    "playbook_version",
    "persona_playbook",
)

_ALL_MIGRATIONS = sorted(p.name for p in MIGRATIONS_DIR.glob("[0-9]*.sql"))
_PHASE3_MIGRATIONS = [
    "0019_status_default_draft.sql",
    "0020_playbook_type_check.sql",
]
# Welle 4: 0025 lockert den `playbook_type_check`-Constraint um den
# Leerstring — gehoert zwingend zur „neuen Welt", sonst legt der Test
# vor dem Phase-3-Step bereits den engen Constraint an und der Test-
# INSERT mit `type='core'` schlaegt mit CheckViolation fehl.
_POST_PHASE3_MIGRATIONS = [
    "0025_playbook_type_allow_empty.sql",
]
_PRE_PHASE3_MIGRATIONS = [
    m for m in _ALL_MIGRATIONS if m not in _PHASE3_MIGRATIONS and m not in _POST_PHASE3_MIGRATIONS
]


def _db_reachable() -> bool:
    async def _check() -> bool:
        try:
            conn = await asyncpg.connect(get_settings().database_url)
        except (asyncpg.PostgresError, OSError):
            return False
        await conn.close()
        return True

    return asyncio.run(_check())


def _copy_migrations(dst: Path, names: list[str]) -> None:
    for name in names:
        shutil.copy(MIGRATIONS_DIR / name, dst / name)


async def _with_isolated_schema(
    body: Callable[[asyncpg.Connection], Awaitable[_T]],
) -> _T:
    """Fuehrt `body(conn)` in einem temporaeren Schema aus und raeumt auf."""
    schema = f"phase3_{secrets.token_hex(6)}"
    conn = await asyncpg.connect(get_settings().database_url)
    try:
        await conn.execute(f'CREATE SCHEMA "{schema}"')
        await conn.execute(f'SET search_path TO "{schema}"')
        return await body(conn)
    finally:
        try:
            await conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        finally:
            await conn.close()


@pytest.mark.integration
def test_migrations_apply_is_idempotent(tmp_path: Path) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")

    (tmp_path / _SELFTEST_FILE).write_text(
        f"CREATE TABLE IF NOT EXISTS {_SELFTEST_TABLE} (id int);",
        encoding="utf-8",
    )

    async def _run() -> tuple[list[str], list[str]]:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            first = await apply_migrations(conn, tmp_path)
            second = await apply_migrations(conn, tmp_path)
            return first, second
        finally:
            await conn.execute(f"DROP TABLE IF EXISTS {_SELFTEST_TABLE};")
            await conn.execute("DELETE FROM schema_migrations WHERE version = $1", _SELFTEST_FILE)
            await conn.close()

    first, second = asyncio.run(_run())
    assert first == [_SELFTEST_FILE]
    assert second == []


@pytest.mark.integration
def test_core_migrations_create_all_tables() -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")

    async def _run() -> set[str]:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await apply_migrations(conn, MIGRATIONS_DIR)
            rows = await conn.fetch(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
            )
        finally:
            await conn.close()
        return {row["table_name"] for row in rows}

    tables = asyncio.run(_run())
    missing = set(_CORE_TABLES) - tables
    assert not missing, f"Fehlende Tabellen nach Migration: {sorted(missing)}"


# --- Phase 3-0 --------------------------------------------------------------


@pytest.mark.integration
def test_phase30_idempotent(tmp_path: Path) -> None:
    """Alle Migrations + Statement-Replay der Phase-3-0-Files ist No-op."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")

    _copy_migrations(tmp_path, _ALL_MIGRATIONS)

    async def _run(conn: asyncpg.Connection) -> tuple[list[str], list[str]]:
        first = await apply_migrations(conn, tmp_path)
        second = await apply_migrations(conn, tmp_path)
        # Manuelles Statement-Replay der neuen Files muss ebenfalls No-op sein.
        for name in _PHASE3_MIGRATIONS + _POST_PHASE3_MIGRATIONS:
            sql = (MIGRATIONS_DIR / name).read_text(encoding="utf-8")
            await conn.execute(sql)
        return first, second

    first, second = asyncio.run(_with_isolated_schema(_run))
    assert first == _ALL_MIGRATIONS
    assert second == []


@pytest.mark.integration
def test_phase30_status_default_and_backfill(tmp_path: Path) -> None:
    """Backfill hebt current_version-Rows ohne Active-Schwester auf 'draft';
    Neu-Insert ohne explizites status faellt auf den neuen Default 'draft'."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")

    async def _run(conn: asyncpg.Connection) -> dict[str, str]:
        # 1) Pre-Phase-3-Stand herstellen: bis einschliesslich 0018 anwenden.
        _copy_migrations(tmp_path, _PRE_PHASE3_MIGRATIONS)
        await apply_migrations(conn, tmp_path)

        # Personal-Tenant fuer FK-Pflicht.
        org_id = await conn.fetchval(
            "INSERT INTO organization (name, slug, kind) VALUES ('o', 'o', 'company') RETURNING id"
        )
        ws_id = await conn.fetchval(
            "INSERT INTO workspace (org_id, name, slug) VALUES ($1, 'w', 'w') RETURNING id",
            org_id,
        )
        owner = uuid4()

        # Persona mit stuck-inactive current_version (kein Active-, kein
        # Draft-Geschwister) — Ziel des Backfills.
        stuck_id = uuid4()
        await conn.execute(
            "INSERT INTO persona (id, workspace_id, owner_id, name, current_version) "
            "VALUES ($1, $2, $3, 'stuck', 1)",
            stuck_id,
            ws_id,
            owner,
        )
        await conn.execute(
            "INSERT INTO persona_version "
            "(persona_id, version, content, status, created_by) "
            "VALUES ($1, 1, '{}'::jsonb, 'inactive', $2)",
            stuck_id,
            owner,
        )

        # Persona mit Active-Schwester — Backfill darf hier NICHT eingreifen.
        skip_id = uuid4()
        await conn.execute(
            "INSERT INTO persona (id, workspace_id, owner_id, name, current_version) "
            "VALUES ($1, $2, $3, 'skip', 2)",
            skip_id,
            ws_id,
            owner,
        )
        await conn.execute(
            "INSERT INTO persona_version "
            "(persona_id, version, content, status, created_by) "
            "VALUES ($1, 1, '{}'::jsonb, 'active', $2)",
            skip_id,
            owner,
        )
        await conn.execute(
            "INSERT INTO persona_version "
            "(persona_id, version, content, status, created_by) "
            "VALUES ($1, 2, '{}'::jsonb, 'inactive', $2)",
            skip_id,
            owner,
        )

        # 2) Phase-3-Migration anwenden.
        _copy_migrations(tmp_path, _PHASE3_MIGRATIONS + _POST_PHASE3_MIGRATIONS)
        await apply_migrations(conn, tmp_path)

        # Status nach Backfill.
        stuck_status = await conn.fetchval(
            "SELECT status FROM persona_version WHERE persona_id = $1",
            stuck_id,
        )
        skip_current_status = await conn.fetchval(
            "SELECT status FROM persona_version WHERE persona_id = $1 AND version = 2",
            skip_id,
        )

        # 3) Neu-Insert ohne status nutzt den neuen Default 'draft'.
        fresh_id = uuid4()
        await conn.execute(
            "INSERT INTO persona (id, workspace_id, owner_id, name) VALUES ($1, $2, $3, 'fresh')",
            fresh_id,
            ws_id,
            owner,
        )
        fresh_status = await conn.fetchval(
            "INSERT INTO persona_version "
            "(persona_id, version, content, created_by) "
            "VALUES ($1, 1, '{}'::jsonb, $2) RETURNING status",
            fresh_id,
            owner,
        )

        return {
            "stuck": stuck_status,
            "skip_current": skip_current_status,
            "fresh": fresh_status,
        }

    statuses = asyncio.run(_with_isolated_schema(_run))
    assert statuses["stuck"] == "draft"
    # Active-Schwester war vorhanden -> Backfill ueberspringt diese Persona.
    assert statuses["skip_current"] == "inactive"
    assert statuses["fresh"] == "draft"


@pytest.mark.integration
def test_phase30_playbook_type_check(tmp_path: Path) -> None:
    """Backfill mapped unbekannte Typen auf 'prompt'; CHECK weist neue
    ungueltige Werte ab; gueltige Werte gehen durch."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")

    async def _run(conn: asyncpg.Connection) -> dict[str, str]:
        _copy_migrations(tmp_path, _PRE_PHASE3_MIGRATIONS)
        await apply_migrations(conn, tmp_path)

        org_id = await conn.fetchval(
            "INSERT INTO organization (name, slug, kind) VALUES ('o', 'o', 'company') RETURNING id"
        )
        ws_id = await conn.fetchval(
            "INSERT INTO workspace (org_id, name, slug) VALUES ($1, 'w', 'w') RETURNING id",
            org_id,
        )
        owner = uuid4()

        legacy_id = uuid4()
        await conn.execute(
            "INSERT INTO playbook (id, workspace_id, owner_id, name, type) "
            "VALUES ($1, $2, $3, 'legacy', 'core')",
            legacy_id,
            ws_id,
            owner,
        )

        _copy_migrations(tmp_path, _PHASE3_MIGRATIONS + _POST_PHASE3_MIGRATIONS)
        await apply_migrations(conn, tmp_path)

        legacy_type = await conn.fetchval("SELECT type FROM playbook WHERE id = $1", legacy_id)

        # Gueltiger Wert geht durch.
        await conn.execute(
            "INSERT INTO playbook (workspace_id, owner_id, name, type) "
            "VALUES ($1, $2, 'ok', 'workflow')",
            ws_id,
            owner,
        )

        # Ungueltiger Wert wird abgewiesen.
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute(
                "INSERT INTO playbook (workspace_id, owner_id, name, type) "
                "VALUES ($1, $2, 'bad', 'banana')",
                ws_id,
                owner,
            )

        return {"legacy": legacy_type}

    types = asyncio.run(_with_isolated_schema(_run))
    assert types["legacy"] == "prompt"


# --- Track P: Mollie-Dunning + Webhook-Dedupe (0039) ------------------------


@pytest.mark.integration
def test_mollie_dunning_dedupe_migration(tmp_path: Path) -> None:
    """0039: `grace_until`-Spalte + `processed_webhook_event`-Dedupe-Ledger.

    Belegt: die Grace-Spalte existiert (NULL-Default), der Dedupe-Claim per
    `ON CONFLICT DO NOTHING RETURNING` liefert beim Replay keine Zeile, und ein
    erneutes Statement-Replay der 0039-Datei ist No-op.
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")

    _copy_migrations(tmp_path, _ALL_MIGRATIONS)

    async def _run(conn: asyncpg.Connection) -> None:
        await apply_migrations(conn, tmp_path)

        # grace_until existiert und ist standardmaessig NULL.
        org_id = await conn.fetchval(
            "INSERT INTO organization (name, slug, kind) VALUES ('o', 's', 'company') RETURNING id"
        )
        await conn.execute(
            "INSERT INTO org_entitlement (org_id, status) VALUES ($1, 'active')", org_id
        )
        grace = await conn.fetchval(
            "SELECT grace_until FROM org_entitlement WHERE org_id = $1", org_id
        )
        assert grace is None

        # Dedupe: der erste Claim liefert eine id, der zweite (Replay) None.
        first = await conn.fetchval(
            "INSERT INTO processed_webhook_event (provider, event_id) VALUES ('mollie', 'tr_1') "
            "ON CONFLICT (provider, event_id) DO NOTHING RETURNING id"
        )
        second = await conn.fetchval(
            "INSERT INTO processed_webhook_event (provider, event_id) VALUES ('mollie', 'tr_1') "
            "ON CONFLICT (provider, event_id) DO NOTHING RETURNING id"
        )
        assert first is not None
        assert second is None

        # Statement-Replay der 0039-Datei muss No-op sein (IF NOT EXISTS / idempotent).
        sql = (MIGRATIONS_DIR / "0039_mollie_dunning_dedupe.sql").read_text(encoding="utf-8")
        await conn.execute(sql)

    asyncio.run(_with_isolated_schema(_run))


# --- 0088: Rollen-Deckel fuer agent-gebundene Tokens (Bestand) --------------


@pytest.mark.integration
def test_agent_bound_admin_tokens_are_capped_and_audited(tmp_path: Path) -> None:
    """0088: aktive agent-gebundene admin-Tokens werden auf `editor` gezogen.

    Der Deckel in `token_service`/`oauth_service` gilt nur fuer neue Tokens —
    ohne diese Migration liefen die vorhandenen admin-Tokens unveraendert
    weiter, und die Grenze waere eine Aussage ueber die Zukunft statt ueber den
    Zustand. Getestet wird an einem Bestand, der vor der Migration angelegt
    wurde: dazu erst alle Migrationen AUSSER 0088 anwenden, dann die Zeilen
    schreiben, dann 0088 nachziehen.

    Drei Zeilen decken die Abgrenzung ab: der aktive admin-Token (wird gedeckelt
    und auditiert), ein widerrufener admin-Token (bleibt — ungueltig, seine
    Rolle ist Audit-Historie) und ein aktiver editor-Token (Gegenprobe, kein
    Audit-Eintrag). Zuletzt der zweite Lauf: er darf weder etwas aendern noch
    ein zweites Audit-Ereignis schreiben.
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")

    cap_file = "0088_agent_bound_token_role_cap.sql"
    _copy_migrations(tmp_path, [m for m in _ALL_MIGRATIONS if m != cap_file])

    async def _run(conn: asyncpg.Connection) -> None:
        await apply_migrations(conn, tmp_path)

        org_id = await conn.fetchval(
            "INSERT INTO organization (name, slug, kind) VALUES ('o', 'cap', 'company') "
            "RETURNING id"
        )
        ws_id = await conn.fetchval(
            "INSERT INTO workspace (org_id, name, slug) VALUES ($1, 'w', 'cap-w') RETURNING id",
            org_id,
        )
        owner = uuid4()
        agent_id = await conn.fetchval(
            "INSERT INTO agent (workspace_id, owner_id, name) VALUES ($1, $2, 'a') RETURNING id",
            ws_id,
            owner,
        )

        async def _insert(name: str, role: str, *, revoked: bool, bound: bool) -> UUID:
            token_id = await conn.fetchval(
                "INSERT INTO api_token "
                "(workspace_id, owner_id, name, token_hash, role, agent_id, revoked_at) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id",
                ws_id,
                owner,
                name,
                f"hash-{name}",
                role,
                agent_id if bound else None,
                datetime.now(UTC) if revoked else None,
            )
            assert isinstance(token_id, UUID)
            return token_id

        active_admin = await _insert("aktiv-admin", "admin", revoked=False, bound=True)
        revoked_admin = await _insert("weg-admin", "admin", revoked=True, bound=True)
        active_editor = await _insert("aktiv-editor", "editor", revoked=False, bound=True)

        # Erst jetzt 0088 — auf einem Bestand, den es vor der Migration gab.
        shutil.copy(MIGRATIONS_DIR / cap_file, tmp_path / cap_file)
        applied = await apply_migrations(conn, tmp_path)
        assert applied == [cap_file]

        async def _role(token_id: UUID) -> str:
            role = await conn.fetchval("SELECT role FROM api_token WHERE id = $1", token_id)
            assert isinstance(role, str)
            return role

        assert await _role(active_admin) == "editor"
        # Der widerrufene bleibt `admin`: ungueltig, und die Rolle ist Historie.
        assert await _role(revoked_admin) == "admin"
        assert await _role(active_editor) == "editor"

        events = await conn.fetch(
            "SELECT target, detail FROM audit_log WHERE action = 'token.role_capped'"
        )
        assert [row["target"] for row in events] == [str(active_admin)]
        detail = json.loads(events[0]["detail"])
        assert detail["from_role"] == "admin"
        assert detail["to_role"] == "editor"
        assert detail["agent_id"] == str(agent_id)

        # Zweiter Lauf: kein weiteres UPDATE, kein zweites Audit-Ereignis. Die
        # Migration laeuft in jeder Umgebung genau einmal, das Statement-Replay
        # belegt die Idempotenz unabhaengig vom Runner-Ledger.
        await conn.execute((MIGRATIONS_DIR / cap_file).read_text(encoding="utf-8"))
        assert await _role(active_admin) == "editor"
        count = await conn.fetchval(
            "SELECT count(*) FROM audit_log WHERE action = 'token.role_capped'"
        )
        assert count == 1

    asyncio.run(_with_isolated_schema(_run))
