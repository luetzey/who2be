"""Integrationstest fuer Migration 0056 (Builder-Playbook-Feedback, ADR-0038).

Analog zu 0055, aber fuer die vier Builder-Playbooks: bestehende Workspaces
(Seed skip-if-exists) bekommen den Feedback-Hinweis nicht. 0056 haengt eine
„Feedback"-Sektion an den aktiven Body an und schreibt eine neue aktive Version
(append-only, idempotent per Block-id `pb-feedback-h`).

Der Test simuliert „alte" Playbooks: er entfernt die (frisch geseedete) Sektion
aus dem aktiven Body und fuehrt 0056 erneut aus.
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

_MIGRATION_0056 = MIGRATIONS_DIR / "0056_builder_playbook_feedback.sql"
_BUILDER_PLAYBOOKS = [
    "Persona anlegen & pflegen",
    "Playbook anlegen & pflegen",
    "Agent anlegen & pflegen",
    "Konsistenz- & Drift-Check",
]
_OLD_BODY = json.dumps(
    [
        {
            "id": "old-pb",
            "type": "paragraph",
            "props": {
                "textColor": "default",
                "backgroundColor": "default",
                "textAlignment": "left",
            },
            "content": [{"type": "text", "text": "Alt-Body ohne Feedback.", "styles": {}}],
            "children": [],
        }
    ]
)


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
def test_migration_0056_refreshes_builder_playbooks() -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    migration_sql = _MIGRATION_0056.read_text()

    async def _run() -> dict[str, Any]:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            # „Alte" Builder-Playbooks simulieren: Feedback-Sektion entfernen.
            await conn.execute(
                "UPDATE playbook_version pv "
                "SET content = jsonb_set(content, '{body}', to_jsonb($3::text)) "
                "FROM playbook pb "
                "WHERE pv.playbook_id = pb.id AND pb.workspace_id = $1 "
                "  AND pb.name = ANY($2::text[]) AND pv.status = 'active'",
                ws,
                _BUILDER_PLAYBOOKS,
                _OLD_BODY,
            )

            await conn.execute(migration_sql)

            rows = await conn.fetch(
                "SELECT pb.name, pb.current_version, "
                "  (SELECT count(*) FROM playbook_version v "
                "     WHERE v.playbook_id = pb.id AND v.status = 'active') AS active_count, "
                "  (SELECT v.version FROM playbook_version v "
                "     WHERE v.playbook_id = pb.id AND v.status = 'active' LIMIT 1) AS active_ver, "
                "  (SELECT (v.content ->> 'body') FROM playbook_version v "
                "     WHERE v.playbook_id = pb.id AND v.status = 'active' LIMIT 1) AS active_body, "
                "  (SELECT count(*) FROM playbook_version v WHERE v.playbook_id = pb.id) AS total "
                "FROM playbook pb WHERE pb.workspace_id = $1 AND pb.name = ANY($2::text[])",
                ws,
                _BUILDER_PLAYBOOKS,
            )

            # Idempotenz: zweiter Lauf erzeugt keine weitere Version.
            await conn.execute(migration_sql)
            totals_after = await conn.fetch(
                "SELECT count(*) AS total FROM playbook_version v "
                "JOIN playbook pb ON pb.id = v.playbook_id "
                "WHERE pb.workspace_id = $1 AND pb.name = ANY($2::text[]) "
                "GROUP BY pb.id",
                ws,
                _BUILDER_PLAYBOOKS,
            )
            return {
                "rows": [dict(r) for r in rows],
                "totals_after": [r["total"] for r in totals_after],
            }
        finally:
            await conn.close()

    try:
        res = asyncio.run(_run())
    finally:
        cleanup_workspaces([owner])

    rows = res["rows"]
    assert len(rows) == 4, "Alle vier Builder-Playbooks erwartet."
    for r in rows:
        assert r["active_count"] == 1, f"{r['name']}: genau eine aktive Version erwartet."
        assert r["active_ver"] == 2, f"{r['name']}: neue aktive Version sollte v2 sein."
        assert r["current_version"] == 2, f"{r['name']}: current_version muss v2 sein."
        body_ids = {b["id"] for b in json.loads(r["active_body"])}
        assert "pb-feedback-h" in body_ids, f"{r['name']}: Feedback-Sektion fehlt."
        assert "old-pb" in body_ids, f"{r['name']}: Bestands-Body verloren (append-only)."

    # Idempotenz: jedes Playbook hat danach genau 2 Versionen (kein v3).
    assert all(t == 2 for t in res["totals_after"]), "Zweiter Lauf erzeugte eine v3."
