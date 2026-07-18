"""Ende-zu-Ende-Tests fuer den `tool-ref`-Placeholder (WP-2, Blueprint
`.claude/plan/2026-07-18-1315_external-tools-tool-ref.md`).

Deckt Acceptance Criterion 2/3 aus `.github/PROJECT.md` ab:
- ein System-Prompt-Template-Body mit einer `tool-ref`-Pill expandiert beim
  Agent-Rendern (`GET .../agents/{id}/render`) zur aktiven ExternalTool-
  Bindung; unbekannter Alias -> sauberer Miss (`unresolved_placeholders`),
  kein Crash (AC 2).
- ein Bindungswechsel (Edit + Promote des ExternalTool) wird OHNE Aenderung
  an der referenzierenden Template-Pill beim naechsten Fetch wirksam (AC 3,
  Fetch-Time-Expansion — "einmal aendern, ueberall aktuell").

Nutzt zusaetzlich den `GET .../playbooks/{id}/rendered`-Pfad als zweiten
Nachweis, dass Persona-/Playbook-/Resource-`body_rendered` denselben
`render_template_body`-Renderer (und damit denselben `tool-ref`-Resolver)
durchlaufen wie der Agent-Render-Pfad — beide Endpunkte importieren dieselbe
Funktion aus `services/placeholders/renderer.py`.

Laeuft nur mit erreichbarer Datenbank; ohne DB wird der Test uebersprungen
(Muster identisch zu `test_fetch_agent_endpoint.py`).
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


def _promote_to_active(client: TestClient, base: str, obj_id: str, headers: dict[str, str]) -> None:
    """Promoviert Version 1 draft -> review -> active."""
    for to in ("review", "active"):
        res = client.post(
            f"{base}/{obj_id}/versions/1/transition", json={"to": to}, headers=headers
        )
        assert res.status_code == 200, res.text


def _promote_version(
    client: TestClient, base: str, obj_id: str, version: int, headers: dict[str, str]
) -> None:
    for to in ("review", "active"):
        res = client.post(
            f"{base}/{obj_id}/versions/{version}/transition", json={"to": to}, headers=headers
        )
        assert res.status_code == 200, res.text


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


def _tool_body(
    *,
    alias: str = "todo",
    display_name: str = "Todoist",
    mcp_server_name: str = "Todoist MCP",
    tool_names: list[str] | None = None,
    usage_notes: str = "Immer fuer To-do-Anfragen nutzen.",
    fallback_note: str | None = None,
) -> dict[str, object]:
    return {
        "name": display_name,
        "alias": alias,
        "content": {
            "display_name": display_name,
            "mcp_server_name": mcp_server_name,
            "tool_names": tool_names if tool_names is not None else ["add_task", "list_tasks"],
            "usage_notes": usage_notes,
            "fallback_note": fallback_note,
            "tags": [],
        },
    }


def _tool_ref_pill(alias: str, block_id: str = "tool-block") -> dict[str, object]:
    return {
        "id": block_id,
        "type": "paragraph",
        "props": {},
        "content": [
            {
                "type": "placeholder",
                "props": {"kind": "tool-ref", "target_id": alias, "label": f"Tool: {alias}"},
            }
        ],
        "children": [],
    }


def _template_body_with_tool_ref(alias: str) -> dict[str, object]:
    doc = {"content": [_tool_ref_pill(alias)]}
    return {
        "name": "Template mit Tool-Ref",
        "content": {"description": "", "body": json.dumps(doc)},
    }


@pytest.mark.integration
def test_tool_ref_pill_expands_at_agent_render_and_rebinds_without_template_edit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC 2 + AC 3: Hit-Expansion beim Agent-Render, danach Re-Binding ohne
    Template-Aenderung wird beim naechsten Fetch wirksam."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)

    try:
        with TestClient(app) as client:
            # 1. Persona anlegen + aktivieren (Voraussetzung fuer 'enabled' Agent).
            persona = client.post(
                f"/v1/workspaces/{ws}/personas", json=_persona_body(), headers=auth
            ).json()
            _promote_to_active(client, f"/v1/workspaces/{ws}/personas", persona["id"], auth)

            # 2. ExternalTool "todo" -> Todoist anlegen + aktivieren.
            tool_base = f"/v1/workspaces/{ws}/external_tools"
            tool = client.post(tool_base, json=_tool_body(), headers=auth)
            assert tool.status_code == 201, tool.text
            tool_id = tool.json()["id"]
            assert tool.json()["alias"] == "todo"
            _promote_to_active(client, tool_base, tool_id, auth)

            # 3. System-Prompt-Template mit tool-ref-Pill (target_id="todo") anlegen.
            tpl = client.post(
                f"/v1/workspaces/{ws}/system-prompts",
                json=_template_body_with_tool_ref("todo"),
                headers=auth,
            )
            assert tpl.status_code == 201, tpl.text
            tpl_id = tpl.json()["id"]
            _promote_to_active(client, f"/v1/workspaces/{ws}/system-prompts", tpl_id, auth)

            # 4. Agent anlegen (enabled — Persona + Template aktiv).
            agent = client.post(
                f"/v1/workspaces/{ws}/agents",
                json={
                    "name": "Carla Agent",
                    "description": "",
                    "persona_id": persona["id"],
                    "system_prompt_template_id": tpl_id,
                    "status": "enabled",
                },
                headers=auth,
            )
            assert agent.status_code == 201, agent.text
            agent_id = agent.json()["id"]

            # 5. GET .../render — Hit-Expansion pruefen.
            render_resp = client.get(f"/v1/workspaces/{ws}/agents/{agent_id}/render", headers=auth)
            assert render_resp.status_code == 200, render_resp.text
            data = render_resp.json()
            assert "todo" in data["content"]
            assert "Todoist" in data["content"]
            assert "Todoist MCP" in data["content"]
            assert "add_task" in data["content"]
            assert "list_tasks" in data["content"]
            assert "Immer fuer To-do-Anfragen nutzen." in data["content"]
            assert "tool-ref:todo" not in data["unresolved_placeholders"]

            # 6. Re-Binding: Tool-Content aendern (Todoist -> Things 3) OHNE das
            #    Template anzufassen. Draft-on-Edit -> Version 2, dann promoten.
            updated = client.put(
                f"{tool_base}/{tool_id}",
                json={
                    "name": "Things 3",
                    "content": {
                        "display_name": "Things 3",
                        "mcp_server_name": "Things 3 MCP",
                        "tool_names": ["create_todo"],
                        "usage_notes": "Things 3 ist jetzt die Quelle der Wahrheit.",
                        "fallback_note": None,
                        "tags": [],
                    },
                },
                headers=auth,
            )
            assert updated.status_code == 200, updated.text
            assert updated.json()["current_version"] == 2
            _promote_version(client, tool_base, tool_id, 2, auth)
            # Alias bleibt stabil ueber das Re-Binding hinweg.
            assert client.get(f"{tool_base}/{tool_id}", headers=auth).json()["alias"] == "todo"

            # 7. Erneuter Fetch — KEINE Template-Aenderung, trotzdem neuer Inhalt.
            rerendered = client.get(f"/v1/workspaces/{ws}/agents/{agent_id}/render", headers=auth)
            assert rerendered.status_code == 200, rerendered.text
            new_content = rerendered.json()["content"]
            assert "Things 3 MCP" in new_content
            assert "create_todo" in new_content
            assert "Things 3 ist jetzt die Quelle der Wahrheit." in new_content
            # Die alte Bindung ist vollstaendig verschwunden (kein Merge-Leck).
            assert "Todoist" not in new_content
            assert "add_task" not in new_content
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_tool_ref_pill_unknown_alias_is_clean_miss(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC 2: unbekannter Alias -> sauberer Miss (unresolved_placeholders), kein Crash."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)

    try:
        with TestClient(app) as client:
            persona = client.post(
                f"/v1/workspaces/{ws}/personas", json=_persona_body(), headers=auth
            ).json()
            _promote_to_active(client, f"/v1/workspaces/{ws}/personas", persona["id"], auth)

            tpl = client.post(
                f"/v1/workspaces/{ws}/system-prompts",
                json=_template_body_with_tool_ref("nicht-vorhanden"),
                headers=auth,
            )
            tpl_id = tpl.json()["id"]
            _promote_to_active(client, f"/v1/workspaces/{ws}/system-prompts", tpl_id, auth)

            agent = client.post(
                f"/v1/workspaces/{ws}/agents",
                json={
                    "name": "Miss-Agent",
                    "description": "",
                    "persona_id": persona["id"],
                    "system_prompt_template_id": tpl_id,
                    "status": "enabled",
                },
                headers=auth,
            ).json()

            render_resp = client.get(
                f"/v1/workspaces/{ws}/agents/{agent['id']}/render", headers=auth
            )
            assert render_resp.status_code == 200, render_resp.text
            data = render_resp.json()
            assert "tool-ref:nicht-vorhanden" in data["unresolved_placeholders"]
            assert "nicht verfuegbar" in data["content"]
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_tool_ref_pill_draft_only_tool_is_miss(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC 2: Alias existiert, aber nur als Draft (kein Active) -> Miss, kein Leak."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)

    try:
        with TestClient(app) as client:
            persona = client.post(
                f"/v1/workspaces/{ws}/personas", json=_persona_body(), headers=auth
            ).json()
            _promote_to_active(client, f"/v1/workspaces/{ws}/personas", persona["id"], auth)

            # ExternalTool anlegen, aber NICHT promoten — bleibt 'draft'.
            tool_base = f"/v1/workspaces/{ws}/external_tools"
            tool = client.post(tool_base, json=_tool_body(alias="draft-only"), headers=auth)
            assert tool.status_code == 201, tool.text
            assert tool.json()["current_status"] == "draft"

            tpl = client.post(
                f"/v1/workspaces/{ws}/system-prompts",
                json=_template_body_with_tool_ref("draft-only"),
                headers=auth,
            )
            tpl_id = tpl.json()["id"]
            _promote_to_active(client, f"/v1/workspaces/{ws}/system-prompts", tpl_id, auth)

            agent = client.post(
                f"/v1/workspaces/{ws}/agents",
                json={
                    "name": "Draft-Miss-Agent",
                    "description": "",
                    "persona_id": persona["id"],
                    "system_prompt_template_id": tpl_id,
                    "status": "enabled",
                },
                headers=auth,
            ).json()

            render_resp = client.get(
                f"/v1/workspaces/{ws}/agents/{agent['id']}/render", headers=auth
            )
            assert render_resp.status_code == 200, render_resp.text
            data = render_resp.json()
            assert "tool-ref:draft-only" in data["unresolved_placeholders"]
            assert "Todoist" not in data["content"]
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_tool_ref_pill_expands_via_playbook_rendered_path_too(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Zweiter Body-Rendering-Pfad: `GET .../playbooks/{id}/rendered` nutzt
    denselben `render_template_body`-Renderer wie der Agent-Render-Pfad —
    der `tool-ref`-Resolver greift also automatisch auch dort, ohne
    Resolver-/Registry-spezifischen Code fuer Playbooks."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)

    try:
        with TestClient(app) as client:
            tool_base = f"/v1/workspaces/{ws}/external_tools"
            tool = client.post(tool_base, json=_tool_body(alias="cal"), headers=auth)
            assert tool.status_code == 201, tool.text
            tool_id = tool.json()["id"]
            _promote_to_active(client, tool_base, tool_id, auth)

            doc = {"content": [_tool_ref_pill("cal")]}
            pb = client.post(
                f"/v1/workspaces/{ws}/playbooks",
                json={
                    "name": "Kalender-Playbook",
                    "content": {
                        "description": "Kalender-Playbook Beschreibung",
                        "body": json.dumps(doc),
                        "type": "prompt",
                        "tags": [],
                        "triggers": None,
                    },
                },
                headers=auth,
            ).json()
            _promote_to_active(client, f"/v1/workspaces/{ws}/playbooks", pb["id"], auth)

            rendered = client.get(
                f"/v1/workspaces/{ws}/playbooks/{pb['id']}/rendered", headers=auth
            )
            assert rendered.status_code == 200, rendered.text
            data = rendered.json()
            assert "Todoist" in data["body_rendered"]
            assert "Todoist MCP" in data["body_rendered"]
            assert "tool-ref:cal" not in data["unresolved"]
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_tool_ref_placeholder_preview_hit_and_miss(monkeypatch: pytest.MonkeyPatch) -> None:
    """Preview-Endpoint (`GET .../placeholders/preview`) loest `tool-ref` generisch
    ueber die REGISTRY auf — kein kind-spezifischer Code im Preview-Service noetig."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    base = f"/v1/workspaces/{ws}/placeholders/preview"

    try:
        with TestClient(app) as client:
            tool_base = f"/v1/workspaces/{ws}/external_tools"
            tool = client.post(tool_base, json=_tool_body(alias="todo"), headers=auth)
            assert tool.status_code == 201, tool.text
            tool_id = tool.json()["id"]
            _promote_to_active(client, tool_base, tool_id, auth)

            hit = client.get(base, params={"kind": "tool-ref", "target_id": "todo"}, headers=auth)
            assert hit.status_code == 200, hit.text
            hit_data = hit.json()
            assert hit_data["unresolved"] is False
            assert "Todoist" in hit_data["text"]

            miss = client.get(
                base, params={"kind": "tool-ref", "target_id": "unbekannt"}, headers=auth
            )
            assert miss.status_code == 200
            assert miss.json()["unresolved"] is True
            assert "nicht verfuegbar" in miss.json()["text"]
    finally:
        cleanup_workspaces([owner])
