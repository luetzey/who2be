"""Integrationstests fuer die List-Card-Pill-Enrichment (Batch-Aggregat, kein N+1).

Deckt die vier List-Endpunkte ab, die die Web-UI fuer die Karten-Pills braucht:

- `GET .../agents` → `persona_name`, `template_name`, `template_version`
  (aktive Template-Version), `playbook_count` (Playbooks der Persona) und
  `pending_memory_count` (Gedaechtnis-Vorschlaege in der Freigabe-Schleuse,
  ADR-0044 — zaehlt NUR `status='pending'`).
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

from collections.abc import Callable
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

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
                assert row["pending_memory_count"] == 0

            # --- Agents: pending_memory_count (Freigabe-Schleuse) -------------
            # Agent 1 bekommt memory_mode=suggest + Token, schlaegt 3 Fakten vor
            # (alle pending); einer wird freigegeben (active), einer abgelehnt
            # (rejected) — zaehlen darf nur der verbliebene pending-Eintrag.
            upd = client.put(
                f"{base}/agents/{g.agents[0]}",
                json={"tool_policy": {"memory_mode": "suggest"}},
                headers=auth,
            )
            assert upd.status_code == 200, upd.text
            token = client.post(
                f"{base}/tokens",
                json={"name": "mem-seed", "agent_id": g.agents[0]},
                headers=auth,
            )
            assert token.status_code == 201, token.text
            mem_auth = {"Authorization": f"Bearer {token.json()['token']}"}
            mem_ids: list[str] = []
            for fact in (
                "Nutzer arbeitet primaer mit Python",
                "Nutzer hostet auf Hetzner",
                "Nutzer bevorzugt knappe Antworten",
            ):
                saved = client.post(
                    f"{base}/agent-memories",
                    json={"fact": fact, "category": "preference", "importance": 7},
                    headers=mem_auth,
                )
                assert saved.status_code == 201, saved.text
                assert saved.json()["status"] == "pending"
                mem_ids.append(saved.json()["id"])
            mem_base = f"{base}/agents/{g.agents[0]}/memories"
            for mem_id, action in ((mem_ids[1], "approve"), (mem_ids[2], "reject")):
                triaged = client.post(
                    f"{mem_base}/{mem_id}/triage", json={"action": action}, headers=auth
                )
                assert triaged.status_code == 200, triaged.text

            agents = client.get(f"{base}/agents", headers=auth)
            assert agents.status_code == 200, agents.text
            assert _row(agents.json(), g.agents[0])["pending_memory_count"] == 1
            # Agent 2 hat keine Memories und bleibt auf 0.
            assert _row(agents.json(), g.agents[1])["pending_memory_count"] == 0

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
