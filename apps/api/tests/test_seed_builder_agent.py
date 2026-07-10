"""Integrationstests fuer den Default-Agenten „Builder" (Welle 3).

Deckt den Seed ab, der bei jeder Workspace-Anlage laeuft
(`_seed_default_agents` in `workspace_repository.py`, gespiegelt von Migration
0047):

1. Vollstaendigkeit: nach `setup_workspace` existieren Persona „Builder" (v1
   active, drei Modi: Architekt default/Kurator/Berater), fuenf Playbooks (v1
   active), fuenf persona_playbook-Links, die Managed-Resource
   „Agent-Bau-Konventionen" (v1 active) samt fuenf
   `playbook_resource_link`s (link_scope='resource'), das Template
   `agent-builder` (active) und der Agent „Builder" (enabled, write-faehige
   tool_policy, Persona + Template verdrahtet).
2. Idempotenz: ein zweiter Seed-Lauf erzeugt keine Duplikate.
3. Render: der `GET .../agents/{id}/rendered`-Endpoint expandiert den Prompt
   ohne offene Persona-Platzhalter (Persona-Name aufgeloest).

Laeuft nur mit erreichbarer Datenbank; ohne DB werden die Tests uebersprungen.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

import asyncpg
import jwt
import pytest
from fastapi.testclient import TestClient

from who2be_api.core import security
from who2be_api.core.config import Settings, get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.main import app
from who2be_api.repositories.workspace_repository import BUILDER_CONTENT_VERSION
from who2be_api.testing.workspace_setup import (
    cleanup_workspaces,
    fresh_user_id,
    setup_workspace,
)

_TEST_SECRET = "integration-test-jwt-secret-padding-0123456789"

# Muss exakt zu den Namen in `_BUILDER_PLAYBOOKS` passen (die ersten vier
# spiegeln Migration 0047; Neuere kommen per Start-Sync in Bestands-Workspaces).
_BUILDER_PLAYBOOK_NAMES = [
    "Persona anlegen & pflegen",
    "Playbook anlegen & pflegen",
    "Agent anlegen & pflegen",
    "Konsistenz- & Drift-Check",
    "Library-Pflege & Feedback-Lauf",
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


def _auth(owner_id: UUID) -> dict[str, str]:
    token = jwt.encode(
        {
            "sub": str(owner_id),
            "aud": "authenticated",
            "role": "authenticated",
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        _TEST_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.integration
def test_builder_agent_seeded_complete() -> None:
    """Nach Workspace-Anlage ist der Builder vollstaendig und aktivierbar geseedet."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    owner = fresh_user_id()
    ws = setup_workspace(owner)

    async def _check(workspace_id: UUID) -> dict[str, object]:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            persona = await conn.fetchrow(
                "SELECT p.current_version, pv.status, pv.content -> 'modes' AS modes "
                "FROM persona p "
                "JOIN persona_version pv "
                "  ON pv.persona_id = p.id AND pv.version = p.current_version "
                "WHERE p.workspace_id = $1 AND p.name = 'Builder'",
                workspace_id,
            )
            playbooks_active = await conn.fetchval(
                "SELECT count(*) FROM playbook pb "
                "JOIN playbook_version pv "
                "  ON pv.playbook_id = pb.id AND pv.version = pb.current_version "
                "WHERE pb.workspace_id = $1 AND pv.status = 'active' "
                "  AND pb.name = ANY($2::text[])",
                workspace_id,
                _BUILDER_PLAYBOOK_NAMES,
            )
            links = await conn.fetchval(
                "SELECT count(*) FROM persona_playbook pp "
                "JOIN persona p ON p.id = pp.persona_id "
                "WHERE pp.workspace_id = $1 AND p.name = 'Builder'",
                workspace_id,
            )
            template_status = await conn.fetchval(
                "SELECT tv.status FROM system_prompt_template t "
                "JOIN system_prompt_template_version tv "
                "  ON tv.template_id = t.id AND tv.version = t.current_version "
                "WHERE t.workspace_id = $1 AND t.slug = 'agent-builder'",
                workspace_id,
            )
            resource = await conn.fetchrow(
                "SELECT r.is_managed, r.managed_content_version, rv.status, rv.locale "
                "FROM resource r "
                "JOIN resource_version rv "
                "  ON rv.resource_id = r.id AND rv.version = 1 "
                "WHERE r.workspace_id = $1 AND r.name = 'Agent-Bau-Konventionen'",
                workspace_id,
            )
            resource_links = await conn.fetch(
                "SELECT prl.link_scope, prl.block_id FROM playbook_resource_link prl "
                "JOIN resource r ON r.id = prl.resource_id "
                "WHERE prl.workspace_id = $1 AND r.name = 'Agent-Bau-Konventionen'",
                workspace_id,
            )
            agent = await conn.fetchrow(
                "SELECT a.status, "
                "       a.persona_id IS NOT NULL AS has_persona, "
                "       a.system_prompt_template_id IS NOT NULL AS has_template, "
                "       (a.tool_policy ->> 'persona_write')::boolean AS persona_write, "
                "       (a.tool_policy ->> 'playbook_write')::boolean AS playbook_write, "
                "       (a.tool_policy ->> 'resource_write')::boolean AS resource_write, "
                "       (a.tool_policy ->> 'agent_write')::boolean AS agent_write, "
                "       (a.tool_policy ->> 'promote_retire')::boolean AS promote_retire "
                "FROM agent a "
                "WHERE a.workspace_id = $1 AND a.name = 'Builder'",
                workspace_id,
            )
            # Flach halten — verschachtelte object-Indizierung waere mypy-strict-unfreundlich.
            return {
                "persona_present": persona is not None,
                "persona_version": persona["current_version"] if persona else None,
                "persona_status": persona["status"] if persona else None,
                "persona_modes": json.loads(persona["modes"]) if persona else None,
                "playbooks_active": playbooks_active,
                "links": links,
                "template_status": template_status,
                "resource_present": resource is not None,
                "resource_managed": resource["is_managed"] if resource else None,
                "resource_stamp": resource["managed_content_version"] if resource else None,
                "resource_v1_status": resource["status"] if resource else None,
                "resource_locale": resource["locale"] if resource else None,
                "resource_link_scopes": [r["link_scope"] for r in resource_links],
                "resource_link_block_ids": [r["block_id"] for r in resource_links],
                "agent_present": agent is not None,
                "agent_status": agent["status"] if agent else None,
                "has_persona": agent["has_persona"] if agent else None,
                "has_template": agent["has_template"] if agent else None,
                "persona_write": agent["persona_write"] if agent else None,
                "playbook_write": agent["playbook_write"] if agent else None,
                "resource_write": agent["resource_write"] if agent else None,
                "agent_write": agent["agent_write"] if agent else None,
                "promote_retire": agent["promote_retire"] if agent else None,
            }
        finally:
            await conn.close()

    try:
        data = asyncio.run(_check(ws))

        assert data["persona_present"] is True, "Persona 'Builder' wurde nicht geseedet."
        assert data["persona_version"] == 1
        assert data["persona_status"] == "active"

        # Multi-Mode-Persona (Content-Stand 5): Architekt (Default, ohne
        # Trigger), Kurator, Berater — genau EIN Default.
        modes = data["persona_modes"]
        assert isinstance(modes, list) and len(modes) == 3, modes
        assert [m["name"] for m in modes] == ["Architekt", "Kurator", "Berater"]
        defaults = [m for m in modes if m["is_default"]]
        assert len(defaults) == 1, "Genau ein Modus muss is_default=True sein."
        assert defaults[0]["name"] == "Architekt"
        assert defaults[0]["trigger"] is None, "Der Default-Modus traegt keinen Trigger."

        assert data["playbooks_active"] == 5, "Es fehlen aktive Builder-Playbooks."
        assert data["links"] == 5, "Persona<->Playbook-Links unvollstaendig."
        assert data["template_status"] == "active"

        # Managed-Resource „Agent-Bau-Konventionen": v1 active, verwaltet und
        # von allen fuenf Builder-Playbooks als Volldokument referenziert.
        assert data["resource_present"] is True, "Managed-Resource wurde nicht geseedet."
        assert data["resource_managed"] is True
        assert data["resource_stamp"] == BUILDER_CONTENT_VERSION
        assert data["resource_v1_status"] == "active"
        assert data["resource_locale"] == "de"
        assert data["resource_link_scopes"] == ["resource"] * 5, data["resource_link_scopes"]
        assert data["resource_link_block_ids"] == [None] * 5

        assert data["agent_present"] is True, "Agent 'Builder' wurde nicht geseedet."
        assert data["agent_status"] == "enabled"
        assert data["has_persona"] is True
        assert data["has_template"] is True
        # Write-faehige Policy (Plan §5.2) — der Meta-Agent darf alles schreiben.
        assert data["persona_write"] is True
        assert data["playbook_write"] is True
        assert data["resource_write"] is True
        assert data["agent_write"] is True
        assert data["promote_retire"] is True
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_builder_seed_idempotent() -> None:
    """Ein zweiter Seed-Lauf legt keine Duplikate an (NOT-EXISTS-Guards)."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    owner = fresh_user_id()
    # `ensure_personal_workspace` (und damit der Seed) ist idempotent — zweimal
    # fuer denselben User trifft denselben Workspace und re-seedet.
    ws = setup_workspace(owner)
    ws_again = setup_workspace(owner)
    assert ws == ws_again, "Idempotenz verletzt: zweiter Lauf erzeugte neuen Workspace."

    async def _counts(workspace_id: UUID) -> dict[str, int]:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            personas = await conn.fetchval(
                "SELECT count(*) FROM persona WHERE workspace_id = $1 AND name = 'Builder'",
                workspace_id,
            )
            playbooks = await conn.fetchval(
                "SELECT count(*) FROM playbook WHERE workspace_id = $1 AND name = ANY($2::text[])",
                workspace_id,
                _BUILDER_PLAYBOOK_NAMES,
            )
            links = await conn.fetchval(
                "SELECT count(*) FROM persona_playbook pp "
                "JOIN persona p ON p.id = pp.persona_id "
                "WHERE pp.workspace_id = $1 AND p.name = 'Builder'",
                workspace_id,
            )
            agents = await conn.fetchval(
                "SELECT count(*) FROM agent WHERE workspace_id = $1 AND name = 'Builder'",
                workspace_id,
            )
            resources = await conn.fetchval(
                "SELECT count(*) FROM resource "
                "WHERE workspace_id = $1 AND name = 'Agent-Bau-Konventionen'",
                workspace_id,
            )
            resource_links = await conn.fetchval(
                "SELECT count(*) FROM playbook_resource_link prl "
                "JOIN resource r ON r.id = prl.resource_id "
                "WHERE prl.workspace_id = $1 AND r.name = 'Agent-Bau-Konventionen'",
                workspace_id,
            )
            return {
                "personas": personas,
                "playbooks": playbooks,
                "links": links,
                "agents": agents,
                "resources": resources,
                "resource_links": resource_links,
            }
        finally:
            await conn.close()

    try:
        counts = asyncio.run(_counts(ws))
        assert counts["personas"] == 1, "Persona dupliziert."
        assert counts["playbooks"] == 5, "Playbooks dupliziert."
        assert counts["links"] == 5, "Links dupliziert."
        assert counts["agents"] == 1, "Agent dupliziert."
        assert counts["resources"] == 1, "Managed-Resource dupliziert."
        assert counts["resource_links"] == 5, "playbook_resource_links dupliziert."
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_builder_agent_renders(monkeypatch: pytest.MonkeyPatch) -> None:
    """Der geseedete Builder rendert ueber /rendered ohne offene Persona-Platzhalter."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))

    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)

    async def _agent_id(workspace_id: UUID) -> str | None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            value = await conn.fetchval(
                "SELECT id FROM agent WHERE workspace_id = $1 AND name = 'Builder'",
                workspace_id,
            )
            return str(value) if value is not None else None
        finally:
            await conn.close()

    try:
        agent_id = asyncio.run(_agent_id(ws))
        assert agent_id is not None, "Builder-Agent nicht gefunden."

        with TestClient(app) as client:
            rendered = client.get(
                f"/v1/workspaces/{ws}/agents/{agent_id}/rendered",
                headers=auth,
            )
            assert rendered.status_code == 200, rendered.text
            data = rendered.json()

            assert data["id"] == agent_id
            assert data["name"] == "Builder"
            assert data["persona"]["name"] == "Builder"

            prompt = data["system_prompt_rendered"]
            # persona-field:name wurde aufgeloest -> Persona-Name steht im Prompt.
            assert "Builder" in prompt
            # Statische Template-Headings erscheinen verbatim (Render lief durch).
            assert "Methodik: Vier Phasen" in prompt
            assert "Agenten-Hinweise" in prompt
    finally:
        cleanup_workspaces([owner])
