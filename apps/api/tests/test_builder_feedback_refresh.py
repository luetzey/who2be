"""Integrationstest fuer Migration 0055 (Builder-Feedback-Refresh, ADR-0038).

Bestehende Workspaces, die den Builder VOR PR #272 geseedet haben, tragen die
Feedback-Bullets nicht (Seed ist skip-if-exists). Migration 0055 zieht sie nach:
haengt den Bullet an den aktiven Persona-/Template-Inhalt an und schreibt eine
NEUE aktive Version (alte -> inactive, current_version gehoben), idempotent per
Block-`id`.

Da zur Migrations-Zeit noch keine Workspaces existieren, simuliert der Test einen
„alten" Builder: er entfernt die (frisch geseedeten) Bullets aus der aktiven
Version und fuehrt dann die 0055-SQL erneut aus.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import asyncpg
import pytest

from who2be_api.core.config import get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace

_MIGRATION_0055 = MIGRATIONS_DIR / "0055_builder_feedback_refresh.sql"
_OLD_BLOCKS = [
    {
        "id": "old-1",
        "type": "paragraph",
        "props": {"textColor": "default", "backgroundColor": "default", "textAlignment": "left"},
        "content": [{"type": "text", "text": "Alt-Inhalt ohne Feedback.", "styles": {}}],
        "children": [],
    }
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


def _prepare_db() -> None:
    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await apply_migrations(conn, MIGRATIONS_DIR)
        finally:
            await conn.close()

    asyncio.run(_run())


@pytest.mark.integration
def test_migration_0055_refreshes_old_builder() -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    migration_sql = _MIGRATION_0055.read_text()

    async def _run() -> dict[str, Any]:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            # 1. „Alten" Builder simulieren: Bullets aus der aktiven Version
            #    entfernen (Blocks ohne bp-li-allowed-fb bzw. Body ohne ab-li-fb).
            old_blocks = json.dumps(_OLD_BLOCKS)
            await conn.execute(
                "UPDATE persona_version pv "
                "SET content = jsonb_set(content, '{content,blocks}', $2::jsonb) "
                "FROM persona p "
                "WHERE pv.persona_id = p.id AND p.workspace_id = $1 "
                "  AND p.name = 'Builder' AND pv.status = 'active'",
                ws,
                old_blocks,
            )
            await conn.execute(
                "UPDATE system_prompt_template_version tv "
                "SET content = jsonb_set(content, '{body}', to_jsonb($2::text)) "
                "FROM system_prompt_template t "
                "WHERE tv.template_id = t.id AND t.workspace_id = $1 "
                "  AND t.slug = 'agent-builder' AND tv.status = 'active'",
                ws,
                old_blocks,
            )

            # 2. Migration 0055 ausfuehren.
            await conn.execute(migration_sql)

            # 3. Persona-Ergebnis lesen.
            prow = await conn.fetchrow(
                "SELECT p.current_version, "
                "  (SELECT count(*) FROM persona_version v "
                "     WHERE v.persona_id = p.id AND v.status = 'active') AS active_count, "
                "  (SELECT v.version FROM persona_version v "
                "     WHERE v.persona_id = p.id AND v.status = 'active' LIMIT 1) AS active_ver, "
                "  (SELECT v.content #> '{content,blocks}' FROM persona_version v "
                "     WHERE v.persona_id = p.id AND v.status = 'active' LIMIT 1) AS active_blocks, "
                "  (SELECT v.status FROM persona_version v "
                "     WHERE v.persona_id = p.id AND v.version = 1 LIMIT 1) AS v1_status "
                "FROM persona p WHERE p.workspace_id = $1 AND p.name = 'Builder'",
                ws,
            )
            trow = await conn.fetchrow(
                "SELECT t.current_version, "
                "  (SELECT count(*) FROM system_prompt_template_version v "
                "     WHERE v.template_id = t.id AND v.status = 'active') AS active_count, "
                "  (SELECT (v.content ->> 'body') FROM system_prompt_template_version v "
                "     WHERE v.template_id = t.id AND v.status = 'active' LIMIT 1) AS active_body, "
                "  (SELECT v.status FROM system_prompt_template_version v "
                "     WHERE v.template_id = t.id AND v.version = 1 LIMIT 1) AS v1_status "
                "FROM system_prompt_template t "
                "WHERE t.workspace_id = $1 AND t.slug = 'agent-builder'",
                ws,
            )

            # 4. Idempotenz: zweiter Lauf erzeugt keine weitere Version.
            await conn.execute(migration_sql)
            persona_versions = await conn.fetchval(
                "SELECT count(*) FROM persona_version v JOIN persona p ON p.id = v.persona_id "
                "WHERE p.workspace_id = $1 AND p.name = 'Builder'",
                ws,
            )
            return {
                "p": dict(prow) if prow else {},
                "t": dict(trow) if trow else {},
                "persona_versions": persona_versions,
            }
        finally:
            await conn.close()

    try:
        res = asyncio.run(_run())
    finally:
        cleanup_workspaces([owner])

    p = res["p"]
    assert p["active_count"] == 1, "Genau eine aktive Persona-Version erwartet."
    assert p["active_ver"] == 2, "Neue aktive Version sollte v2 sein."
    assert p["current_version"] == 2, "current_version muss auf v2 zeigen."
    assert p["v1_status"] == "inactive", "Alte v1 muss inaktiviert sein."
    # Roher asyncpg-Connect ohne jsonb-Codec → die jsonb-Spalte kommt als String.
    block_ids = {b["id"] for b in json.loads(p["active_blocks"])}
    assert "bp-li-allowed-fb" in block_ids, "Feedback-Bullet fehlt in der Persona."
    assert "old-1" in block_ids, "Bestandsinhalt darf nicht verloren gehen (append-only)."

    t = res["t"]
    assert t["active_count"] == 1
    assert t["current_version"] == 2
    assert t["v1_status"] == "inactive"
    body_ids = {b["id"] for b in json.loads(t["active_body"])}
    assert "ab-li-fb" in body_ids, "Feedback-Bullet fehlt im Template-Body."
    assert "old-1" in body_ids, "Bestands-Body darf nicht verloren gehen (append-only)."

    # Idempotenz: nach dem zweiten Lauf weiterhin genau 2 Persona-Versionen.
    assert res["persona_versions"] == 2, "Zweiter Migrationslauf darf keine v3 erzeugen."
