"""Integrationstest fuer den Builder-Lite-Seed (schlanke Builder-Variante).

Belegt: ein neuer Workspace bekommt das managed 'agent-builder-lite'-Template
(active) und den managed Agenten 'Builder-Lite', der die BESTEHENDE Builder-
Persona wiederverwendet und mit dem lite Template verdrahtet ist. Laeuft nur mit
erreichbarer Datenbank; ohne DB wird der Test uebersprungen.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import asyncpg
import pytest

from who2be_api.core.config import get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace


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
def test_builder_lite_seeded_managed_and_wired() -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    owner = fresh_user_id()
    ws = setup_workspace(owner)

    async def _check(workspace_id: UUID) -> dict[str, object]:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            tmpl = await conn.fetchrow(
                "SELECT t.id, t.is_managed, tv.status "
                "FROM system_prompt_template t "
                "JOIN system_prompt_template_version tv "
                "  ON tv.template_id = t.id AND tv.version = 1 "
                "WHERE t.workspace_id = $1 AND t.slug = 'agent-builder-lite'",
                workspace_id,
            )
            builder_persona = await conn.fetchval(
                "SELECT id FROM persona WHERE workspace_id = $1 AND name = 'Builder'",
                workspace_id,
            )
            agent = await conn.fetchrow(
                "SELECT persona_id, system_prompt_template_id, status, is_managed, "
                "       (tool_policy ->> 'agent_write')::boolean AS agent_write "
                "FROM agent WHERE workspace_id = $1 AND name = 'Builder-Lite'",
                workspace_id,
            )
            return {
                "tmpl_present": tmpl is not None,
                "tmpl_managed": tmpl["is_managed"] if tmpl else None,
                "tmpl_status": tmpl["status"] if tmpl else None,
                "tmpl_id": tmpl["id"] if tmpl else None,
                "builder_persona": builder_persona,
                "agent_present": agent is not None,
                "agent_persona": agent["persona_id"] if agent else None,
                "agent_template": agent["system_prompt_template_id"] if agent else None,
                "agent_status": agent["status"] if agent else None,
                "agent_managed": agent["is_managed"] if agent else None,
                "agent_write": agent["agent_write"] if agent else None,
            }
        finally:
            await conn.close()

    try:
        data = asyncio.run(_check(ws))

        # Template: vorhanden, managed (gesperrt), aktive v1.
        assert data["tmpl_present"] is True, "'agent-builder-lite'-Template fehlt."
        assert data["tmpl_managed"] is True
        assert data["tmpl_status"] == "active"

        # Agent: vorhanden, enabled, managed, schreibfaehige Policy.
        assert data["agent_present"] is True, "Agent 'Builder-Lite' fehlt."
        assert data["agent_status"] == "enabled"
        assert data["agent_managed"] is True
        assert data["agent_write"] is True

        # Reuse: selbe Builder-Persona, verdrahtet mit dem lite Template.
        assert data["builder_persona"] is not None, "Builder-Persona fehlt (Voraussetzung)."
        assert data["agent_persona"] == data["builder_persona"], (
            "Builder-Lite nutzt nicht die bestehende Builder-Persona."
        )
        assert data["agent_template"] == data["tmpl_id"]
    finally:
        cleanup_workspaces([owner])
