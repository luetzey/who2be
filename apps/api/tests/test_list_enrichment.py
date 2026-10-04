"""Integrationstests fuer die List-Card-Pill-Enrichment (Batch-Aggregat, kein N+1).

Deckt die vier List-Endpunkte ab, die die Web-UI fuer die Karten-Pills braucht:

- `GET .../agents` → `persona_name`, `template_name`, `template_version`
  (aktive Template-Version) und `playbook_count` (Playbooks der Persona).
  Einen Gedaechtnis-Zaehler traegt die Liste nicht (ADR-0053 6.4.1, Rot-Probe
  `test_agent_list_carries_no_memory_counter`).
- `GET .../personas` → `playbook_count` + `agent_count`.
- `GET .../system-prompts` → `agent_count`.
- `GET .../resources` → `playbook_link_count` (DISTINCT Playbooks) +
  `sub_resource_count`.

Graph (ein Workspace): Persona P verlinkt 3 Playbooks (A/B/C); Template T wird
auf `active` promotet; 2 Agenten (A1/A2) zeigen beide auf P + T. Resource R wird
von 2 Playbooks (A/B, `link_scope='resource'`) referenziert und haelt 2
Sub-Resources (S1/S2). Erwartete Zaehler: Persona P → playbook_count=3,
agent_count=2; Template T → agent_count=2; Resource R → playbook_link_count=2,
sub_resource_count=2; jeder Agent → playbook_count=3, template_version=1.

Der zentrale conftest-Skip ueberspringt diese Tests ohne erreichbare DB
(mit WHO2BE_REQUIRE_DB=1 schlagen sie stattdessen hart fehl).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from uuid import UUID

import asyncpg
import pytest
from fastapi.testclient import TestClient

from who2be_api.core.config import get_settings
from who2be_api.main import app
from who2be_api.testing.workspace_setup import (
    cleanup_workspaces,
    fresh_user_id,
    setup_workspace,
)

AuthFactory = Callable[[UUID], dict[str, str]]


def _persona_body(name: str) -> dict[str, object]:
    return {"name": name, "content": {"description": "d", "system_prompt": "s"}}


def _playbook_body(name: str) -> dict[str, object]:
    return {
        "name": name,
        "content": {
            "description": "d",
            "body": "1. Step.",
            "type": "workflow",
            "tags": [],
            "triggers": "test",
        },
    }


def _resource_body(name: str) -> dict[str, object]:
    return {"name": name, "content": {"description": "d", "blocks": [], "tags": []}}


def _template_body(name: str) -> dict[str, object]:
    return {"name": name, "content": {"description": "", "body": "Hi {{ persona.name }}"}}


class _Graph:
    """Baut den Enrichment-Graphen und haelt die erzeugten IDs."""

    def __init__(self, client: TestClient, ws: UUID, auth: dict[str, str]) -> None:
        base = f"/v1/workspaces/{ws}"

        self.persona = client.post(
            f"{base}/personas", json=_persona_body("Coach Carla"), headers=auth
        ).json()["id"]

        self.playbooks = [
            client.post(f"{base}/playbooks", json=_playbook_body(n), headers=auth).json()["id"]
            for n in ("A", "B", "C")
        ]
        linked = client.put(
            f"{base}/personas/{self.persona}/playbooks",
            json={"playbook_ids": self.playbooks},
            headers=auth,
        )
        assert linked.status_code == 200, linked.text

        create_tpl = client.post(
            f"{base}/system-prompts", json=_template_body("Support-Template"), headers=auth
        )
        assert create_tpl.status_code == 201, create_tpl.text
        self.template = create_tpl.json()["id"]
        # v1 draft → review → active, damit `template_version` die aktive Version traegt.
        for target in ("review", "active"):
            r = client.post(
                f"{base}/system-prompts/{self.template}/versions/1/transition",
                json={"to": target},
                headers=auth,
            )
            assert r.status_code == 200, r.text

        self.agents = [
            client.post(
                f"{base}/agents",
                json={
                    "name": name,
                    "persona_id": self.persona,
                    "system_prompt_template_id": self.template,
                },
                headers=auth,
            ).json()["id"]
            for name in ("Agent 1", "Agent 2")
        ]

        self.resource = client.post(
            f"{base}/resources", json=_resource_body("Handbuch"), headers=auth
        ).json()["id"]
        self.sub_resources = [
            client.post(f"{base}/resources", json=_resource_body(n), headers=auth).json()["id"]
            for n in ("Sub 1", "Sub 2")
        ]
        # Resource R wird von 2 Playbooks (A/B) im Volldokument-Scope referenziert.
        for pb in self.playbooks[:2]:
            rl = client.put(
                f"{base}/playbooks/{pb}/resource_links",
                json={
                    "links": [
                        {"resource_id": self.resource, "position": 0, "link_scope": "resource"}
                    ]
                },
                headers=auth,
            )
            assert rl.status_code == 200, rl.text
        # R haelt 2 Sub-Resources.
        sub = client.put(
            f"{base}/resources/{self.resource}/sub_resources",
            json={"links": [{"child_id": cid} for cid in self.sub_resources]},
            headers=auth,
        )
        assert sub.status_code == 200, sub.text


def _row(items: list[dict[str, object]], item_id: str) -> dict[str, object]:
    match = next((it for it in items if str(it["id"]) == item_id), None)
    assert match is not None, f"{item_id} nicht in Liste {[it['id'] for it in items]}"
    return match


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_list_endpoints_expose_enrichment_counts(make_auth_headers: AuthFactory) -> None:
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    base = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            g = _Graph(client, ws, auth)

            # --- Agents: Namen + aktive Template-Version + playbook_count ------
            agents = client.get(f"{base}/agents", headers=auth)
            assert agents.status_code == 200, agents.text
            for agent_id in g.agents:
                row = _row(agents.json(), agent_id)
                assert row["persona_name"] == "Coach Carla"
                assert row["template_name"] == "Support-Template"
                assert row["template_version"] == 1
                assert row["playbook_count"] == 3

            # --- Personas: playbook_count + agent_count -----------------------
            personas = client.get(f"{base}/personas", headers=auth)
            assert personas.status_code == 200, personas.text
            prow = _row(personas.json(), g.persona)
            assert prow["playbook_count"] == 3
            assert prow["agent_count"] == 2

            # --- System-Prompts: agent_count ----------------------------------
            templates = client.get(f"{base}/system-prompts", headers=auth)
            assert templates.status_code == 200, templates.text
            trow = _row(templates.json(), g.template)
            assert trow["agent_count"] == 2

            # --- Resources: playbook_link_count + sub_resource_count ----------
            resources = client.get(f"{base}/resources", headers=auth)
            assert resources.status_code == 200, resources.text
            rrow = _row(resources.json(), g.resource)
            assert rrow["playbook_link_count"] == 2
            assert rrow["sub_resource_count"] == 2
            # Eine unverknuepfte Sub-Resource bleibt auf den Defaults (0/0).
            srow = _row(resources.json(), g.sub_resources[0])
            assert srow["playbook_link_count"] == 0
            assert srow["sub_resource_count"] == 0
    finally:
        cleanup_workspaces([owner])


def _seed_pending_agent_memory(workspace_id: UUID, members: dict[str, UUID]) -> None:
    """Mitgliedschaften der Rollen-User plus pending lesson und pending
    Agentengedaechtnis (`scope='agent'`) am ersten Agenten des Workspaces."""

    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            for role, user_id in members.items():
                await conn.execute(
                    "INSERT INTO workspace_member (workspace_id, user_id, role) "
                    "VALUES ($1, $2, $3)",
                    workspace_id,
                    user_id,
                    role,
                )
            agent_id = await conn.fetchval(
                "SELECT id FROM agent WHERE workspace_id = $1 ORDER BY created_at LIMIT 1",
                workspace_id,
            )
            assert agent_id is not None, "Workspace-Seed hat keinen Agenten angelegt"
            insert = (
                "INSERT INTO agent_memory (workspace_id, agent_id, created_by_agent_id, "
                " status, fact, kind, scope, origin) "
                "VALUES ($1, $2, $2, 'pending', $3, $4, 'agent', $5)"
            )
            await conn.execute(
                insert, workspace_id, agent_id, "Lernvorschlag", "lesson", "inferred"
            )
            await conn.execute(
                insert, workspace_id, agent_id, "Agentenfakt", "user_fact", "user_stated"
            )
        finally:
            await conn.close()

    asyncio.run(_run())


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
@pytest.mark.parametrize("role", ["viewer", "editor"])
def test_agent_list_carries_no_memory_counter(role: str, make_auth_headers: AuthFactory) -> None:
    """Rot-Probe ADR-0053 6.4.1: `GET /agents` traegt keinen Gedaechtnis-Zaehler.

    Gegen den alten Code rot: `pending_memory_count` stand in jedem
    Listeneintrag und zaehlte hier fuer viewer UND editor 2 (lesson
    eingeschlossen, Agentengedaechtnis auch fuer viewer). Gezaehlt wird nur
    noch ueber `/memories/counts` mit der Sichtbarkeitsregel `_memory_where`.
    Fremdes Nutzergedaechtnis zu seeden macht die Probe nicht rot:
    `scope='user'` hat per CHECK immer `agent_id IS NULL`.
    """
    owner = fresh_user_id()
    member = fresh_user_id()
    ws = setup_workspace(owner)
    url = f"/v1/workspaces/{ws}/agents"
    try:
        _seed_pending_agent_memory(ws, {role: member})
        with TestClient(app) as client:
            resp = client.get(url, headers=make_auth_headers(member))
            assert resp.status_code == 200, resp.text
            items = resp.json()
            assert items, "Agentenliste leer"
            for item in items:
                assert "pending_memory_count" not in item
            assert "Lernvorschlag" not in resp.text
            assert "Agentenfakt" not in resp.text
    finally:
        cleanup_workspaces([owner, member])
