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
import re
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
                "  (tool_policy ->> 'external_tool_write')::boolean AS external_tool_write, "
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

    # 14 Aggregate aktualisiert (Persona + 2 Templates + 8 Playbooks + 1 Resource
    # + 2 Agenten seit Content-Stand 18); zweiter Lauf 0.
    assert res["first"] == 14, res["first"]
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
        # Content-Stand 11: External-Tool-Schreibrecht (ADR-0043) kommt via
        # Policy-Sync auf Bestands-Buildern an.
        assert agent["external_tool_write"] is True, agent
        assert agent["managed_content_version"] == BUILDER_CONTENT_VERSION, agent
    # Kanonischer Inhalt wiederhergestellt (Feedback-Bullets aus den Sidecars).
    assert "bp-li-allowed-fb" in res["persona_block_ids"]
    assert "ab-li-fb" in res["template_body_ids"]
    # Content-Stand 5: die drei Persona-Modi kommen ueber das Content-Replace an.
    assert [m["name"] for m in res["persona_modes"]] == ["Architekt", "Kurator", "Berater"]
    # Content-Stand 5: Resource-Inhalt + Tags wiederhergestellt und gestempelt.
    assert res["resource_stamp"] == BUILDER_CONTENT_VERSION
    assert "res-conv-h-trigger" in res["resource_block_ids"]
    # Content-Stand 11: External-Tools-Sektion in den Konventionen.
    assert "res-conv-h-exttool" in res["resource_block_ids"]
    assert res["resource_tags"] == ["konventionen", "agent-building", "meta"]
    # Die vier klassischen Playbooks tragen die 0056-Feedback-Sektion; Pflege-
    # (Content-Stand 4) und External-Tool-Playbook (Content-Stand 11) haben
    # eigene Feedback-Sektionen, die Lernschleifen-Playbooks (Content-Stand 18)
    # eine Nachhalte-Zeile in den Notes.
    for name, ids in res["playbook_body_idsets"].items():
        if name == "Library-Pflege & Feedback-Lauf":
            assert "pb-maint-h-feedback" in ids
        elif name == "External Tool anlegen & pflegen":
            assert "pb-exttool-h-feedback" in ids
        elif name == "Fall aus Muster & Fall-Triage":
            assert "d7-p81" in ids
        elif name == "Feedback-Gespräch (Review) moderieren":
            assert "fg-p54" in ids
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
    # Content-Stand 11: External-Tool-Playbook mit dabei.
    assert "pb-exttool-h-zweck" in all_playbook_ids


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
            resource_link = await conn.fetchval(
                "SELECT count(*) FROM playbook_resource_link prl "
                "JOIN resource r ON r.id = prl.resource_id "
                "WHERE prl.workspace_id = $1 AND prl.playbook_id = $2 "
                "AND r.name = 'Agent-Bau-Konventionen' AND prl.link_scope = 'resource'",
                ws,
                row["id"] if row else None,
            )
            return {
                "first": first,
                "second": second,
                "row": dict(row) if row else None,
                "link": link,
                "resource_link": resource_link,
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
    # Nachgeruestete Playbooks bekommen den lazy-Pointer auf die Konventions-
    # Resource direkt im Insert-missing (der Resource-Zweig laeuft in
    # Bestands-Workspaces mit vorhandener Resource nicht mehr).
    assert res["resource_link"] == 1, "playbook_resource_link auf die Konventionen fehlt."


@pytest.mark.integration
def test_sync_is_locale_scoped_between_de_and_en_workspaces() -> None:
    """Locale-Scoping (ADR-0045, WP8): der Sync laeuft pro Sprache mit dem
    jeweiligen ContentPack und ist ueber `workspace.content_locale` gescopet —
    EN-Workspaces bekommen EN-Bodies/-Namen zurueck (Content-Restore +
    Insert-missing mit `locale='en'` auf Entity+Version), und es bleedet kein
    Pack in Workspaces der anderen Sprache (keine DE-Pack-Rows im EN-Workspace
    und umgekehrt)."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    owner_de = fresh_user_id()
    owner_en = fresh_user_id()
    ws_de = setup_workspace(owner_de)
    ws_en = setup_workspace(owner_en, content_locale="en")

    en_missing = "Library Maintenance & Feedback Run"
    en_outdated = "Create & Maintain Persona"

    from who2be_api.repositories.builder_content import get_content_pack

    de_names = [p.name for p in get_content_pack("de").playbooks]
    en_names = [p.name for p in get_content_pack("en").playbooks]

    async def _run() -> dict[str, Any]:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            # EN-Workspace praeparieren: ein Playbook fehlt (Insert-missing-Fall),
            # eines ist veraltet (Junk-Body + Stempel 0, Content-Restore-Fall).
            await conn.execute(
                "DELETE FROM playbook WHERE workspace_id = $1 AND name = $2",
                ws_en,
                en_missing,
            )
            await conn.execute(
                "UPDATE playbook_version pv "
                "SET content = jsonb_set(content, '{body}', to_jsonb($2::text)) "
                "FROM playbook pb WHERE pv.playbook_id = pb.id AND pb.workspace_id = $1 "
                "AND pb.name = $3 AND pv.status = 'active'",
                ws_en,
                _JUNK,
                en_outdated,
            )
            await conn.execute(
                "UPDATE playbook SET managed_content_version = 0 "
                "WHERE workspace_id = $1 AND name = $2",
                ws_en,
                en_outdated,
            )

            first = await sync_managed_builder_content(conn)
            second = await sync_managed_builder_content(conn)  # idempotent

            restored_body = await conn.fetchval(
                "SELECT pv.content ->> 'body' FROM playbook_version pv "
                "JOIN playbook pb ON pb.id = pv.playbook_id "
                "WHERE pb.workspace_id = $1 AND pb.name = $2 AND pv.status = 'active'",
                ws_en,
                en_outdated,
            )
            missing_row = await conn.fetchrow(
                "SELECT pb.locale, pb.is_managed, pb.managed_content_version, "
                "  (SELECT v.locale FROM playbook_version v "
                "     WHERE v.playbook_id = pb.id AND v.status = 'active') AS version_locale, "
                "  (SELECT v.content ->> 'body' FROM playbook_version v "
                "     WHERE v.playbook_id = pb.id AND v.status = 'active') AS body "
                "FROM playbook pb WHERE pb.workspace_id = $1 AND pb.name = $2",
                ws_en,
                en_missing,
            )
            de_named_in_en = await conn.fetchval(
                "SELECT count(*) FROM playbook WHERE workspace_id = $1 AND name = ANY($2::text[])",
                ws_en,
                de_names,
            )
            en_named_in_de = await conn.fetchval(
                "SELECT count(*) FROM playbook WHERE workspace_id = $1 AND name = ANY($2::text[])",
                ws_de,
                en_names,
            )
            de_resource_in_en = await conn.fetchval(
                "SELECT count(*) FROM resource "
                "WHERE workspace_id = $1 AND name = 'Agent-Bau-Konventionen'",
                ws_en,
            )
            en_resource_in_de = await conn.fetchval(
                "SELECT count(*) FROM resource "
                "WHERE workspace_id = $1 AND name = 'Agent-Building Conventions'",
                ws_de,
            )
            return {
                "first": first,
                "second": second,
                "restored_body": restored_body,
                "missing_row": dict(missing_row) if missing_row else None,
                "de_named_in_en": de_named_in_en,
                "en_named_in_de": en_named_in_de,
                "de_resource_in_en": de_resource_in_en,
                "en_resource_in_de": en_resource_in_de,
            }
        finally:
            await conn.close()

    try:
        res = asyncio.run(_run())
    finally:
        cleanup_workspaces([owner_de, owner_en])

    # Genau die beiden praeparierten EN-Aggregate wurden angefasst; der
    # (aktuelle) DE-Workspace blieb unberuehrt.
    assert res["first"] == 2, res["first"]
    assert res["second"] == 0, "Sync muss idempotent sein (Stempel-Guard)."

    # Content-Restore stellt den EN-Body wieder her (nicht den DE-Text).
    restored_body = res["restored_body"]
    assert isinstance(restored_body, str)
    assert "CRUD workflow for personas" in restored_body
    assert "junk" not in restored_body

    # Insert-missing im EN-Workspace nutzt EN-Namen und schreibt `locale='en'`
    # explizit auf Entity- UND Versions-Row.
    row = res["missing_row"]
    assert row is not None, "Fehlendes EN-Playbook wurde nicht angelegt."
    assert row["is_managed"] is True
    assert row["managed_content_version"] == BUILDER_CONTENT_VERSION
    assert row["locale"] == "en"
    assert row["version_locale"] == "en"
    assert "Feedback-driven maintenance run across the agent library" in row["body"]

    # Kein Cross-Locale-Bleed: kein DE-Pack-Element im EN-Workspace, keines
    # der EN-Pack-Elemente im DE-Workspace.
    assert res["de_named_in_en"] == 0
    assert res["en_named_in_de"] == 0
    assert res["de_resource_in_en"] == 0
    assert res["en_resource_in_de"] == 0


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
    Builder-Persona) und die acht `playbook_resource_link`s
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
    assert len(links) == 8, "Alle acht Builder-Playbooks muessen verlinkt sein."
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
                "  (tool_policy ->> 'external_tool_write')::boolean AS external_tool_write, "
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
        # Content-Stand 11: External-Tool-Schreibrecht (ADR-0043).
        assert agent["external_tool_write"] is True, agent
        assert agent["agent_read"] == "all", agent


@pytest.mark.integration
def test_sync_v18_links_new_playbooks_and_keeps_existing_links() -> None:
    """Content-Stand 18 (Lernschleife E4b, D7-Risiko): ein Bestands-Workspace
    auf Stempel 17 kennt die beiden Lernschleifen-Playbooks noch nicht.

    Der Sync muss sie anlegen (managed, v1 active, Body = Sidecar) und an die
    Builder-Persona haengen — und zwar additiv: die sechs bisherigen
    Builder-Links und ein vom Owner selbst gesetzter Link auf ein eigenes
    Playbook bleiben mit identischen Playbook-IDs bestehen.

    Die Stempel stehen als Literal auf 17 (Stand vor dem Bump auf 18), nicht
    auf `BUILDER_CONTENT_VERSION - 1`, damit der simulierte Altstand nicht mit
    jedem spaeteren Bump mitwandert. Eine Rot-Probe auf den Bump belegt dieser
    Test nicht: der Insert-missing-Zweig laeuft ohne Stempel-Guard, die
    fehlenden Playbooks kommen also auch ohne Bump an. Er belegt die additive
    Verlinkung und das Anlegen der fehlenden Playbooks.
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    owner = fresh_user_id()
    ws = setup_workspace(owner)

    from who2be_api.repositories.builder_content import get_content_pack, load_sidecar

    pack = get_content_pack("de")
    new_playbooks = [p for p in pack.playbooks if p.key in {"cases", "feedback_session"}]
    assert len(new_playbooks) == 2
    new_names = [p.name for p in new_playbooks]

    async def _run() -> dict[str, Any]:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            # v17-Stand simulieren: die beiden neuen Playbooks fehlen
            # (FK-Cascade raeumt Versionen + Links ab), alle Stempel auf 17.
            await conn.execute(
                "DELETE FROM playbook WHERE workspace_id = $1 AND name = ANY($2::text[])",
                ws,
                new_names,
            )
            for table in ("persona", "playbook", "resource", "agent"):
                await conn.execute(
                    f"UPDATE {table} SET managed_content_version = $2 "  # noqa: S608
                    "WHERE workspace_id = $1 AND is_managed = true",
                    ws,
                    17,
                )
            await conn.execute(
                "UPDATE system_prompt_template SET managed_content_version = $2 "
                "WHERE workspace_id = $1 AND is_managed = true",
                ws,
                17,
            )
            persona_id = await conn.fetchval(
                "SELECT id FROM persona WHERE workspace_id = $1 AND name = 'Builder'", ws
            )
            # Ein vom Owner selbst angelegtes, unverwaltetes Playbook, das er an
            # den Builder gehaengt hat — der Sync darf diesen Link nicht kappen.
            own_id = await conn.fetchval(
                "INSERT INTO playbook (workspace_id, owner_id, name, type, tags, triggers) "
                "VALUES ($1, $2, 'Eigenes Owner-Playbook', 'workflow', '{}', '') "
                "RETURNING id",
                ws,
                owner,
            )
            await conn.execute(
                "INSERT INTO persona_playbook (persona_id, playbook_id, workspace_id, owner_id) "
                "VALUES ($1, $2, $3, $4)",
                persona_id,
                own_id,
                ws,
                owner,
            )
            before = {
                r["playbook_id"]
                for r in await conn.fetch(
                    "SELECT playbook_id FROM persona_playbook WHERE persona_id = $1", persona_id
                )
            }

            await sync_managed_builder_content(conn)

            after_rows = await conn.fetch(
                "SELECT pb.id, pb.name, pb.is_managed, pb.managed_content_version, "
                "  pv.version, pv.status, pv.content ->> 'body' AS body "
                "FROM persona_playbook pp "
                "JOIN playbook pb ON pb.id = pp.playbook_id "
                "LEFT JOIN playbook_version pv "
                "  ON pv.playbook_id = pb.id AND pv.status = 'active' "
                "WHERE pp.persona_id = $1",
                persona_id,
            )
            return {
                "before": before,
                "own_id": own_id,
                "after": [dict(r) for r in after_rows],
            }
        finally:
            await conn.close()

    try:
        res = asyncio.run(_run())
    finally:
        cleanup_workspaces([owner])

    after_ids = {r["id"] for r in res["after"]}
    # 6 bisherige Builder-Links + 1 Owner-Link, unveraendert erhalten.
    assert len(res["before"]) == 7, res["before"]
    assert res["before"] <= after_ids, "Der Sync hat bestehende Persona-Links entfernt."
    assert res["own_id"] in after_ids
    # Dazu genau die zwei neuen, verwalteten Playbooks.
    assert len(after_ids) == 9, [r["name"] for r in res["after"]]
    by_name = {r["name"]: r for r in res["after"]}
    for playbook in new_playbooks:
        row = by_name.get(playbook.name)
        assert row is not None, f"{playbook.name!r} haengt nicht an der Builder-Persona."
        assert row["is_managed"] is True
        assert row["managed_content_version"] == BUILDER_CONTENT_VERSION
        assert (row["version"], row["status"]) == (1, "active")
        assert json.loads(row["body"]) == json.loads(load_sidecar(playbook.sidecar, "de"))


@pytest.mark.integration
def test_sync_distributes_workarea_capabilities_to_v14_builder() -> None:
    """Content-Stand 15 (ADR-0047): ein Bestands-Builder auf Stempel 14 kennt
    `workarea_write`/`kb_write`/`kb_edge_write` nicht — der Sync zieht sie nach.

    Der Stempel steht bewusst als Literal auf 14 (Stand vor dem Bump auf 15),
    nicht auf `BUILDER_CONTENT_VERSION - 1` und nicht auf 0: damit belegt er,
    dass GENAU der Versions-Bump die Verteilung ausloest. Ohne ihn bliebe der
    Stempel-Guard `<` unerfuellt und die neue Policy erreichte kein einziges
    bestehendes Deployment — die Flags waeren nur in frisch geseedeten
    Workspaces vorhanden.
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    owner = fresh_user_id()
    ws = setup_workspace(owner)

    async def _run() -> dict[str, Any]:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            # v14-Stand simulieren: die drei Keys fehlen ganz (so sah die
            # Policy vor ADR-0047 aus), Stempel auf 14 (Stand vor dem Bump).
            await conn.execute(
                "UPDATE agent SET tool_policy = "
                "  tool_policy - 'workarea_write' - 'kb_write' - 'kb_edge_write', "
                "  managed_content_version = $2 "
                "WHERE workspace_id = $1 AND name IN ('Builder', 'Builder-Lite')",
                ws,
                14,
            )
            before = await conn.fetch(
                "SELECT name, tool_policy ? 'workarea_write' AS has_key "
                "FROM agent WHERE workspace_id = $1 "
                "AND name IN ('Builder', 'Builder-Lite') ORDER BY name",
                ws,
            )
            updated = await sync_managed_builder_content(conn)
            rows = await conn.fetch(
                "SELECT name, managed_content_version, "
                "  (tool_policy ->> 'workarea_write')::boolean AS workarea_write, "
                "  (tool_policy ->> 'kb_write')::boolean AS kb_write, "
                "  (tool_policy ->> 'kb_edge_write')::boolean AS kb_edge_write "
                "FROM agent WHERE workspace_id = $1 "
                "AND name IN ('Builder', 'Builder-Lite') ORDER BY name",
                ws,
            )
            return {
                "before": [dict(r) for r in before],
                "updated": updated,
                "agents": [dict(r) for r in rows],
            }
        finally:
            await conn.close()

    try:
        res = asyncio.run(_run())
    finally:
        cleanup_workspaces([owner])

    assert all(row["has_key"] is False for row in res["before"]), res["before"]
    assert res["updated"] == 2, res["updated"]
    for agent in res["agents"]:
        assert agent["managed_content_version"] == BUILDER_CONTENT_VERSION, agent
        assert agent["workarea_write"] is True, agent
        assert agent["kb_write"] is True, agent
        assert agent["kb_edge_write"] is True, agent


# --- Content-Stand 20: Laengen & Wohin (Builder schlank B1) -----------------

# Stabile Anker des Abschnitts; Playbooks laden ihn spaeter gezielt per
# `fetch_resource(block_ids=...)` bzw. `{{resource:<uuid>#<anker>}}` (K4, B3).
_LENGTHS_ANCHORS = (
    "res-conv-h-laengen",
    "res-conv-h-laengen-budgets",
    "res-conv-h-laengen-wohin",
    "res-conv-h-laengen-schreibregeln",
)
# W2 (Owner 2026-10-22): acht Budget-Zeilen; die Zahlen aus Ziel- und Warnspalte.
_W2_BUDGET_ROWS = 8
_W2_NUMBERS = {"400", "600", "150", "250", "3", "5", "1000", "1500", "300", "500", "8", "6", "9"}


def _md_section(blocks: list[dict[str, Any]], anchor: str) -> str:
    """Markdown eines Abschnitts (Anker-Ueberschrift bis zur naechsten gleicher Ebene)."""
    from who2be_api.repositories.playbook_resource_link_repository import block_section_text
    from who2be_models.blocknote_markdown import to_markdown

    ids, _ = block_section_text(blocks, anchor)
    assert ids, f"Anker {anchor!r} fehlt"
    by_id = {b["id"]: b for b in blocks}
    return to_markdown([by_id[i] for i in ids if i in by_id])


def _table_rows(md: str) -> list[list[str]]:
    rows = []
    for line in md.splitlines():
        if line.startswith("| ") and not line.startswith("| ---"):
            rows.append([cell.strip() for cell in line.strip().strip("|").split(" | ")])
    return rows


@pytest.mark.parametrize("locale", ["de", "en"])
def test_conventions_lengths_section_is_one_readable_section(locale: str) -> None:
    """Der Abschnitt ist ueber seinen Anker als eine Einheit ladbar und im
    Markdown-Dialekt (ADR-0058) vollstaendig abbildbar: zwei GFM-Tabellen, vier
    Schreibregeln, keine geschuetzten Marker. Der Rundlauf ueber den Konverter
    ist bitgleich — sonst koennte ein Agent den Abschnitt nicht per
    `edit_content` aendern, ohne ihn zu zerstoeren."""
    from who2be_api.repositories.builder_content import get_content_pack
    from who2be_models.blocknote_markdown import from_markdown, to_markdown

    pack = get_content_pack(locale)
    blocks = json.loads(pack.resource.load_body(locale))
    md = _md_section(blocks, "res-conv-h-laengen")
    for anchor in _LENGTHS_ANCHORS:
        assert f"[#{anchor}]" in md, anchor
    assert "<!-- w2b:" not in md
    budgets = _table_rows(_md_section(blocks, "res-conv-h-laengen-budgets"))
    assert len(budgets) == 1 + _W2_BUDGET_ROWS, budgets
    numbers = {n for row in budgets[1:] for cell in row[1:] for n in re.findall(r"\d+", cell)}
    assert numbers == _W2_NUMBERS, numbers
    placement = _table_rows(_md_section(blocks, "res-conv-h-laengen-wohin"))
    assert len(placement) == 11, placement  # Kopf + 10 Zeilen (Bericht §5.2)
    rules = _md_section(blocks, "res-conv-h-laengen-schreibregeln")
    assert rules.count("\n1. ") == 4, rules
    whole = to_markdown(blocks)
    assert from_markdown(whole, base=blocks, allow_tables=True) == blocks


def test_conventions_lengths_section_matches_across_locales() -> None:
    """DE und EN tragen dieselben Block-IDs in derselben Ordnung und dieselben
    Zahlen in jeder Budget-Zeile — inhaltsgleich, nur uebersetzt."""
    from who2be_api.repositories.builder_content import get_content_pack

    def section(locale: str) -> tuple[list[str], list[list[str]]]:
        pack = get_content_pack(locale)
        blocks = json.loads(pack.resource.load_body(locale))
        from who2be_api.repositories.playbook_resource_link_repository import (
            block_section_text,
        )

        ids, _ = block_section_text(blocks, "res-conv-h-laengen")
        rows = _table_rows(_md_section(blocks, "res-conv-h-laengen-budgets"))
        numbers = [re.findall(r"\d+", " ".join(row[1:])) for row in rows[1:]]
        return ids, numbers

    assert section("de") == section("en")


@pytest.mark.parametrize("locale", ["de", "en"])
def test_budget_numbers_live_only_in_the_conventions(locale: str) -> None:
    """Single Source (Karte B1): die W2-Zahlen stehen genau einmal, in den
    Konventionen. Die Pruefpunkte in Persona-Playbook und Konsistenz-Check
    verweisen per Anker dorthin, statt Zahlen zu wiederholen."""
    from who2be_api.repositories.builder_content import get_content_pack, load_sidecar
    from who2be_models.blocknote_markdown import to_markdown

    pack = get_content_pack(locale)
    unit = r"(?:Woerter|Wörter|words|Zeichen|characters|KB)"
    budget_re = re.compile(r"\b(?:400|600|150|250|1000|1 000|1500|1 500|300|500)\s?" + unit)
    others = [t.sidecar for t in pack.templates] + [
        pack.persona.content_sidecar,
        pack.persona.modes_sidecar,
        *[p.sidecar for p in pack.playbooks],
    ]
    for sidecar in others:
        text = load_sidecar(sidecar, locale)
        assert not budget_re.search(text), f"{locale}/{sidecar}: {budget_re.search(text)}"
    by_key = {p.key: p for p in pack.playbooks}
    for key, block_ids in (
        ("persona", ("pb-persona-li-laengen", "pb-persona-li-laengen-update")),
        ("consistency", ("pb-check-li-persona-laenge", "pb-check-li-pb-laenge")),
    ):
        md = to_markdown(json.loads(by_key[key].load_body(locale)))
        for block_id in block_ids:
            assert block_id in by_key[key].load_body(locale), (key, block_id)
        assert "res-conv-h-laengen" in md, key


@pytest.mark.integration
def test_sync_v20_distributes_lengths_section_and_checkpoints() -> None:
    """Content-Stand 20: ein Bestands-Workspace auf Stempel 19 bekommt den
    Abschnitt „Laengen & Wohin\" und die beiden Pruefpunkte per Sync.

    Der Stempel steht bewusst als Literal auf 19 (Stand vor B1), nicht auf
    `BUILDER_CONTENT_VERSION - 1`: fehlt der Bump auf 20, findet der Sync
    nichts zu tun und der Test wird rot. So belegt er, dass genau der Bump die
    Verteilung ausloest. Der alte Inhalt (ohne Abschnitt) wird vorher
    eingespielt, damit der Sync sichtbar etwas aendert.
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    owner = fresh_user_id()
    ws = setup_workspace(owner)

    from who2be_api.repositories.builder_content import get_content_pack

    pack = get_content_pack("de")
    canonical = json.loads(pack.resource.load_body("de"))
    old_blocks = [b for b in canonical if "laengen" not in b["id"]]
    assert len(old_blocks) < len(canonical)
    by_key = {p.key: p for p in pack.playbooks}

    async def _run() -> dict[str, Any]:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await conn.execute(
                "UPDATE resource_version rv "
                "SET content = jsonb_set(rv.content, '{blocks}', $2::jsonb) "
                "FROM resource r WHERE rv.resource_id = r.id AND r.workspace_id = $1 "
                "AND r.name = 'Agent-Bau-Konventionen' AND rv.status = 'active'",
                ws,
                json.dumps(old_blocks),
            )
            await conn.execute(
                "UPDATE playbook_version pv "
                "SET content = jsonb_set(content, '{body}', to_jsonb($2::text)) "
                "FROM playbook pb WHERE pv.playbook_id = pb.id AND pb.workspace_id = $1 "
                "AND pb.name = ANY($3::text[]) AND pv.status = 'active'",
                ws,
                _JUNK,
                [by_key["persona"].name, by_key["consistency"].name],
            )
            await conn.execute(
                "UPDATE resource SET managed_content_version = $2 "
                "WHERE workspace_id = $1 AND name = 'Agent-Bau-Konventionen'",
                ws,
                19,
            )
            await conn.execute(
                "UPDATE playbook SET managed_content_version = $2 "
                "WHERE workspace_id = $1 AND name = ANY($3::text[])",
                ws,
                19,
                [by_key["persona"].name, by_key["consistency"].name],
            )
            updated = await sync_managed_builder_content(conn)
            again = await sync_managed_builder_content(conn)
            resource = await conn.fetchrow(
                "SELECT r.managed_content_version AS stamp, rv.content -> 'blocks' AS blocks "
                "FROM resource r JOIN resource_version rv "
                "  ON rv.resource_id = r.id AND rv.status = 'active' "
                "WHERE r.workspace_id = $1 AND r.name = 'Agent-Bau-Konventionen'",
                ws,
            )
            bodies = await conn.fetch(
                "SELECT pb.name, pv.content ->> 'body' AS body FROM playbook_version pv "
                "JOIN playbook pb ON pb.id = pv.playbook_id "
                "WHERE pb.workspace_id = $1 AND pb.name = ANY($2::text[]) "
                "AND pv.status = 'active'",
                ws,
                [by_key["persona"].name, by_key["consistency"].name],
            )
            return {
                "updated": updated,
                "again": again,
                "stamp": resource["stamp"],
                "blocks": json.loads(resource["blocks"]),
                "bodies": {r["name"]: json.loads(r["body"]) for r in bodies},
            }
        finally:
            await conn.close()

    try:
        res = asyncio.run(_run())
    finally:
        cleanup_workspaces([owner])

    # Genau die drei zurueckgestempelten Aggregate (1 Resource + 2 Playbooks).
    assert res["updated"] == 3, res["updated"]
    assert res["again"] == 0, "Sync muss idempotent sein (Stempel-Guard)."
    assert res["stamp"] == BUILDER_CONTENT_VERSION
    assert [b["id"] for b in res["blocks"]] == [b["id"] for b in canonical]
    for key, block_id in (
        ("persona", "pb-persona-li-laengen"),
        ("consistency", "pb-check-li-persona-laenge"),
    ):
        body = json.dumps(res["bodies"][by_key[key].name], ensure_ascii=False)
        assert block_id in body, key
        assert "res-conv-h-laengen" in body, key


@pytest.mark.integration
def test_sync_v21_distributes_lean_persona_and_builder_template() -> None:
    """Content-Stand 21 (Builder schlank B2): ein Bestands-Workspace auf
    Stempel 20 bekommt die gestraffte Builder-Persona und das Builder-Template
    ohne `tools-overview`, mit `persona-ref`.

    Der Stempel steht bewusst als Literal auf 20 (Stand vor B2): fehlt der
    Bump auf 21, findet der Sync nichts zu tun und der Test wird rot.
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    owner = fresh_user_id()
    ws = setup_workspace(owner)

    from who2be_api.repositories.builder_content import get_content_pack

    pack = get_content_pack("de")
    canonical_profile = json.loads(pack.persona.load_content("de"))
    template = next(t for t in pack.templates if t.slug == "agent-builder")
    canonical_template = json.loads(template.load_body("de"))

    async def _run() -> dict[str, Any]:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await conn.execute(
                "UPDATE persona_version pv SET content = $2::jsonb "
                "FROM persona p WHERE pv.persona_id = p.id AND p.workspace_id = $1 "
                "AND p.is_managed = true AND pv.status = 'active'",
                ws,
                _JUNK_PERSONA,
            )
            await conn.execute(
                "UPDATE persona SET managed_content_version = 20 "
                "WHERE workspace_id = $1 AND is_managed = true",
                ws,
            )
            await conn.execute(
                "UPDATE system_prompt_template_version tv SET content = $2::jsonb "
                "FROM system_prompt_template t WHERE tv.template_id = t.id "
                "AND t.workspace_id = $1 AND t.slug = 'agent-builder' AND tv.status = 'active'",
                ws,
                json.dumps({"description": "", "body": _JUNK}),
            )
            await conn.execute(
                "UPDATE system_prompt_template SET managed_content_version = 20 "
                "WHERE workspace_id = $1 AND slug = 'agent-builder'",
                ws,
            )
            updated = await sync_managed_builder_content(conn)
            again = await sync_managed_builder_content(conn)
            persona = await conn.fetchrow(
                "SELECT p.managed_content_version AS stamp, pv.content AS content "
                "FROM persona p JOIN persona_version pv "
                "  ON pv.persona_id = p.id AND pv.status = 'active' "
                "WHERE p.workspace_id = $1 AND p.is_managed = true",
                ws,
            )
            tmpl = await conn.fetchrow(
                "SELECT t.managed_content_version AS stamp, tv.content ->> 'body' AS body "
                "FROM system_prompt_template t JOIN system_prompt_template_version tv "
                "  ON tv.template_id = t.id AND tv.status = 'active' "
                "WHERE t.workspace_id = $1 AND t.slug = 'agent-builder'",
                ws,
            )
            return {
                "updated": updated,
                "again": again,
                "persona_stamp": persona["stamp"],
                "persona": json.loads(persona["content"]),
                "template_stamp": tmpl["stamp"],
                "template": json.loads(tmpl["body"]),
            }
        finally:
            await conn.close()

    try:
        res = asyncio.run(_run())
    finally:
        cleanup_workspaces([owner])

    assert res["updated"] == 2, res["updated"]
    assert res["again"] == 0, "Sync muss idempotent sein (Stempel-Guard)."
    assert res["persona_stamp"] == BUILDER_CONTENT_VERSION
    assert res["template_stamp"] == BUILDER_CONTENT_VERSION
    assert res["persona"]["content"]["blocks"] == canonical_profile
    assert res["template"] == canonical_template
    kinds = json.dumps(res["template"])
    assert '"persona-ref"' in kinds
    assert "tools-overview" not in kinds
