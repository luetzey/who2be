"""Integrationstests fuer SystemPromptTemplates + Agents + Render-Endpoint.

Deckt Phase 3 Runde 3 Track 3 ab:
- Default-Templates pro Workspace gesetzt (Seed via Migration 0023b bzw.
  Workspace-Create-Hook).
- CRUD fuer Templates und Agents inkl. Workspace-Isolation und Permission-
  Matrix (Viewer read-only).
- Render-Endpoint mit allen drei Formaten + Cross-Workspace-Schutz.
- Migration 0023b ist idempotent: zweiter Lauf erzeugt keine Duplikate.

Laeuft nur mit erreichbarer Datenbank; ohne DB wird der Test uebersprungen.
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
from who2be_api.testing.workspace_setup import (
    cleanup_workspaces,
    fresh_user_id,
    setup_workspace,
)

_TEST_SECRET = "integration-test-jwt-secret-padding-0123456789"


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


def _set_role(workspace_id: UUID, user_id: UUID, role: str) -> None:
    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await conn.execute(
                "INSERT INTO workspace_member (workspace_id, user_id, role) "
                "VALUES ($1, $2, $3) ON CONFLICT (workspace_id, user_id) DO UPDATE "
                "SET role = excluded.role",
                workspace_id,
                user_id,
                role,
            )
        finally:
            await conn.close()

    asyncio.run(_run())


def _persona_body() -> dict[str, object]:
    return {
        "name": "Coach Carla",
        "content": {
            "description": "Senior Customer-Support-Coach",
            "system_prompt": "",
            "traits": [],
            "tags": ["support"],
            "content": {
                "description": "",
                "blocks": [
                    {
                        "id": "block-1",
                        "type": "paragraph",
                        "props": {},
                        "content": [{"type": "text", "text": "Empathisch.", "styles": {}}],
                        "children": [],
                    }
                ],
            },
        },
    }


def _playbook_body(name: str, triggers: str | None = None) -> dict[str, object]:
    return {
        "name": name,
        "content": {
            "description": f"{name} description",
            "body": f"Body von {name}",
            "type": "prompt",
            "tags": [],
            "triggers": triggers,
        },
    }


def _template_body(name: str, body: str) -> dict[str, object]:
    return {
        "name": name,
        "content": {"description": "", "body": body},
    }


@pytest.mark.integration
def test_default_templates_seeded_for_workspace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    base = f"/v1/workspaces/{ws}/system-prompts"
    try:
        with TestClient(app) as client:
            res = client.get(base, headers=auth)
            assert res.status_code == 200
            slugs = {row["slug"] for row in res.json()}
            assert {
                "customer-support-agent",
                "knowledge-worker",
                "conversational-coach",
            } <= slugs
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_seed_migration_idempotent() -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    try:

        async def _count() -> int:
            conn = await asyncpg.connect(get_settings().database_url)
            try:
                value: int = await conn.fetchval(
                    "SELECT COUNT(*)::int FROM system_prompt_template WHERE workspace_id = $1",
                    ws,
                )
                return value
            finally:
                await conn.close()

        async def _rerun() -> None:
            conn = await asyncpg.connect(get_settings().database_url)
            try:
                sql = (MIGRATIONS_DIR / "0023b_seed_default_templates.sql").read_text()
                await conn.execute(sql)
            finally:
                await conn.close()

        before = asyncio.run(_count())
        asyncio.run(_rerun())
        after = asyncio.run(_count())
        assert before == after >= 3
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_template_crud_and_versioning(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    base = f"/v1/workspaces/{ws}/system-prompts"
    try:
        with TestClient(app) as client:
            create = client.post(
                base,
                json=_template_body("Mein Template", "Hi {{ persona.name }}"),
                headers=auth,
            )
            assert create.status_code == 201, create.text
            tpl = create.json()
            tpl_id = tpl["id"]
            assert tpl["slug"] == "mein-template"
            assert tpl["current_version"] == 1
            assert tpl["current_status"] == "draft"

            # Promote v1 to active via transition (draft → review → active).
            r1 = client.post(
                f"{base}/{tpl_id}/versions/1/transition",
                json={"to": "review"},
                headers=auth,
            )
            assert r1.status_code == 200, r1.text
            r2 = client.post(
                f"{base}/{tpl_id}/versions/1/transition",
                json={"to": "active"},
                headers=auth,
            )
            assert r2.status_code == 200
            fetched = client.get(f"{base}/{tpl_id}", headers=auth).json()
            assert fetched["current_status"] == "active"

            # PUT: Active wird unangetastet bleiben, neue Draft entsteht.
            put = client.put(
                f"{base}/{tpl_id}",
                json=_template_body("Mein Template", "Neu {{ persona.name }}"),
                headers=auth,
            )
            assert put.status_code == 200
            updated = put.json()
            assert updated["current_version"] == 2
            assert updated["current_status"] == "draft"

            # Slug-Konflikt: zweites Template mit demselben Namen → 409
            conflict = client.post(base, json=_template_body("Mein Template", "X"), headers=auth)
            assert conflict.status_code == 409
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_agent_crud_and_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    other = fresh_user_id()
    ws = setup_workspace(owner)
    other_ws = setup_workspace(other)
    auth = _auth(owner)
    auth_other = _auth(other)
    try:
        with TestClient(app) as client:
            # Persona im eigenen Workspace.
            persona = client.post(
                f"/v1/workspaces/{ws}/personas",
                json=_persona_body(),
                headers=auth,
            ).json()
            # Default-Template (aus Seed) auswaehlen.
            tpl = client.get(f"/v1/workspaces/{ws}/system-prompts", headers=auth).json()
            tpl_id = next(t["id"] for t in tpl if t["slug"] == "customer-support-agent")

            # Agent erstellen
            agent = client.post(
                f"/v1/workspaces/{ws}/agents",
                json={
                    "name": "Carla Bot",
                    "description": "Coach Carla als Customer-Support-Agent",
                    "persona_id": persona["id"],
                    "system_prompt_template_id": tpl_id,
                },
                headers=auth,
            )
            assert agent.status_code == 201, agent.text
            agent_id = agent.json()["id"]

            # Liste enthaelt den Agent.
            listed = client.get(f"/v1/workspaces/{ws}/agents", headers=auth).json()
            assert any(a["id"] == agent_id for a in listed)

            # Cross-Workspace 403 (anderer User darf nicht lesen).
            cross = client.get(f"/v1/workspaces/{ws}/agents/{agent_id}", headers=auth_other)
            assert cross.status_code == 403
            # Aber in seinem eigenen Workspace ist er nicht zu finden.
            cross2 = client.get(f"/v1/workspaces/{other_ws}/agents/{agent_id}", headers=auth_other)
            assert cross2.status_code == 404

            # Loeschen
            deleted = client.delete(f"/v1/workspaces/{ws}/agents/{agent_id}", headers=auth)
            assert deleted.status_code == 204
    finally:
        cleanup_workspaces([owner, other])


@pytest.mark.integration
def test_render_endpoint_returns_substituted_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    try:
        with TestClient(app) as client:
            # Persona + Playbook + Verknuepfung.
            persona = client.post(
                f"/v1/workspaces/{ws}/personas",
                json=_persona_body(),
                headers=auth,
            ).json()
            pb = client.post(
                f"/v1/workspaces/{ws}/playbooks",
                json=_playbook_body("Reset", triggers="passwort, reset"),
                headers=auth,
            ).json()
            link = client.put(
                f"/v1/workspaces/{ws}/personas/{persona['id']}/playbooks",
                json={"playbook_ids": [pb["id"]]},
                headers=auth,
            )
            assert link.status_code == 200

            # Eigenes BlockNote-Template anlegen + aktivieren (Track B: Nur-
            # BlockNote — Pills statt Liquid-Tokens).
            tpl_doc = [
                {
                    "id": "t1",
                    "type": "paragraph",
                    "props": {},
                    "content": [
                        {"type": "text", "text": "Du bist ", "styles": {}},
                        {
                            "type": "placeholder",
                            "props": {
                                "kind": "persona-field",
                                "target_id": "name",
                                "label": "Name",
                            },
                        },
                        {"type": "text", "text": ". Profil: ", "styles": {}},
                        {
                            "type": "placeholder",
                            "props": {
                                "kind": "persona-field",
                                "target_id": "profile",
                                "label": "Profil",
                            },
                        },
                        {"type": "text", "text": " Unbekannt: ", "styles": {}},
                        {
                            "type": "placeholder",
                            "props": {"kind": "xyz", "target_id": "", "label": "X"},
                        },
                    ],
                    "children": [],
                }
            ]
            tpl = client.post(
                f"/v1/workspaces/{ws}/system-prompts",
                json=_template_body("Test-Tpl", json.dumps(tpl_doc)),
                headers=auth,
            ).json()
            client.post(
                f"/v1/workspaces/{ws}/system-prompts/{tpl['id']}/versions/1/transition",
                json={"to": "review"},
                headers=auth,
            )
            client.post(
                f"/v1/workspaces/{ws}/system-prompts/{tpl['id']}/versions/1/transition",
                json={"to": "active"},
                headers=auth,
            )

            # Agent anlegen.
            agent = client.post(
                f"/v1/workspaces/{ws}/agents",
                json={
                    "name": "Carla",
                    "description": "",
                    "persona_id": persona["id"],
                    "system_prompt_template_id": tpl["id"],
                },
                headers=auth,
            ).json()

            # Render (plain).
            plain = client.get(
                f"/v1/workspaces/{ws}/agents/{agent['id']}/render",
                headers=auth,
            )
            assert plain.status_code == 200
            data = plain.json()
            assert "Coach Carla" in data["content"]
            assert "Empathisch" in data["content"]
            # Unbekanntes Pill-Kind → Fehler-Marker im Text, keine Exception.
            assert "<Unbekannter Placeholder: xyz>" in data["content"]
            assert data["format"] == "plain"

            # Render (markdown).
            md = client.get(
                f"/v1/workspaces/{ws}/agents/{agent['id']}/render?format=markdown",
                headers=auth,
            ).json()
            assert md["format"] == "markdown"

            # Render (html).
            html = client.get(
                f"/v1/workspaces/{ws}/agents/{agent['id']}/render?format=html",
                headers=auth,
            ).json()
            assert html["format"] == "html"
            assert "Coach Carla" in html["content"]
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_viewer_can_read_and_render_but_not_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    admin = fresh_user_id()
    viewer = fresh_user_id()
    ws = setup_workspace(admin)
    # Viewer als zweites Mitglied einhaengen.
    _set_role(ws, viewer, "viewer")
    try:
        with TestClient(app) as client:
            admin_auth = _auth(admin)
            viewer_auth = _auth(viewer)

            persona = client.post(
                f"/v1/workspaces/{ws}/personas",
                json=_persona_body(),
                headers=admin_auth,
            ).json()
            tpl = client.get(f"/v1/workspaces/{ws}/system-prompts", headers=admin_auth).json()
            tpl_id = next(t["id"] for t in tpl if t["slug"] == "customer-support-agent")
            agent = client.post(
                f"/v1/workspaces/{ws}/agents",
                json={
                    "name": "Viewer-Test",
                    "description": "",
                    "persona_id": persona["id"],
                    "system_prompt_template_id": tpl_id,
                },
                headers=admin_auth,
            ).json()

            # Viewer kann lesen + rendern.
            assert client.get(f"/v1/workspaces/{ws}/agents", headers=viewer_auth).status_code == 200
            render = client.get(
                f"/v1/workspaces/{ws}/agents/{agent['id']}/render",
                headers=viewer_auth,
            )
            assert render.status_code == 200

            # Viewer darf NICHT schreiben.
            create = client.post(
                f"/v1/workspaces/{ws}/agents",
                json={
                    "name": "Hack",
                    "description": "",
                    "persona_id": persona["id"],
                    "system_prompt_template_id": tpl_id,
                },
                headers=viewer_auth,
            )
            assert create.status_code == 403
            tpl_create = client.post(
                f"/v1/workspaces/{ws}/system-prompts",
                json=_template_body("Viewer-Hack", "x"),
                headers=viewer_auth,
            )
            assert tpl_create.status_code == 403
    finally:
        cleanup_workspaces([admin, viewer])
