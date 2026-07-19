"""Integrationstest fuer den Builder-Content-Start-Sync (zentrale Verteilung).

`sync_managed_builder_content` hebt managed Builder-Aggregate, deren
`managed_content_version` < `BUILDER_CONTENT_VERSION` liegt, auf den kanonischen
Sidecar-Stand (In-place-Replace des aktiven Versions-Inhalts). Der erste Test
simuliert einen veralteten Builder (Stempel 0 + zerstoerter Inhalt), fuehrt den
Sync und prueft die Wiederherstellung + Idempotenz. Dazu die Sync-
Erweiterungen: Insert-missing legt in `_BUILDER_PLAYBOOKS` neu ergaenzte
Playbooks in Bestands-Workspaces nach, beim Stempeln werden die Playbook-
Row-Metadaten (type/tags/triggers) mit verteilt (Content-Stand 4), und die
Managed-Resource „Agent-Bau-Konventionen" wird per Content-Update bzw.
Insert-missing samt `playbook_resource_link`s verteilt; die Persona-Modi
(Architekt/Kurator/Berater) kommen ueber das Persona-Content-Replace in
Bestands-Personas an (Content-Stand 5). Seit Content-Stand 6 zieht der Sync
auch die AGENT-Rows nach: die tool_policy der Builder-Agenten
(Builder/Builder-Lite) wird bei Stempel-Rueckstand auf den kanonischen Stand
ersetzt (`feedback_resolve` erreicht so Bestands-Builder).
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
_JUNK_RESOURCE = json.dumps({"description": "x", "blocks": [], "tags": []})


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
                "UPDATE system_prompt_template_version tv "
                "SET content = jsonb_set(content, '{body}', to_jsonb($2::text)) "
                "FROM system_prompt_template t "
                "WHERE tv.template_id = t.id AND t.workspace_id = $1 "
                "AND t.slug = 'agent-builder-lite' AND tv.status = 'active'",
                ws,
                _JUNK,
            )
            await conn.execute(
                "UPDATE system_prompt_template SET managed_content_version = 0 "
                "WHERE workspace_id = $1 AND slug = 'agent-builder-lite'",
                ws,
            )
            await conn.execute(
                "UPDATE resource_version rv SET content = $2::jsonb FROM resource r "
                "WHERE rv.resource_id = r.id AND r.workspace_id = $1 "
                "AND r.name = 'Agent-Bau-Konventionen' AND rv.status = 'active'",
                ws,
                _JUNK_RESOURCE,
            )
            await conn.execute(
                "UPDATE resource SET managed_content_version = 0 "
                "WHERE workspace_id = $1 AND name = 'Agent-Bau-Konventionen'",
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
            # Veraltete Agenten simulieren: `feedback_resolve` aus der Policy
            # entfernen (Stand vor Content-Stand 6) + Stempel 0.
            await conn.execute(
                "UPDATE agent SET tool_policy = tool_policy - 'feedback_resolve', "
                "managed_content_version = 0 "
                "WHERE workspace_id = $1 AND is_managed = true "
                "AND name IN ('Builder', 'Builder-Lite')",
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
            persona_modes = await conn.fetchval(
                "SELECT pv.content -> 'modes' FROM persona_version pv "
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
            resource_row = await conn.fetchrow(
                "SELECT r.managed_content_version, rv.content -> 'blocks' AS blocks, "
                "  rv.content -> 'tags' AS tags "
                "FROM resource r "
                "JOIN resource_version rv "
                "  ON rv.resource_id = r.id AND rv.status = 'active' "
                "WHERE r.workspace_id = $1 AND r.name = 'Agent-Bau-Konventionen'",
                ws,
            )
            agent_rows = await conn.fetch(
                "SELECT name, managed_content_version, "
                "  (tool_policy ->> 'feedback_resolve')::boolean AS feedback_resolve, "
                "  tool_policy ->> 'memory_mode' AS memory_mode, "
                "  tool_policy ->> 'memory_directive' AS memory_directive "
                "FROM agent WHERE workspace_id = $1 AND is_managed = true "
                "AND name IN ('Builder', 'Builder-Lite') ORDER BY name",
                ws,
            )
            return {
                "first": first,
                "second": second,
                "persona_block_ids": {b["id"] for b in json.loads(persona_blocks)},
                "persona_modes": json.loads(persona_modes),
                "persona_stamp": persona_stamp,
                "template_body_ids": {b["id"] for b in json.loads(template_body)},
                "playbook_body_idsets": {
                    r["name"]: {b["id"] for b in json.loads(r["body"])} for r in playbook_bodies
                },
                "resource_stamp": resource_row["managed_content_version"],
                "resource_block_ids": {b["id"] for b in json.loads(resource_row["blocks"])},
                "resource_tags": json.loads(resource_row["tags"]),
                "agents": [dict(r) for r in agent_rows],
            }
        finally:
            await conn.close()

    try:
        res = asyncio.run(_run())
    finally:
        cleanup_workspaces([owner])

    # 11 Aggregate aktualisiert (Persona + 2 Templates + 5 Playbooks + 1 Resource
    # + 2 Agenten seit Content-Stand 6); zweiter Lauf 0.
    assert res["first"] == 11, res["first"]
    assert res["second"] == 0, "Sync muss idempotent sein (Stempel-Guard)."
    assert res["persona_stamp"] == BUILDER_CONTENT_VERSION
    # Content-Stand 6: die kanonische Policy (inkl. feedback_resolve) und der
    # Stempel kommen auf beiden Builder-Agenten an.
    assert [a["name"] for a in res["agents"]] == ["Builder", "Builder-Lite"]
    for agent in res["agents"]:
        assert agent["feedback_resolve"] is True, agent
        # Content-Stand 10: Builder-Gedaechtnis in der Kurations-Stufe
        # (suggest + recommended) erreicht Bestands-Builder via Policy-Sync.
        assert agent["memory_mode"] == "suggest", agent
        assert agent["memory_directive"] == "recommended", agent
        assert agent["managed_content_version"] == BUILDER_CONTENT_VERSION, agent
    # Kanonischer Inhalt wiederhergestellt (Feedback-Bullets aus den Sidecars).
    assert "bp-li-allowed-fb" in res["persona_block_ids"]
    assert "ab-li-fb" in res["template_body_ids"]
    # Content-Stand 5: die drei Persona-Modi kommen ueber das Content-Replace an.
    assert [m["name"] for m in res["persona_modes"]] == ["Architekt", "Kurator", "Berater"]
    # Content-Stand 5: Resource-Inhalt + Tags wiederhergestellt und gestempelt.
    assert res["resource_stamp"] == BUILDER_CONTENT_VERSION
    assert "res-conv-h-trigger" in res["resource_block_ids"]
    assert res["resource_tags"] == ["konventionen", "agent-building", "meta"]
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


@pytest.mark.integration
def test_sync_inserts_missing_resource_in_existing_workspace() -> None:
    """Insert-missing (Content-Stand 5): ein v4-Bestands-Workspace (ohne die
    Managed-Resource) bekommt „Agent-Bau-Konventionen" per Sync nachgelegt —
    Row managed + gestempelt, v1 active (locale 'de', created_by = Owner der
    Builder-Persona) und die fuenf `playbook_resource_link`s
    (link_scope='resource') von allen Builder-Playbooks."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    name = "Agent-Bau-Konventionen"

    async def _run() -> dict[str, Any]:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            # Bestands-Workspace auf Content-Stand 4 simulieren: die Resource
            # loeschen (FK-Cascade raeumt Versionen + Links ab).
            await conn.execute(
                "DELETE FROM resource WHERE workspace_id = $1 AND name = $2", ws, name
            )

            first = await sync_managed_builder_content(conn)
            second = await sync_managed_builder_content(conn)  # idempotent

            row = await conn.fetchrow(
                "SELECT r.id, r.is_managed, r.managed_content_version, "
                "  (SELECT v.version FROM resource_version v "
                "     WHERE v.resource_id = r.id AND v.status = 'active') AS active_ver, "
                "  (SELECT v.created_by FROM resource_version v "
                "     WHERE v.resource_id = r.id AND v.status = 'active') AS created_by, "
                "  (SELECT v.locale FROM resource_version v "
                "     WHERE v.resource_id = r.id AND v.status = 'active') AS locale, "
                "  (SELECT v.content -> 'blocks' FROM resource_version v "
                "     WHERE v.resource_id = r.id AND v.status = 'active') AS blocks, "
                "  (SELECT v.content -> 'tags' FROM resource_version v "
                "     WHERE v.resource_id = r.id AND v.status = 'active') AS tags "
                "FROM resource r WHERE r.workspace_id = $1 AND r.name = $2",
                ws,
                name,
            )
            links = await conn.fetch(
                "SELECT prl.link_scope, prl.block_id, pb.name AS playbook_name, "
                "  pb.is_managed AS playbook_managed "
                "FROM playbook_resource_link prl "
                "JOIN playbook pb ON pb.id = prl.playbook_id "
                "WHERE prl.workspace_id = $1 AND prl.resource_id = $2",
                ws,
                row["id"] if row else None,
            )
            return {
                "first": first,
                "second": second,
                "row": dict(row) if row else None,
                "links": [dict(link) for link in links],
            }
        finally:
            await conn.close()

    try:
        res = asyncio.run(_run())
    finally:
        cleanup_workspaces([owner])

    # Genau die fehlende Resource wurde angelegt; alles andere war aktuell.
    assert res["first"] == 1, res["first"]
    assert res["second"] == 0, "Sync muss idempotent sein (Row existiert + Stempel)."
    row = res["row"]
    assert row is not None, "Fehlende Resource wurde nicht angelegt."
    assert row["is_managed"] is True
    assert row["managed_content_version"] == BUILDER_CONTENT_VERSION
    assert row["active_ver"] == 1, "v1 muss aktiv sein."
    assert row["created_by"] is not None, "created_by = Owner der Builder-Persona."
    assert row["locale"] == "de"
    assert "res-conv-h-trigger" in {b["id"] for b in json.loads(row["blocks"])}
    assert json.loads(row["tags"]) == ["konventionen", "agent-building", "meta"]
    links = res["links"]
    assert len(links) == 5, "Alle fuenf Builder-Playbooks muessen verlinkt sein."
    assert all(link["link_scope"] == "resource" for link in links)
    assert all(link["block_id"] is None for link in links)
    assert all(link["playbook_managed"] is True for link in links)


@pytest.mark.integration
def test_sync_distributes_persona_modes_to_existing_persona() -> None:
    """Modi-Verteilung (Content-Stand 5): eine Bestands-Builder-Persona mit
    altem Content OHNE `modes`-Feld bekommt per Sync die drei kanonischen Modi
    (Architekt default ohne Trigger, Kurator, Berater)."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    owner = fresh_user_id()
    ws = setup_workspace(owner)

    # Alt-Schema-Content (vor Gap 3.4): gar kein `modes`-Key — der Sync ersetzt
    # den aktiven Versions-Inhalt wholesale, nicht feldweise.
    old_content = json.dumps(
        {
            "description": "alt",
            "traits": [],
            "tags": [],
            "content": {"description": "", "blocks": []},
            "skills": [],
        }
    )

    async def _run() -> dict[str, Any]:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await conn.execute(
                "UPDATE persona_version pv SET content = $2::jsonb FROM persona p "
                "WHERE pv.persona_id = p.id AND p.workspace_id = $1 AND p.name = 'Builder' "
                "AND pv.status = 'active'",
                ws,
                old_content,
            )
            await conn.execute(
                "UPDATE persona SET managed_content_version = 0 "
                "WHERE workspace_id = $1 AND name = 'Builder'",
                ws,
            )

            count = await sync_managed_builder_content(conn)

            modes_json = await conn.fetchval(
                "SELECT pv.content -> 'modes' FROM persona_version pv "
                "JOIN persona p ON p.id = pv.persona_id "
                "WHERE p.workspace_id = $1 AND p.name = 'Builder' AND pv.status = 'active'",
                ws,
            )
            stamp = await conn.fetchval(
                "SELECT managed_content_version FROM persona "
                "WHERE workspace_id = $1 AND name = 'Builder'",
                ws,
            )
            return {"count": count, "modes": json.loads(modes_json), "stamp": stamp}
        finally:
            await conn.close()

    try:
        res = asyncio.run(_run())
    finally:
        cleanup_workspaces([owner])

    assert res["count"] == 1, res["count"]
    assert res["stamp"] == BUILDER_CONTENT_VERSION
    modes = res["modes"]
    assert [m["name"] for m in modes] == ["Architekt", "Kurator", "Berater"]
    defaults = [m for m in modes if m["is_default"]]
    assert len(defaults) == 1 and defaults[0]["name"] == "Architekt"
    assert defaults[0]["trigger"] is None, "Der Default-Modus traegt keinen Trigger."
    # Kurator bindet das Pflege-Playbook bewusst in Prosa, nicht via playbook_id
    # (UUIDs sind workspace-spezifisch, kanonischer Content bleibt identisch).
    assert all(m.get("playbook_id") is None for m in modes)


@pytest.mark.integration
def test_sync_updates_agent_policy_of_existing_builder() -> None:
    """Policy-Verteilung (Content-Stand 6): Bestands-Builder-Agenten mit alter
    tool_policy (`feedback_resolve` fehlt bzw. explizit false) und altem Stempel
    bekommen per Sync die kanonische Policy (feedback_resolve=True, Writes/Reads
    unveraendert breit) + Stempel `BUILDER_CONTENT_VERSION`; zweiter Lauf 0."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    owner = fresh_user_id()
    ws = setup_workspace(owner)

    async def _run() -> dict[str, Any]:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            # Alt-Stand simulieren, beide Vor-v6-Formen: beim Builder fehlt der
            # Key ganz (Policy von vor ADR-0038-Erweiterung), beim Builder-Lite
            # steht er explizit auf false.
            await conn.execute(
                "UPDATE agent SET tool_policy = tool_policy - 'feedback_resolve', "
                "managed_content_version = 0 "
                "WHERE workspace_id = $1 AND name = 'Builder'",
                ws,
            )
            await conn.execute(
                "UPDATE agent SET tool_policy = "
                "jsonb_set(tool_policy, '{feedback_resolve}', 'false'::jsonb), "
                "managed_content_version = 0 "
                "WHERE workspace_id = $1 AND name = 'Builder-Lite'",
                ws,
            )

            first = await sync_managed_builder_content(conn)
            second = await sync_managed_builder_content(conn)  # idempotent

            rows = await conn.fetch(
                "SELECT name, is_managed, managed_content_version, "
                "  (tool_policy ->> 'feedback_resolve')::boolean AS feedback_resolve, "
                "  (tool_policy ->> 'agent_write')::boolean AS agent_write, "
                "  (tool_policy ->> 'promote_retire')::boolean AS promote_retire, "
                "  tool_policy ->> 'agent_read' AS agent_read "
                "FROM agent WHERE workspace_id = $1 "
                "AND name IN ('Builder', 'Builder-Lite') ORDER BY name",
                ws,
            )
            return {
                "first": first,
                "second": second,
                "agents": [dict(r) for r in rows],
            }
        finally:
            await conn.close()

    try:
        res = asyncio.run(_run())
    finally:
        cleanup_workspaces([owner])

    # Genau die beiden Agent-Rows wurden nachgezogen; alles andere war aktuell.
    assert res["first"] == 2, res["first"]
    assert res["second"] == 0, "Sync muss idempotent sein (Stempel-Guard)."
    assert [a["name"] for a in res["agents"]] == ["Builder", "Builder-Lite"]
    for agent in res["agents"]:
        assert agent["is_managed"] is True
        assert agent["managed_content_version"] == BUILDER_CONTENT_VERSION, agent
        assert agent["feedback_resolve"] is True, agent
        # Wholesale-Replace auf die kanonische Policy — die breiten
        # Meta-Agent-Rechte bleiben erhalten.
        assert agent["agent_write"] is True, agent
        assert agent["promote_retire"] is True, agent
        assert agent["agent_read"] == "all", agent
