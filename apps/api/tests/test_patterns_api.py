"""Integrationstests Lernschleife D5b: `GET /patterns?agent_id` (ADR-0053 6.5).

Belegt am Router (echte DB, echter Auth-Pfad):

- **Rechte:** viewer 403, editor 200, Agent ohne `case_triage` 403,
  Agent mit `case_triage` 200.
- **Antwortform:** `threshold` und `window_days` vom Server (PM-Entscheidung
  Q8), Muster aus beiden Quellen (Fall und Lernvorschlag).
- **Filter `agent_id`:** das gefilterte Ergebnis unterscheidet sich vom
  ungefilterten, je Agent genau dessen Muster.
- **Mandantengrenze:** ein Agent aus einem fremden Workspace liefert eine
  leere Liste, keine fremden Muster.

Die Rechenregeln selbst (Schwelle, Zeitfenster, Cluster) deckt
`test_pattern_service.py` ab; hier geht es um den Vertrag der HTTP-Schicht.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from who2be_api.main import app
from who2be_api.testing.api_helpers import agent_token, db_execute
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace
from who2be_models import WorkspaceRole
from who2be_models.pattern import PATTERN_CASE_WINDOW_DAYS, PATTERN_MIN_COUNT

pytestmark = pytest.mark.integration

_PLAYBOOK = {"description": "d", "body": "1. Schritt.", "type": "workflow", "tags": []}


class _World:
    def __init__(
        self, client: TestClient, ws: UUID, owner: UUID, auth: dict[str, str], make: Any
    ) -> None:
        self.client = client
        self.ws = ws
        self.owner = owner
        self.auth = auth
        self.base = f"/v1/workspaces/{ws}"
        self._make = make
        self.extra_users: list[UUID] = []

    def member(self, role: WorkspaceRole) -> dict[str, str]:
        user = fresh_user_id()
        db_execute(
            "INSERT INTO workspace_member (workspace_id, user_id, role) VALUES ($1, $2, $3)",
            self.ws,
            user,
            role.value,
        )
        self.extra_users.append(user)
        headers: dict[str, str] = self._make(user)
        return headers

    def agent(
        self, name: str, policy: dict[str, object] | None = None
    ) -> tuple[str, dict[str, str]]:
        return agent_token(self.client, self.base, name, policy or {}, self.auth)

    def assigned_case(self, agent_id: str, playbook_id: str, situation: str) -> str:
        made = self.client.post(
            f"{self.base}/cases",
            json={
                "agent_id": agent_id,
                "situation": situation,
                "behavior": "Verhalten",
                "expected_behavior": "Erwartet",
            },
            headers=self.auth,
        )
        assert made.status_code == 201, made.text
        case_id: str = made.json()["id"]
        put = self.client.put(
            f"{self.base}/cases/{case_id}/elements",
            json={"elements": [{"target": "playbook", "entity_id": playbook_id}]},
            headers=self.auth,
        )
        assert put.status_code == 200, put.text
        return case_id

    def lesson(self, agent_id: str, fact: str, occurrences: int) -> None:
        db_execute(
            "INSERT INTO agent_memory (workspace_id, agent_id, status, fact, kind, scope, "
            " created_by_agent_id, origin, source, occurrence_count) "
            "VALUES ($1, $2, 'pending', $3, 'lesson', 'agent', $2, 'inferred', 'agent', $4)",
            self.ws,
            UUID(agent_id),
            fact,
            occurrences,
        )

    def playbook(self, name: str) -> str:
        res = self.client.post(
            f"{self.base}/playbooks",
            json={"name": name, "content": {**_PLAYBOOK, "triggers": name}},
            headers=self.auth,
        )
        assert res.status_code == 201, res.text
        return str(res.json()["id"])

    def get(self, headers: dict[str, str], **params: Any) -> Any:
        return self.client.get(f"{self.base}/patterns", params=params, headers=headers)


@pytest.fixture
def world(migrated_db: None, patched_jwt_secret: str, make_auth_headers: Any) -> Iterator[_World]:
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    w: _World | None = None
    try:
        with TestClient(app) as client:
            w = _World(client, ws, owner, make_auth_headers(owner), make_auth_headers)
            yield w
    finally:
        cleanup_workspaces([owner, *(w.extra_users if w else [])])


def _seed_both_sources(w: _World) -> tuple[str, str, list[str]]:
    """Agent A: Fall-Muster (n Faelle, gleiches Playbook); Agent B: Lernvorschlags-Muster."""
    a_id, _ = w.agent("A")
    b_id, _ = w.agent("B")
    playbook = w.playbook("PB")
    cases = sorted(w.assigned_case(a_id, playbook, f"Fall {i}") for i in range(PATTERN_MIN_COUNT))
    w.lesson(b_id, "Antworte immer zuerst mit der Zusammenfassung.", PATTERN_MIN_COUNT)
    return a_id, b_id, cases


def test_rights_per_role(world: _World) -> None:
    w = world
    _plain_id, plain_auth = w.agent("Ohne Triage")
    _triage_id, triage_auth = w.agent("Builder", {"case_triage": True})
    viewer = w.member(WorkspaceRole.viewer)
    editor = w.member(WorkspaceRole.editor)

    refused_viewer = w.get(viewer)
    assert refused_viewer.status_code == 403
    refused_agent = w.get(plain_auth)
    assert refused_agent.status_code == 403
    assert refused_agent.json()["reason"] == "missing_capability"
    for headers in (editor, triage_auth, w.auth):
        res = w.get(headers)
        assert res.status_code == 200, res.text


def test_response_carries_threshold_and_both_sources(world: _World) -> None:
    w = world
    a_id, b_id, cases = _seed_both_sources(w)

    res = w.get(w.auth)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["threshold"] == PATTERN_MIN_COUNT
    assert body["window_days"] == PATTERN_CASE_WINDOW_DAYS
    by_source = {p["source"]: p for p in body["patterns"]}
    assert set(by_source) == {"case", "lesson"}
    case = by_source["case"]
    assert case["agent_id"] == a_id
    assert case["count"] == PATTERN_MIN_COUNT
    assert case["element"]["target"] == "playbook"
    assert sorted(case["evidence_ids"]) == cases
    lesson = by_source["lesson"]
    assert lesson["agent_id"] == b_id
    assert lesson["count"] == PATTERN_MIN_COUNT
    assert lesson["element"] is None


def test_agent_filter_narrows_the_result(world: _World) -> None:
    """Gefiltert ist ungleich ungefiltert, je Agent genau dessen Muster."""
    w = world
    a_id, b_id, _cases = _seed_both_sources(w)

    def agents(**params: Any) -> list[str]:
        res = w.get(w.auth, **params)
        assert res.status_code == 200, res.text
        return [p["agent_id"] for p in res.json()["patterns"]]

    unfiltered = agents()
    assert sorted(unfiltered) == sorted([a_id, b_id])
    only_a = agents(agent_id=a_id)
    only_b = agents(agent_id=b_id)
    assert only_a == [a_id]
    assert only_b == [b_id]
    assert only_a != unfiltered and only_b != unfiltered
    assert w.get(w.auth, agent_id="x").status_code == 422


def test_foreign_workspace_agent_yields_nothing(world: _World, make_auth_headers: Any) -> None:
    """Agent-ID aus Workspace B im Filter von A: leere Liste, keine Muster von B."""
    w = world
    _seed_both_sources(w)
    other_owner = fresh_user_id()
    other_ws = setup_workspace(other_owner)
    w.extra_users.append(other_owner)
    other_auth = make_auth_headers(other_owner)
    other_base = f"/v1/workspaces/{other_ws}"
    foreign_agent, _ = agent_token(w.client, other_base, "Fremd", {}, other_auth)
    db_execute(
        "INSERT INTO agent_memory (workspace_id, agent_id, status, fact, kind, scope, "
        " created_by_agent_id, origin, source, occurrence_count) "
        "VALUES ($1, $2, 'pending', 'Fremde Lektion', 'lesson', 'agent', $2, 'inferred', "
        "'agent', $3)",
        other_ws,
        UUID(foreign_agent),
        PATTERN_MIN_COUNT,
    )
    # Gegenprobe: B sieht sein eigenes Muster.
    own = w.client.get(f"{other_base}/patterns", headers=other_auth)
    assert [p["agent_id"] for p in own.json()["patterns"]] == [foreign_agent]

    filtered = w.get(w.auth, agent_id=foreign_agent)
    assert filtered.status_code == 200
    assert filtered.json()["patterns"] == []
    assert foreign_agent not in w.get(w.auth).text
    # Fremder Workspace im Pfad: kein Zugang.
    assert w.client.get(f"{other_base}/patterns", headers=w.auth).status_code in {403, 404}
