"""Integrationstests fuer das Workflow-Starter-Template (Migration 0027).

Prueft:
1. Migration-Test: nach `apply_migrations` existiert `workflow-starter` pro
   Workspace, `body_format='blocknote'`, `current_version=1`, `status='active'`.
2. Renderer-Smoke: der Seed-Body ohne Persona-Kontext (persona_id=None) durch
   `render_template_body` rendern -> unresolved enthaelt die zwei
   persona-field-Keys; Text enthaelt Sektionsueberschriften und
   Tools-Overview-Markdown.

Laeuft nur mit erreichbarer Datenbank; ohne DB wird der Test uebersprungen.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from who2be_api.core.config import get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.services.placeholders.registry import RenderContext
from who2be_api.services.placeholders.renderer import render_template_body
from who2be_api.testing.workspace_setup import (
    cleanup_workspaces,
    fresh_user_id,
    setup_workspace,
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
def test_workflow_starter_template_exists_after_migration() -> None:
    """Nach apply_migrations existiert 'workflow-starter' mit body_format='blocknote'."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    owner = fresh_user_id()
    ws = setup_workspace(owner)

    async def _check(workspace_id: UUID) -> dict[str, object]:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            row = await conn.fetchrow(
                """
                SELECT t.slug, t.body_format, t.current_version,
                       tv.status AS current_status
                  FROM system_prompt_template t
                  JOIN system_prompt_template_version tv
                    ON tv.template_id = t.id AND tv.version = t.current_version
                 WHERE t.workspace_id = $1
                   AND t.slug = 'workflow-starter'
                """,
                workspace_id,
            )
            if row is None:
                return {}
            return {
                "slug": row["slug"],
                "body_format": row["body_format"],
                "current_version": row["current_version"],
                "current_status": row["current_status"],
            }
        finally:
            await conn.close()

    try:
        data = asyncio.run(_check(ws))
        assert data, "Template 'workflow-starter' wurde nicht gefunden."
        assert data["slug"] == "workflow-starter"
        assert data["body_format"] == "blocknote", (
            f"Erwartet body_format='blocknote', erhalten: {data['body_format']!r}"
        )
        assert data["current_version"] == 1
        assert data["current_status"] == "active"
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_workflow_starter_template_renderer_smoke() -> None:
    """Renderer-Smoke: Seed-Body ohne Persona-Kontext.

    persona_id=None:
    - unresolved enthaelt 'persona-field:name' und 'persona-field:description'
    - gerenderter Text enthaelt Sektionsueberschriften aus Heading-Bloecken
    - gerenderter Text enthaelt Tools-Overview-Markdown (Verfuegbare Werkzeuge)
    - 'Heute ist der' erscheint (date-Placeholder wurde expandiert)
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    owner = fresh_user_id()
    ws = setup_workspace(owner)

    async def _fetch_body(workspace_id: UUID) -> str:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            row = await conn.fetchrow(
                """
                SELECT (tv.content ->> 'body') AS body
                  FROM system_prompt_template t
                  JOIN system_prompt_template_version tv
                    ON tv.template_id = t.id AND tv.version = t.current_version
                 WHERE t.workspace_id = $1
                   AND t.slug = 'workflow-starter'
                """,
                workspace_id,
            )
            if row is None:
                return ""
            return str(row["body"])
        finally:
            await conn.close()

    async def _render(body_text: str, workspace_id: UUID) -> tuple[str, list[str]]:
        ctx = RenderContext(
            workspace_id=workspace_id,
            persona_id=None,  # Kein Persona-Kontext -> persona-field = Miss
            now=datetime(2026, 5, 31, 12, 0, 0, tzinfo=UTC),
        )
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            return await render_template_body(body_text, "blocknote", ctx, conn)
        finally:
            await conn.close()

    try:
        body = asyncio.run(_fetch_body(ws))
        assert body, "Body des Starter-Templates ist leer."

        # Validieren, dass das JSON ein Top-Level-Array ist.
        parsed = json.loads(body)
        assert isinstance(parsed, list), f"Body ist kein Top-Level-Array: {type(parsed)}"

        text, unresolved = asyncio.run(_render(body, ws))

        # Persona-field-Misses muessen in unresolved erscheinen.
        assert "persona-field:name" in unresolved, (
            f"'persona-field:name' fehlt in unresolved: {unresolved}"
        )
        assert "persona-field:description" in unresolved, (
            f"'persona-field:description' fehlt in unresolved: {unresolved}"
        )

        # Sektionsueberschriften aus Heading-Bloecken muessen im Text erscheinen.
        for heading in ("Rolle", "Verfuegbare Werkzeuge", "So gehst du vor", "Letzter Stand"):
            assert heading in text, f"Sektionsueberschrift '{heading}' fehlt in gerendertem Text."

        # Tools-Overview muss expandiert sein.
        assert "list_triggers()" in text, "Tools-Overview wurde nicht expandiert."
        assert "fetch_playbook(playbook_id)" in text, "fetch_playbook fehlt in Tools-Overview."

        # Datum muss expandiert sein (format: "human" -> "31. Mai 2026").
        assert "31. Mai 2026" in text, f"Datum-Placeholder nicht expandiert: {text[:200]!r}"

        # date und tools-overview erzeugen keine Misses.
        assert "date:human" not in unresolved
        assert "tools-overview:" not in " ".join(unresolved)

    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_workflow_starter_template_idempotent_rerun() -> None:
    """Zweiter Lauf von apply_migrations erzeugt kein Duplikat des Templates."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    owner = fresh_user_id()
    ws = setup_workspace(owner)

    async def _count_templates(workspace_id: UUID) -> int:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            row = await conn.fetchrow(
                "SELECT COUNT(*) AS n FROM system_prompt_template "
                "WHERE workspace_id = $1 AND slug = 'workflow-starter'",
                workspace_id,
            )
            return int(row["n"]) if row else 0
        finally:
            await conn.close()

    try:
        count_before = asyncio.run(_count_templates(ws))
        _prepare_db()  # zweiter Lauf
        count_after = asyncio.run(_count_templates(ws))
        assert count_after == count_before == 1, (
            f"Idempotenz verletzt: {count_before} -> {count_after}"
        )
    finally:
        cleanup_workspaces([owner])
