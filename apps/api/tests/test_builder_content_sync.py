"""Integrationstest fuer den Builder-Content-Start-Sync (zentrale Verteilung).

`sync_managed_builder_content` hebt managed Builder-Aggregate, deren
`managed_content_version` < `BUILDER_CONTENT_VERSION` liegt, auf den kanonischen
Sidecar-Stand (In-place-Replace des aktiven Versions-Inhalts). Der erste Test
simuliert einen veralteten Builder (Stempel 0 + zerstoerter Inhalt), fuehrt den
Sync und prueft die Wiederherstellung + Idempotenz. Dazu die beiden Sync-
Erweiterungen (Content-Stand 4): Insert-missing legt in `_BUILDER_PLAYBOOKS`
neu ergaenzte Playbooks in Bestands-Workspaces nach, und beim Stempeln werden
die Row-Metadaten (type/tags/triggers) mit verteilt.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import asyncpg
import pytest

from who2be_api.core.config import get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.repositories.workspace_repository import (
    BUILDER_CONTENT_VERSION,
    sync_managed_builder_content,
)
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
                "SELECT pb.name, pv.content ->> 'body' AS body FROM playbook_version pv "
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
                "playbook_body_idsets": {
                    r["name"]: {b["id"] for b in json.loads(r["body"])} for r in playbook_bodies
                },
            }
        finally:
            await conn.close()

    try:
        res = asyncio.run(_run())
    finally:
        cleanup_workspaces([owner])

    # 7 Aggregate aktualisiert (Persona + Template + 5 Playbooks); zweiter Lauf 0.
    assert res["first"] == 7, res["first"]
    assert res["second"] == 0, "Sync muss idempotent sein (Stempel-Guard)."
    assert res["persona_stamp"] == BUILDER_CONTENT_VERSION
    # Kanonischer Inhalt wiederhergestellt (Feedback-Bullets aus den Sidecars).
    assert "bp-li-allowed-fb" in res["persona_block_ids"]
    assert "ab-li-fb" in res["template_body_ids"]
    # Die vier klassischen Playbooks tragen die 0056-Feedback-Sektion; das
    # Pflege-Playbook (Content-Stand 4) hat eine eigene Feedback-Sektion.
    for name, ids in res["playbook_body_idsets"].items():
        if name == "Library-Pflege & Feedback-Lauf":
            assert "pb-maint-h-feedback" in ids
        else:
            assert "pb-feedback-h" in ids, name
    # WP-A (Content-Stand 3): die neuen Builder-Befaehigungs-Sektionen sind
    # nach dem Sync in den jeweiligen Playbook-Bodies vorhanden.
    all_playbook_ids = set().union(*res["playbook_body_idsets"].values())
    # Agent-Playbook: Placeholder-Authoring + ADR-0040-Aufloesung (Templates via MCP).
    assert "pb-agent-h-placeholder" in all_playbook_ids
    assert "pb-agent-code-placeholder" in all_playbook_ids
    # Persona-Playbook: Modi-Sektion inkl. Schema-Beispiel.
    assert "pb-persona-h-modi" in all_playbook_ids
    assert "pb-persona-code-modi" in all_playbook_ids
    # Playbook-Playbook: Token-Spar-Strategie (search + find_usages vor Neuanlage).
    assert "pb-playbook-h-tokens" in all_playbook_ids
    assert "pb-playbook-tokens-search" in all_playbook_ids
    # Konsistenz-Playbook: Template-/Placeholder-Check + Trigger-Normalisierung.
    assert "pb-check-ol-template" in all_playbook_ids
    # Content-Stand 4: Pflege-Playbook mit dabei (Zweck-Sektion aus dem Sidecar).
    assert "pb-maint-h-zweck" in all_playbook_ids


@pytest.mark.integration
def test_sync_inserts_missing_playbook_in_existing_workspace() -> None:
    """Insert-missing: ein v3-Bestands-Workspace (ohne das fuenfte Playbook)
    bekommt „Library-Pflege & Feedback-Lauf" per Sync nachgelegt — Row managed
    + gestempelt, v1 active, persona_playbook-Link zur Builder-Persona."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    name = "Library-Pflege & Feedback-Lauf"

    async def _run() -> dict[str, Any]:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            # Bestands-Workspace auf Content-Stand 3 simulieren: das fuenfte
            # Playbook loeschen (FK-Cascade raeumt Versionen + Links ab).
            await conn.execute(
                "DELETE FROM playbook WHERE workspace_id = $1 AND name = $2", ws, name
            )

            first = await sync_managed_builder_content(conn)
            second = await sync_managed_builder_content(conn)  # idempotent

            row = await conn.fetchrow(
                "SELECT pb.id, pb.is_managed, pb.managed_content_version, pb.type, "
                "  pb.triggers, pb.tags, "
                "  (SELECT v.version FROM playbook_version v "
                "     WHERE v.playbook_id = pb.id AND v.status = 'active') AS active_ver, "
                "  (SELECT v.created_by FROM playbook_version v "
                "     WHERE v.playbook_id = pb.id AND v.status = 'active') AS created_by, "
                "  (SELECT v.locale FROM playbook_version v "
                "     WHERE v.playbook_id = pb.id AND v.status = 'active') AS locale, "
                "  (SELECT v.content ->> 'body' FROM playbook_version v "
                "     WHERE v.playbook_id = pb.id AND v.status = 'active') AS body "
                "FROM playbook pb WHERE pb.workspace_id = $1 AND pb.name = $2",
                ws,
                name,
            )
            link = await conn.fetchval(
                "SELECT count(*) FROM persona_playbook pp "
                "JOIN persona per ON per.id = pp.persona_id "
                "WHERE pp.workspace_id = $1 AND per.name = 'Builder' "
                "AND pp.playbook_id = $2",
                ws,
                row["id"] if row else None,
            )
            return {
                "first": first,
                "second": second,
                "row": dict(row) if row else None,
                "link": link,
            }
        finally:
            await conn.close()

    try:
        res = asyncio.run(_run())
    finally:
        cleanup_workspaces([owner])

    # Genau das fehlende Playbook wurde angelegt; alles andere war aktuell.
    assert res["first"] == 1, res["first"]
    assert res["second"] == 0, "Sync muss idempotent sein (Row existiert + Stempel)."
    row = res["row"]
    assert row is not None, "Fehlendes Playbook wurde nicht angelegt."
    assert row["is_managed"] is True
    assert row["managed_content_version"] == BUILDER_CONTENT_VERSION
    assert row["type"] == "workflow"
    assert "pflege-lauf" in row["triggers"]
    assert "pflege" in row["tags"]
    assert row["active_ver"] == 1, "v1 muss aktiv sein."
    assert row["created_by"] is not None, "created_by = Owner der Builder-Persona."
    assert row["locale"] == "de"
    assert "pb-maint-h-zweck" in {b["id"] for b in json.loads(row["body"])}
    assert res["link"] == 1, "persona_playbook-Link zur Builder-Persona fehlt."


@pytest.mark.integration
def test_sync_updates_playbook_row_metadata() -> None:
    """Metadaten-Drift: geaenderte Trigger/Tags/Type werden beim Stempeln auf
    der Playbook-Row nachgezogen, nicht nur im Versions-Content."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    name = "Konsistenz- & Drift-Check"

    async def _run() -> dict[str, Any]:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            # Veralteten Stand simulieren: alte (kollidierende) Trigger + Tags
            # auf der Row und Stempel zurueckdrehen.
            await conn.execute(
                "UPDATE playbook SET triggers = $2, tags = $3, type = $4, "
                "managed_content_version = 0 WHERE workspace_id = $1 AND name = $5",
                ws,
                "konsistenz, drift, pruefen, aktivierbar, activatable, qualitaetscheck",
                ["alt-tag"],
                "workflow",
                name,
            )

            count = await sync_managed_builder_content(conn)

            row = await conn.fetchrow(
                "SELECT type, tags, triggers, managed_content_version "
                "FROM playbook WHERE workspace_id = $1 AND name = $2",
                ws,
                name,
            )
            return {"count": count, "row": dict(row) if row else None}
        finally:
            await conn.close()

    try:
        res = asyncio.run(_run())
    finally:
        cleanup_workspaces([owner])

    assert res["count"] == 1, res["count"]
    row = res["row"]
    assert row is not None
    assert row["managed_content_version"] == BUILDER_CONTENT_VERSION
    assert row["type"] == "checklist", "Row-Type muss auf den kanonischen Stand zurueck."
    assert row["tags"] == ["konsistenz", "qa", "agent-building"]
    # Kanonische Trigger verteilt; die kollisionstraechtigen Alt-Trigger
    # ("pruefen", "qualitaetscheck") sind weg.
    assert row["triggers"] == (
        "konsistenz, drift, agenten pruefen, library pruefen, agent-drift, aktivierbar, activatable"
    )
