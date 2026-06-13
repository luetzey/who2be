"""Integrationstests fuer den Default-Agenten „Builder" (Welle 3).

Deckt den Seed ab, der bei jeder Workspace-Anlage laeuft
(`_seed_default_agents` in `workspace_repository.py`, gespiegelt von Migration
0047):

1. Vollstaendigkeit: nach `setup_workspace` existieren Persona „Builder" (v1
   active), vier Playbooks (v1 active), vier persona_playbook-Links, das
   Template `agent-builder` (active) und der Agent „Builder" (enabled,
   write-faehige tool_policy, Persona + Template verdrahtet).
2. Idempotenz: ein zweiter Seed-Lauf erzeugt keine Duplikate.
3. Render: der `GET .../agents/{id}/rendered`-Endpoint expandiert den Prompt
   ohne offene Persona-Platzhalter (Persona-Name aufgeloest).

Laeuft nur mit erreichbarer Datenbank; ohne DB werden die Tests uebersprungen.
"""

from __future__ import annotations

import asyncio
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
from who2be_api.testing.workspace_setup import (
    cleanup_workspaces,
    fresh_user_id,
    setup_workspace,
)

_TEST_SECRET = "integration-test-jwt-secret-padding-0123456789"

# Muss exakt zu den Namen in `_BUILDER_PLAYBOOKS` / Migration 0047 passen.
_BUILDER_PLAYBOOK_NAMES = [
    "Persona anlegen & pflegen",
    "Playbook anlegen & pflegen",
    "Agent anlegen & pflegen",
    "Konsistenz- & Drift-Check",
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
                "SELECT p.current_version, pv.status "
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
                "playbooks_active": playbooks_active,
                "links": links,
                "template_status": template_status,
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

        assert data["playbooks_active"] == 4, "Es fehlen aktive Builder-Playbooks."
        assert data["links"] == 4, "Persona<->Playbook-Links unvollstaendig."
        assert data["template_status"] == "active"

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
            return {
                "personas": personas,
                "playbooks": playbooks,
                "links": links,
                "agents": agents,
            }
        finally:
            await conn.close()

    try:
        counts = asyncio.run(_counts(ws))
        assert counts["personas"] == 1, "Persona dupliziert."
        assert counts["playbooks"] == 4, "Playbooks dupliziert."
        assert counts["links"] == 4, "Links dupliziert."
        assert counts["agents"] == 1, "Agent dupliziert."
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
