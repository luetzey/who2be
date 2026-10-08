"""Integrationstests Lernschleife D2c-2: convert und promote am Router (ADR-0053 6.4/6.5).

Belegt am Router (echte DB, echter Auth-Pfad):

- `POST /agents/{agent_id}/memories/{memory_id}/convert`: ein offener
  Lernvorschlag wird ein Fall (201, Agent aus dem Lernvorschlag, Body ohne
  `agent_id`); Wiederholung 409 `memory_not_convertible`.
- `POST /feedback/{feedback_id}/promote`: ein offenes Alt-Feedback wird ein
  Fall (201); Wiederholung 409 `feedback_not_promotable`.
- Rechte: Agent-Token 403 (auch mit `case_triage`), viewer 403, editor 201.
- Fremder Workspace: Objekt aus B ist fuer A nicht da (404), Workspace B im
  Pfad mit A-Login wird abgewiesen.

Atomaritaet und Geschaeftsregeln deckt `test_case_convert_promote.py`
(Service) ab; hier geht es um den Vertrag der HTTP-Schicht.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from who2be_api.main import app
from who2be_api.testing.api_helpers import agent_token, db_execute, db_fetchval
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace
from who2be_models import WorkspaceRole

pytestmark = pytest.mark.integration

_PLAYBOOK = {"description": "d", "body": "1. Schritt.", "type": "workflow", "tags": []}
_CASE_FIELDS = {"situation": "Lage", "behavior": "Verhalten", "expected_behavior": "Erwartet"}


class _World:
    def __init__(self, client: TestClient, make: Any) -> None:
        self.client = client
        self._make = make
        self.users: list[UUID] = []

    def workspace(self) -> tuple[str, dict[str, str]]:
        owner = fresh_user_id()
        self.users.append(owner)
        ws = setup_workspace(owner)
        return f"/v1/workspaces/{ws}", self._make(owner)

    def member(self, base: str, role: WorkspaceRole) -> dict[str, str]:
        user = fresh_user_id()
        self.users.append(user)
        db_execute(
            "INSERT INTO workspace_member (workspace_id, user_id, role) VALUES ($1, $2, $3)",
            UUID(base.rsplit("/", 1)[1]),
            user,
            role.value,
        )
        headers: dict[str, str] = self._make(user)
        return headers

    def lesson(self, base: str, agent_id: str) -> str:
        """Offener Lernvorschlag des Agenten, direkt in der DB (wie die Service-Tests)."""
        return str(
            db_fetchval(
                "INSERT INTO agent_memory (workspace_id, agent_id, status, fact, kind, scope, "
                " created_by_agent_id, origin, source) "
                "VALUES ($1, $2::uuid, 'pending', 'Frist nennen', 'lesson', 'agent', $2::uuid, "
                " 'inferred', 'agent') RETURNING id",
                UUID(base.rsplit("/", 1)[1]),
                agent_id,
            )
        )

    def feedback(self, base: str, auth: dict[str, str], agent_auth: dict[str, str]) -> str:
        """Offenes Alt-Feedback ueber den regulaeren Weg (`POST /feedback`)."""
        playbook = self.client.post(
            f"{base}/playbooks",
            json={"name": "Frist", "content": {**_PLAYBOOK, "triggers": "frist"}},
            headers=auth,
        )
        assert playbook.status_code == 201, playbook.text
        res = self.client.post(
            f"{base}/feedback",
            json={
                "entity_type": "playbook",
                "entity_id": playbook.json()["id"],
                "signal": "incorrect",
                "note": "Schritt 1 nennt keine Frist",
            },
            headers=agent_auth,
        )
        assert res.status_code == 201, res.text
        return str(res.json()["id"])

    def convert(self, base: str, agent_id: str, memory_id: str, headers: dict[str, str]) -> Any:
        return self.client.post(
            f"{base}/agents/{agent_id}/memories/{memory_id}/convert",
            json=_CASE_FIELDS,
            headers=headers,
        )

    def promote(self, base: str, feedback_id: str, agent_id: str, headers: dict[str, str]) -> Any:
        return self.client.post(
            f"{base}/feedback/{feedback_id}/promote",
            json={"agent_id": agent_id, **_CASE_FIELDS},
            headers=headers,
        )


@pytest.fixture
def world(migrated_db: None, patched_jwt_secret: str, make_auth_headers: Any) -> Iterator[_World]:
    w: _World | None = None
    try:
        with TestClient(app) as client:
            w = _World(client, make_auth_headers)
            yield w
    finally:
        cleanup_workspaces(w.users if w else [])


def test_convert_rights_conflict_and_scope(world: _World) -> None:
    w = world
    base, auth = w.workspace()
    agent_id, agent_auth = agent_token(w.client, base, "Betroffen", {}, auth)
    _t, triage_auth = agent_token(w.client, base, "Builder", {"case_triage": True}, auth)
    viewer = w.member(base, WorkspaceRole.viewer)
    editor = w.member(base, WorkspaceRole.editor)
    memory_id = w.lesson(base, agent_id)

    # Agent-Tokens nie (auch der Builder nicht), viewer nicht.
    for headers in (agent_auth, triage_auth, viewer):
        denied = w.convert(base, agent_id, memory_id, headers)
        assert denied.status_code == 403, denied.text
    # Body mit agent_id (oder Zuordnung) ist kein CaseConvertRequest (Q2, Weiche 1).
    extras: list[dict[str, Any]] = [{"agent_id": agent_id}, {"elements": []}]
    for extra in extras:
        bad = w.client.post(
            f"{base}/agents/{agent_id}/memories/{memory_id}/convert",
            json={**_CASE_FIELDS, **extra},
            headers=editor,
        )
        assert bad.status_code == 422, extra

    created = w.convert(base, agent_id, memory_id, editor)
    assert created.status_code == 201, created.text
    case = created.json()
    assert case["agent_id"] == agent_id
    assert case["status"] == "open"
    assert case["reporter_kind"] == "human"
    assert case["source_memory_id"] == memory_id

    # Wiederholung: eigener Grund, kein zweiter Fall.
    again = w.convert(base, agent_id, memory_id, editor)
    assert again.status_code == 409, again.text
    assert again.json()["reason"] == "memory_not_convertible"
    listed = w.client.get(f"{base}/cases", headers=editor).json()
    assert [c["id"] for c in listed] == [case["id"]]

    # Fremder Workspace: B-Lernvorschlag unter A nicht da; B im Pfad abgewiesen.
    base_b, auth_b = w.workspace()
    agent_b, _ = agent_token(w.client, base_b, "Fremd", {}, auth_b)
    memory_b = w.lesson(base_b, agent_b)
    foreign = w.convert(base, agent_b, memory_b, auth)
    assert foreign.status_code == 404
    assert foreign.json()["reason"] == "agent_not_found"
    assert w.convert(base, agent_id, memory_b, auth).status_code == 404
    assert w.convert(base_b, agent_b, memory_b, auth).status_code in (403, 404)
    assert w.convert(base_b, agent_b, memory_b, auth_b).status_code == 201


def test_promote_rights_conflict_and_scope(world: _World) -> None:
    w = world
    base, auth = w.workspace()
    agent_id, agent_auth = agent_token(w.client, base, "Betroffen", {}, auth)
    _t, triage_auth = agent_token(
        w.client, base, "Builder", {"case_triage": True, "feedback_resolve": True}, auth
    )
    viewer = w.member(base, WorkspaceRole.viewer)
    editor = w.member(base, WorkspaceRole.editor)
    feedback_id = w.feedback(base, auth, agent_auth)

    for headers in (agent_auth, triage_auth, viewer):
        denied = w.promote(base, feedback_id, agent_id, headers)
        assert denied.status_code == 403, denied.text
    # Zuordnung im Body bleibt verboten (Q2: Melden und Einordnen getrennt).
    bad = w.client.post(
        f"{base}/feedback/{feedback_id}/promote",
        json={"agent_id": agent_id, **_CASE_FIELDS, "elements": []},
        headers=editor,
    )
    assert bad.status_code == 422

    created = w.promote(base, feedback_id, agent_id, editor)
    assert created.status_code == 201, created.text
    case = created.json()
    assert case["agent_id"] == agent_id
    assert case["source_feedback_id"] == feedback_id
    assert case["reporter_kind"] == "human"

    again = w.promote(base, feedback_id, agent_id, editor)
    assert again.status_code == 409, again.text
    assert again.json()["reason"] == "feedback_not_promotable"
    detail = w.client.get(f"{base}/feedback/{feedback_id}", headers=editor)
    assert detail.status_code == 200, detail.text
    assert f"case:{case['id']}" in detail.text

    base_b, auth_b = w.workspace()
    _agent_b, agent_b_auth = agent_token(w.client, base_b, "Fremd", {}, auth_b)
    feedback_b = w.feedback(base_b, auth_b, agent_b_auth)
    foreign = w.promote(base, feedback_b, agent_id, auth)
    assert foreign.status_code == 404
    assert foreign.json()["reason"] == "feedback_element_not_found"
    assert w.promote(base_b, feedback_b, agent_id, auth).status_code in (403, 404)
