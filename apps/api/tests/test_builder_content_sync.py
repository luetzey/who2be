"""Integrationstest fuer den Builder-Content-Start-Sync (zentrale Verteilung).

`sync_managed_builder_content` hebt managed Builder-Aggregate, deren
`managed_content_version` < `BUILDER_CONTENT_VERSION` liegt, auf den kanonischen
Sidecar-Stand (In-place-Replace des aktiven Versions-Inhalts). Der Test
simuliert einen veralteten Builder (Stempel 0 + zerstoerter Inhalt), fuehrt den
Sync und prueft die Wiederherstellung + Idempotenz.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import asyncpg
import pytest

from who2be_api.core.config import get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.repositories.workspace_repository import sync_managed_builder_content
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace

_JUNK = json.dumps(
    [{"id": "junk", "type": "paragraph", "props": {}, "content": [], "children": []}]
)
_JUNK_PERSONA = json.dumps(
    {
        "description": "x",
        "traits": [],
        "tags": [],
        "content": {"description": "", "blocks": []},
        "modes": [],
        "skills": [],
    }
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
def test_sync_restores_outdated_builder() -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    owner = fresh_user_id()
    ws = setup_workspace(owner)

    async def _run() -> dict[str, Any]:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            # Veralteten Builder simulieren: aktiven Inhalt zerstoeren + Stempel 0.
            await conn.execute(
                "UPDATE persona_version pv SET content = $2::jsonb FROM persona p "
                "WHERE pv.persona_id = p.id AND p.workspace_id = $1 AND p.name = 'Builder' "
                "AND pv.status = 'active'",
                ws,
                _JUNK_PERSONA,
            )
            await conn.execute(
                "UPDATE persona SET managed_content_version = 0 "
                "WHERE workspace_id = $1 AND name = 'Builder'",
                ws,
            )
            await conn.execute(
                "UPDATE system_prompt_template_version tv "
                "SET content = jsonb_set(content, '{body}', to_jsonb($2::text)) "
                "FROM system_prompt_template t "
                "WHERE tv.template_id = t.id AND t.workspace_id = $1 "
                "AND t.slug = 'agent-builder' AND tv.status = 'active'",
                ws,
                _JUNK,
            )
            await conn.execute(
                "UPDATE system_prompt_template SET managed_content_version = 0 "
                "WHERE workspace_id = $1 AND slug = 'agent-builder'",
                ws,
            )
            await conn.execute(
                "UPDATE playbook_version pv "
                "SET content = jsonb_set(content, '{body}', to_jsonb($2::text)) "
                "FROM playbook pb WHERE pv.playbook_id = pb.id AND pb.workspace_id = $1 "
                "AND pb.is_managed = true AND pv.status = 'active'",
                ws,
                _JUNK,
            )
            await conn.execute(
                "UPDATE playbook SET managed_content_version = 0 "
                "WHERE workspace_id = $1 AND is_managed = true",
                ws,
            )

            first = await sync_managed_builder_content(conn)
            second = await sync_managed_builder_content(conn)  # idempotent

            persona_blocks = await conn.fetchval(
                "SELECT pv.content #> '{content,blocks}' FROM persona_version pv "
                "JOIN persona p ON p.id = pv.persona_id "
                "WHERE p.workspace_id = $1 AND p.name = 'Builder' AND pv.status = 'active'",
                ws,
            )
            persona_stamp = await conn.fetchval(
                "SELECT managed_content_version FROM persona "
                "WHERE workspace_id = $1 AND name = 'Builder'",
                ws,
            )
            template_body = await conn.fetchval(
                "SELECT tv.content ->> 'body' FROM system_prompt_template_version tv "
                "JOIN system_prompt_template t ON t.id = tv.template_id "
                "WHERE t.workspace_id = $1 AND t.slug = 'agent-builder' AND tv.status = 'active'",
                ws,
            )
            playbook_bodies = await conn.fetch(
                "SELECT pv.content ->> 'body' AS body FROM playbook_version pv "
                "JOIN playbook pb ON pb.id = pv.playbook_id "
                "WHERE pb.workspace_id = $1 AND pb.is_managed = true AND pv.status = 'active'",
                ws,
            )
            return {
                "first": first,
                "second": second,
                "persona_block_ids": {b["id"] for b in json.loads(persona_blocks)},
                "persona_stamp": persona_stamp,
                "template_body_ids": {b["id"] for b in json.loads(template_body)},
                "playbook_body_idsets": [
                    {b["id"] for b in json.loads(r["body"])} for r in playbook_bodies
                ],
            }
        finally:
            await conn.close()

    try:
        res = asyncio.run(_run())
    finally:
        cleanup_workspaces([owner])

    # 6 Aggregate aktualisiert (Persona + Template + 4 Playbooks); zweiter Lauf 0.
    assert res["first"] == 6, res["first"]
    assert res["second"] == 0, "Sync muss idempotent sein (Stempel-Guard)."
    assert res["persona_stamp"] == 1
    # Kanonischer Inhalt wiederhergestellt (Feedback-Bullets aus den Sidecars).
    assert "bp-li-allowed-fb" in res["persona_block_ids"]
    assert "ab-li-fb" in res["template_body_ids"]
    for ids in res["playbook_body_idsets"]:
        assert "pb-feedback-h" in ids
