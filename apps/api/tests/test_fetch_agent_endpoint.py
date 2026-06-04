"""Integrationstests fuer den `GET .../agents/{id}/rendered`-Endpoint (Welle 5).

Testet den vollstaendigen Pfad:
  Workspace + Persona + Playbook + Resource + blocknote-Template mit allen
  vier Placeholder-Kinds → expandierter String in `system_prompt_rendered`.

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


def _playbook_body(name: str, body_text: str = "") -> dict[str, object]:
    return {
        "name": name,
        "content": {
            "description": f"{name} Beschreibung",
            "body": body_text or f"Body von {name}",
            "type": "prompt",
            "tags": [],
            "triggers": None,
        },
    }


def _resource_body(name: str, block_text: str) -> dict[str, object]:
    return {
        "name": name,
        "content": {
            "description": f"{name} Beschreibung",
            "blocks": [
                {
                    "id": "r-block-1",
                    "type": "paragraph",
                    "props": {},
                    "content": [{"type": "text", "text": block_text, "styles": {}}],
                    "children": [],
                }
            ],
        },
    }


def _promote_to_active(client: TestClient, base: str, obj_id: str, headers: dict[str, str]) -> None:
    """Promoviert eine Version von draft -> review -> active."""
    v = 1
    client.post(f"{base}/{obj_id}/versions/{v}/transition", json={"to": "review"}, headers=headers)
    client.post(f"{base}/{obj_id}/versions/{v}/transition", json={"to": "active"}, headers=headers)


def _blocknote_template_body(
    name: str,
    playbook_id: str,
    resource_id: str,
    persona_field: str = "name",
) -> dict[str, object]:
    """Erzeugt ein blocknote-formatiertes Template mit allen vier Placeholder-Kinds."""
    doc = {
        "content": [
            {
                "id": "intro",
                "type": "paragraph",
                "props": {},
                "content": [
                    {"type": "text", "text": "Ich bin ", "styles": {}},
                    {
                        "type": "placeholder",
                        "props": {
                            "kind": "persona-field",
                            "target_id": persona_field,
                            "label": f"Persona: {persona_field}",
                        },
                    },
                    {"type": "text", "text": ". Heute ist ", "styles": {}},
                    {
                        "type": "placeholder",
                        "props": {"kind": "date", "target_id": "human", "label": "Datum"},
                    },
                    {"type": "text", "text": ".", "styles": {}},
                ],
                "children": [],
            },
            {
                "id": "pb-block",
                "type": "paragraph",
                "props": {},
                "content": [
                    {
                        "type": "placeholder",
                        "props": {
                            "kind": "playbook",
                            "target_id": playbook_id,
                            "label": f"Playbook: {playbook_id[:8]}",
                        },
                    }
                ],
                "children": [],
            },
            {
                "id": "res-block",
                "type": "paragraph",
                "props": {},
                "content": [
                    {
                        "type": "placeholder",
                        "props": {
                            "kind": "resource",
                            "target_id": resource_id,
                            "label": f"Resource: {resource_id[:8]}",
                        },
                    }
                ],
                "children": [],
            },
        ]
    }
    return {
        "name": name,
        "content": {"description": "", "body": json.dumps(doc)},
    }


@pytest.mark.integration
def test_fetch_agent_rendered_expands_all_placeholder_kinds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Integrationstest: alle vier Placeholder-Kinds werden korrekt expandiert."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)

    try:
        with TestClient(app) as client:
            # 1. Persona anlegen + aktivieren.
            persona = client.post(
                f"/v1/workspaces/{ws}/personas",
                json=_persona_body(),
                headers=auth,
            ).json()
            _promote_to_active(client, f"/v1/workspaces/{ws}/personas", persona["id"], auth)

            # 2. Playbook anlegen + aktivieren.
            pb = client.post(
                f"/v1/workspaces/{ws}/playbooks",
                json=_playbook_body("Reset-Handbuch", "Schritt 1: Passwort reset."),
                headers=auth,
            ).json()
            _promote_to_active(client, f"/v1/workspaces/{ws}/playbooks", pb["id"], auth)

            # 3. Resource anlegen + aktivieren.
            res = client.post(
                f"/v1/workspaces/{ws}/resources",
                json=_resource_body("FAQ-Doc", "Antwort auf die haeufigste Frage."),
                headers=auth,
            ).json()
            _promote_to_active(client, f"/v1/workspaces/{ws}/resources", res["id"], auth)

            # 4. BlockNote-Template anlegen.
            tpl_body = _blocknote_template_body(
                "Test-Template-Welle5",
                pb["id"],
                res["id"],
                persona_field="name",
            )
            tpl = client.post(
                f"/v1/workspaces/{ws}/system-prompts",
                json=tpl_body,
                headers=auth,
            )
            assert tpl.status_code == 201, tpl.text
            tpl_data = tpl.json()
            tpl_id = tpl_data["id"]
            _promote_to_active(client, f"/v1/workspaces/{ws}/system-prompts", tpl_id, auth)

            # 5. Agent anlegen (enabled — Persona + Template sind aktiv).
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

            # 6. /rendered Endpoint aufrufen.
            rendered = client.get(
                f"/v1/workspaces/{ws}/agents/{agent_id}/rendered",
                headers=auth,
            )
            assert rendered.status_code == 200, rendered.text
            data = rendered.json()

            # Struktur pruefen.
            assert data["id"] == agent_id
            assert data["name"] == "Carla Agent"
            assert data["system_prompt_template_id"] == tpl_id
            assert "persona" in data
            assert data["persona"]["name"] == "Coach Carla"

            # Placeholder-Expansion pruefen.
            prompt = data["system_prompt_rendered"]

            # persona-field: Name der Persona.
            assert "Coach Carla" in prompt

            # date: aktuelles Datum (muss ein Monatsname enthalten, da "human"-Format).
            de_months = [
                "Januar",
                "Februar",
                "März",
                "April",
                "Mai",
                "Juni",
                "Juli",
                "August",
                "September",
                "Oktober",
                "November",
                "Dezember",
            ]
            assert any(month in prompt for month in de_months), (
                f"Kein Monatsname gefunden in: {prompt!r}"
            )

            # playbook: Name und Body des Playbooks.
            assert "Reset-Handbuch" in prompt
            assert "Schritt 1" in prompt

            # resource: Name und Block-Text der Resource.
            assert "FAQ-Doc" in prompt
            assert "haeufigste Frage" in prompt

    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_fetch_agent_rendered_plain_format_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """plain-Format-Templates werden unveraendert zurueckgegeben."""
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
                f"/v1/workspaces/{ws}/personas",
                json=_persona_body(),
                headers=auth,
            ).json()
            # Persona aktiv schalten — Voraussetzung fuer einen enabled Agent.
            _promote_to_active(client, f"/v1/workspaces/{ws}/personas", persona["id"], auth)

            # plain-Template: Body wird unveraendert geliefert.
            plain_body = "Du bist ein hilfreicher Assistent."
            tpl = client.post(
                f"/v1/workspaces/{ws}/system-prompts",
                json={"name": "Plain-Tpl", "content": {"description": "", "body": plain_body}},
                headers=auth,
            ).json()
            _promote_to_active(client, f"/v1/workspaces/{ws}/system-prompts", tpl["id"], auth)

            agent = client.post(
                f"/v1/workspaces/{ws}/agents",
                json={
                    "name": "Plain-Agent",
                    "description": "",
                    "persona_id": persona["id"],
                    "system_prompt_template_id": tpl["id"],
                    "status": "enabled",
                },
                headers=auth,
            ).json()

            rendered = client.get(
                f"/v1/workspaces/{ws}/agents/{agent['id']}/rendered",
                headers=auth,
            )
            assert rendered.status_code == 200
            assert rendered.json()["system_prompt_rendered"] == plain_body

    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_fetch_agent_rendered_disabled_agent_returns_409(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deaktivierter Agent -> 409."""
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
                f"/v1/workspaces/{ws}/personas",
                json=_persona_body(),
                headers=auth,
            ).json()
            tpl = client.get(f"/v1/workspaces/{ws}/system-prompts", headers=auth).json()
            tpl_id = next(t["id"] for t in tpl if t["slug"] == "customer-support-agent")

            agent = client.post(
                f"/v1/workspaces/{ws}/agents",
                json={
                    "name": "Disabled-Agent",
                    "description": "",
                    "persona_id": persona["id"],
                    "system_prompt_template_id": tpl_id,
                    "status": "disabled",
                },
                headers=auth,
            ).json()

            rendered = client.get(
                f"/v1/workspaces/{ws}/agents/{agent['id']}/rendered",
                headers=auth,
            )
            assert rendered.status_code == 409

    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_fetch_agent_rendered_not_found_returns_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unbekannte Agent-ID -> 404."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    fake_id = "00000000-0000-0000-0000-000000000099"

    try:
        with TestClient(app) as client:
            rendered = client.get(
                f"/v1/workspaces/{ws}/agents/{fake_id}/rendered",
                headers=auth,
            )
            assert rendered.status_code == 404

    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_agent_render_blocknote_fills_unresolved_placeholders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Welle 6: BlockNote-Branch von AgentRenderService befuellt unresolved_placeholders.

    Template enthaelt einen validen persona-field:name-Pill (sollte aufloesen)
    und einen invaliden Playbook-UUID-Pill (sollte Miss ergeben). Der
    GET .../agents/{id}/render Endpoint muss das Feld korrekt befuellen.
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)

    invalid_playbook_uuid = "00000000-dead-beef-0000-000000000000"

    try:
        with TestClient(app) as client:
            # Persona anlegen und aktiv schalten — ein Agent ist nur mit aktiver
            # Persona aktivierbar (enabled) und damit renderbar.
            persona = client.post(
                f"/v1/workspaces/{ws}/personas",
                json=_persona_body(),
                headers=auth,
            ).json()
            _promote_to_active(client, f"/v1/workspaces/{ws}/personas", persona["id"], auth)

            # Template: persona-field:name (sollte aufloesen) + invalider Playbook.
            doc = {
                "content": [
                    {
                        "id": "p1",
                        "type": "paragraph",
                        "props": {},
                        "content": [
                            {
                                "type": "placeholder",
                                "props": {
                                    "kind": "persona-field",
                                    "target_id": "name",
                                    "label": "Persona: Name",
                                },
                            },
                        ],
                        "children": [],
                    },
                    {
                        "id": "p2",
                        "type": "paragraph",
                        "props": {},
                        "content": [
                            {
                                "type": "placeholder",
                                "props": {
                                    "kind": "playbook",
                                    "target_id": invalid_playbook_uuid,
                                    "label": "Playbook: nicht existent",
                                },
                            },
                        ],
                        "children": [],
                    },
                ]
            }
            tpl = client.post(
                f"/v1/workspaces/{ws}/system-prompts",
                json={
                    "name": "Welle6-Test-Template",
                    "content": {"description": "", "body": json.dumps(doc)},
                },
                headers=auth,
            )
            assert tpl.status_code == 201, tpl.text
            tpl_id = tpl.json()["id"]
            _promote_to_active(client, f"/v1/workspaces/{ws}/system-prompts", tpl_id, auth)

            agent = client.post(
                f"/v1/workspaces/{ws}/agents",
                json={
                    "name": "Welle6-Test-Agent",
                    "description": "",
                    "persona_id": persona["id"],
                    "system_prompt_template_id": tpl_id,
                    "status": "enabled",
                },
                headers=auth,
            )
            assert agent.status_code == 201, agent.text
            agent_id = agent.json()["id"]

            # GET .../render — prueft AgentRenderService BlockNote-Branch.
            render_resp = client.get(
                f"/v1/workspaces/{ws}/agents/{agent_id}/render",
                headers=auth,
            )
            assert render_resp.status_code == 200, render_resp.text
            data = render_resp.json()

            # Persona-Field sollte aufgeloest worden sein (Name in content).
            assert "Coach Carla" in data["content"]

            # Invalider Playbook -> Miss im unresolved.
            assert f"playbook:{invalid_playbook_uuid}" in data["unresolved_placeholders"]

            # persona-field:name aufgeloest -> NICHT in unresolved.
            assert "persona-field:name" not in data["unresolved_placeholders"]

    finally:
        cleanup_workspaces([owner])
